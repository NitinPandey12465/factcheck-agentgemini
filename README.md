# 🔍 FactCheck Agent

An AI-powered fact-checking web app that extracts claims from PDFs and verifies them against live web data.

## 🚀 Live Demo
> _(paste your Streamlit Cloud URL here after deployment)_

## ✨ Features
- **Extract** — Automatically identifies statistics, dates, financial figures, and factual claims from any PDF
- **Verify** — Uses GPT-4o with web search to cross-reference each claim against live data
- **Report** — Flags claims as ✅ Verified, ⚠️ Inaccurate, or ❌ False with explanations and correct values
- **Download** — Export the full report as JSON

## 🛠️ Tech Stack
| Layer | Tool |
|---|---|
| Frontend | Streamlit |
| AI Model | OpenAI GPT-4o / GPT-4o-mini |
| PDF Parsing | pdfplumber |
| Deployment | Streamlit Cloud |

## 📦 Local Setup

```bash
git clone https://github.com/YOUR_USERNAME/factcheck-agent
cd factcheck-agent
pip install -r requirements.txt
streamlit run app.py
```

Set your OpenAI API key either:
- In the app's Configuration panel (session only), OR
- In `.streamlit/secrets.toml`: `OPENAI_API_KEY = "sk-..."`

## ☁️ Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo → select `app.py`
4. In **Secrets**, add: `OPENAI_API_KEY = "sk-your-key-here"`
5. Click **Deploy** — done!

## 📂 Project Structure

```
factcheck-agent/
├── app.py               # Main Streamlit application
├── requirements.txt     # Python dependencies
├── .streamlit/
│   └── secrets.toml     # API keys (never commit!)
└── README.md
```

## 🧪 Testing with a Trap Document

The app is designed to catch:
- Outdated statistics (e.g., wrong year or wrong % figure)
- Fabricated financial data
- Incorrect dates of events
- Hallucinated technical metrics

Upload any PDF and the agent will flag suspicious claims with correct sourced data.

## 📄 License
MIT
