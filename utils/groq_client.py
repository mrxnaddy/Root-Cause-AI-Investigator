"""
groq_client.py
---------------
All LLM calls go through this file. Two models are used on purpose:
- MODEL_FAST   -> cheap/fast extraction tasks (per-file evidence extraction)
- MODEL_REASON -> the heavier root-cause reasoning + follow-up chat

Every call is wrapped with retry logic and strict JSON-safety parsing,
because LLMs occasionally wrap JSON in markdown fences or add stray text.
"""

import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

MODEL_FAST = "openai/gpt-oss-120b"
MODEL_REASON = "openai/gpt-oss-20b"

MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# Client + low-level call helpers
# ---------------------------------------------------------------------------

def get_client():
    from groq import Groq
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not found. Create a .env file (see .env.example) "
            "and set your key from https://console.groq.com/keys"
        )
    return Groq(api_key=api_key)


def _extract_json_block(raw_text: str):
    """
    LLMs sometimes wrap JSON in ```json ... ``` fences or add a short
    sentence before/after. This pulls out the first valid-looking
    JSON object or array and parses it.
    """
    if not raw_text:
        return None

    text = raw_text.strip()

    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: find the outermost {...} block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _call_groq(system_prompt: str, user_prompt: str, model: str,
               temperature: float = 0.2, force_json: bool = True):
    """
    Returns (parsed_json_or_none, raw_text_or_none, error_or_none).
    Retries up to MAX_RETRIES times on failure or malformed JSON.
    """
    client = get_client()
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            kwargs = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            if force_json:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
            raw_text = response.choices[0].message.content

            if not force_json:
                return None, raw_text, None

            parsed = _extract_json_block(raw_text)
            if parsed is not None:
                return parsed, raw_text, None

            last_error = "Model did not return valid JSON."

        except Exception as e:
            last_error = str(e)

    return None, None, last_error


# ---------------------------------------------------------------------------
# 1. Evidence extraction (per uploaded file)
# ---------------------------------------------------------------------------

EVENT_EXTRACTION_SYSTEM_PROMPT = """You are an evidence-extraction engine for a root-cause investigation tool.

You will be given raw content from ONE uploaded file (a log, complaint list, email, report, etc.).
Extract every distinct dated occurrence you can find and classify each as either:
- "FACT"  -> a directly stated data point or measurement (e.g. "conversion rate was 1.1%")
- "EVENT" -> something that happened at a point in time (e.g. "campaign v4 deployed", "customer reported error")

Respond ONLY with a JSON object in this exact shape, nothing else:
{
  "events": [
    {
      "date": "YYYY-MM-DD",
      "type": "FACT" or "EVENT",
      "description": "short plain-English description",
      "raw_snippet": "the exact line(s) from the source that support this"
    }
  ]
}

Rules:
- If no date is present for an item, skip it (do not guess dates).
- Keep descriptions short and factual, no speculation about causes here.
- If the file has no extractable dated events, return {"events": []}.
- Do not include markdown, explanations, or text outside the JSON object.
"""


def extract_evidence_events(text: str, source_filename: str, model: str = MODEL_FAST):
    """
    Runs one file's raw text through the LLM to pull out dated FACT/EVENT items.
    Returns (list_of_events, error_or_none). Each event dict gets 'source_file' attached.
    """
    if not text or not text.strip():
        return [], None

    # Guard against extremely long files blowing the context window
    trimmed_text = text[:12000]

    user_prompt = f"Source file: {source_filename}\n\nContent:\n{trimmed_text}"

    parsed, _, error = _call_groq(
        EVENT_EXTRACTION_SYSTEM_PROMPT, user_prompt, model=model, temperature=0.1
    )

    if error:
        return [], error

    events = parsed.get("events", []) if isinstance(parsed, dict) else []
    for e in events:
        e["source_file"] = source_filename

    return events, None


