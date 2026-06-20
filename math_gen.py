import os
from pydantic import BaseModel, Field
from typing import List
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# Define the expected JSON structure
class MathProblem(BaseModel):
    question: str = Field(description="The math question. Use standard LaTeX math mode for equations.")
    answer: str = Field(description="The step-by-step solution. Use standard LaTeX math mode.")

class MathPaper(BaseModel):
    problems: List[MathProblem] = Field(description="List of math problems generated.")

def generate_paper(count: int, topic: str, difficulty: str, year_level: str) -> List[MathProblem]:
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

    # Prompt Engineering for LaTeX output
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert mathematics examiner. Generate {count} unique math problems.
        
TARGET AUDIENCE:
- Topic: {topic}
- Year/Grade Level: {year_level}
- Difficulty: {difficulty}

FORMAT INSTRUCTIONS:
1. You are generating content that will be injected directly into a LaTeX document.
2. For inline math, use $ ... $ (e.g., Let $x = 5$).
3. For block math, use $$ ... $$ or \\[ ... \\].
4. Do not use markdown wrappers like ```latex. Just output the raw text and math.
5. Provide clear, accurate step-by-step solutions in the 'answer' field."""),
        ("human", "Generate the {count} math problems now.")
    ])
    
    # Enforce structured JSON output via Pydantic
    structured_llm = llm.with_structured_output(MathPaper)
    chain = prompt | structured_llm
    
    print(f"Contacting LLM to generate {count} problems...")
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