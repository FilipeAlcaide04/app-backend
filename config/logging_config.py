"""
Configuração centralizada de logging.

Importar no entrypoint (api.py) ANTES de qualquer outro import:
    from config.logging_config import setup_logging
    setup_logging()
"""

import logging
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
LOG_DATE = "%H:%M:%S"

# Módulos que só interessam em DEBUG — ficam em WARNING por defeito
QUIET_MODULES = [
    "httpcore",
    "httpx",
    "urllib3",
    "sqlalchemy.engine",
    "sentence_transformers",
    "openai",
    "hpack",
    "uvicorn.access",
]


def setup_logging(level: str = "INFO"):
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE))
    root.addHandler(handler)

    for mod in QUIET_MODULES:
        logging.getLogger(mod).setLevel(logging.WARNING)
