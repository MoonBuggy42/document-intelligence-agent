"""
AI Research Assistant — Flask Web Application
Wraps the existing LangChain research agent and math paper generator
with a web UI and async task processing.
"""

import os
import sys
import re
import json
import uuid
import threading
import time
from datetime import datetime

from flask import (
    Flask, render_template, request, jsonify, send_from_directory
)
from dotenv import load_dotenv

load_dotenv()

# Ensure UTF-8 output
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# ---------------------------------------------------------------------------
# Flask App Setup
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__, static_folder='static', template_folder='templates')

# ---------------------------------------------------------------------------
# In-memory task store  { task_id: { status, result, error, ... } }
# ---------------------------------------------------------------------------
tasks: dict = {}

# ---------------------------------------------------------------------------
# Helper: extract JSON from messy agent output
# ---------------------------------------------------------------------------
def extract_json_block(text: str):
    def try_parse(candidate):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    for open_char in ('{', '['):
        start_positions = [m.start() for m in re.finditer(re.escape(open_char), text)]
        close_char = '}' if open_char == '{' else ']'
        for start in start_positions:
            depth = 0; in_string = False; escape = False
            for i in range(start, len(text)):
                ch = text[i]
                if escape:
                    escape = False; continue
                if ch == '\\':
                    escape = True; continue
                if ch == '"':
                    in_string = not in_string
                if in_string:
                    continue
                if ch == open_char:
                    depth += 1
                elif ch == close_char:
                    depth -= 1
                    if depth == 0:
                        parsed = try_parse(text[start:i + 1])
                        if parsed is not None:
                            return parsed
    return None


# ---------------------------------------------------------------------------
# Research agent runner (runs in a thread)
# ---------------------------------------------------------------------------
def run_research_task(task_id: str, query: str):
    """Execute the LangChain research agent and store the result."""
    try:
        tasks[task_id]['status'] = 'running'
        tasks[task_id]['progress_message'] = 'Initialising research agent...'

        from pydantic import BaseModel
        from langchain_mistralai import ChatMistralAI
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import PydanticOutputParser
        from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
        from tools import (
            search_tool, arxiv_tool, web_scraper_tool,
            graph_creator_tool, pdf_generator_tool, python_repl_tool,
            WORKSPACE_ROOT
        )

        class ResearchResponse(BaseModel):
            topic: str
            summary: str
            sources: list[str]
            tools_used: list[str]

        api_key = (os.getenv("MISTRALAI_API_KEY")
                   or os.getenv("MISTRAL_API_KEY")
                   or os.getenv("MISTRAL_KEY"))

        if not api_key:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = 'No Mistral API key configured. Set MISTRALAI_API_KEY.'
            return

        llm = ChatMistralAI(
            model_name="mistral-large-latest",
            api_key=api_key,
            max_tokens=8384,
            temperature=0.1,
            timeout=300,
        )
        parser = PydanticOutputParser(pydantic_object=ResearchResponse)

        # Patch graph / PDF output directory so files go to output/
        import tools as _t
        _t.WORKSPACE_ROOT = OUTPUT_DIR

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an expert research assistant tasked with producing long, detailed, publication-quality research reports.\n\n"
                "CRITICAL ORDER OF ACTIONS:\n"
                "1. Run 'search_academic_papers' AND 'ArxivSearch' to gather broad source material before writing anything.\n"
                "2. Use 'WebScraper' on 2-3 relevant URLs to pull deeper detail from the best sources.\n"
                "3. Use 'PythonREPL' to compute all numerical results and print them.\n"
                "4. Invoke 'graph_creator' to build MULTIPLE graphs — aim for at least 5-8 covering different variables.\n"
                "5. Call 'pdf_generator' ONCE at the end with the full HTML. Embed every graph using the exact "
                "<img src='path' /> string returned by graph_creator.\n\n"
                "GRAPH FORMAT — strictly enforced:\n"
                '   data_json must be a FLAT JSON list of series objects:\n'
                '   [{{"x": [...], "y": [...], "name": "Series Label", "mode": "lines"}}]\n'
                "   Valid modes: 'lines' (default), 'bar', 'markers'.\n"
                '   Do NOT wrap data_json in a Plotly-style {{"data": [...], "layout": {{...}}}} object.\n\n'
                "DOCUMENT STRUCTURE — the PDF content_html MUST contain ALL of these sections in order:\n"
                "   <h2>Abstract</h2>, <h2>Introduction</h2>, <h2>Literature Review</h2>,\n"
                "   <h2>Theoretical Background</h2>, <h2>Methodology</h2>,\n"
                "   <h2>Results and Analysis</h2>, <h2>Discussion</h2>,\n"
                "   <h2>Conclusion</h2>, <h2>Future Directions</h2>, <h2>References</h2>\n\n"
                "WRITING DEPTH — every section must have 3-5 substantial paragraphs of flowing prose.\n"
                "   Each paragraph should be 5-8 sentences minimum. Cite sources inline as (Author, Year).\n\n"
                "HTML FORMATTING — use HTML <sub>/<sup> tags. Do NOT use Unicode subscript/superscript.\n"
                "MATH — use $$ ... $$ block syntax for equations.\n"
                "PYTHON REPL — scipy is NOT installed. Use numpy (pre-imported as 'np').\n\n"
                "Formatting parameters:\n{format_instructions}."
            ),
            ("placeholder", "{chat_history}"),
            ("human", "{query}"),
            ("placeholder", "{agent_scratchpad}")
        ]).partial(format_instructions=parser.get_format_instructions())

        tools = [search_tool, arxiv_tool, web_scraper_tool,
                 pdf_generator_tool, graph_creator_tool, python_repl_tool]

        agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
        agent_executor = AgentExecutor(
            agent=agent, tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=25,
        )

        tasks[task_id]['progress_message'] = 'Searching arXiv and academic web sources...'

        raw_response = agent_executor.invoke({"query": query})

        # Parse the output
        output_text = None
        if isinstance(raw_response, dict):
            output_text = raw_response.get("output")
            if isinstance(output_text, list) and output_text:
                output_text = output_text[0]
            if isinstance(output_text, dict):
                output_text = (output_text.get("text")
                               or output_text.get("output_text")
                               or str(output_text))
        else:
            output_text = str(raw_response)

        # Try to parse structured response
        result_data = {}
        try:
            parsed = parser.parse(output_text)
            result_data = parsed.model_dump() if hasattr(parsed, 'model_dump') else parsed.dict()
        except Exception:
            json_data = extract_json_block(output_text) if output_text else None
            if json_data and isinstance(json_data, dict):
                result_data = json_data
            else:
                result_data = {
                    'topic': query,
                    'summary': output_text[:2000] if output_text else 'Report generated.',
                    'sources': [],
                    'tools_used': []
                }

        # Find generated PDF
        pdf_path = None
        for f in os.listdir(OUTPUT_DIR):
            if f.lower().endswith('.pdf'):
                pdf_path = f
                break

        if pdf_path:
            result_data['pdf_path'] = pdf_path

        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['result'] = result_data
        tasks[task_id]['progress_message'] = 'Research report complete!'

    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)


