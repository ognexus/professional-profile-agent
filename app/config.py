"""
config.py — Load environment variables and expose typed settings.
All app code should import from here rather than reading os.environ directly.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve .env relative to the project root (one level above app/)
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env", override=False)


class Settings:
    # Anthropic
    anthropic_api_key: str = os.environ["ANTHROPIC_API_KEY"]
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    anthropic_model_fast: str = os.getenv("ANTHROPIC_MODEL_FAST", "claude-haiku-4-5-20251001")

    # Storage
    db_path: Path = _ROOT / os.getenv("DB_PATH", "data/profile_agent.db")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Skills directory — skills are loaded as markdown and injected into system prompts
    skills_dir: Path = _ROOT / "skills"
    prompts_dir: Path = _ROOT / "prompts"
    agents_dir: Path = _ROOT / "agents"


settings = Settings()