def events_from_dataframe(df, source_filename: str, date_column: str = None):
    """
    For tabular evidence (CSV/XLSX) we don't need the LLM at all --
    every row IS a fact. This keeps token usage down and is 100% accurate.
    Auto-detects a date-like column if not specified.
    """
    import pandas as pd

    if date_column is None:
        for col in df.columns:
            if "date" in col.lower():
                date_column = col
                break

    events = []
    if date_column is None:
        return events  # no date column found, can't build timeline facts from this file

    for _, row in df.iterrows():
        try:
            date_val = pd.to_datetime(row[date_column]).strftime("%Y-%m-%d")
        except Exception:
            continue

        other_cols = {c: row[c] for c in df.columns if c != date_column}
        description = ", ".join(f"{k}={v}" for k, v in other_cols.items())

        events.append({
            "date": date_val,
            "type": "FACT",
            "description": description,
            "raw_snippet": row.to_dict(),
            "source_file": source_filename,
        })

    return events


# ---------------------------------------------------------------------------
# 2. Root-cause reasoning
# ---------------------------------------------------------------------------

ROOT_CAUSE_SYSTEM_PROMPT = """You are a rigorous root-cause investigator. You are given a chronological
list of evidence items (FACTs and EVENTs) gathered from multiple source files, plus a user question
about why something happened.

Your job:
1. Classify relationships between evidence into: CORRELATION, POSSIBLE CAUSE, or CONFIRMED CAUSE.
   - CORRELATION: two things move together in time but the causal link is unproven.
   - POSSIBLE CAUSE: a correlation with a plausible mechanism and partial evidence.
   - CONFIRMED CAUSE: multiple independent evidence sources converge on the same explanation.
2. Identify the single most likely root cause, with a confidence percentage (0-100).
3. List 2-4 alternative explanations with their own confidence percentages.
4. Every claim must cite which source file(s) support it. Do not invent evidence that wasn't provided.
5. Confidence percentages across root cause + alternatives do not need to sum to 100 -- they are
   independent likelihood estimates, not a probability distribution.

Respond ONLY with a JSON object in this exact shape:
{
  "timeline": [
    {"date": "YYYY-MM-DD", "description": "...", "source_file": "...", "classification": "FACT|EVENT|CORRELATION|POSSIBLE CAUSE|CONFIRMED CAUSE"}
  ],
  "root_cause": {
    "description": "one or two sentence plain-English root cause",
    "confidence": 87,
    "supporting_evidence": ["short evidence bullet 1", "short evidence bullet 2"],
    "evidence_sources": ["filename1", "filename2"]
  },
  "alternative_causes": [
    {"description": "...", "confidence": 21, "evidence_sources": ["..."]}
  ],
  "reasoning_summary": "2-4 sentence explanation of how you reached this conclusion"
}

Do not include markdown, headers, or any text outside the JSON object.
"""


def analyze_root_cause(timeline_events: list, question: str, model: str = MODEL_REASON):
    """
    timeline_events: list of dicts with at least {date, type/classification, description, source_file}
    question: the user's natural-language question, e.g. "Why did sales fall Aug 12-18?"

    Returns (result_dict_or_none, error_or_none).
    """
    # Trim raw_snippet payloads (esp. dict rows) so we don't blow the context window
    slim_timeline = []
    for e in timeline_events:
        slim_timeline.append({
            "date": e.get("date"),
            "type": e.get("type", e.get("classification", "FACT")),
            "description": e.get("description"),
            "source_file": e.get("source_file"),
        })

    user_prompt = json.dumps({
        "user_question": question,
        "evidence_timeline": slim_timeline,
    }, indent=2)

    parsed, _, error = _call_groq(
        ROOT_CAUSE_SYSTEM_PROMPT, user_prompt, model=model, temperature=0.25
    )

    if error:
        return None, error

    return parsed, None


# ---------------------------------------------------------------------------
# 3. Follow-up chat (keeps timeline + prior turns as context)
# ---------------------------------------------------------------------------

