import os
import subprocess
import re

def build_latex_content(problems, title="Math Practice Worksheet", show_answers=False, include_diagrams=True) -> str:
    """Builds the LaTeX source string with TikZ diagram support."""
    latex_content = r"""\documentclass[12pt]{article}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{geometry}
\usepackage{enumitem}
\usepackage{tikz}
\usetikzlibrary{calc,angles,quotes,shapes.geometric,arrows.meta}
\geometry{a4paper, margin=1in}

\begin{document}

\begin{center}
    \Large \textbf{""" + title + r"""}
\end{center}
\vspace{0.5cm}

\textbf{Name:} \underline{\hspace{6cm}} \hfill \textbf{Date:} \underline{\hspace{4cm}}
\vspace{0.8cm}

\begin{enumerate}[label=\textbf{\arabic*.}, leftmargin=*]
"""

    for p in problems:
        # Inject the LLM's Question
        latex_content += r"\item " + p.question + "\n\n"
        
        # Check if diagram is present
        diagram = (getattr(p, 'diagram_code', None) or "").strip() if include_diagrams else ""
        if diagram:
            # Avoid duplicate if already inside question string
            if r"\begin{tikzpicture}" not in p.question:
                latex_content += r"\begin{center}" + "\n" + diagram + "\n" + r"\end{center}" + "\n\n"

        if show_answers:
            # Inject the LLM's Answer
            latex_content += r"\textbf{Solution:}\\ " + p.answer + "\n\n"
            latex_content += r"\vspace{0.8cm}" + "\n\n"
        else:
            # Leave appropriate blank space for the student to work
            space = "3.5cm" if diagram else "5cm"
            latex_content += rf"\vspace{{{space}}}" + "\n\n"
            
    latex_content += r"\end{enumerate}" + "\n\n" + r"\end{document}"
    return latex_content


def compile_latex(tex_filename: str, output_pdf: str) -> bool:
    """Invokes pdflatex to compile a .tex file."""
    tex_dir = os.path.dirname(os.path.abspath(tex_filename)) or os.getcwd()
    tex_base = os.path.basename(tex_filename)
    pdf_base = os.path.splitext(tex_base)[0] + '.pdf'
    expected_pdf = os.path.join(tex_dir, pdf_base)

    # Remove existing PDF to ensure fresh detection
    if os.path.exists(expected_pdf):
        try:
            os.remove(expected_pdf)
        except Exception:
            pass

    cmd = ["pdflatex", "-interaction=nonstopmode", tex_base]
    proc = subprocess.run(cmd, cwd=tex_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Clean up LaTeX auxiliary junk files
    for ext in ['.aux', '.log']:
        aux_file = os.path.join(tex_dir, os.path.splitext(tex_base)[0] + ext)
        if os.path.exists(aux_file):
            try:
                os.remove(aux_file)
            except Exception:
                pass

    # Success if pdflatex generated a non-empty PDF
    if os.path.exists(expected_pdf) and os.path.getsize(expected_pdf) > 0:
        return True

    return proc.returncode == 0


def create_pdf(problems, filename="math_worksheet.pdf", show_answers=False, title="Math Practice Worksheet"):
    """
    Generates a .tex file and compiles it to PDF using system pdflatex.
    Supports TikZ diagrams and provides a fallback if a diagram has syntax issues.
    """
    base_name = os.path.splitext(filename)[0]
    tex_filename = base_name + '.tex'

    # 1. First attempt: with diagrams
    latex_content = build_latex_content(problems, title=title, show_answers=show_answers, include_diagrams=True)
    with open(tex_filename, "w", encoding="utf-8") as f:
        f.write(latex_content)
        
    print(f"Saved LaTeX source to {tex_filename}")
    print(f"Compiling {tex_filename} with pdflatex...")

    try:
        success = compile_latex(tex_filename, filename)
        if success:
            print(f"[OK] Successfully compiled {filename}")
            return True
        else:
            print(f"[WARN] Primary compilation failed. Attempting fallback without diagrams...")
            # Fallback attempt: compile without diagrams in case of TikZ syntax quirks
            fallback_content = build_latex_content(problems, title=title, show_answers=show_answers, include_diagrams=False)
            with open(tex_filename, "w", encoding="utf-8") as f:
                f.write(fallback_content)

            fallback_success = compile_latex(tex_filename, filename)
            if fallback_success:
                print(f"[OK] Successfully compiled {filename} using fallback mode.")
                return True
            else:
                print(f"[ERROR] Error compiling LaTeX even in fallback mode.")
                return False

    except FileNotFoundError:
        print("[ERROR] 'pdflatex' command not found! Please ensure LaTeX is installed and in your PATH.")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error compiling LaTeX: {e}")
        return False