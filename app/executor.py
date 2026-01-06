from __future__ import annotations
from .schemas import Plan, Evidence, HypothesisVerdict, FinalResult
from . import tools

ALLOWED = {
    "resolve_period",
    "compute_kpis",
    "funnel_breakdown",
    "segment_impact",
    "sanity_check_data",
}

def _evaluate_verdicts(evidence: Evidence) -> list[HypothesisVerdict]:
    verdicts: list[HypothesisVerdict] = []

    kpis = evidence.kpis or {}
    cvr = kpis.get("cvr", {})
    sessions = kpis.get("sessions", {})

    # Deterministic, simple Phase-1 rules
    # Thresholds can be tuned later
    def rel_change(d: dict) -> float | None:
        v = d.get("rel_change")
        return float(v) if v is not None else None

    sess_rc = rel_change(sessions)
    cvr_rc = rel_change(cvr)

    # H1: sessions changed materially
    if sess_rc is not None and abs(sess_rc) >= 0.05:
        verdicts.append(HypothesisVerdict(hypothesis_id="H1", status="supported", reason=f"Sessions changed by {sess_rc:.1%}."))
    else:
        verdicts.append(HypothesisVerdict(hypothesis_id="H1", status="inconclusive", reason="Sessions change not clearly material."))

    # H2: CVR changed materially
    if cvr_rc is not None and abs(cvr_rc) >= 0.05:
        verdicts.append(HypothesisVerdict(hypothesis_id="H2", status="supported", reason=f"CVR changed by {cvr_rc:.1%}."))
    else:
        verdicts.append(HypothesisVerdict(hypothesis_id="H2", status="inconclusive", reason="CVR change not clearly material."))

    # H3: funnel rate delta shows notable drop
    funnel = evidence.funnel.get("rate_deltas", {}) if evidence.funnel else {}
    worst = None
    for k, v in funnel.items():
        d = v.get("abs_change")
        if d is None:
            continue
        if worst is None or d < worst[1]:
            worst = (k, d)
    if worst and worst[1] <= -0.03:
        verdicts.append(HypothesisVerdict(hypothesis_id="H3", status="supported", reason=f"Worst funnel rate change: {worst[0]} {worst[1]:+.2%} (abs)."))
    else:
        verdicts.append(HypothesisVerdict(hypothesis_id="H3", status="inconclusive", reason="No clear funnel-step rate drop detected."))

    # H4: any segment table exists
    segs = evidence.segments or {}
    if segs:
        verdicts.append(HypothesisVerdict(hypothesis_id="H4", status="supported", reason="Segment impact tables computed (device/channel/country)."))
    else:
        verdicts.append(HypothesisVerdict(hypothesis_id="H4", status="inconclusive", reason="No segment evidence computed."))

    return verdicts

def execute_plan(plan: Plan, df):
    ev = Evidence()

    period_prev = None
    period_cur = None

    for step in plan.execution_steps:
        if step.tool_name not in ALLOWED:
            raise ValueError(f"Tool not allowed: {step.tool_name}")

        if step.tool_name == "sanity_check_data":
            ev.sanity = tools.sanity_check_data(df)

        elif step.tool_name == "resolve_period":
            prev, cur = tools.resolve_period(step.args.get("question_text", plan.question), df)
            period_prev, period_cur = prev, cur

        elif step.tool_name == "compute_kpis":
            if not (period_prev and period_cur):
                raise RuntimeError("Periods not resolved before compute_kpis")
            ev.kpis = tools.compute_kpis(df, period_prev, period_cur)

        elif step.tool_name == "funnel_breakdown":
            if not (period_prev and period_cur):
                raise RuntimeError("Periods not resolved before funnel_breakdown")
            ev.funnel = tools.funnel_breakdown(df, period_prev, period_cur)

        elif step.tool_name == "segment_impact":
            if not (period_prev and period_cur):
                raise RuntimeError("Periods not resolved before segment_impact")
            seg_col = step.args["segment_col"]
            ev.segments[seg_col] = tools.segment_impact(df, period_prev, period_cur, seg_col)

    verdicts = _evaluate_verdicts(ev)
    next_checks = [
        "Check tracking / instrumentation changes around the period boundary.",
        "Verify if any campaign, budget, or targeting changes occurred last week.",
        "Inspect funnel step UX or error rates (especially on mobile).",
        "Look for product/pricing/shipping changes that could affect checkout completion."
    ]

    return FinalResult(plan=plan, evidence=ev, verdicts=verdicts, next_checks=next_checks)