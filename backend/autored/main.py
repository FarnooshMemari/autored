"""Entry point: `uvicorn autored.main:app --port 8000` (binds where you tell it;
keep it on 127.0.0.1 unless AUTORED_API_TOKEN is set)."""
from .api.app import create_app

app = create_app()
