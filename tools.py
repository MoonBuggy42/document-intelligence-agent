import json
import os
import re
import requests
import io
import time
import ast
import tempfile
import contextlib
from bs4 import BeautifulSoup
from langchain_community.tools import DuckDuckGoSearchRun, Tool
from langchain_community.tools.arxiv.tool import ArxivQueryRun
from langchain_community.utilities import ArxivAPIWrapper
from langchain_core.tools import tool, StructuredTool

# Debug artifacts
WORKSPACE_ROOT = os.path.dirname(__file__)
LAST_GRAPH_PAYLOAD = os.path.join(WORKSPACE_ROOT, 'last_graph_payload.json')
LAST_PDF_PAYLOAD   = os.path.join(WORKSPACE_ROOT, 'last_pdf_payload.json')

# ── FIX 1: Unicode sub/superscript → HTML tags ──────────────────────────────
# Helvetica (ReportLab's default) has no glyphs for Unicode subscript/superscript
# code-points (₂, ₃, ₄, ⁺, ⁻ …).  They render as ■.  Convert them to proper
# <sub>/<sup> HTML tags before ReportLab ever sees the content.
_SUB_CHARS = {
    '₀':'0','₁':'1','₂':'2','₃':'3','₄':'4','₅':'5','₆':'6','₇':'7','₈':'8','₉':'9',
    'ₐ':'a','ₑ':'e','ₒ':'o','ₓ':'x','ₙ':'n','ₕ':'h','ₖ':'k','ₗ':'l','ₘ':'m','ₚ':'p',
    'ₛ':'s','ₜ':'t',
}
_SUP_CHARS = {
    '⁰':'0','¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9',
    '⁺':'+','⁻':'-','ⁿ':'n','ⁱ':'i',
}

def _replace_unicode_scripts(text: str) -> str:
    """Replace consecutive Unicode sub/superscript chars with HTML <sub>/<sup> tags."""
    result = []
    i = 0
    while i < len(text):
        c = text[i]
        if c in _SUB_CHARS:
            group = []
            while i < len(text) and text[i] in _SUB_CHARS:
                group.append(_SUB_CHARS[text[i]])
                i += 1
            result.append(f'<sub>{"".join(group)}</sub>')
        elif c in _SUP_CHARS:
            group = []
            while i < len(text) and text[i] in _SUP_CHARS:
                group.append(_SUP_CHARS[text[i]])
                i += 1
            result.append(f'<sup>{"".join(group)}</sup>')
        else:
            result.append(c)
            i += 1
    return ''.join(result)

# ── FIX 2: Simplify LaTeX that matplotlib's mathtext doesn't support ─────────
# matplotlib doesn't implement AMS arrows (\xrightleftharpoons, \xrightarrow{}).
# Substitute them before rendering and fall back gracefully if it still fails.
_LATEX_SUBS = [
    (r'\\xrightleftharpoons\s*\[[^\]]*\]\s*\{[^}]*\}', r'\\rightleftharpoons'),
    (r'\\xrightleftharpoons\s*\{[^}]*\}',              r'\\rightleftharpoons'),
    (r'\\xrightleftharpoons',                           r'\\rightleftharpoons'),
    (r'\\xrightarrow\s*\{[^}]*\}',                     r'\\rightarrow'),
    (r'\\xrightarrow',                                  r'\\rightarrow'),
    (r'\\xleftarrow\s*\{[^}]*\}',                      r'\\leftarrow'),
    (r'\\xleftarrow',                                   r'\\leftarrow'),
    (r'\\underset\s*\{[^}]*\}\s*\{([^}]*)\}',          r'\1'),
    (r'\\overset\s*\{[^}]*\}\s*\{([^}]*)\}',           r'\1'),
]

def _simplify_latex(formula: str) -> str:
    for pattern, repl in _LATEX_SUBS:
        formula = re.sub(pattern, repl, formula)
    return formula

# 1. SEARCH & ARXIV TOOLS
search = DuckDuckGoSearchRun()
search_tool = Tool(name="search_academic_papers", func=search.run,
                   description="Search the web for academic papers and scientific references.")