FOLLOWUP_SYSTEM_PROMPT = """You are continuing a root-cause investigation conversation.
You already have the full evidence timeline and a prior root-cause analysis as context
(provided below). Answer the user's follow-up question directly and concisely, grounding
every claim in the evidence timeline you were given. If the evidence doesn't support an
answer, say so plainly instead of guessing. Plain text response, no JSON needed here.
"""


def followup_chat(conversation_history: list, timeline_events: list,
                   prior_analysis: dict, new_question: str, model: str = MODEL_FAST):
    """
    conversation_history: list of {"role": "user"/"assistant", "content": "..."} from earlier turns
    timeline_events: the same evidence timeline used in analyze_root_cause
    prior_analysis: the dict returned by analyze_root_cause (for context)
    new_question: the new follow-up question from the user

    Returns (answer_text_or_none, error_or_none).
    """
    client = get_client()

    context_blob = json.dumps({
        "evidence_timeline": timeline_events,
        "prior_root_cause_analysis": prior_analysis,
    }, indent=2, default=str)[:14000]  # guard context window

    messages = [
        {"role": "system", "content": FOLLOWUP_SYSTEM_PROMPT + "\n\nContext:\n" + context_blob}
    ]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": new_question})

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.4,
            )
            return response.choices[0].message.content, None
        except Exception as e:
            last_error = str(e)

    return None, last_error


# ---------------------------------------------------------------------------
# 4. What-If Scenario Simulator
# ---------------------------------------------------------------------------
#
# IMPORTANT DISTINCTION FROM THE ROOT-CAUSE ENGINE ABOVE:
# analyze_root_cause() explains what already happened, grounded in evidence
# that exists. This function speculates about a hypothetical the user is
# proposing ("what if I cut price 10%?") that has NOT happened yet and has
# no direct evidence in the uploaded files. Every output from this function
# must be treated and displayed as an ESTIMATE, never as a confirmed fact --
# the system prompt below enforces that, and the confidence ceiling is kept
# deliberately lower than what analyze_root_cause() would report for an
# evidence-backed conclusion.

SCENARIO_SIMULATOR_SYSTEM_PROMPT = """You are a cautious "what-if" scenario estimator inside a root-cause
investigation tool. The user will propose a hypothetical change (e.g. "what if I reduce price by 10%?",
"what if I roll back the checkout change?") that has NOT actually happened. You have the evidence
timeline and the prior root-cause analysis as context.

Your job is to give a REASONED ESTIMATE of the likely outcome, clearly grounded in patterns already
visible in the evidence -- not a guarantee, not a fact.

Strict rules:
- NEVER present this as a confirmed outcome. It is always a speculative projection.
- Base your reasoning only on patterns actually present in the evidence timeline and prior analysis.
  If the evidence doesn't support reasoning about this scenario at all, say so and keep confidence low.
- Cap your confidence at 70 -- these are inherently uncertain projections, never certainties.
- List the specific assumptions you had to make to produce this estimate.
- Be explicit about what evidence (if any) supports the direction of your estimate.

Respond ONLY with a JSON object in this exact shape:
{
  "scenario": "short restatement of the what-if scenario",
  "estimated_outcome": "1-2 sentence plain-English projection of what would likely happen",
  "estimated_confidence": 45,
  "supporting_patterns": ["pattern from evidence 1", "pattern from evidence 2"],
  "assumptions": ["assumption 1", "assumption 2"],
  "caveat": "one sentence reminding the user this is a speculative estimate, not a guarantee"
}

Do not include markdown or any text outside the JSON object.
"""


