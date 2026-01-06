from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass

@dataclass(frozen=True)
class Period:
    start: pd.Timestamp
    end: pd.Timestamp  # inclusive

def load_dataset(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df

def resolve_period(question_text: str, df: pd.DataFrame) -> tuple[Period, Period]:
    """
    Phase 1: supports 'last week' only.
    Uses max date in dataset as anchor.
    Returns (current_period, previous_period) each 7 days.
    """
    q = question_text.lower()
    anchor = df["date"].max().normalize()

    if "last week" in q:
        current_end = anchor
        current_start = (anchor - pd.Timedelta(days=6))
        prev_end = current_start - pd.Timedelta(days=1)
        prev_start = prev_end - pd.Timedelta(days=6)
        return Period(prev_start, prev_end), Period(current_start, current_end)

    # fallback: treat "last week" anyway
    current_end = anchor
    current_start = (anchor - pd.Timedelta(days=6))
    prev_end = current_start - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=6)
    return Period(prev_start, prev_end), Period(current_start, current_end)

def _filter_period(df: pd.DataFrame, period: Period) -> pd.DataFrame:
    return df[(df["date"] >= period.start) & (df["date"] <= period.end)].copy()

def compute_kpis(df: pd.DataFrame, period_a: Period, period_b: Period, segment: dict | None = None) -> dict:
    """
    period_a = previous, period_b = current
    """
    dfa = _filter_period(df, period_a)
    dfb = _filter_period(df, period_b)

    if segment:
        for k, v in segment.items():
            dfa = dfa[dfa[k] == v]
            dfb = dfb[dfb[k] == v]

    def agg(d: pd.DataFrame) -> dict:
        sessions = int(d["sessions"].sum())
        conversions = int(d["conversions"].sum())
        cvr = (conversions / sessions) if sessions > 0 else np.nan
        return {"sessions": sessions, "conversions": conversions, "cvr": float(cvr)}

    a = agg(dfa)
    b = agg(dfb)

    def delta(key: str) -> dict:
        av, bv = a[key], b[key]
        abs_change = bv - av
        rel_change = (abs_change / av) if av not in (0, np.nan) and av != 0 else np.nan
        return {"previous": av, "current": bv, "abs_change": abs_change, "rel_change": float(rel_change) if not np.isnan(rel_change) else None}

    return {
        "sessions": delta("sessions"),
        "conversions": delta("conversions"),
        "cvr": delta("cvr"),
        "segment": segment or {},
    }

def funnel_breakdown(df: pd.DataFrame, period_a: Period, period_b: Period) -> dict:
    steps = ["step_view_product", "step_add_to_cart", "step_checkout", "step_purchase"]

    def agg(d: pd.DataFrame) -> dict:
        totals = {s: int(d[s].sum()) for s in steps}
        rates = {}
        for i in range(1, len(steps)):
            prev = totals[steps[i-1]]
            cur = totals[steps[i]]
            rates[f"{steps[i-1]}→{steps[i]}"] = float(cur / prev) if prev > 0 else None
        return {"totals": totals, "rates": rates}

    a = agg(_filter_period(df, period_a))
    b = agg(_filter_period(df, period_b))

    # Compute rate deltas
    rate_deltas = {}
    for k in a["rates"].keys():
        av, bv = a["rates"][k], b["rates"][k]
        if av is None or bv is None:
            rate_deltas[k] = {"previous": av, "current": bv, "abs_change": None}
        else:
            rate_deltas[k] = {"previous": av, "current": bv, "abs_change": bv - av}

    return {"previous": a, "current": b, "rate_deltas": rate_deltas}

def segment_impact(df: pd.DataFrame, period_a: Period, period_b: Period, segment_col: str, top_n: int = 8) -> dict:
    """
    For each segment value, compute conversions and CVR delta.
    Returns top movers by conversion abs_change.
    """
    dfa = _filter_period(df, period_a)
    dfb = _filter_period(df, period_b)

    def summarize(d: pd.DataFrame) -> pd.DataFrame:
        g = d.groupby(segment_col, dropna=False).agg(
            sessions=("sessions", "sum"),
            conversions=("conversions", "sum"),
        ).reset_index()
        g["cvr"] = g["conversions"] / g["sessions"].replace(0, np.nan)
        return g

    a = summarize(dfa).rename(columns={"sessions": "sessions_prev", "conversions": "conversions_prev", "cvr": "cvr_prev"})
    b = summarize(dfb).rename(columns={"sessions": "sessions_cur", "conversions": "conversions_cur", "cvr": "cvr_cur"})

    m = a.merge(b, on=segment_col, how="outer").fillna(0)
    m["conversions_abs_change"] = m["conversions_cur"] - m["conversions_prev"]
    m["sessions_abs_change"] = m["sessions_cur"] - m["sessions_prev"]

    # CVR change is safer computed from non-zero sessions
    m["cvr_prev"] = m.apply(lambda r: (r["conversions_prev"] / r["sessions_prev"]) if r["sessions_prev"] else np.nan, axis=1)
    m["cvr_cur"] = m.apply(lambda r: (r["conversions_cur"] / r["sessions_cur"]) if r["sessions_cur"] else np.nan, axis=1)
    m["cvr_abs_change"] = m["cvr_cur"] - m["cvr_prev"]

    m = m.sort_values("conversions_abs_change").head(top_n)  # most negative movers
    rows = m.to_dict(orient="records")
    return {"segment_col": segment_col, "rows": rows}

def sanity_check_data(df: pd.DataFrame) -> dict:
    checks = {}

    required = ["date","sessions","conversions","step_view_product","step_add_to_cart","step_checkout","step_purchase"]
    missing = [c for c in required if c not in df.columns]
    checks["missing_required_columns"] = missing

    checks["negative_values"] = {}
    for c in required[1:]:
        if c in df.columns:
            checks["negative_values"][c] = int((df[c] < 0).sum())

    # basic funnel monotonicity heuristic (aggregated)
    agg = df[["step_view_product","step_add_to_cart","step_checkout","step_purchase"]].sum()
    checks["funnel_monotonicity_ok"] = bool(
        (agg["step_view_product"] >= agg["step_add_to_cart"] >= agg["step_checkout"] >= agg["step_purchase"])
    )

    return checks