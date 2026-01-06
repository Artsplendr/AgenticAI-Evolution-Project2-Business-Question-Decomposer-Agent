from pydantic import BaseModel
import os

class Settings(BaseModel):
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    dataset_path: str = os.getenv("DATASET_PATH", "data/sample_events.csv")

settings = Settings()
