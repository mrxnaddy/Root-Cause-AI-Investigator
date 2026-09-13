# 🔎 Root Cause AI Investigator

Upload messy evidence — CSVs, logs, customer complaints, screenshots, PDFs.
Ask **"why did this happen?"** Get a causal chain, not just a summary.

```
FACT → EVENT → CORRELATION → POSSIBLE CAUSE → CONFIRMED CAUSE
```

Built for a hackathon submission. Runs on **Streamlit** + the **Groq API**.

---

## ✨ Features

| Feature | What it does |
|---|---|
| 🧠 **Causal Timeline** | Classifies every piece of evidence into FACT / EVENT / CORRELATION / POSSIBLE CAUSE / CONFIRMED CAUSE |
| 🎯 **Root Cause + Confidence** | Names the most likely cause with a confidence %, backed by cited evidence |
| 🧠 **Confidence Breakdown** | Explains *why* the confidence score is what it is (source diversity, corroboration, lead over alternatives) |
| 🕵️ **Red-Team Critic** | A second, independent AI pass stress-tests the conclusion — confidence can only go **down**, never up (enforced in code) |
| 📈 **Auto-Anomaly Detection** | Statistically flags unusual data points the moment files are uploaded — no LLM call needed |
| 📊 **Statistical Correlation Engine** | Computes real Pearson correlation coefficients between uploaded metrics |
| 🕸️ **Evidence → Cause Network Graph** | Visualizes which files back which explanation |
| 💰 **Impact Calculator + Severity Score** | Quantifies the financial impact using your own uploaded numbers |
| 🛠️ **Prevention Recommendations** | Prioritized, actionable steps to stop recurrence |
| 🔮 **What-If Scenario Simulator** | Answers hypotheticals, always clearly labeled `ESTIMATE` (confidence capped at 70%) |
| 🧾 **Executive Summary** | A short, non-technical summary for stakeholders |
| 🌐 **Urdu Translation** | Toggle to translate key outputs |
| 🔗 **Similar-Incident Pattern Matching** | Flags when a new investigation resembles a past one |
| 🗂️ **History Log** | Reload and compare past investigations |
| 🔐 **PII Redaction** | Emails, phone numbers, and card numbers are redacted *before* anything reaches the LLM |
| 💬 **Follow-up Chat** | Keep asking questions with full context retained |
| 📄 **Export** | Download the full investigation as Markdown or PDF |

Two demo scenarios are bundled in:
1. **SaaS Checkout Failure** — a mobile payment bug tanking revenue
2. **Product Defect Refund Spike** — a supplier packaging change causing returns

---

## 🗂️ Project Structure

```
root-cause-ai/
├── app.py                      # Main Streamlit app
├── requirements.txt            # Runtime dependencies
├── requirements-dev.txt        # + pytest, for running tests
├── .env.example                # Copy to .env and add your Groq API key
├── utils/
│   ├── parsers.py              # CSV/XLSX/PDF/DOCX/TXT/LOG/image ingestion
│   ├── groq_client.py          # All LLM calls (extraction, reasoning, critic, translation...)
│   ├── timeline.py             # Merges evidence into a chronological timeline + charts
│   ├── impact_calculator.py    # Financial impact + severity scoring
│   ├── anomaly_detector.py     # Statistical anomaly detection (z-score, trailing baseline)
│   ├── correlation_engine.py   # Pearson correlation across uploaded metrics
│   ├── evidence_graph.py       # Evidence-to-cause network graph
│   ├── confidence_breakdown.py # Explains the confidence score
│   ├── pattern_matcher.py      # Similar-incident detection
│   ├── history.py              # Session investigation history log
│   ├── pii_redactor.py         # Regex-based PII scrubbing before LLM calls
│   ├── report.py                # Markdown / PDF report generation
│   └── ui_theme.py             # Custom dark theme + reusable UI components
├── sample_data/                # Scenario 1 demo files
│   └── scenario_2/             # Scenario 2 demo files
└── tests/                      # pytest suite (65 tests)
```

---

## 🚀 Setup

### 1. Clone / extract the project
```bash
cd root-cause-ai
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Add your Groq API key
```bash
cp .env.example .env
```
Edit `.env` and paste your key (get one free at [console.groq.com/keys](https://console.groq.com/keys)):
```
GROQ_API_KEY=your_actual_key_here
```

### 5. Run the app
```bash
streamlit run app.py
```
The app opens at `http://localhost:8501`. Click **"Load Sample Data"** in the sidebar for an instant demo — no files needed.

---

## 🧪 Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

65 tests cover parsing, impact calculation, anomaly detection, correlation math, PII redaction, pattern matching, history, confidence breakdown, timeline merging, and Groq client logic (mocked — no API key needed to run tests).

---

## 🧠 How It Works

```
Upload → Redact PII → Extract (Fast LLM) → Analyze (Reasoning LLM) → Critique (2nd LLM Pass) → Present
```

- **Extraction** uses `llama-3.1-8b-instant` — fast, cheap, per-file evidence extraction.
- **Reasoning, critique, and translation** use `llama-3.3-70b-versatile` — the heavier lifting.
- Tabular files (CSV/XLSX) are converted to facts **without an LLM call at all** — every row is already a fact, no need to ask a model to find what's already structured.
- Anomaly detection and correlation are pure statistics (numpy/pandas) — instant and free.

---

## ☁️ Deploying to Streamlit Community Cloud

1. Push this project to a GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → point it at your repo, with `app.py` as the entry point.
3. In **Settings → Secrets**, add:
   ```
   GROQ_API_KEY = "your_actual_key_here"
   ```
4. Deploy. No other configuration needed — `requirements.txt` handles the rest.

---

## ⚠️ Notes

- Screenshots/images don't use OCR (unreliable on cloud hosting) — the app asks you to paste the visible text instead, which is then treated like any other evidence.
- The What-If Simulator's confidence is hard-capped at 70% in code, and the Red-Team Critic's confidence can never exceed the original — both are enforced programmatically, not just by prompting the model to behave.
- PII redaction is regex-based and best-effort — a solid demonstration of the *practice*, not a compliance-grade guarantee.

---

## 📄 License

Built for hackathon submission purposes.
