"""
Micro Agents - Ficheiros individuais para cada tipo de pensamento cognitivo

Cada agente tem seu próprio ficheiro e especialidade:
- social_agent.py: Perspectiva social e interpessoal
- logical_agent.py: Análise lógica e racional
- emotional_agent.py: Processamento emocional
- critical_agent.py: Análise crítica
- ethical_agent.py: Perspectiva ética
- creative_agent.py: Pensamento criativo e inovador
"""

from .social_agent import SocialAgent
from .logical_agent import LogicalAgent
from .emotional_agent import EmotionalAgent
from .critical_agent import CriticalAgent
from .ethical_agent import EthicalAgent
from .creative_agent import CreativeAgent

__all__ = [
    'SocialAgent',
    'LogicalAgent',
    'EmotionalAgent',
    'CriticalAgent',
    'EthicalAgent',
    'CreativeAgent',
]

# Mapeamento de tipos de agentes
AGENTS_MAP = {
    'social': SocialAgent,
    'logical': LogicalAgent,
    'emotional': EmotionalAgent,
    'critical': CriticalAgent,
    'ethical': EthicalAgent,
    'creative': CreativeAgent,
}

def get_agent_class(agent_type: str):
    """Retorna a classe do agente pelo tipo"""
    return AGENTS_MAP.get(agent_type.lower())
