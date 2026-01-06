from __future__ import annotations
import json
from .schemas import Plan
from .llm_client import get_client
from .config import settings

PLANNER_SYSTEM = """You are a planning engine.
Return ONLY valid JSON for a Plan that matches this schema:
- question: string
- periods: list of {label,start_date,end_date}
- hypotheses: list of {id,title,metric,status}
- segments: list of segment columns
- execution_steps: list of {tool_name,args}

Constraints:
- tool_name must be one of: resolve_period, compute_kpis, funnel_breakdown, segment_impact, sanity_check_data
- execution_steps must be executable in order.
- No prose. JSON only.
"""

def rule_based_plan(question: str) -> Plan:
    # Phase 1: last week, core hypotheses
    return Plan.model_validate({
        "question": question,
        "periods": [
            {"label": "previous", "start_date": "AUTO", "end_date": "AUTO"},
            {"label": "current", "start_date": "AUTO", "end_date": "AUTO"},
        ],
        "hypotheses": [
            {"id": "H1", "title": "Traffic volume changed (sessions)", "metric": "sessions", "status": "untested"},
            {"id": "H2", "title": "Conversion efficiency changed (CVR)", "metric": "cvr", "status": "untested"},
            {"id": "H3", "title": "Funnel step drop (checkout or add_to_cart)", "metric": "funnel_rates", "status": "untested"},
            {"id": "H4", "title": "Mix shift by segment (device/channel/country)", "metric": "segment_impact", "status": "untested"},
        ],
        "segments": ["device", "channel", "country"],
        "execution_steps": [
            {"tool_name": "sanity_check_data", "args": {}},
            {"tool_name": "resolve_period", "args": {"question_text": question}},
            {"tool_name": "compute_kpis", "args": {}},
            {"tool_name": "funnel_breakdown", "args": {}},
            {"tool_name": "segment_impact", "args": {"segment_col": "device"}},
            {"tool_name": "segment_impact", "args": {"segment_col": "channel"}},
            {"tool_name": "segment_impact", "args": {"segment_col": "country"}},
        ]
    })

def plan_with_llm(question: str) -> Plan:
    client = get_client()
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": json.dumps({"question": question})},
        ],
        temperature=0,
    )
    text = resp.choices[0].message.content or ""
    data = json.loads(text)
    return Plan.model_validate(data)

def get_plan(question: str) -> Plan:
    # Try LLM once; fallback to rule plan
    try:
        return plan_with_llm(question)
    except Exception:
        return rule_based_plan(question)