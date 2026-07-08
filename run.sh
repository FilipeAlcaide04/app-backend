# ativa o venv
source .venv/bin/activate

# corre a API
python -m uvicorn api.api:app --reload