def safe_arxiv_search(query: str) -> str:
    try:
        time.sleep(2)
        wrapper = ArxivAPIWrapper(top_k=2, doc_content_chars_max=1500)
        results = wrapper.run(query)
        return results if results else f"No arxiv papers found for: {query}"
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "Too Many Requests" in error_str:
            return ("arXiv API rate limit exceeded. Try again in a few minutes, "
                    "or rely on the web search tool instead.")
        return f"Error searching arXiv: {error_str[:200]}"

# 3. GRAPH CREATOR
@tool
def generate_and_save_graph(payload) -> str:
    """Generates a professional chart and saves as PNG.

    data_json must be a FLAT list of series objects, e.g.:
      [{"x": [1,2,3], "y": [4,5,6], "name": "My Series"}]

    Optional "mode" per series: "lines" (default), "bar", "markers".
    Do NOT wrap data_json in a Plotly-style {"data": [...], "layout": {...}} object.
    """
    try:
        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except Exception:
                data = {"data_json": payload}
        elif isinstance(payload, dict):
            data = payload
        else:
            return "Error: Unsupported input type for graph tool"

        data_json  = data.get("data_json") or data.get("data") or data.get("series")
        title      = data.get("title")    or data.get("name")   or "Chart"
        x_label    = data.get("x_label") or data.get("xlabel") or "x"
        y_label    = data.get("y_label") or data.get("ylabel") or "y"
        file_name  = data.get("file_name") or data.get("fileName") or data.get("path") or "chart.png"

        if isinstance(data_json, str):
            series_list = json.loads(data_json)
        else:
            series_list = data_json

        # Unwrap Plotly-style {"data": [...], "layout": {...}}
        if isinstance(series_list, dict):
            series_list = series_list.get("data", [series_list])
        if not isinstance(series_list, list):
            series_list = [series_list]
        if series_list and not isinstance(series_list[0], dict):
            ys = series_list
            series_list = [{"x": list(range(len(ys))), "y": ys, "name": title}]

        if not os.path.isabs(file_name):
            file_name = os.path.join(WORKSPACE_ROOT, file_name)

        try:
            import plotly.graph_objects as go
            fig = go.Figure()
            for s in series_list:
                x, y, name = s.get('x'), s.get('y'), s.get('name', '')
                mode  = s.get('mode', 'lines+markers')
                stype = s.get('type', '')
                if stype == 'bar' or mode == 'bar':
                    fig.add_trace(go.Bar(x=x, y=y, name=name))
                elif mode == 'markers':
                    fig.add_trace(go.Scatter(x=x, y=y, mode='markers', name=name))
                else:
                    fig.add_trace(go.Scatter(x=x, y=y, mode='lines+markers', name=name))
            fig.update_layout(title=title, xaxis_title=x_label, yaxis_title=y_label,
                              template='plotly_white', width=1200, height=600)
            try:
                fig.write_image(file_name, engine='kaleido')
            except Exception:
                fig.write_image(file_name)
        except Exception:
            try:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
                for s in series_list:
                    x_data, y_data = s.get('x'), s.get('y')
                    name  = s.get('name', 'series')
                    mode  = s.get('mode',  'lines')
                    stype = s.get('type',  '')
                    if stype == 'bar' or mode == 'bar':
                        ax.bar(x_data, y_data, label=name, alpha=0.75)
                    elif mode == 'markers':
                        ax.scatter(x_data, y_data, label=name)
                    else:
                        ax.plot(x_data, y_data, marker='o', label=name)
                ax.set_title(title); ax.set_xlabel(x_label); ax.set_ylabel(y_label)
                ax.grid(True, linestyle='--', alpha=0.6)
                if len(series_list) > 1:
                    ax.legend()
                fig.tight_layout()
                fig.savefig(file_name, dpi=300, bbox_inches='tight')
                plt.close(fig)
            except Exception as e:
                return f"Error generating graph: {e}"

        try:
            with open(LAST_GRAPH_PAYLOAD, 'w', encoding='utf-8') as f:
                json.dump({"payload": data, "output_file": file_name}, f, indent=2)
        except Exception:
            pass

        file_name_html = file_name.replace('\\', '/')
        return (f"Graph successfully generated and saved to '{file_name}'. "
                f"INSTRUCTION: MUST include <img src='{file_name_html}' /> in your content_html parameter.")
    except Exception as e:
        return f"Error generating graph: {e}"