def simulate_scenario(timeline_events: list, prior_analysis: dict,
                       scenario_question: str, impact_data: dict = None,
                       model: str = MODEL_REASON) -> tuple:
    """
    timeline_events: the evidence timeline (same as used in analyze_root_cause)
    prior_analysis: the dict returned by analyze_root_cause, for context
    scenario_question: the user's hypothetical, e.g. "What if I reduce price by 10%?"
    impact_data: optional dict from impact_calculator.calculate_financial_impact(),
                 gives the simulator real numbers to reason from if available

    Returns (result_dict_or_none, error_or_none). result_dict is always labeled
    as an estimate -- the caller (app.py) is responsible for rendering it with
    a visible "ESTIMATE" badge, never alongside confirmed facts.
    """
    slim_timeline = []
    for e in timeline_events:
        slim_timeline.append({
            "date": e.get("date"),
            "type": e.get("type", e.get("classification", "FACT")),
            "description": e.get("description"),
            "source_file": e.get("source_file"),
        })

    payload = {
        "scenario_question": scenario_question,
        "evidence_timeline": slim_timeline,
        "prior_root_cause_analysis": prior_analysis,
    }
    if impact_data:
        payload["known_financial_impact"] = impact_data

    user_prompt = json.dumps(payload, indent=2, default=str)[:14000]

    parsed, _, error = _call_groq(
        SCENARIO_SIMULATOR_SYSTEM_PROMPT, user_prompt, model=model, temperature=0.3
    )

    if error:
        return None, error

    # Hard safety net: even if the model ignores the cap, enforce it in code.
    if isinstance(parsed, dict) and "estimated_confidence" in parsed:
        try:
            parsed["estimated_confidence"] = min(70, int(parsed["estimated_confidence"]))
        except (ValueError, TypeError):
            parsed["estimated_confidence"] = 0

    return parsed, None


# ---------------------------------------------------------------------------
# 5. Prevention Recommendations
# ---------------------------------------------------------------------------
#
# Runs AFTER analyze_root_cause() succeeds. Takes the confirmed root cause
# (plus alternatives, for context) and produces concrete, prioritized
# actions to prevent recurrence. Grounded in the same evidence -- this is
# not a scenario simulation, it's "given what we now know caused this,
# what should the team actually go do."

RECOMMENDATIONS_SYSTEM_PROMPT = """You are a pragmatic incident-response advisor. You are given a
confirmed root cause analysis (and possibly alternative causes) from a root-cause investigation.
Produce a short, prioritized list of concrete actions the team should take to prevent this from
happening again.

Rules:
- Every recommendation must directly address the root cause or a named alternative -- no generic
  "improve monitoring in general" filler unless the evidence specifically points to a monitoring gap.
- Assign a priority: "High" (directly prevents recurrence of the confirmed root cause),
  "Medium" (reduces risk or improves detection time), or "Low" (good practice, lower urgency).
- Assign a category: "Technical Fix", "Process Change", "Monitoring", or "Communication".
- Keep each recommendation to 1-2 sentences. Produce 3-6 recommendations total.
- Ground each recommendation in the evidence you were given -- reference what specifically failed.

Respond ONLY with a JSON object in this exact shape:
{
  "recommendations": [
    {
      "title": "short action title, a few words",
      "priority": "High",
      "category": "Technical Fix",
      "description": "1-2 sentences on what to do and why",
      "addresses": "which cause (root or alternative) this action addresses"
    }
  ]
}

Do not include markdown or any text outside the JSON object.
"""


def generate_recommendations(root_cause: dict, alternative_causes: list = None,
                              timeline_events: list = None, model: str = MODEL_REASON) -> tuple:
    """
    root_cause: the dict from analyze_root_cause()'s "root_cause" key
    alternative_causes: the list from analyze_root_cause()'s "alternative_causes" key
    timeline_events: optional -- a few key evidence items for extra grounding

    Returns (result_dict_or_none, error_or_none). result_dict has one key,
    "recommendations", a list of action dicts as described above.
    """
    slim_timeline = []
    if timeline_events:
        for e in timeline_events[:15]:  # keep the prompt small, root cause is already the focus
            slim_timeline.append({
                "date": e.get("date"),
                "description": e.get("description"),
                "source_file": e.get("source_file"),
            })

    payload = {
        "root_cause": root_cause,
        "alternative_causes": alternative_causes or [],
        "key_evidence": slim_timeline,
    }
    user_prompt = json.dumps(payload, indent=2, default=str)

    parsed, _, error = _call_groq(
        RECOMMENDATIONS_SYSTEM_PROMPT, user_prompt, model=model, temperature=0.3
    )

    if error:
        return None, error

    if not isinstance(parsed, dict) or "recommendations" not in parsed:
        return {"recommendations": []}, None

    return parsed, None


