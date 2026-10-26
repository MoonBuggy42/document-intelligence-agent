import os
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# Define the expected JSON structure
class MathProblem(BaseModel):
    question: str = Field(description="The math question. Use standard LaTeX math mode for equations.")
    has_diagram: bool = Field(default=False, description="True if a visual diagram or figure illustrates or accompanies this problem.")
    diagram_code: str = Field(
        default="",
        description=(
            "Valid self-contained LaTeX TikZ diagram code enclosed strictly in \\begin{tikzpicture} ... \\end{tikzpicture}. "
            "Use standard TikZ (e.g. \\draw, \\node, \\coordinate, \\fill) to plot geometry shapes, right-angle triangles, coordinate axes with curves, circles with chords/radii, or vectors. "
            "If no diagram is needed for this question, set to empty string (\"\")."
        )
    )
    answer: str = Field(description="The step-by-step solution. Use standard LaTeX math mode.")

class MathPaper(BaseModel):
    problems: List[MathProblem] = Field(description="List of math problems generated.")

def generate_paper(count: int, topic: str, difficulty: str, year_level: str, include_diagrams: bool = True) -> List[MathProblem]:
    """Generates math questions using LangChain and an LLM."""
    
    # Attempt to load LLM based on available keys
    api_key = os.getenv("MISTRAL_API_KEY") or os.getenv("MISTRALAI_API_KEY")
    if api_key:
        from langchain_mistralai import ChatMistralAI
        llm = ChatMistralAI(model="mistral-large-latest", api_key=api_key, temperature=0.2)
    else:
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            print("ERROR: No API key found. Please set MISTRAL_API_KEY or OPENAI_API_KEY.")
            return []
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o", api_key=openai_key, temperature=0.2)

    diagram_instructions = (
        """
DIAGRAM (TIKZ) INSTRUCTIONS:
1. When generating problems that benefit from visual figures (e.g., Geometry, Trigonometry, Coordinate Geometry, Function Graphs, Angles, Triangles, Polygons, Vectors):
   - Set 'has_diagram' to True.
   - Provide clean, robust, standalone TikZ code in the 'diagram_code' field.
   - The snippet MUST start with \\begin{tikzpicture} and end with \\end{tikzpicture}.
   - Keep figures reasonably scaled (e.g., \\begin{tikzpicture}[scale=0.8] or coordinate ranges between -4 and 5).
   - Use standard commands: \\draw, \\coordinate, \\node, \\fill, \\arc, \\clip.
   - Label lengths, points, and angles clearly (e.g., \\node[below] at (2,0) {$b = 8$ cm};).
   - For coordinate graphs: Draw axes with arrows (\\draw[->] (-3,0) -- (3,0) node[right] {$x$};) and draw curves with smooth coordinates or standard TikZ plots.
   - Ensure every TikZ statement ends with a semicolon (;) and has matching braces.
2. For purely algebraic or arithmetic problems that do not naturally need visuals, set 'has_diagram' to False and 'diagram_code' to "".
"""
        if include_diagrams else
        """
DIAGRAM INSTRUCTIONS: Do not generate diagrams. Set 'has_diagram' to False and 'diagram_code' to "".
"""
    )

    # Prompt Engineering for LaTeX output
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are an expert mathematics examiner. Generate {{count}} unique math problems.
        
TARGET AUDIENCE:
- Topic: {{topic}}
- Year/Grade Level: {{year_level}}
- Difficulty: {{difficulty}}

FORMAT INSTRUCTIONS:
1. You are generating content that will be injected directly into a LaTeX document with packages: amsmath, amssymb, tikz.
2. For inline math, use $ ... $ (e.g., Let $x = 5$).
3. For block math, use $$ ... $$ or \\[ ... \\].
4. Do not use markdown wrappers like ```latex. Just output the raw text and math.
5. Provide clear, accurate step-by-step solutions in the 'answer' field.
{diagram_instructions}"""),
        ("human", "Generate the {count} math problems now.")
    ])
    
    # Enforce structured JSON output via Pydantic
    structured_llm = llm.with_structured_output(MathPaper)
    chain = prompt | structured_llm
    
    print(f"Contacting LLM to generate {count} problems (include_diagrams={include_diagrams})...")
    try:
        result = chain.invoke({
            "count": count,
            "topic": topic,
            "year_level": year_level,
            "difficulty": difficulty
        })
        return result.problems if result else []
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return []