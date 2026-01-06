## `tests/test_smoke.py` (quick sanity)
```python
from app.tools import load_dataset
from app.planner_llm import rule_based_plan
from app.executor import execute_plan

def test_smoke():
    df = load_dataset("data/sample_events.csv")
    plan = rule_based_plan("Why did conversion drop last week?")
    result = execute_plan(plan, df)
    assert result.evidence.kpis["sessions"]["current"] >= 0
    assert "rate_deltas" in result.evidence.funnel