# ---------------------------------------------------------------------------
# Math paper runner (runs in a thread)
# ---------------------------------------------------------------------------
def run_math_task(task_id: str, count: int, topic: str,
                  difficulty: str, year_level: str, include_diagrams: bool = True):
    """Generate math worksheet + answer key PDFs."""
    try:
        tasks[task_id]['status'] = 'running'
        tasks[task_id]['progress_message'] = 'Contacting LLM to design math problems...'

        from math_gen import generate_paper
        from pdf_exporter import create_pdf

        problems = generate_paper(
            count=count, topic=topic,
            difficulty=difficulty, year_level=year_level,
            include_diagrams=include_diagrams
        )

        if not problems:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = 'LLM returned no problems. Check your API key.'
            return

        tasks[task_id]['progress_message'] = 'Compiling LaTeX to PDF...'

        title = f"{year_level} Math: {topic}"
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', f"{year_level}_{topic}_{difficulty}").lower()
        worksheet_name = f"{safe_name}.pdf"
        answers_name = f"{safe_name}_answers.pdf"

        worksheet_path = os.path.join(OUTPUT_DIR, worksheet_name)
        answers_path = os.path.join(OUTPUT_DIR, answers_name)

        # Save current directory, cd to output so pdflatex artifacts go there
        prev_cwd = os.getcwd()
        os.chdir(OUTPUT_DIR)
        try:
            create_pdf(problems, worksheet_path, title=title)
            create_pdf(problems, answers_path, show_answers=True,
                       title=title + " (Answer Key)")
        finally:
            os.chdir(prev_cwd)

        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['result'] = {
            'title': title,
            'worksheet_path': worksheet_name,
            'answers_path': answers_name,
            'problem_count': len(problems),
        }
        tasks[task_id]['progress_message'] = 'Math paper compiled!'

    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    api_key = (os.getenv("MISTRALAI_API_KEY")
               or os.getenv("MISTRAL_API_KEY")
               or os.getenv("MISTRAL_KEY"))
    return jsonify({
        'status': 'ok',
        'api_key_configured': bool(api_key),
        'timestamp': datetime.utcnow().isoformat(),
    })


@app.route('/api/research', methods=['POST'])
def api_research():
    data = request.get_json(force=True)
    query = data.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query is required'}), 400

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        'type': 'research',
        'status': 'queued',
        'query': query,
        'created_at': datetime.utcnow().isoformat(),
        'result': None,
        'error': None,
        'progress_message': 'Task queued...',
    }

    thread = threading.Thread(
        target=run_research_task, args=(task_id, query), daemon=True
    )
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'queued'})


@app.route('/api/math', methods=['POST'])
def api_math():
    data = request.get_json(force=True)
    topic = data.get('topic', '').strip()
    if not topic:
        return jsonify({'error': 'Topic is required'}), 400

    count = int(data.get('count', 5))
    difficulty = data.get('difficulty', 'Medium')
    year_level = data.get('year_level', 'Year 10')
    include_diagrams = bool(data.get('include_diagrams', True))

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        'type': 'math',
        'status': 'queued',
        'topic': topic,
        'count': count,
        'difficulty': difficulty,
        'year_level': year_level,
        'include_diagrams': include_diagrams,
        'created_at': datetime.utcnow().isoformat(),
        'result': None,
        'error': None,
        'progress_message': 'Task queued...',
    }

    thread = threading.Thread(
        target=run_math_task,
        args=(task_id, count, topic, difficulty, year_level, include_diagrams),
        daemon=True,
    )
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'queued'})


@app.route('/api/task/<task_id>')
def api_task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)


@app.route('/api/download/<path:filename>')
def api_download(filename):
    """Serve generated files from the output directory."""
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    print(f"🚀 AI Research Assistant running at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
