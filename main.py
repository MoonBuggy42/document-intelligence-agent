from dotenv import load_dotenv
import os
import sys
import re
import json
import requests
from pydantic import BaseModel
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from tools import search_tool, arxiv_tool, web_scraper_tool, graph_creator_tool, pdf_generator_tool, python_repl_tool

load_dotenv()

try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass

class ResearchResponse(BaseModel):
    topic: str
    summary: str
    sources: list[str]
    tools_used: list[str]

api_key = os.getenv("MISTRALAI_API_KEY") or os.getenv("MISTRAL_API_KEY") or os.getenv("MISTRAL_KEY")

llm = ChatMistralAI(
    model_name="mistral-large-latest",
    api_key=api_key,
    max_tokens=8384,
    temperature=0.1,
    timeout=300,   # FIX: prevents ReadTimeout on long PDF-generation responses
)
parser = PydanticOutputParser(pydantic_object=ResearchResponse)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert research assistant tasked with producing long, detailed, publication-quality research reports.\n\n"
            "CRITICAL ORDER OF ACTIONS:\n"
            "1. Run 'search_academic_papers' AND 'ArxivSearch' to gather broad source material before writing anything.\n"
            "2. Use 'WebScraper' on 2-3 relevant URLs to pull deeper detail from the best sources.\n"
            "3. Use 'PythonREPL' to compute all numerical results (Km, Vmax, Ea, activation entropy, Q10, etc.) and print them.\n"
            "4. Invoke 'graph_creator' to build MULTIPLE graphs — aim for at least 5-8 covering different variables.\n"
            "5. Call 'pdf_generator' ONCE at the end with the full HTML. Embed every graph using the exact "
            "<img src='path' /> string returned by graph_creator.\n\n"
            "GRAPH FORMAT — strictly enforced:\n"
            "   data_json must be a FLAT JSON list of series objects:\n"
            '   [{{"x": [...], "y": [...], "name": "Series Label", "mode": "lines"}}]\n'
            "   Valid modes: 'lines' (default), 'bar', 'markers'.\n"
            "   Do NOT wrap data_json in a Plotly-style {{'data': [...], 'layout': {{...}}}} object.\n\n"
            "DOCUMENT STRUCTURE — the PDF content_html MUST contain ALL of these sections in order:\n"
            "   <h2>Abstract</h2>                — 200-300 word structured summary\n"
            "   <h2>Introduction</h2>            — background, significance, objectives (3-5 paragraphs)\n"
            "   <h2>Literature Review</h2>       — detailed synthesis of existing research (4-6 paragraphs)\n"
            "   <h2>Theoretical Background</h2>  — full derivations, mechanisms, governing equations\n"
            "   <h2>Methodology</h2>             — experimental/analytical approach, data sources\n"
            "   <h2>Results and Analysis</h2>    — every graph embedded here with a descriptive caption below it\n"
            "   <h2>Discussion</h2>              — interpret findings, compare to literature, limitations (4-6 paragraphs)\n"
            "   <h2>Conclusion</h2>              — key takeaways, practical implications (2-3 paragraphs)\n"
            "   <h2>Future Directions</h2>       — open questions, proposed follow-up studies\n"
            "   <h2>References</h2>              — Harvard style, every source cited in text\n\n"
            "WRITING DEPTH RULES — strictly enforced:\n"
            "   - Every section must have at least 3-5 substantial paragraphs of flowing prose — NO bullet-point summaries.\n"
            "   - Each paragraph should be 5-8 sentences minimum.\n"
            "   - After each graph write a dedicated <p><b>Figure N:</b> ...</p> caption paragraph.\n"
            "   - Cite sources inline as (Author, Year) throughout the text.\n"
            "   - Total content_html should target 4000-8000 words.\n\n"
            "HTML FORMATTING RULES:\n"
            "   - Subscripts and superscripts MUST use HTML tags: H<sub>2</sub>O<sub>2</sub>, Fe<sup>3+</sup>, CuSO<sub>4</sub>.\n"
            "   - Do NOT use Unicode subscript/superscript characters (₂ ₃ ₄ ⁺ ⁻ etc.) — they render as ■ boxes in the PDF.\n\n"
            "MATH FORMATTING:\n"
            "   - Place ALL equations on their own line using $$ ... $$ block syntax.\n"
            "   - Define every variable immediately after its equation in a <ul> list.\n"
            "   - Derive equations step-by-step; do not just state the final form.\n"
            "   - Avoid AMS-only LaTeX commands (\\xrightleftharpoons, \\xrightarrow) — use \\rightleftharpoons, \\rightarrow instead.\n\n"
            "PYTHON REPL RULES:\n"
            "   (a) scipy is NOT installed — use numpy for ALL math.\n"
            "       Linear regression: coeffs = np.polyfit(x, y, 1)  -> slope=coeffs[0], intercept=coeffs[1]\n"
            "   (b) numpy is pre-imported as 'np' — no import needed.\n"
            "   (c) Use np.trapezoid() NOT np.trapz() — trapz was removed in NumPy 2.0.\n"
            "   (d) Always use print() to display any value you need to read back.\n"
            "   (e) Never use a bare multi-line dict/list literal as the last expression.\n"
            "       WRONG:  {{'key': value, ...}}          RIGHT: result = {{'key': value}}; print(result)\n\n"
            "Formatting parameters:\n{format_instructions}."
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{query}"),
        ("placeholder", "{agent_scratchpad}")
    ]
).partial(format_instructions=parser.get_format_instructions())

tools = [search_tool, arxiv_tool, web_scraper_tool, pdf_generator_tool, graph_creator_tool, python_repl_tool]
agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,  # FIX: surface errors as agent observations instead of crashing
    max_iterations=25,           # FIX: cap runaway loops that balloon context
)

query = input("Enter your research query: ")
raw_response = agent_executor.invoke({"query": query})

output_text = None
if isinstance(raw_response, dict):
    output_text = raw_response.get("output")
    if isinstance(output_text, list) and output_text: output_text = output_text[0]
    if isinstance(output_text, dict): output_text = output_text.get("text") or output_text.get("output_text") or str(output_text)
else: output_text = str(raw_response)

def extract_json_block(text: str):
    def try_parse(candidate: str):
        try: return json.loads(candidate)
        except json.JSONDecodeError: return None
    for open_char in ('{', '['):
        start_positions = [m.start() for m in re.finditer(re.escape(open_char), text)]
        close_char = '}' if open_char == '{' else ']'
        for start in start_positions:
            depth = 0; in_string = False; escape = False
            for i in range(start, len(text)):
                ch = text[i]
                if escape: escape = False; continue
                if ch == '\\': escape = True; continue
                if ch == '"': in_string = not in_string
                if in_string: continue
                if ch == open_char: depth += 1
                elif ch == close_char:
                    depth -= 1
                    if depth == 0:
                        parsed = try_parse(text[start:i+1])
                        if parsed is not None: return parsed
    return None

def print_response(response):
    # FIX: .dict() is deprecated in Pydantic v2 — use .model_dump() with fallback
    if hasattr(response, "model_dump"):
        data = response.model_dump()
    elif hasattr(response, "dict"):
        data = response.dict()
    else:
        data = response
    print("\n=== Research Execution Complete ===")
    print(f"Topic: {data.get('topic', '')}\n")
    print("Summary:\n" + data.get('summary', '').strip() + "\n")

try: print_response(parser.parse(output_text))
except Exception:
    json_data = extract_json_block(output_text)
    if json_data is not None:
        try: print_response(parser.parse(json_data))
        except Exception: print("Raw response fallback:", output_text)
    else: print("Raw output:", output_text)