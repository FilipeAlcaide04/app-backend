"""
PromptManager - carrega prompts versionadas da base de dados.
"""

from collections import defaultdict
from typing import Any, Dict
import logging

from sqlalchemy.orm import Session

from data.schema_cognitive import PromptTemplate

logger = logging.getLogger(__name__)


class SafeDict(defaultdict):
    def __missing__(self, key):
        return "{" + key + "}"


class PromptManager:
    """Renderiza prompts editáveis guardadas em `prompt_templates`."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, key: str) -> str:
        prompt = self.db.query(PromptTemplate).filter(
            PromptTemplate.key == key,
            PromptTemplate.is_active == True,
        ).first()
        if not prompt:
            logger.warning("[prompt] template não encontrada: %s", key)
            return ""
        return prompt.template

    def render(self, key: str, **variables: Any) -> str:
        template = self.get(key)
        if not template:
            return ""
        safe_vars: Dict[str, Any] = SafeDict(str)
        safe_vars.update({
            k: "" if v is None else v
            for k, v in variables.items()
        })
        try:
            return template.format_map(safe_vars)
        except Exception as e:
            logger.warning("[prompt] erro ao renderizar %s: %s", key, e)
            return template