# ---------------------------------------------------------------------------
# 6. Executive Summary Generator
# ---------------------------------------------------------------------------
#
# analyze_root_cause()'s "reasoning_summary" is written for someone reading
# the full evidence timeline. This produces a SEPARATE, shorter summary in
# plain business language -- no filenames, no technical jargon -- meant to
# be dropped straight into a stakeholder email or slide.

EXECUTIVE_SUMMARY_SYSTEM_PROMPT = """You are writing a one-paragraph executive summary of an incident
investigation for a non-technical business stakeholder (e.g. a VP or founder who has 30 seconds).

Rules:
- 3-5 sentences total. No filenames, no technical jargon (no "502 errors", no "z-scores").
- Cover, in plain language: what happened, the business impact if given, what caused it, and what
  is being done about it.
- Confident and direct in tone, but do not overstate certainty beyond the confidence level given.
- If a financial impact figure is provided, mention it in plain terms (e.g. "an estimated $X in lost revenue").

Respond ONLY with a JSON object in this exact shape:
{
  "executive_summary": "the 3-5 sentence paragraph"
}

Do not include markdown or any text outside the JSON object.
"""


def generate_executive_summary(root_cause: dict, alternative_causes: list = None,
                                impact_data: dict = None, top_recommendation: dict = None,
                                model: str = MODEL_FAST) -> tuple:
    """
    Returns (summary_text_or_none, error_or_none) -- a single plain-language
    paragraph suitable for a stakeholder update, separate from the more
    technical reasoning_summary produced by analyze_root_cause().
    """
    payload = {
        "root_cause": root_cause,
        "alternative_causes": alternative_causes or [],
    }
    if impact_data and not impact_data.get("error"):
        payload["financial_impact"] = impact_data
    if top_recommendation:
        payload["top_recommendation"] = top_recommendation

    user_prompt = json.dumps(payload, indent=2, default=str)

    parsed, _, error = _call_groq(
        EXECUTIVE_SUMMARY_SYSTEM_PROMPT, user_prompt, model=model, temperature=0.3
    )

    if error:
        return None, error

    summary = parsed.get("executive_summary") if isinstance(parsed, dict) else None
    if not summary:
        return None, "Model did not return an executive summary."

    return summary, None


# ---------------------------------------------------------------------------
# 7. Bilingual Output (English <-> Urdu translation)
# ---------------------------------------------------------------------------
#
# Translates a batch of investigation text fields in ONE call (cheaper and
# more consistent than translating each field separately). The caller
# passes a dict of {field_name: english_text}; gets back the same keys
# with translated values.

TRANSLATION_SYSTEM_PROMPT = """You are a precise translator for a business incident-investigation report.
You will receive a JSON object where each key is a field name and each value is English text.
Translate every value into {target_language}, preserving the original meaning, tone, and any numbers
or percentages exactly as given. Keep proper nouns (file names, product names) unchanged.

Respond ONLY with a JSON object using the EXACT SAME KEYS as the input, with translated values.
Do not include markdown or any text outside the JSON object.
"""


def translate_investigation(content: dict, target_language: str = "Urdu",
                             model: str = MODEL_FAST) -> tuple:
    """
    content: dict of {field_name: english_text}, e.g.
             {"root_cause_description": "...", "reasoning_summary": "...", "executive_summary": "..."}
    target_language: display name of the target language, e.g. "Urdu"

    Returns (translated_dict_or_none, error_or_none) with the same keys as `content`.
    """
    if not content:
        return {}, None

    system_prompt = TRANSLATION_SYSTEM_PROMPT.format(target_language=target_language)
    user_prompt = json.dumps(content, indent=2, default=str)

    parsed, _, error = _call_groq(system_prompt, user_prompt, model=model, temperature=0.1)

    if error:
        return None, error

    if not isinstance(parsed, dict):
        return None, "Model did not return a valid translation object."

    # Safety net: if the model drops a key, fall back to the original English for it
    # rather than silently losing content from the UI.
    result = {}
    for key, original_value in content.items():
        result[key] = parsed.get(key, original_value)

    return result, None


