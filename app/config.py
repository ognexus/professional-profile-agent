"""
config.py — Load environment variables and expose typed settings.

Priority order for each setting:
  1. os.environ (local .env loaded via python-dotenv)
  2. st.secrets (Streamlit Cloud secrets)
  3. Hard-coded defaults

All app code should import from here rather than reading os.environ directly.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve .env relative to the project root (one level above app/)
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env", override=False)


def _get(key: str, default: str | None = None) -> str | None:
    """
    Resolve a config value — env var first, then Streamlit secrets, then default.
    Streamlit secrets are used when deployed on Streamlit Cloud.
    """
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        secret = st.secrets.get(key)
        if secret:
            return str(secret)
    except Exception:
        pass
    return default


class Settings:
    # Anthropic
    @property
    def anthropic_api_key(self) -> str:
        key = _get("ANTHROPIC_API_KEY")
        if not key:
            raise KeyError(
                "ANTHROPIC_API_KEY not found. "
                "Add it to your .env file (local) or Streamlit Cloud secrets (deployed)."
            )
        return key

    @property
    def anthropic_model(self) -> str:
        return _get("ANTHROPIC_MODEL", "claude-sonnet-4-6") or "claude-sonnet-4-6"

    @property
    def anthropic_model_fast(self) -> str:
        return _get("ANTHROPIC_MODEL_FAST", "claude-haiku-4-5-20251001") or "claude-haiku-4-5-20251001"

    # Storage
    @property
    def db_path(self) -> Path:
        return _ROOT / (_get("DB_PATH", "data/profile_agent.db") or "data/profile_agent.db")

    # Logging
    @property
    def log_level(self) -> str:
        return _get("LOG_LEVEL", "INFO") or "INFO"

    # Skill/prompt directories (always relative to project root)
    skills_dir: Path = _ROOT / "skills"
    prompts_dir: Path = _ROOT / "prompts"
    agents_dir: Path = _ROOT / "agents"


settings = Settings()
