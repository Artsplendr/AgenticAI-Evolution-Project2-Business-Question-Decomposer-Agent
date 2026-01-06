# Business Question Decomposer (Plan → Execute → Narrative Summary)

Ask a business question like:
- "Why did conversion drop last week?"

Pipeline:
1) Planner (LLM) outputs JSON Plan (fallback rule-plan)
2) Deterministic tools compute evidence (pandas)
3) Narrator (LLM) writes a grounded executive summary

## Setup
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# create a .env file and add your secrets (at minimum OPENAI_API_KEY)
echo "OPENAI_API_KEY=" >> .env
```

## Venv quick commands (macOS/Linux)
```bash
# activate (from project root)
source .venv/bin/activate

# deactivate
deactivate

# confirm you're in the venv
which python
which pip

# upgrade packaging tools
python -m pip install --upgrade pip setuptools wheel

# reinstall from requirements
python -m pip install -r requirements.txt

# recreate venv with Python 3.11 (if needed)
python3.11 -m venv .venv
source .venv/bin/activate
```
