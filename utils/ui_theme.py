"""
ui_theme.py
-----------
Custom look-and-feel for the app -- a dark, modern "investigation console"
theme instead of default Streamlit styling. Pure CSS injected via
st.markdown, plus small helper functions that render consistent styled
cards so app.py doesn't need to repeat HTML/CSS everywhere.

Uses a Google Fonts @import (Sora for headlines, Inter for body) -- this
is a browser-side CSS request from the end user's machine when the app is
deployed, not a backend dependency, so it stays Streamlit Cloud-safe with
zero new Python packages.
"""

import streamlit as st


PALETTE = {
    "bg": "#0a0b10",
    "bg_glow": "#141726",
    "panel": "#151822",
    "panel_alt": "#1b1f2c",
    "panel_border": "#2a2f40",
    "panel_border_light": "#363c50",
    "accent_red": "#ef4444",
    "accent_red_dark": "#b91c1c",
    "accent_amber": "#f59e0b",
    "accent_blue": "#3b82f6",
    "accent_green": "#22c55e",
    "text_primary": "#f1f2f6",
    "text_muted": "#8b93a7",
}


def inject_custom_css():
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }}

        /* Overall app background -- subtle radial glow, not flat black */
        .stApp {{
            background:
                radial-gradient(ellipse 900px 500px at 15% -10%, rgba(239,68,68,0.09), transparent 60%),
                radial-gradient(ellipse 700px 400px at 100% 0%, rgba(59,130,246,0.07), transparent 60%),
                {PALETTE['bg']};
        }}

        .block-container {{
            padding-top: 1.6rem;
            max-width: 1250px;
        }}

        /* ---------------- Sidebar ---------------- */
        section[data-testid="stSidebar"] {{
            background-color: {PALETTE['panel']};
            border-right: 1px solid {PALETTE['panel_border']};
        }}
        section[data-testid="stSidebar"] > div {{
            padding-top: 0.5rem;
        }}
        section[data-testid="stSidebar"] h1 {{
            font-family: 'Sora', sans-serif;
            font-size: 20px !important;
            -webkit-text-fill-color: {PALETTE['text_primary']} !important;
            background: none !important;
            font-weight: 700 !important;
            margin-bottom: 2px;
        }}
        section[data-testid="stSidebar"] hr {{
            border-color: {PALETTE['panel_border']};
            margin: 14px 0;
        }}
        section[data-testid="stSidebar"] label p {{
            font-weight: 600 !important;
            font-size: 13px !important;
            color: {PALETTE['text_primary']} !important;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }}

        /* File uploader dropzone */
        section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{
            background-color: {PALETTE['panel_alt']};
            border: 1.5px dashed {PALETTE['panel_border_light']};
            border-radius: 10px;
        }}

        /* ---------------- Headings ---------------- */
        h1, h2, h3 {{
            font-family: 'Sora', sans-serif;
            letter-spacing: -0.3px;
        }}

        h1 {{
            background: linear-gradient(100deg, {PALETTE['accent_red']} 10%, {PALETTE['accent_amber']} 90%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
        }}

        h3 {{
            font-weight: 700 !important;
        }}

        /* ---------------- Metric widgets ---------------- */
        div[data-testid="stMetric"] {{
            background: linear-gradient(160deg, {PALETTE['panel_alt']}, {PALETTE['panel']});
            border: 1px solid {PALETTE['panel_border']};
            border-radius: 12px;
            padding: 14px 18px;
        }}
        div[data-testid="stMetricLabel"] {{
            color: {PALETTE['text_muted']} !important;
            font-size: 12px !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* ---------------- Buttons ---------------- */
        .stButton > button, .stDownloadButton > button {{
            border-radius: 999px;
            border: 1px solid {PALETTE['panel_border_light']};
            font-weight: 600;
            padding: 0.5rem 1.1rem;
            transition: all 0.15s ease-in-out;
            background-color: {PALETTE['panel_alt']};
            color: {PALETTE['text_primary']};
        }}
        .stButton > button[kind="primary"] {{
            background: linear-gradient(100deg, {PALETTE['accent_red']}, {PALETTE['accent_red_dark']});
            border: none;
            box-shadow: 0 0 0 rgba(239,68,68,0);
        }}
        .stButton > button[kind="primary"]:hover {{
            box-shadow: 0 4px 22px rgba(239,68,68,0.45);
        }}
        .stButton > button:hover, .stDownloadButton > button:hover {{
            transform: translateY(-1px);
            border-color: {PALETTE['accent_red']};
        }}
        .stButton > button:disabled {{
            opacity: 0.4;
        }}

        /* ---------------- Expander ---------------- */
        div[data-testid="stExpander"] {{
            background-color: {PALETTE['panel']};
            border: 1px solid {PALETTE['panel_border']};
            border-radius: 12px;
        }}
        div[data-testid="stExpander"] summary {{
            font-weight: 600;
        }}

        /* ---------------- Chat messages ---------------- */
        div[data-testid="stChatMessage"] {{
            background-color: {PALETTE['panel']};
            border: 1px solid {PALETTE['panel_border']};
            border-radius: 12px;
        }}

        /* ---------------- Tables / dataframes ---------------- */
        div[data-testid="stDataFrame"] {{
            border: 1px solid {PALETTE['panel_border']};
            border-radius: 10px;
            overflow: hidden;
        }}

        hr {{ border-color: {PALETTE['panel_border']}; }}

        /* ---------------- Custom classes used by render_* helpers ---------------- */
        .rc-card {{
            background: linear-gradient(160deg, {PALETTE['panel_alt']}, {PALETTE['panel']});
            border: 1px solid {PALETTE['panel_border']};
            border-radius: 14px;
            padding: 20px 22px;
            margin-bottom: 14px;
        }}

        .rc-hero-wrap {{
            display: flex;
            align-items: center;
            gap: 18px;
            padding: 10px 0 6px 0;
        }}
        .rc-hero-icon {{
            font-size: 34px;
            width: 62px;
            height: 62px;
            min-width: 62px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 16px;
            background: linear-gradient(145deg, rgba(239,68,68,0.22), rgba(245,158,11,0.12));
            border: 1px solid rgba(239,68,68,0.35);
            box-shadow: 0 0 30px rgba(239,68,68,0.18);
        }}
        .rc-hero-title {{
            font-family: 'Sora', sans-serif;
            font-weight: 800;
            font-size: 34px;
            line-height: 1.1;
            background: linear-gradient(100deg, {PALETTE['accent_red']} 10%, {PALETTE['accent_amber']} 90%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0;
        }}
        .rc-hero-tagline {{
            color: {PALETTE['text_muted']};
            font-size: 15px;
            margin-top: 4px;
        }}
        .rc-pill-row {{
            display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap;
        }}
        .rc-pill {{
            font-size: 12px;
            font-weight: 600;
            padding: 4px 12px;
            border-radius: 999px;
            background-color: {PALETTE['panel_alt']};
            border: 1px solid {PALETTE['panel_border_light']};
            color: {PALETTE['text_muted']};
        }}

        .rc-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        .rc-badge-estimate {{
            background-color: rgba(245, 158, 11, 0.18);
            color: {PALETTE['accent_amber']};
            border: 1px solid {PALETTE['accent_amber']};
        }}
        .rc-badge-confirmed {{
            background-color: rgba(239, 68, 68, 0.18);
            color: {PALETTE['accent_red']};
            border: 1px solid {PALETTE['accent_red']};
        }}
        .rc-badge-severity-low {{ background-color: rgba(34,197,94,0.18); color:#22c55e; border:1px solid #22c55e; }}
        .rc-badge-severity-medium {{ background-color: rgba(245,158,11,0.18); color:#f59e0b; border:1px solid #f59e0b; }}
        .rc-badge-severity-high {{ background-color: rgba(249,115,22,0.18); color:#f97316; border:1px solid #f97316; }}
        .rc-badge-severity-critical {{ background-color: rgba(239,68,68,0.18); color:#ef4444; border:1px solid #ef4444; }}

        .rc-muted {{ color: {PALETTE['text_muted']}; font-size: 13px; }}

        /* ---------------- Empty-state onboarding ---------------- */
        .rc-step-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-top: 22px;
        }}
        .rc-step-card {{
            background: linear-gradient(160deg, {PALETTE['panel_alt']}, {PALETTE['panel']});
            border: 1px solid {PALETTE['panel_border']};
            border-radius: 14px;
            padding: 20px;
        }}
        .rc-step-num {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 28px; height: 28px;
            border-radius: 50%;
            background: linear-gradient(100deg, {PALETTE['accent_red']}, {PALETTE['accent_amber']});
            color: white;
            font-weight: 700;
            font-size: 13px;
            margin-bottom: 10px;
        }}
        .rc-step-title {{
            font-weight: 700;
            font-size: 15px;
            margin-bottom: 6px;
            color: {PALETTE['text_primary']};
        }}
        .rc-step-desc {{
            color: {PALETTE['text_muted']};
            font-size: 13px;
            line-height: 1.5;
        }}

        /* ---------------- Mobile responsiveness ---------------- */
        @media (max-width: 640px) {{
            .rc-hero-wrap {{ flex-direction: column; align-items: flex-start; gap: 10px; }}
            .rc-hero-title {{ font-size: 24px; }}
            .rc-hero-icon {{ width: 46px; height: 46px; min-width: 46px; font-size: 24px; }}
            .rc-step-grid {{ grid-template-columns: 1fr; }}
            .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
        }}
    </style>
    """, unsafe_allow_html=True)


def render_hero_header():
    st.markdown("""
    <div class="rc-hero-wrap">
        <div class="rc-hero-icon">🔎</div>
        <div>
            <div class="rc-hero-title">Root Cause AI Investigator</div>
            <div class="rc-hero-tagline">Upload messy evidence. Ask <i>why</i> something happened. Get a causal chain — not just a summary.</div>
            <div class="rc-pill-row">
                <span class="rc-pill">🧠 AI Reasoning</span>
                <span class="rc-pill">📊 Statistical Backing</span>
                <span class="rc-pill">🕵️ Adversarial Review</span>
                <span class="rc-pill">🔐 PII-Safe</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_empty_state():
    st.markdown("""
    <div class="rc-step-grid">
        <div class="rc-step-card">
            <div class="rc-step-num">1</div>
            <div class="rc-step-title">📂 Load your evidence</div>
            <div class="rc-step-desc">Upload CSVs, logs, PDFs, or customer complaints — or click <b>Load Sample Data</b> in the sidebar for an instant demo.</div>
        </div>
        <div class="rc-step-card">
            <div class="rc-step-num">2</div>
            <div class="rc-step-title">⚙️ Let it process</div>
            <div class="rc-step-desc">Evidence is PII-redacted, converted into a dated timeline, and scanned for anomalies and correlations automatically.</div>
        </div>
        <div class="rc-step-card">
            <div class="rc-step-num">3</div>
            <div class="rc-step-title">🕵️ Ask why</div>
            <div class="rc-step-desc">Type your question in the sidebar and hit <b>Investigate</b> to get a root cause, confidence score, and a red-team review.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_estimate_badge_html() -> str:
    return '<span class="rc-badge rc-badge-estimate">⚠ Estimate — not a confirmed fact</span>'


def render_confirmed_badge_html() -> str:
    return '<span class="rc-badge rc-badge-confirmed">✔ Evidence-backed</span>'


def severity_badge_html(label: str) -> str:
    css_class = {
        "Low": "rc-badge-severity-low",
        "Medium": "rc-badge-severity-medium",
        "High": "rc-badge-severity-high",
        "Critical": "rc-badge-severity-critical",
    }.get(label, "rc-badge-severity-medium")
    return f'<span class="rc-badge {css_class}">{label} severity</span>'


def render_card(content_html: str):
    st.markdown(f'<div class="rc-card">{content_html}</div>', unsafe_allow_html=True)