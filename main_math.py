import argparse
from math_gen import generate_paper
from pdf_exporter import create_pdf

def main():
    parser = argparse.ArgumentParser(description="Generate an AI-powered Math Practice Paper")
    parser.add_argument("--count", type=int, default=5, help="Number of problems")
    parser.add_argument("--topic", type=str, default="Polynomials", help="Topic of the questions")
    parser.add_argument("--difficulty", type=str, default="Medium", choices=["Easy", "Medium", "Hard", "Harder", "Olympiad"], help="Difficulty level")
    parser.add_argument("--year_level", type=str, default="Year 10", help="Target student year/grade level")
    parser.add_argument("--output", type=str, default="math_paper.pdf", help="Output filename that is unique to the topic and difficulty (e.g., 'year10_polynomials_medium.pdf')")
    
    args = parser.parse_args()
    
    print(f"Generating {args.count} problems on '{args.topic}' for {args.year_level} (Difficulty: {args.difficulty})...")
    
    # 1. Ask LLM to generate the problems
    problems = generate_paper(
        count=args.count, 
        topic=args.topic, 
        difficulty=args.difficulty, 
        year_level=args.year_level
    )
    
    if not problems:
        print("Failed to generate problems. Check your API key.")
        return

    title = f"{args.year_level} Math: {args.topic}"
    
    # 2. Compile Worksheet PDF
    create_pdf(problems, args.output, title=title)
    
    # 3. Compile Answer Key PDF
    answer_file = args.output.replace(".pdf", "_answers.pdf")
    create_pdf(problems, answer_file, show_answers=True, title=title + " (Answer Key)")
    
    print("\nProcess Complete!")
    print(f"Worksheet: {args.output}")
    print(f"Answer Key: {answer_file}")

if __name__ == "__main__":
    main()