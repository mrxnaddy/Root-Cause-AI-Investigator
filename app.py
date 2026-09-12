"""
app.py
------
Root Cause AI Investigator -- main Streamlit app. Full feature set:

Core loop:
1. Upload evidence (or load sample data) -> parsed -> PII-redacted -> events extracted
2. Proactive auto-analysis on load: anomaly detection + statistical correlations
   (pure math, no LLM, shown before the user even asks a question)
3. User asks "why did X happen?" -> Groq builds a classified causal timeline,
   root cause, alternatives, confidence
4. Confidence Breakdown explains the number; a Red-Team Critic pass
   independently stress-tests the conclusion (confidence can only go down)
5. Evidence-to-cause network graph, financial Impact Calculator + severity,
   prioritized Prevention Recommendations, an Executive Summary for
   stakeholders, and a What-If Scenario Simulator (always labeled ESTIMATE)
6. Similar-incident pattern matching against a session History Log
7. Optional Urdu translation of key outputs
8. Follow-up chat, and export to Markdown/PDF
"""

import os
from datetime import date
import streamlit as st
import pandas as pd

from utils import parsers
from utils import groq_client
from utils import timeline as tl
from utils import report
from utils import impact_calculator as impact_calc
from utils import evidence_graph as ev_graph
from utils import ui_theme
from utils import anomaly_detector
from utils import confidence_breakdown as conf_breakdown
from utils import pii_redactor
from utils import correlation_engine
from utils import pattern_matcher
from utils import history as history_log

SAMPLE_DATA_DIR = os.path.join(os.path.dirname(__file__), "sample_data")