wrapped_graph_func = getattr(generate_and_save_graph, 'func', generate_and_save_graph)

def graph_creator(data_json, title: str = "Chart", x_label: str = "x",
                  y_label: str = "y", file_name: str = "chart.png") -> str:
    return wrapped_graph_func({"data_json": data_json, "title": title,
                               "x_label": x_label, "y_label": y_label, "file_name": file_name})

graph_creator_tool = StructuredTool.from_function(
    graph_creator, name="graph_creator",
    description=(
        "Generate a chart PNG. data_json must be a FLAT JSON list of series dicts: "
        '[{"x":[...],"y":[...],"name":"...","mode":"lines|bar|markers"}]. '
        'Do NOT wrap in {"data":[...],"layout":{...}}.'
    ),
)

# 4. REPORTLAB PDF GENERATOR
@tool
def generate_formatted_pdf_document(file_name: str, doc_title: str, doc_topic: str, content_html: str) -> str:
    """
    Creates a high-quality PDF.

    CRITICAL MATH & FORMATTING INSTRUCTIONS FOR AI:
    - Place ALL math equations on their own separate line using block syntax: $$ equation $$.
    - Do NOT use inline math ($y=mx+c$) inside text paragraphs.
    - MUST include a <h2>References</h2> section at the end in HARVARD style.
    - Use standard HTML tags (<p>, <h2>, <ul>, <ol>, <li>) to structure the document.
    - Whenever you generate a graph, MUST include <img src='path' /> in content_html.
    - Use HTML <sub> and <sup> tags for subscripts and superscripts (e.g. H<sub>2</sub>O<sub>2</sub>).
      Do NOT use Unicode subscript/superscript characters (₂, ⁺, etc.) — they render as boxes.
    """
    if not file_name.lower().endswith('.pdf'):
        return "Error: file_name must end in .pdf"

    try:
        import matplotlib.pyplot as plt
        import matplotlib as mpl
        from PIL import Image as PILImage
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import (
            Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
            ListFlowable, ListItem
        )
        from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT

        plt.switch_backend('Agg')
        mpl.rcParams['mathtext.fontset'] = 'cm'
        mpl.rcParams['text.color'] = '#1a1a1a'

        # ── FIX 1: convert Unicode sub/super to HTML tags before anything else ──
        content_html = _replace_unicode_scripts(content_html)

        # ── FIX 2: better math block renderer with fallback chain ────────────────
        def math_image_block(formula: str):
            formula = formula.strip().strip('$')

            def _render(f: str):
                dpi = 400
                fig = plt.figure(figsize=(4, 1.5), dpi=dpi)
                fig.patch.set_alpha(0.0)
                fig.text(0.5, 0.5, f'${f}$', fontsize=24, ha='center', va='center')
                buf = io.BytesIO()
                fig.savefig(buf, format='PNG', dpi=dpi, transparent=True,
                            bbox_inches='tight', pad_inches=0.2)
                plt.close(fig)
                buf.seek(0)
                img = Image(buf)
                scale = 72 / dpi
                img.drawWidth  = img.imageWidth  * scale
                img.drawHeight = img.imageHeight * scale
                img.hAlign = 'CENTER'
                return img

            # Attempt 1: original formula
            try:
                return _render(formula)
            except Exception:
                plt.close('all')

            # Attempt 2: simplified formula (AMS arrow substitutions)
            try:
                return _render(_simplify_latex(formula))
            except Exception:
                plt.close('all')

            # Attempt 3: plain-text fallback rendered as italic paragraph
            clean = re.sub(r'\\[a-zA-Z]+\*?', ' ', formula)
            clean = re.sub(r'[\{\}\[\]_\^]', '', clean).strip()
            style = ParagraphStyle('MathFallback', fontName='Helvetica-Oblique',
                                   fontSize=11, alignment=1, spaceAfter=6)
            return Paragraph(f'<i>{clean}</i>', style)

        def math_image_inline(formula: str) -> str:
            formula = formula.strip().strip('$')
            try:
                dpi = 400
                fig = plt.figure(figsize=(2, 0.75), dpi=dpi)
                fig.patch.set_alpha(0.0)
                fig.text(0.5, 0.5, f'${formula}$', fontsize=14, ha='center', va='center')
                buf = io.BytesIO()
                fig.savefig(buf, format='PNG', dpi=dpi, transparent=True,
                            bbox_inches='tight', pad_inches=0.02)
                plt.close(fig)
                buf.seek(0)
                fd, path = tempfile.mkstemp(suffix='.png')
                os.close(fd)
                with open(path, 'wb') as fh:
                    fh.write(buf.getvalue())
                with PILImage.open(path) as im:
                    w, h = im.size
                scale  = 72 / dpi
                width  = int(w * scale)
                height = int(h * scale)
                valign = -height * 0.25
                return f'<img src="{path.replace(chr(92), "/")}" width="{width}" height="{height}" valign="{valign}"/>'
            except Exception:
                plt.close('all')
                # Inline fallback: try simplified, then plain text
                try:
                    simplified = _simplify_latex(formula)
                    dpi = 400
                    fig = plt.figure(figsize=(2, 0.75), dpi=dpi)
                    fig.patch.set_alpha(0.0)
                    fig.text(0.5, 0.5, f'${simplified}$', fontsize=14, ha='center', va='center')
                    buf = io.BytesIO()
                    fig.savefig(buf, format='PNG', dpi=dpi, transparent=True,
                                bbox_inches='tight', pad_inches=0.02)
                    plt.close(fig)
                    buf.seek(0)
                    fd, path = tempfile.mkstemp(suffix='.png')
                    os.close(fd)
                    with open(path, 'wb') as fh:
                        fh.write(buf.getvalue())
                    with PILImage.open(path) as im:
                        w, h = im.size
                    scale  = 72 / dpi
                    width  = int(w * scale)
                    height = int(h * scale)
                    valign = -height * 0.25
                    return f'<img src="{path.replace(chr(92), "/")}" width="{width}" height="{height}" valign="{valign}"/>'
                except Exception:
                    plt.close('all')
                    clean = re.sub(r'\\[a-zA-Z]+\*?', '', formula)
                    clean = re.sub(r'[\{\}\[\]_\^]', '', clean).strip()
                    return f'<i>{clean}</i>'

        # HTML pre-processing
        content_html = re.sub(r'\$\$(.+?)\$\$', r'<math-block>\1</math-block>', content_html, flags=re.S)
        content_html = re.sub(r'\\\[(.+?)\\\]', r'<math-block>\1</math-block>', content_html, flags=re.S)
        content_html = re.sub(r'\$(.+?)\$',     r'<math-inline>\1</math-inline>', content_html, flags=re.S)
        content_html = re.sub(r'\\\((.+?)\\\)', r'<math-inline>\1</math-inline>', content_html, flags=re.S)

        styles = {
            'Title':      ParagraphStyle('Title',   fontName='Helvetica-Bold',    fontSize=26, leading=30, textColor=colors.white),
            'Topic':      ParagraphStyle('Topic',   fontName='Helvetica-Oblique', fontSize=14, leading=16, textColor=colors.HexColor('#bdc3c7')),
            'Heading1':   ParagraphStyle('H1',      fontName='Helvetica-Bold',    fontSize=18, leading=22, textColor=colors.HexColor('#2c3e50'), spaceBefore=20, spaceAfter=10),
            'Heading2':   ParagraphStyle('H2',      fontName='Helvetica-Bold',    fontSize=16, leading=20, textColor=colors.HexColor('#2c3e50'), spaceBefore=18, spaceAfter=8),
            'Heading3':   ParagraphStyle('H3',      fontName='Helvetica-Bold',    fontSize=14, leading=18, textColor=colors.HexColor('#34495e'), spaceBefore=15, spaceAfter=6),
            'BodyText':   ParagraphStyle('Body',    fontName='Helvetica',         fontSize=11, leading=16, alignment=TA_JUSTIFY, spaceAfter=12),
            'HarvardRef': ParagraphStyle('Harvard', fontName='Helvetica',         fontSize=10, leading=14, alignment=TA_LEFT, leftIndent=30, firstLineIndent=-30, spaceAfter=10),
        }

        def process_inline_nodes(nodes) -> str:
            segs = []
            for child in nodes:
                if getattr(child, 'name', None) is None:
                    t = str(child).replace('\n', ' ')
                    t = t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    segs.append(t)
                elif child.name == 'math-inline':
                    segs.append(math_image_inline(child.text))
                elif child.name in ('strong', 'b'):
                    segs.append(f'<b>{process_inline_nodes(child.children)}</b>')
                elif child.name in ('em', 'i'):
                    segs.append(f'<i>{process_inline_nodes(child.children)}</i>')
                elif child.name == 'u':
                    segs.append(f'<u>{process_inline_nodes(child.children)}</u>')
                elif child.name == 'br':
                    segs.append('<br/>')
                elif child.name == 'sup':
                    segs.append(f'<super>{process_inline_nodes(child.children)}</super>')
                elif child.name == 'sub':
                    segs.append(f'<sub>{process_inline_nodes(child.children)}</sub>')
                else:
                    segs.append(process_inline_nodes(child.children))
            return ''.join(segs)

        def parse_html_to_story(html_str):
            soup = BeautifulSoup(html_str, 'html.parser')
            state = {'in_references': False}

            def parse_container(node, current_style):
                flowables, inline_buffer = [], []

                def flush():
                    if inline_buffer:
                        snippet = process_inline_nodes(inline_buffer)
                        if snippet.strip():
                            flowables.append(Paragraph(snippet, current_style))
                        inline_buffer.clear()

                for child in node.children:
                    if getattr(child, 'name', None) is None:
                        if inline_buffer or str(child).strip():
                            inline_buffer.append(child)
                    elif child.name == 'math-block':
                        flush()
                        flowables.append(Spacer(1, 6))
                        flowables.append(math_image_block(child.get_text(strip=True)))
                        flowables.append(Spacer(1, 12))
                    elif child.name == 'img':
                        flush()
                        img_src = child.get('src')
                        if img_src:
                            rp = img_src if os.path.isabs(img_src) else os.path.join(WORKSPACE_ROOT, img_src)
                            if not os.path.exists(rp):
                                rp = img_src
                            if os.path.exists(rp):
                                try:
                                    img = Image(rp)
                                    max_w = A4[0] - 40*mm
                                    max_h = A4[1] - 80*mm
                                    ratio = 1.0
                                    if img.imageWidth > max_w:
                                        ratio = max_w / img.imageWidth
                                    if img.imageHeight * ratio > max_h:
                                        ratio = max_h / img.imageHeight
                                    img.drawWidth  = img.imageWidth  * ratio
                                    img.drawHeight = img.imageHeight * ratio
                                    img.hAlign = 'CENTER'
                                    flowables.extend([Spacer(1, 10), img, Spacer(1, 15)])
                                except Exception as e:
                                    flowables.append(Paragraph(f'<i>[Error loading image: {e}]</i>', styles['BodyText']))
                            else:
                                flowables.append(Paragraph(f'<i>[Image not found: {img_src}]</i>', styles['BodyText']))
                    elif child.name in ('ul', 'ol'):
                        flush()
                        items = []
                        for li in child.find_all('li', recursive=False):
                            li_f = parse_container(li, styles['BodyText'])
                            if li_f:
                                items.append(ListItem(li_f[0] if len(li_f) == 1 and isinstance(li_f[0], Paragraph) else li_f, leftIndent=15, spaceAfter=4))
                        if items:
                            flowables.append(ListFlowable(items, bulletType='bullet' if child.name == 'ul' else '1', leftIndent=15, spaceAfter=12))
                    elif child.name in ('h1', 'h2', 'h3'):
                        flush()
                        ct = child.get_text(strip=True).lower()
                        if 'reference' in ct or 'bibliography' in ct:
                            state['in_references'] = True
                        elif state['in_references'] and child.name == 'h2':
                            state['in_references'] = False
                        sname = 'Heading2' if child.name == 'h2' else ('Heading1' if child.name == 'h1' else 'Heading3')
                        flowables.append(Paragraph(process_inline_nodes([child]), styles[sname]))
                    elif child.name in ('p', 'div'):
                        flush()
                        flowables.extend(parse_container(child, styles['HarvardRef'] if state['in_references'] else styles['BodyText']))
                    else:
                        inline_buffer.append(child)

                flush()
                return flowables

            root = soup.body if soup.body else soup
            return parse_container(root, styles['BodyText'])

        doc = SimpleDocTemplate(file_name, pagesize=A4,
                                rightMargin=20*mm, leftMargin=20*mm,
                                topMargin=25*mm, bottomMargin=25*mm)
        story = []

        banner_table = Table([[Paragraph(doc_title, styles['Title'])],
                               [Paragraph(doc_topic, styles['Topic'])]],
                              colWidths=[A4[0] - 40*mm])
        banner_table.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,-1), colors.HexColor('#1a252f')),
            ('TOPPADDING',   (0,0), (-1,-1), 20),
            ('BOTTOMPADDING',(0,-1),(-1,-1), 20),
            ('LEFTPADDING',  (0,0), (-1,-1), 20),
            ('RIGHTPADDING', (0,0), (-1,-1), 20),
        ]))
        story.append(banner_table)
        story.append(Spacer(1, 20))
        story.extend(parse_html_to_story(content_html))

        def on_first_page(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(colors.HexColor('#7f8c8d'))
            canvas.setStrokeColor(colors.HexColor('#bdc3c7'))
            canvas.setLineWidth(0.5)
            canvas.line(20*mm, 15*mm, A4[0]-20*mm, 15*mm)
            canvas.drawRightString(A4[0]-20*mm, 10*mm, f'Page {doc.page}')
            canvas.drawString(20*mm, 10*mm, doc_title[:50]+('...' if len(doc_title)>50 else ''))
            canvas.restoreState()

        def on_later_pages(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(colors.HexColor('#7f8c8d'))
            canvas.setStrokeColor(colors.HexColor('#bdc3c7'))
            canvas.setLineWidth(0.5)
            canvas.line(20*mm, A4[1]-15*mm, A4[0]-20*mm, A4[1]-15*mm)
            canvas.drawRightString(A4[0]-20*mm, A4[1]-12*mm, doc_topic[:50]+('...' if len(doc_topic)>50 else ''))
            canvas.line(20*mm, 15*mm, A4[0]-20*mm, 15*mm)
            canvas.drawRightString(A4[0]-20*mm, 10*mm, f'Page {doc.page}')
            canvas.drawString(20*mm, 10*mm, doc_title[:50]+('...' if len(doc_title)>50 else ''))
            canvas.restoreState()

        doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
        if not os.path.isabs(file_name):
            file_name = os.path.join(WORKSPACE_ROOT, file_name)

        try:
            with open(LAST_PDF_PAYLOAD, 'w', encoding='utf-8') as f:
                json.dump({"file_name": file_name, "title": doc_title, "topic": doc_topic}, f, indent=2)
        except Exception:
            pass

        return f"PDF '{file_name}' generated beautifully using ReportLab."

    except Exception as e:
        import traceback
        return f"ReportLab PDF generation failed: {e}\n{traceback.format_exc()}"


wrapped_pdf_func = getattr(generate_formatted_pdf_document, 'func', generate_formatted_pdf_document)

def pdf_generator(file_name: str, doc_title: str, doc_topic: str, content_html: str) -> str:
    return wrapped_pdf_func(file_name, doc_title, doc_topic, content_html)

pdf_generator_tool = StructuredTool.from_function(
    pdf_generator, name="pdf_generator",
    description="Create a formatted PDF document from HTML content, title, topic, and filename.",
)

def scrape_website_content(url: str) -> str:
    """Fetch and return cleaned page text, capped to avoid context bloat."""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        for s in soup(['script', 'style', 'noscript']):
            s.decompose()
        text = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True))
        return text[:6000]
    except Exception as e:
        return f"Error fetching {url}: {e}"

