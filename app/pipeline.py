from __future__ import annotations
from .planner_llm import get_plan
from .executor import execute_plan
from .tools import load_dataset

def run(question: str, dataset_path: str):
    df = load_dataset(dataset_path)
    plan = get_plan(question)
    result = execute_plan(plan, df)
    return df, plan, result