st.set_page_config(
    page_title="Root Cause AI Investigator",
    page_icon="🔎",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def init_session_state():
    defaults = {
        "parsed_files": [],
        "evidence_events": [],
        "analysis_result": None,
        "conversation_history": [],
        "last_question": "",
        "extraction_errors": [],
        "impact_result": None,
        "recommendations_result": None,
        "scenario_history": [],
        "anomalies": [],
        "correlations": [],
        "redaction_summaries": [],
        "executive_summary": None,
        "critic_result": None,
        "similar_incidents": [],
        "history": [],
        "translated_cache": {},
        "show_urdu": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_investigation():
    """Clears analysis + every downstream feature, but keeps uploaded files and history."""
    st.session_state.analysis_result = None
    st.session_state.conversation_history = []
    st.session_state.last_question = ""
    st.session_state.impact_result = None
    st.session_state.recommendations_result = None
    st.session_state.scenario_history = []
    st.session_state.executive_summary = None
    st.session_state.critic_result = None
    st.session_state.similar_incidents = []
    st.session_state.translated_cache = {}


# ---------------------------------------------------------------------------
# Evidence building (PII redaction now runs before any text reaches the LLM)
# ---------------------------------------------------------------------------

def build_events_for_file(parsed: dict, pasted_text: str = None):
    """Returns (events, error, redaction_summary_or_none)."""
    if parsed.get("error"):
        return [], parsed["error"], None

    file_type = parsed["file_type"]
    filename = parsed["filename"]

    if file_type in ("csv", "xlsx") and parsed.get("dataframe") is not None:
        events = groq_client.events_from_dataframe(parsed["dataframe"], filename)
        return events, None, None

    text_source = parsed.get("text")
    if file_type == "image":
        text_source = pasted_text

    if not text_source or not text_source.strip():
        return [], None, None

    redaction = pii_redactor.redact_text(text_source)
    redacted_text = redaction["redacted_text"]
    redaction_summary = None
    if redaction["redaction_count"] > 0:
        redaction_summary = {
            "filename": filename,
            "count": redaction["redaction_count"],
            "types": redaction["redaction_types"],
        }

    events, error = groq_client.extract_evidence_events(redacted_text, filename)
    return events, error, redaction_summary


def scan_proactive_insights():
    """Runs anomaly detection + correlation scanning across all tabular files -- pure math, instant."""
    all_anomalies = []
    for parsed in st.session_state.parsed_files:
        df = parsed.get("dataframe")
        if df is not None:
            all_anomalies.extend(anomaly_detector.scan_dataframe_for_anomalies(df, parsed["filename"]))
    st.session_state.anomalies = all_anomalies

    st.session_state.correlations = correlation_engine.scan_correlations(
        st.session_state.parsed_files, min_abs_r=0.5
    )


def process_all_files(pasted_texts: dict):
    all_event_lists = []
    errors = []
    redaction_summaries = []

    progress = st.progress(0.0, text="Extracting evidence...")
    total = max(len(st.session_state.parsed_files), 1)

    for i, parsed in enumerate(st.session_state.parsed_files):
        pasted = pasted_texts.get(parsed["filename"])
        events, error, redaction_summary = build_events_for_file(parsed, pasted_text=pasted)
        if error:
            errors.append(f"{parsed['filename']}: {error}")
        if redaction_summary:
            redaction_summaries.append(redaction_summary)
        all_event_lists.append(events)
        progress.progress((i + 1) / total, text=f"Processed {parsed['filename']}")

    progress.empty()

    st.session_state.evidence_events = tl.merge_events(all_event_lists)
    st.session_state.extraction_errors = errors
    st.session_state.redaction_summaries = redaction_summaries

    scan_proactive_insights()


def load_sample_data(scenario: int = 1):
    if scenario == 2:
        folder = os.path.join(SAMPLE_DATA_DIR, "scenario_2")
        sample_files = ["orders.csv", "quality_complaints.txt", "supplier_log.txt", "shipping_log.txt"]
    else:
        folder = SAMPLE_DATA_DIR
        sample_files = ["sales.csv", "ad_spend.csv", "ga_export.csv", "complaints.txt", "error_logs.txt"]

    parsed_list = []
    for fname in sample_files:
        path = os.path.join(folder, fname)
        with open(path, "rb") as f:
            parsed_list.append(parsers.parse_file(f))

    st.session_state.parsed_files = parsed_list
    reset_investigation()
    process_all_files(pasted_texts={})


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _files_signature(uploaded_files) -> tuple:
    """A cheap fingerprint of the current upload set, so we only re-parse/re-process
    when the actual files change -- not on every Streamlit rerun (e.g. every time
    the user types a character in the question box)."""
    return tuple((f.name, f.size) for f in uploaded_files)


def render_sidebar():
    st.sidebar.title("🔎 Root Cause AI")
    st.sidebar.caption("Upload messy evidence. Ask why something happened. Get a causal answer, not a summary.")

    scenario_choice = st.sidebar.selectbox(
        "Demo scenario",
        options=["Scenario 1: SaaS Checkout Failure", "Scenario 2: Product Defect Refund Spike"],
        key="scenario_select",
    )
    if st.sidebar.button("📂 Load Sample Data (demo)", use_container_width=True):
        with st.spinner("Loading and processing sample evidence..."):
            if scenario_choice.startswith("Scenario 2"):
                load_sample_data(scenario=2)
            else:
                load_sample_data(scenario=1)
        st.sidebar.success("Sample data loaded!")

    st.sidebar.divider()

    uploaded_files = st.sidebar.file_uploader(
        "Upload evidence files",
        type=["csv", "xlsx", "xls", "pdf", "docx", "txt", "log", "eml", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    pasted_texts = {}

    if uploaded_files:
        signature = _files_signature(uploaded_files)

        # Only re-parse + auto-process when the upload set actually changed --
        # this is what fixes "Investigate stays disabled" caused by the old
        # code re-running (and silently no-op'ing) on every keystroke rerun.
        if st.session_state.get("last_uploaded_signature") != signature:
            st.session_state.last_uploaded_signature = signature
            newly_parsed = parsers.parse_many(uploaded_files)
            st.session_state.parsed_files = newly_parsed
            reset_investigation()

            image_files = [p for p in newly_parsed if p["file_type"] == "image"]
            if not image_files:
                # No screenshots needing pasted text -- process immediately,
                # no extra click required.
                with st.spinner("Extracting evidence with AI..."):
                    process_all_files({})
                st.sidebar.success(f"Processed {len(newly_parsed)} file(s) automatically.")

        # Screenshots always need the user's pasted text first, so that part
        # of the flow stays manual regardless of whether this is a fresh
        # upload or a rerun.
        current_parsed = st.session_state.parsed_files
        image_files = [p for p in current_parsed if p["file_type"] == "image"]
        if image_files:
            st.sidebar.info("For screenshots, paste the visible text below so it can be used as evidence:")
            for img in image_files:
                pasted_texts[img["filename"]] = st.sidebar.text_area(
                    f"Text from {img['filename']}", key=f"paste_{img['filename']}"
                )
            if st.sidebar.button("⚙️ Process Uploaded Files", use_container_width=True):
                with st.spinner("Extracting evidence with AI..."):
                    process_all_files(pasted_texts)
                st.sidebar.success(f"Processed {len(current_parsed)} file(s).")

    st.sidebar.divider()

# Check karein ke evidence events hon YA files upload hui hon
    has_data = bool(st.session_state.get("evidence_events")) or bool(
        st.session_state.get("parsed_files")
    )

    question = st.sidebar.text_area(
        "Ask: why did this happen?",
        placeholder="e.g. Why did sales fall between Aug 12-18?",
        key="question_input",
    )

    investigate_clicked = st.sidebar.button(
        "🕵️ Investigate",
        type="primary",
        use_container_width=True,
        disabled=not has_data,
    )

    if not has_data:
        st.sidebar.markdown(
            '<div style="background:rgba(245,158,11,0.12); border:1px solid #f59e0b; '
            'border-radius:8px; padding:8px 12px; font-size:13px; color:#f59e0b;">'
            "⚠ No evidence loaded yet. Click <b>Load Sample Data</b> or upload files above "
            "-- the Investigate button unlocks automatically once evidence is ready.</div>",
            unsafe_allow_html=True,
        )

    # Function ka return statement - Indentation match hona zaroori hai
    return question, investigate_clicked

    st.sidebar.divider()
    st.session_state.show_urdu = st.sidebar.checkbox("🌐 Show Urdu translation", value=st.session_state.show_urdu)

    render_history_picker()

    return question, investigate_clicked


def render_history_picker():
    if not st.session_state.history:
        return
    with st.sidebar.expander(f"🗂️ Past Investigations ({len(st.session_state.history)})", expanded=False):
        labels = [history_log.format_history_label(e) for e in st.session_state.history]
        selected_idx = st.selectbox(
            "Reload a past investigation", options=list(range(len(labels))),
            format_func=lambda i: labels[i], key="history_select",
        )
        if st.button("Load selected investigation", key="load_history_btn", use_container_width=True):
            entry = history_log.get_entry(st.session_state.history, selected_idx)
            if entry:
                st.session_state.analysis_result = entry["full_result"]
                st.session_state.last_question = entry["question"]
                st.session_state.recommendations_result = None
                st.session_state.executive_summary = None
                st.session_state.critic_result = None
                st.session_state.scenario_history = []
                st.session_state.translated_cache = {}
                st.success(f"Loaded: {entry['question']}")


def render_investigation_comparison():
    """Compares two past investigations side by side -- root cause, confidence,
    and a deterministic text-similarity score reusing the pattern matcher."""
    if len(st.session_state.history) < 2:
        return

    st.subheader("📊 Compare Investigations")
    st.caption("See how two past investigations relate -- useful for spotting recurring issues.")

    labels = [history_log.format_history_label(e) for e in st.session_state.history]
    col1, col2 = st.columns(2)
    with col1:
        idx_a = st.selectbox("Investigation A", options=list(range(len(labels))),
                              format_func=lambda i: labels[i], key="compare_a_select")
    with col2:
        default_b = min(1, len(labels) - 1)
        idx_b = st.selectbox("Investigation B", options=list(range(len(labels))),
                              format_func=lambda i: labels[i], index=default_b, key="compare_b_select")

    entry_a = history_log.get_entry(st.session_state.history, idx_a)
    entry_b = history_log.get_entry(st.session_state.history, idx_b)
    if not entry_a or not entry_b:
        return

    root_a = (entry_a.get("full_result") or {}).get("root_cause", {})
    root_b = (entry_b.get("full_result") or {}).get("root_cause", {})

    colA, colB = st.columns(2)
    with colA:
        st.markdown(f"**{entry_a['timestamp']}**")
        st.caption(entry_a["question"])
        st.write(root_a.get("description", "N/A"))
        st.metric("Confidence", f"{root_a.get('confidence', 0)}%")
        if root_a.get("evidence_sources"):
            st.caption(f"Sources: {', '.join(root_a['evidence_sources'])}")
    with colB:
        st.markdown(f"**{entry_b['timestamp']}**")
        st.caption(entry_b["question"])
        st.write(root_b.get("description", "N/A"))
        st.metric("Confidence", f"{root_b.get('confidence', 0)}%")
        if root_b.get("evidence_sources"):
            st.caption(f"Sources: {', '.join(root_b['evidence_sources'])}")

    if idx_a != idx_b:
        similarity = pattern_matcher.jaccard_similarity(
            pattern_matcher._tokenize(root_a.get("description", "")),
            pattern_matcher._tokenize(root_b.get("description", "")),
        )
        st.info(f"Text similarity between these two root causes: **{round(similarity * 100)}%**")


# ---------------------------------------------------------------------------
# File previews + proactive insights (anomalies + correlations, before analysis)
# ---------------------------------------------------------------------------

def render_file_previews():
    if not st.session_state.parsed_files:
        return
    with st.expander(f"📁 {len(st.session_state.parsed_files)} evidence file(s) loaded", expanded=False):
        for parsed in st.session_state.parsed_files:
            st.markdown(f"**{parsed['filename']}** — `{parsed['file_type']}`")
            if parsed.get("error"):
                st.error(parsed["error"])
            elif parsed.get("dataframe") is not None:
                st.dataframe(parsed["dataframe"].head(5), use_container_width=True)
            else:
                st.text(parsed.get("preview", ""))
            st.divider()

    if st.session_state.extraction_errors:
        with st.expander("⚠️ Extraction warnings", expanded=False):
            for err in st.session_state.extraction_errors:
                st.warning(err)

    if st.session_state.redaction_summaries:
        with st.expander("🔐 Privacy: PII redacted before sending to AI", expanded=False):
            st.info(pii_redactor.format_redaction_summary(st.session_state.redaction_summaries))


def render_proactive_insights():
    if not st.session_state.evidence_events:
        return

    st.subheader("Raw Evidence Timeline")
    st.caption(f"{len(st.session_state.evidence_events)} dated evidence items extracted so far, before causal analysis.")
    fig = tl.build_timeline_figure(st.session_state.evidence_events, title="Evidence collected")
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.session_state.anomalies:
            st.markdown("**📈 Auto-detected anomalies** *(statistical, before you even ask a question)*")
            for a in st.session_state.anomalies[:6]:
                st.markdown(f"- {anomaly_detector.format_anomaly_summary(a)}")

    with col2:
        if st.session_state.correlations:
            st.markdown("**🔗 Strong statistical correlations found**")
            for c in st.session_state.correlations[:6]:
                st.markdown(f"- {correlation_engine.format_correlation_summary(c)}")


# ---------------------------------------------------------------------------
# Root cause + confidence breakdown + critic + graph
# ---------------------------------------------------------------------------

def _display_text(key: str, fallback: str) -> str:
    """Returns the Urdu translation if the toggle is on and available, else the English fallback."""
    if st.session_state.show_urdu and key in st.session_state.translated_cache:
        return st.session_state.translated_cache[key]
    return fallback


def ensure_translation_current(texts_needed: dict):
    """If Urdu is toggled on and any needed field isn't cached yet, translate the whole batch."""
    if not st.session_state.show_urdu:
        return
    missing = [k for k in texts_needed if k not in st.session_state.translated_cache]
    if not missing:
        return
    with st.spinner("Translating to Urdu..."):
        translated, error = groq_client.translate_investigation(texts_needed, target_language="Urdu")
    if error:
        st.warning(f"Urdu translation unavailable: {error}")
        return
    st.session_state.translated_cache.update(translated)


def render_analysis_results():
    result = st.session_state.analysis_result
    if not result:
        return

    root_cause = result.get("root_cause", {})
    alternatives = result.get("alternative_causes", [])
    classified_timeline = result.get("timeline", st.session_state.evidence_events)
    reasoning_summary = result.get("reasoning_summary", "")

    texts_needed = {
        "root_cause_description": root_cause.get("description", ""),
        "reasoning_summary": reasoning_summary,
    }
    if st.session_state.executive_summary:
        texts_needed["executive_summary"] = st.session_state.executive_summary
    ensure_translation_current(texts_needed)

    st.subheader("🎯 Likely Root Cause")
    st.markdown(ui_theme.render_confirmed_badge_html(), unsafe_allow_html=True)

    render_kpi_strip(root_cause)

    conf = root_cause.get("confidence", 0)
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### {_display_text('root_cause_description', root_cause.get('description', 'N/A'))}")
        if reasoning_summary:
            st.write(_display_text("reasoning_summary", reasoning_summary))
    with col2:
        st.metric("Confidence", f"{conf}%")

    evidence = root_cause.get("supporting_evidence", [])
    sources = root_cause.get("evidence_sources", [])
    if evidence:
        st.markdown("**Evidence:**")
        for item in evidence:
            st.markdown(f"✅ {item}")
    if sources:
        st.caption(f"Sources: {', '.join(sources)}")

    st.divider()
    render_confidence_breakdown(root_cause, alternatives)

    if st.session_state.similar_incidents:
        st.divider()
        render_similar_incidents()

    st.divider()
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("📊 Causal Timeline")
        fig = tl.build_timeline_figure(classified_timeline, title="Classified Evidence Timeline")
        st.plotly_chart(fig, use_container_width=True)
    with col_right:
        st.subheader("⚖️ Alternative Explanations")
        conf_fig = tl.build_confidence_chart(root_cause, alternatives)
        st.plotly_chart(conf_fig, use_container_width=True)

    st.divider()
    st.subheader("🕸️ Evidence → Cause Network")
    st.caption("Which files actually back which explanation -- more connections means stronger support.")
    graph_fig = ev_graph.build_evidence_graph(root_cause, alternatives)
    st.plotly_chart(graph_fig, use_container_width=True)

    st.divider()
    render_critic_review(result)

    st.divider()
    render_impact_calculator()

    st.divider()
    render_recommendations(result)

    st.divider()
    render_executive_summary(result)

    st.divider()
    render_scenario_simulator(result)

    st.divider()
    render_download_buttons(result)

    st.divider()
    render_followup_chat(result)


def render_kpi_strip(root_cause: dict):
    """Top-level at-a-glance dashboard row -- Confidence, Severity, $ Impact, Days Affected.
    Severity/Impact/Days show a placeholder until the Impact Calculator below has been run once."""
    impact = st.session_state.impact_result
    confidence = root_cause.get("confidence", 0)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Confidence", f"{confidence}%")

    if impact and not impact.get("error"):
        severity = impact_calc.calculate_severity_score(
            impact["pct_change"], impact["days_affected"], confidence=confidence
        )
        col2.metric("Severity", severity["label"])
        col3.metric("Est. Impact", f"{impact['total_impact']:,.0f}")
        col4.metric("Days Affected", impact["days_affected"])
    else:
        col2.metric("Severity", "—")
        col3.metric("Est. Impact", "—", help="Run the Impact Calculator below to populate this")
        col4.metric("Days Affected", "—")


def render_confidence_breakdown(root_cause: dict, alternatives: list):
    st.subheader("🧠 What's Behind This Confidence Score?")
    breakdown = conf_breakdown.calculate_confidence_breakdown(root_cause, alternatives)
    for f in breakdown["factors"]:
        score_display = f"{f['score']}%" if f["score"] is not None else "N/A"
        st.markdown(f"**{f['label']}: {score_display}** — {f['explanation']}")


def render_similar_incidents():
    st.subheader("🔗 Similar Past Incidents")
    st.caption("Detected via text and evidence overlap with your investigation history -- no AI guessing.")
    for match in st.session_state.similar_incidents:
        st.markdown(f"- {pattern_matcher.format_similarity_summary(match)}")


def render_critic_review(result: dict):
    st.subheader("🕵️ Red-Team Critic Review")
    st.caption("An independent, adversarial second pass that stress-tests the conclusion above. Confidence can only go down from here, never up.")

    if st.button("Run Red-Team Review", key="critic_btn"):
        with st.spinner("Challenging the conclusion..."):
            critic_result, error = groq_client.run_critic_review(
                result.get("root_cause", {}),
                result.get("alternative_causes", []),
                result.get("timeline", st.session_state.evidence_events),
            )
        if error:
            st.error(f"Critic review failed: {error}")
        else:
            st.session_state.critic_result = critic_result

    critic = st.session_state.critic_result
    if critic:
        original_conf = result.get("root_cause", {}).get("confidence", 0)
        adjusted_conf = critic.get("adjusted_confidence", original_conf)

        col1, col2, col3 = st.columns(3)
        col1.metric("Original confidence", f"{original_conf}%")
        col2.metric("Post-critique confidence", f"{adjusted_conf}%", f"{adjusted_conf - original_conf}%")
        col3.markdown(f"**Verdict:** {critic.get('verdict', 'N/A')}")

        st.write(critic.get("critique_summary", ""))

        weaknesses = critic.get("weaknesses", [])
        if weaknesses:
            st.markdown("**Weaknesses identified:**")
            for w in weaknesses:
                st.markdown(f"- {w}")

        if critic.get("most_critical_evidence"):
            st.markdown(f"**Single point of failure in the argument:** {critic['most_critical_evidence']}")

        unconsidered = critic.get("unconsidered_alternatives", [])
        if unconsidered:
            st.markdown("**Alternatives not seriously considered:**")
            for u in unconsidered:
                st.markdown(f"- {u}")


# ---------------------------------------------------------------------------
# Impact Calculator (unchanged from earlier phase)
# ---------------------------------------------------------------------------

def render_impact_calculator():
    tabular_files = [p for p in st.session_state.parsed_files if p.get("dataframe") is not None]
    if not tabular_files:
        return

    st.subheader("💰 Impact Calculator")
    st.caption("Quantify the cost of the incident using your own uploaded numbers -- pure math, not a guess.")

    file_options = [p["filename"] for p in tabular_files]
    selected_file = st.selectbox("Data file", file_options, key="impact_file_select")
    selected_parsed = next(p for p in tabular_files if p["filename"] == selected_file)
    df = selected_parsed["dataframe"]

    numeric_cols = impact_calc.find_numeric_columns(df)
    if not numeric_cols:
        st.info("No numeric columns found in this file to measure impact on.")
        return

    metric_col = st.selectbox("Metric to measure (e.g. revenue)", numeric_cols, key="impact_metric_select")

    all_dates = [pd.to_datetime(e["date"]) for e in st.session_state.evidence_events if e.get("date")]
    default_start = min(all_dates).date() if all_dates else date.today()
    default_end = max(all_dates).date() if all_dates else date.today()

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        incident_start = st.date_input("Incident start", value=default_start, key="impact_start")
    with col2:
        incident_end = st.date_input("Incident end", value=default_end, key="impact_end")
    with col3:
        st.write("")
        st.write("")
        calc_clicked = st.button("Calculate Impact", key="calc_impact_btn", use_container_width=True)

    if calc_clicked:
        impact = impact_calc.calculate_financial_impact(
            df, metric_col, str(incident_start), str(incident_end)
        )
        st.session_state.impact_result = impact

    impact = st.session_state.impact_result
    if impact:
        if impact.get("error"):
            st.warning(impact["error"])
        else:
            colA, colB, colC = st.columns(3)
            colA.metric("Baseline avg", f"{impact['baseline_avg']:,.2f}")
            colB.metric("Incident avg", f"{impact['incident_avg']:,.2f}", f"{impact['pct_change']}%")
            colC.metric("Estimated total impact", f"{impact['total_impact']:,.2f}")

            confidence = 0
            if st.session_state.analysis_result:
                confidence = st.session_state.analysis_result.get("root_cause", {}).get("confidence", 0)
            severity = impact_calc.calculate_severity_score(
                impact["pct_change"], impact["days_affected"], confidence=confidence
            )
            st.markdown(ui_theme.severity_badge_html(severity["label"]) +
                        f"&nbsp;&nbsp;<span class='rc-muted'>Severity score: {severity['score']}/100</span>",
                        unsafe_allow_html=True)
            st.caption(impact_calc.format_impact_summary(impact))


# ---------------------------------------------------------------------------
# Recommendations (unchanged from earlier phase)
# ---------------------------------------------------------------------------

def render_recommendations(result: dict):
    st.subheader("🛠️ Prevention Recommendations")
    st.caption("Concrete, prioritized actions to stop this from happening again.")

    if st.button("Generate Recommendations", key="gen_reco_btn"):
        with st.spinner("Thinking through prevention steps..."):
            reco_result, error = groq_client.generate_recommendations(
                result.get("root_cause", {}),
                result.get("alternative_causes", []),
                result.get("timeline", st.session_state.evidence_events),
            )
        if error:
            st.error(f"Could not generate recommendations: {error}")
        else:
            st.session_state.recommendations_result = reco_result

    reco = st.session_state.recommendations_result
    if reco and reco.get("recommendations"):
        priority_order = {"High": 0, "Medium": 1, "Low": 2}
        priority_emoji = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
        sorted_recs = sorted(
            reco["recommendations"],
            key=lambda r: priority_order.get(r.get("priority", "Low"), 3),
        )
        for r in sorted_recs:
            emoji = priority_emoji.get(r.get("priority"), "⚪")
            st.markdown(f"{emoji} **{r.get('title', '')}** — *{r.get('category', '')}*")
            st.write(r.get("description", ""))
            st.caption(f"Addresses: {r.get('addresses', 'N/A')}")
            st.write("")


# ---------------------------------------------------------------------------
# Executive Summary
# ---------------------------------------------------------------------------

def render_executive_summary(result: dict):
    st.subheader("🧾 Executive Summary")
    st.caption("A short, non-technical summary for stakeholders -- separate from the technical reasoning above.")

    if st.button("Generate Executive Summary", key="gen_exec_summary_btn"):
        top_recommendation = None
        if st.session_state.recommendations_result and st.session_state.recommendations_result.get("recommendations"):
            top_recommendation = st.session_state.recommendations_result["recommendations"][0]

        with st.spinner("Writing summary..."):
            summary, error = groq_client.generate_executive_summary(
                result.get("root_cause", {}),
                result.get("alternative_causes", []),
                st.session_state.impact_result,
                top_recommendation,
            )
        if error:
            st.error(f"Could not generate executive summary: {error}")
        else:
            st.session_state.executive_summary = summary
            st.session_state.translated_cache.pop("executive_summary", None)

    if st.session_state.executive_summary:
        st.info(_display_text("executive_summary", st.session_state.executive_summary))


# ---------------------------------------------------------------------------
# What-If Scenario Simulator (unchanged from earlier phase)
# ---------------------------------------------------------------------------

def render_scenario_simulator(result: dict):
    st.subheader("🔮 What-If Scenario Simulator")
    st.caption("Ask a hypothetical (e.g. \"What if I reduce price by 10%?\"). Answers are ESTIMATES, not facts.")

    scenario_question = st.text_input(
        "Your what-if question", placeholder="What if I fix the mobile checkout bug tomorrow?",
        key="scenario_input",
    )
    simulate_clicked = st.button("Simulate", key="simulate_btn")

    if simulate_clicked and scenario_question and scenario_question.strip():
        impact_data = st.session_state.impact_result
        if impact_data and impact_data.get("error"):
            impact_data = None
        with st.spinner("Estimating likely outcome..."):
            sim_result, error = groq_client.simulate_scenario(
                result.get("timeline", st.session_state.evidence_events),
                result,
                scenario_question,
                impact_data=impact_data,
            )
        if error:
            st.error(f"Could not simulate scenario: {error}")
        else:
            st.session_state.scenario_history.append({
                "question": scenario_question,
                "result": sim_result,
            })

    for entry in reversed(st.session_state.scenario_history[-3:]):
        sim = entry["result"]
        st.markdown(ui_theme.render_estimate_badge_html(), unsafe_allow_html=True)
        st.markdown(f"**Q: {entry['question']}**")
        st.write(sim.get("estimated_outcome", ""))

        confidence = sim.get("estimated_confidence", 0)
        st.progress(min(max(confidence, 0), 100) / 100)
        st.caption(f"Estimated confidence: {confidence}% (capped -- this is speculative, not a fact)")

        with st.expander("Assumptions & supporting patterns"):
            patterns = sim.get("supporting_patterns", [])
            if patterns:
                st.markdown("**Supporting patterns from evidence:**")
                for p in patterns:
                    st.markdown(f"- {p}")
            assumptions = sim.get("assumptions", [])
            if assumptions:
                st.markdown("**Assumptions made:**")
                for a in assumptions:
                    st.markdown(f"- {a}")
            if sim.get("caveat"):
                st.info(sim["caveat"])
        st.write("")


# ---------------------------------------------------------------------------
# Download + follow-up chat (unchanged)
# ---------------------------------------------------------------------------

def render_download_buttons(result: dict):
    st.subheader("📄 Export Report")

    question = st.session_state.last_question
    timeline_events = result.get("timeline", st.session_state.evidence_events)
    root_cause = result.get("root_cause", {})
    alternatives = result.get("alternative_causes", [])
    reasoning_summary = result.get("reasoning_summary", "")

    col1, col2 = st.columns(2)

    with col1:
        md_report = report.generate_markdown_report(
            question, timeline_events, root_cause, alternatives, reasoning_summary
        )
        st.download_button(
            "⬇️ Download Markdown Report",
            data=md_report,
            file_name="root_cause_report.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with col2:
        try:
            pdf_bytes = report.generate_pdf_report(
                question, timeline_events, root_cause, alternatives, reasoning_summary
            )
            st.download_button(
                "⬇️ Download PDF Report",
                data=pdf_bytes,
                file_name="root_cause_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"PDF export unavailable: {e}")


def render_followup_chat(result: dict):
    st.subheader("💬 Follow-up Questions")

    for turn in st.session_state.conversation_history:
        with st.chat_message(turn["role"]):
            st.write(turn["content"])

    followup = st.chat_input("Ask a follow-up about this investigation...")
    if followup:
        st.session_state.conversation_history.append({"role": "user", "content": followup})
        with st.chat_message("user"):
            st.write(followup)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer, error = groq_client.followup_chat(
                    st.session_state.conversation_history[:-1],
                    result.get("timeline", st.session_state.evidence_events),
                    result,
                    followup,
                )
            if error:
                st.error(f"Could not get a response: {error}")
            else:
                st.write(answer)
                st.session_state.conversation_history.append({"role": "assistant", "content": answer})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    init_session_state()
    ui_theme.inject_custom_css()
    ui_theme.render_hero_header()

    question, investigate_clicked = render_sidebar()

    if not st.session_state.parsed_files:
        ui_theme.render_empty_state()

    render_file_previews()
    render_proactive_insights()

    if investigate_clicked:
        if not question or not question.strip():
            st.warning("Please type a question in the sidebar first, e.g. 'Why did sales fall between Aug 12-18?'")
        else:
            st.session_state.last_question = question
            reset_investigation()
            st.session_state.last_question = question  # reset_investigation clears it, so set again

            with st.spinner("Analyzing evidence and reasoning about root cause..."):
                result, error = groq_client.analyze_root_cause(
                    st.session_state.evidence_events, question
                )
            if error:
                st.error(f"Analysis failed: {error}")
            else:
                st.session_state.analysis_result = result

                # Pattern-match against PRIOR history before adding this one in
                matches = pattern_matcher.find_similar_incidents(
                    result.get("root_cause", {}), st.session_state.history, threshold=0.15
                )
                st.session_state.similar_incidents = matches

                entry = history_log.create_history_entry(
                    question, result, len(st.session_state.evidence_events)
                )
                st.session_state.history = history_log.add_to_history(st.session_state.history, entry)

    st.divider()
    render_analysis_results()

    if st.session_state.history:
        st.divider()
        render_investigation_comparison()


if __name__ == "__main__":
    main()