# 🔬 AI Research Assistant

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/framework-Flask-lightgrey.svg)](https://flask.palletsprojects.com/)
[![LangChain](https://img.shields.io/badge/orchestration-LangChain-brightgreen.svg)](https://www.langchain.com/)
[![Mistral AI](https://img.shields.io/badge/LLM-Mistral%20AI-orange.svg)](https://mistral.ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

An autonomous, multi-modal AI research and educational assistant powered by **LangChain**, **Mistral AI**, and **Flask**. The assistant orchestrates autonomous tool-use workflows to conduct in-depth scientific investigations, statistical computations, and dynamic problem set compilation, exporting polished, publication-ready PDF documents.

---

## 📸 Overview & Preview

<!-- Screenshot Placeholder -->
<p align="center">
  <img src="https://raw.githubusercontent.com/placeholder/ai-research-assistant/main/assets/preview-placeholder.png" alt="AI Research Assistant UI Preview" width="85%" style="border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);" />
  <br>
  <em>Figure: AI Research Assistant Web Interface & Automated PDF Generation Pipeline</em>
</p>

---

## ✨ Features

### 1. 📑 Autonomous Research Reports
- **Multi-Source Synthesis**: Performs broad literature searches using DuckDuckGo and ArXiv academic search tools, extracting and reviewing papers autonomously.
- **Deep Web Scraping**: Extracts comprehensive contextual information and data from primary sources using BeautifulSoup.
- **Embedded Numerical Computation**: Executes real-time mathematical derivations, linear regressions, and kinetics calculations via a Python REPL sandbox powered by NumPy.
- **Interactive Visualizations**: Synthesizes and plots multi-variable datasets (Plotly & Matplotlib) and automatically embeds them into generated reports.
- **Publication-Grade PDFs**: Produces structured papers formatted with Abstract, Literature Review, Methodology, Results with Figure captions, Discussion, and Harvard-style citations.

### 2. 📐 AI-Powered Math Practice Papers
- **Custom Problem Generation**: Automatically synthesizes graded curriculum-aligned problem sets according to year level (e.g., Year 7–12) and difficulty (`Easy`, `Medium`, `Hard`, `Test`, `Olympiad`).
- **LaTeX Math Rendering**: Formulates clean mathematical expressions with rigorous derivations and step-by-step reasoning.
- **Companion Answer Keys**: Automatically compiles two synchronized documents: a clean Student Practice Worksheet PDF and a comprehensive Step-by-Step Answer Key PDF.

---

## 🛠 Tech Stack

- **Backend Framework**: [Flask](https://flask.palletsprojects.com/) & [Gunicorn](https://gunicorn.org/)
- **LLM & Agents**: [LangChain](https://www.langchain.com/), [Mistral AI](https://mistral.ai/) (`mistral-large-latest`)
- **Academic & Web Tools**: `duckduckgo-search`, `arxiv`, `beautifulsoup4`, `requests`
- **Data & Computation**: `numpy`, `python-dotenv`, `pydantic`
- **Visualization**: `plotly`, `kaleido`, `matplotlib`, `pillow`
- **Document Exporting**: `reportlab`

---

## 🔑 Environment Variables

Create a `.env` file in the root directory and supply your API credentials:

| Variable | Description | Required | Example |
| :--- | :--- | :---: | :--- |
| `MISTRALAI_API_KEY` | Mistral AI API key for LLM agents | **Yes** | `your_mistral_api_key_here` |
| `PORT` | Web server listening port (production sets this automatically) | No | `5000` |
| `FLASK_ENV` | Environment mode (`development` or `production`) | No | `production` |
| `OPENAI_API_KEY` | Optional alternative LLM provider key | No | `sk-...` |
| `ANTHROPIC_API_KEY` | Optional alternative LLM provider key | No | `sk-ant-...` |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+** installed on your system
- A valid **Mistral AI API Key**

### 1. Clone Repository
```bash
git clone https://github.com/your-username/ai-research-assistant.git
cd ai-research-assistant
```

### 2. Create and Activate Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root:
```env
MISTRALAI_API_KEY=your_mistral_api_key_here
```

### 5. Run the Application

#### Web Interface (Flask)
```bash
python app.py
```
*Access the local web dashboard at `http://localhost:5000`.*

#### CLI: Research Assistant Agent
```bash
python main.py
```

#### CLI: Math Paper Generator
```bash
python main_math.py --topic "Quadratic Functions" --difficulty "Hard" --year_level "Year 11" --count 5
```

---

## ☁️ Deployment

### One-Click Deploy to Render

Deploy this application directly on Render with a single click:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### Manual Blueprint Setup (Render)

1. Fork or push this repository to GitHub.
2. Sign in to [Render](https://render.com/) and click **New +** > **Blueprint**.
3. Connect your repository. Render will automatically detect [`render.yaml`](render.yaml):
  - Render builds the [`Dockerfile`](Dockerfile), which installs Python 3.11 and TeX Live for math worksheet PDFs.
4. Set the `MISTRALAI_API_KEY` in the Render environment variables dashboard.
5. Click **Apply** to deploy.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