arxiv_tool       = Tool(name="ArxivSearch", func=safe_arxiv_search,      description="Search arXiv (rate-limited wrapper)")
web_scraper_tool = Tool(name="WebScraper",  func=scrape_website_content, description="Fetch and extract text from a web page")


def python_repl_executor(code: str) -> str:
    """Execute Python code and return captured output.

    Fixes:
    1. numpy pre-imported as 'np'; np.trapz alias added for NumPy 2.0+.
    2. FIX 3: robust body/last-line split — uses compile() to verify the split
       is valid before executing.  If the body has a SyntaxError (e.g. because
       the agent wrote a multi-line dict literal and the closing '}' was peeled
       off as the 'last line'), the whole code block is exec'd instead, avoiding
       the crash that caused hallucinated Lineweaver-Burk x-values (10^15–10^18).
    3. REPL-style last-line eval so expression values are captured automatically.
    """
    try:
        import numpy as np
        if not hasattr(np, 'trapz') and hasattr(np, 'trapezoid'):
            try:
                np.trapz = np.trapezoid
            except AttributeError:
                pass

        repl_globals: dict = {
            "__builtins__": __builtins__,
            "np":        np,
            "numpy":     np,
            "trapz":     getattr(np, 'trapz',     getattr(np, 'trapezoid', None)),
            "trapezoid": getattr(np, 'trapezoid', getattr(np, 'trapz',     None)),
        }
        try:
            import matplotlib.pyplot as plt
            repl_globals["plt"] = plt
        except ImportError:
            pass

        local_vars: dict = {}
        buffer = io.StringIO()

        lines = code.strip().splitlines()
        if not lines:
            return "Python code executed successfully with no output."

        *body_lines, last_line = lines
        body_code = "\n".join(body_lines)

        # ── FIX 3: validate the split with compile() before executing ────────────
        # If the body has a SyntaxError (most commonly because a multi-line dict/
        # list literal was split at its closing brace), fall back to exec-ing the
        # entire code block as a single unit — no REPL-style eval.
        body_ok = True
        if body_code.strip():
            try:
                compile(body_code, '<string>', 'exec')
            except SyntaxError:
                body_ok = False

        last_is_expr = False
        if body_ok:
            try:
                compile(last_line, '<string>', 'eval')
                last_is_expr = True
            except SyntaxError:
                last_is_expr = False

        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            if not body_ok:
                # Split was invalid — execute the whole block untouched
                exec(code, repl_globals, local_vars)
            else:
                if body_code.strip():
                    exec(body_code, repl_globals, local_vars)
                if last_is_expr:
                    result = eval(last_line, repl_globals, local_vars)
                    if result is not None:
                        print(repr(result))
                else:
                    exec(last_line, repl_globals, local_vars)

        output = buffer.getvalue().strip()
        return output or "Python code executed successfully with no output."
    except Exception as e:
        import traceback
        return f"Python execution error: {e}\n{traceback.format_exc()}"


python_repl_tool = Tool(
    name="PythonREPL",
    func=python_repl_executor,
    description=(
        "A Python REPL. numpy is pre-imported as 'np'. scipy is NOT available — "
        "use np.polyfit(x, y, 1) for regression. "
        "Use np.trapezoid() not np.trapz() (removed in NumPy 2.0). "
        "To return data from the REPL, use print() or assign to a variable and print it. "
        "Do NOT use a bare multi-line dict/list literal as the final expression — "
        "assign it first: result = {...}; print(result)."
    ),
)

my_agent_tools = [search_tool, arxiv_tool, web_scraper_tool, python_repl_tool,
                  graph_creator_tool, pdf_generator_tool]