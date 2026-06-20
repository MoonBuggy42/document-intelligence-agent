import subprocess
import sys  # FIX: needed for sys.executable
import time
import json
import os
from tools import generate_formatted_pdf_document

WORKDIR = os.path.dirname(__file__)
LAST_GRAPH = os.path.join(WORKDIR, 'last_graph_payload.json')
LAST_PDF = os.path.join(WORKDIR, 'last_pdf_payload.json')

query = "quantum mechanics (use all tools and generate a pdf with graphs on the topic)"

# FIX: use sys.executable instead of a hardcoded Windows venv path so this script
# works regardless of platform or where the venv lives.
proc = subprocess.run(
    [sys.executable, os.path.join(WORKDIR, 'main.py')],
    input=query + "\n",
    text=True,
    capture_output=True,
)
print(proc.stdout)
print(proc.stderr)

# Wait a moment for tools to flush
time.sleep(1)

graph_path = None
if os.path.exists(LAST_GRAPH):
    try:
        with open(LAST_GRAPH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            graph_path = data.get('output_file')
    except Exception as e:
        print('Failed reading last graph payload:', e)

# If agent didn't create a PDF but produced a graph, force-embed it
if graph_path and not os.path.exists(os.path.join(WORKDIR, 'agent_forced_report.pdf')):
    img_path = graph_path.replace('\\', '/')
    content_html = (
        f"<h1>Agent Report: Quantum Mechanics</h1>"
        f"<p>Generated graph included below.</p>"
        f"<img src='{img_path}'/>"
        f"<h2>References</h2><p>See sources collected by the agent.</p>"
    )
    try:
        # FIX: always use the .func attribute to call the raw function directly,
        # bypassing LangChain wrapper logic that can interfere outside an agent loop.
        pdf_fn = getattr(generate_formatted_pdf_document, 'func', generate_formatted_pdf_document)
        out = pdf_fn('agent_forced_report.pdf', 'Quantum Mechanics', 'Quantum Mechanics', content_html)
        print('Forced PDF generation result:', out)
    except Exception as e:
        print('Error generating forced PDF:', e)

# Clean debug files
for p in (LAST_GRAPH, LAST_PDF):
    try:
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass

print('Done.')