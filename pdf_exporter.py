import os
import subprocess

def create_pdf(problems, filename="math_worksheet.pdf", show_answers=False, title="Math Practice Worksheet"):
    """
    Generates a .tex file and compiles it to PDF using system pdflatex.
    """
    base_name = os.path.splitext(filename)[0]
    tex_filename = base_name + '.tex'
    
    # LaTeX document template
    latex_content = r"""\documentclass[12pt]{article}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{geometry}
\usepackage{enumitem}
\geometry{a4paper, margin=1in}

\begin{document}

\begin{center}
    \Large \textbf{""" + title + r"""}
\end{center}
\vspace{0.5cm}

\textbf{Name:} \underline{\hspace{6cm}} \hfill \textbf{Date:} \underline{\hspace{4cm}}
\vspace{1cm}

\begin{enumerate}[label=\textbf{\arabic*.}, leftmargin=*]
"""

    for p in problems:
        # Inject the LLM's Question
        latex_content += r"\item " + p.question + "\n\n"
        
        if show_answers:
            # Inject the LLM's Answer
            latex_content += r"\textbf{Solution:}\\ " + p.answer + "\n\n"
            latex_content += r"\vspace{0.8cm}" + "\n\n"
        else:
            # Leave blank space for the student to work
            latex_content += r"\vspace{5cm}" + "\n\n"
            
    latex_content += r"\end{enumerate}" + "\n\n" + r"\end{document}"

    # Write the .tex file to disk
    with open(tex_filename, "w", encoding="utf-8") as f:
        f.write(latex_content)
        
    print(f"Saved LaTeX source to {tex_filename}")
    
    # Trigger your local LaTeX compiler
    try:
        print(f"Compiling {tex_filename} with pdflatex...")
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_filename], 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        print(f"✅ Successfully compiled {filename}")
        
        # Clean up LaTeX auxiliary junk files
        for ext in ['.aux', '.log']:
            if os.path.exists(base_name + ext):
                os.remove(base_name + ext)
                
    except FileNotFoundError:
        print("❌ Error: 'pdflatex' command not found! Please ensure LaTeX is installed and in your PATH.")
        print(f"You can still compile {tex_filename} manually in an editor like TeXstudio or Overleaf.")
    except subprocess.CalledProcessError:
        print(f"⚠️ Warning: Error compiling LaTeX. There might be a rogue character in the LLM's generation.")
        print(f"Check {tex_filename} to fix it manually.")