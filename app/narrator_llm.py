from __future__ import annotations
import json
from .llm_client import get_client
from .config import settings
from .schemas import FinalResult

NARRATOR_SYSTEM = """You are an analytics narrator writing an executive summary for business stakeholders.

Hard rules:
- Use ONLY the provided evidence (numbers, deltas, segment tables).
- Do NOT invent numbers or causes.
- If evidence is missing, state that explicitly.

Output format (strict):
- Do NOT include any title or heading line.

Sections (use bullet points):
1) Overall performance
2) Primary driver(s)
3) Segment insights
   - Device
   - Channel
   - Country
4) Confidence (low / medium / high, with justification)
5) Recommended next checks (2–4 bullets)

Guidance:
- Start from overall KPIs, then drill into segments.
- Mention a segment ONLY if it materially contributes to the change.
- Prefer clear, direct language over narrative prose.
- Keep the total length under ~200 words.

"""

def narrate(result: FinalResult) -> str:
    client = get_client()

    payload = {
        "question": result.plan.question,
        "kpis": result.evidence.kpis,
        "funnel": result.evidence.funnel,
        "segments": result.evidence.segments,
        "verdicts": [v.model_dump() for v in result.verdicts],
        "next_checks": result.next_checks,
    }

    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": NARRATOR_SYSTEM},
            {"role": "user", "content": json.dumps(payload)},
        ],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()