# ---------------------------------------------------------------------------
# 8. Red-Team Critic Pass (adversarial self-review)
# ---------------------------------------------------------------------------
#
# Runs a SEPARATE LLM call, with a different persona (skeptical reviewer,
# not the original investigator), specifically instructed to look for
# holes in the root-cause conclusion rather than support it. This is a
# second, independent pass over the same evidence -- a lightweight form
# of multi-agent cross-checking that catches overconfident conclusions a
# single reasoning pass might not flag on its own.

CRITIC_SYSTEM_PROMPT = """You are a skeptical senior investigator conducting a red-team review of a
root-cause conclusion that ANOTHER analyst already reached. You did not write the original
conclusion -- your job is to find problems with it, not defend it.

Look specifically for:
- Correlation being treated as causation without enough independent corroboration
- Evidence that is weaker or more ambiguous than the original confidence suggests
- Plausible alternative explanations the original analysis did not seriously consider
- Which single piece of cited evidence, if it turned out to be wrong or missing, would most
  weaken the conclusion (a single point of failure in the argument)

Rules:
- Be genuinely critical. If the conclusion is well-supported, say so plainly -- don't invent
  weaknesses that aren't there. But do not rubber-stamp a weak conclusion either.
- Your adjusted_confidence must be LESS THAN OR EQUAL TO the original confidence. A red-team
  review can only maintain or lower confidence, never raise it -- you were not given new
  supporting evidence, only asked to stress-test what's already there.
- Ground every criticism in the evidence and analysis you were actually given.

Respond ONLY with a JSON object in this exact shape:
{
  "critique_summary": "2-3 sentence overall assessment of how well the conclusion holds up",
  "weaknesses": ["specific weakness 1", "specific weakness 2"],
  "most_critical_evidence": "the single piece of evidence this conclusion would be weakest without",
  "unconsidered_alternatives": ["an alternative explanation not seriously considered, if any"],
  "adjusted_confidence": 82,
  "verdict": "Holds up well" or "Holds up with caveats" or "Significant concerns"
}

Do not include markdown or any text outside the JSON object.
"""


def run_critic_review(root_cause: dict, alternative_causes: list = None,
                       timeline_events: list = None, model: str = MODEL_REASON) -> tuple:
    """
    root_cause / alternative_causes: from analyze_root_cause()'s output
    timeline_events: the evidence timeline, for grounding the critique

    Returns (result_dict_or_none, error_or_none). The returned
    adjusted_confidence is guaranteed (by code, not just prompt instruction)
    to never exceed the original root_cause confidence.
    """
    slim_timeline = []
    if timeline_events:
        for e in timeline_events[:20]:
            slim_timeline.append({
                "date": e.get("date"),
                "description": e.get("description"),
                "source_file": e.get("source_file"),
            })

    payload = {
        "original_root_cause": root_cause,
        "original_alternative_causes": alternative_causes or [],
        "evidence_timeline": slim_timeline,
    }
    user_prompt = json.dumps(payload, indent=2, default=str)

    parsed, _, error = _call_groq(
        CRITIC_SYSTEM_PROMPT, user_prompt, model=model, temperature=0.35
    )

    if error:
        return None, error

    if not isinstance(parsed, dict):
        return None, "Model did not return a valid critique object."

    # Hard safety net: never let the critic raise confidence above the original,
    # regardless of what the model returns.
    original_confidence = root_cause.get("confidence", 100)
    try:
        adjusted = int(parsed.get("adjusted_confidence", original_confidence))
    except (ValueError, TypeError):
        adjusted = original_confidence
    parsed["adjusted_confidence"] = min(adjusted, original_confidence)

    return parsed, None
