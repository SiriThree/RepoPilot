import os

from app.core.config import get_settings


os.environ["REPOPILOT_FORCE_LLM_FALLBACK"] = "true"
get_settings.cache_clear()
