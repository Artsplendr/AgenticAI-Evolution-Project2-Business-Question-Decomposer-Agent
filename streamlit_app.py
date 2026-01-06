from __future__ import annotations
import os
import re
import pandas as pd
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv

# Load env BEFORE importing modules that read environment variables
load_dotenv(override=True)

from app.pipeline import run
from app.narrator_llm import narrate

st.set_page_config(page_title="Business Question Decomposer (Plan → Execute)", layout="wide")
st.title("Business Question Decomposer (Plan → Execute)")

# Slightly narrower sidebar (≈10% reduction)
st.markdown(
    """
    <style>
      /* Streamlit sidebar width tweak */
      [data-testid="stSidebar"] {
        width: 260px;
        min-width: 260px;
        max-width: 260px;
      }
      /* Reduce left/right page paddings ~50% */
      [data-testid="stAppViewContainer"] > .main .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
        padding-top: 2.4rem;   /* ensure title is fully visible */
      }
      /* Give the page title a little breathing room from the top edge */
      .block-container h1:first-child {
        margin-top: 0.4rem;
      }
      /* Tighter line-height for Executive Summary */
      .exec-summary {
        line-height: 1 !important;
      }
      .exec-summary p, .exec-summary li {
        line-height: 1 !important;
        margin-bottom: 0.2rem;
      }
      .exec-summary ul, .exec-summary ol {
        margin-top: 0.2rem;
        margin-bottom: 0.2rem;
        padding-left: 1.1rem; /* keep bullets aligned but compact */
      }
      .exec-subtitle {
        font-weight: 700;
        margin-top: 0.8rem;   /* +~10% space above sections */
        margin-bottom: 0.3rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# Helpers ----------------------------------------------------------------------
def sanitize_summary(text: str) -> str:
    """Clean LLM output:
    - remove any 'Title:' line
    - convert top-level section bullets to bold subtitles without bullets
    """
    bullet_chars = r'\-\*\u2022\u2013\u2014\u00B7o'  # -,*,•,–,—,·,o
    section_re = re.compile(
        rf'^\s*[{bullet_chars}]\s*(Overall performance|Primary driver\(s\)|Segment insights|Confidence|Recommended next checks)\s*:?\s*$',
        re.IGNORECASE,
    )
    # Case where section title and content are on the SAME line, e.g.:
    # "- Overall performance: Sessions increased ..."
    section_inline_re = re.compile(
        rf'^\s*[{bullet_chars}]\s*(Overall performance|Primary driver\(s\)|Segment insights|Confidence|Recommended next checks)\s*:\s*(.+)\s*$',
        re.IGNORECASE,
    )
    lines = []
    current_section = None
    list_sections = {"overall performance", "segment insights", "recommended next checks"}
    open_ul = False
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s.lower().startswith("title:"):
            continue
        m_inline = section_inline_re.match(s)
        if m_inline:
            label = m_inline.group(1)
            rest = m_inline.group(2)
            lines.append(f'<div class="exec-subtitle">{label}</div>')
            current_section = label.lower()
            if current_section in list_sections and rest:
                item = re.sub(rf'^[{bullet_chars}]\s*', '', rest.strip())
                if not open_ul:
                    lines.append('<ul class="exec-inner">'); open_ul = True
                # For Overall performance, split multiple sentences into separate bullets
                if current_section == "overall performance":
                    for sentence in filter(None, [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z(])', item)]):
                        lines.append(f"<li>{sentence}</li>")
                else:
                    lines.append(f"<li>{item}</li>")
            else:
                if open_ul:
                    lines.append('</ul>'); open_ul = False
                lines.append(rest)
            continue
        m = section_re.match(s)
        if m:
            label = m.group(1)
            # Render as bold subtitle (no bullet), add small spacing handled by CSS
            lines.append(f'<div class="exec-subtitle">{label}</div>')
            current_section = label.lower()
            if open_ul:
                lines.append('</ul>'); open_ul = False
        else:
            if current_section in list_sections and s:
                item = re.sub(rf'^[{bullet_chars}]\s*', '', s)
                if not open_ul:
                    lines.append('<ul class="exec-inner">'); open_ul = True
                if current_section == "overall performance":
                    for sentence in filter(None, [si.strip() for si in re.split(r'(?<=[.!?])\s+(?=[A-Z(])', item)]):
                        lines.append(f"<li>{sentence}</li>")
                else:
                    lines.append(f"<li>{item}</li>")
            else:
                if open_ul and s == "":
                    lines.append('</ul>'); open_ul = False
                lines.append(ln)
    if open_ul:
        lines.append('</ul>')
    return "\n".join(lines).strip()

def make_cvr_overall_figure(df: pd.DataFrame):
    df_daily = df.groupby("date", as_index=False).agg(
        sessions=("sessions", "sum"),
        conversions=("conversions", "sum"),
    )
    df_daily["cvr"] = df_daily["conversions"] / df_daily["sessions"].replace(0, pd.NA)
    fig = px.line(df_daily, x="date", y="cvr", title="Daily CVR (overall)")
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def make_cvr_by_segment_figure(df: pd.DataFrame, segment_col: str):
    if segment_col not in df.columns:
        return None
    seg = (
        df.groupby(["date", segment_col], as_index=False)
          .agg(sessions=("sessions", "sum"), conversions=("conversions", "sum"))
    )
    seg["cvr"] = seg["conversions"] / seg["sessions"].replace(0, pd.NA)
    fig = px.line(seg, x="date", y="cvr", color=segment_col,
                  title=f"Daily CVR by {segment_col}")
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
    return fig

with st.sidebar:
    st.header("Inputs")
    dataset_path = st.text_input("Dataset path", value=os.getenv("DATASET_PATH", "data/sample_events.csv"))
    question = st.text_area("Business question", value="Why did conversion drop last week?", height=100)
    run_btn = st.button("Run analysis", type="primary")

if run_btn:
    try:
        df, plan, result = run(question, dataset_path)

        # 1/3 left (narrative), 2/3 right (KPIs + charts)
        col1, col2 = st.columns([1, 2])

        with col1:
            # Move narrative to the left column (top)
            st.subheader("Executive Summary")
            try:
                summary_text = narrate(result)  # already implemented in your pipeline
                summary_text = sanitize_summary(summary_text)
                # Show only the summary text with tighter line spacing
                st.markdown(f'<div class="exec-summary">{summary_text}</div>', unsafe_allow_html=True)
            except Exception as e:
                st.warning(f"Narrator unavailable (check OPENAI_API_KEY). Showing a basic fallback.\n\n{e}")
                st.write("Evidence computed successfully. Add OPENAI_API_KEY to enable narrated summary.")

        with col2:
            st.subheader("Top KPIs (previous vs current)")
            k = result.evidence.kpis
            kpi_rows = []
            for name in ["sessions", "conversions", "cvr"]:
                d = k.get(name, {})
                kpi_rows.append({
                    "metric": name,
                    "previous": d.get("previous"),
                    "current": d.get("current"),
                    "abs_change": d.get("abs_change"),
                    "rel_change": d.get("rel_change"),
                })
            st.dataframe(pd.DataFrame(kpi_rows), use_container_width=True)

            # 2x2 small charts grid under KPIs
            fig_overall = make_cvr_overall_figure(df)
            fig_device = make_cvr_by_segment_figure(df, "device")
            fig_channel = make_cvr_by_segment_figure(df, "channel")
            fig_country = make_cvr_by_segment_figure(df, "country")

            r1c1, r1c2 = st.columns(2)
            r2c1, r2c2 = st.columns(2)
            if fig_overall:
                r1c1.plotly_chart(fig_overall, use_container_width=True)
            if fig_device:
                r1c2.plotly_chart(fig_device, use_container_width=True)
            if fig_channel:
                r2c1.plotly_chart(fig_channel, use_container_width=True)
            if fig_country:
                r2c2.plotly_chart(fig_country, use_container_width=True)

        st.divider()

        st.subheader("Segment impact (largest negative movers by conversions)")
        for seg_col, seg_data in (result.evidence.segments or {}).items():
            st.markdown(f"**{seg_col}**")
            rows = seg_data.get("rows", [])
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
            else:
                st.write("No rows.")

        st.divider()

        st.subheader("Verdicts (deterministic)")
        st.dataframe(pd.DataFrame([v.model_dump() for v in result.verdicts]), use_container_width=True)

        # Move Plan and Sanity checks to the bottom
        st.divider()
        with st.expander("Plan (validated)", expanded=False):
            st.json(plan.model_dump())

        with st.expander("Funnel breakdown", expanded=False):
            st.json(result.evidence.funnel)

        with st.expander("Sanity checks", expanded=False):
            st.json(result.evidence.sanity)

    except Exception as e:
        st.error(f"Run failed: {e}")