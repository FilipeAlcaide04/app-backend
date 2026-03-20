"""
Sistema de logging para o sistema de agentes
"""
import logging
from datetime import datetime
from typing import Optional

# Configuração do logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('agent_system')

def log_agent_activated(agent_id: str, user_id: Optional[str] = None):
    """Regista ativação de um agente"""
    logger.info(f"Agent activate: {agent_id} | User: {user_id or 'N/A'}")

def log_agent_created(agent_id: str, name: str):
    """Regista criação de um agente"""
    logger.info(f"✨ AGENTE CRIADO: {agent_id} ({name})")

def log_agent_updated(agent_id: str, name: str):
    """Regista atualização de um agente"""
    logger.info(f"🔄 AGENTE ATUALIZADO: {agent_id} ({name})")

def log_agent_deleted(agent_id: str):
    """Regista remoção de um agente"""
    logger.info(f"🗑️ AGENTE REMOVIDO: {agent_id}")

def log_message_received(agent_id: str, message: str):
    """Regista mensagem recebida"""
    message_preview = message[:50] + "..." if len(message) > 50 else message
    logger.info(f"💬 MENSAGEM RECEBIDA | Agente: {agent_id} | Mensagem: {message_preview}")

def log_micro_agent_used(agent_id: str, micro_agent: str, result: Optional[str] = None):
    """Regista uso de um micro-agente"""
    logger.info(f"🔧 MICRO-AGENTE USADO: {micro_agent} | Agente: {agent_id}")

def log_memory_saved(agent_id: str, memory_type: str, content_preview: str):
    """Regista guarda de memória"""
    logger.info(f"💾 MEMÓRIA GUARDADA | Agente: {agent_id} | Tipo: {memory_type} | Preview: {content_preview[:50]}")

def log_memory_retrieved(agent_id: str, count: int, memory_contents: list = None):
    """Regista recuperação de memórias"""
    if memory_contents is None:
        memory_contents = []
    if count > 0 and memory_contents:
        # Mostra preview das memórias (primeiras 100 chars de cada)
        previews = [content[:100] + "..." if len(content) > 100 else content for content in memory_contents]
        memories_preview = " | ".join([f"[{i+1}] {preview}" for i, preview in enumerate(previews)])
        logger.info(f"🔍 MEMÓRIAS RECUPERADAS | Agente: {agent_id} | Quantidade: {count} | Memórias: {memories_preview}")
    else:
        logger.info(f"🔍 MEMÓRIAS RECUPERADAS | Agente: {agent_id} | Quantidade: {count}")

def log_document_uploaded(agent_id: Optional[str], filename: str):
    """Regista upload de documento"""
    logger.info(f"📄 DOCUMENTO UPLOADED | Agente: {agent_id or 'N/A'} | Ficheiro: {filename}")

def log_document_associated(agent_id: str, document_id: int):
    """Regista associação de documento a agente"""
    logger.info(f"🔗 DOCUMENTO ASSOCIADO | Agente: {agent_id} | Documento ID: {document_id}")

def log_llm_call(agent_id: str, agent_name: str, model: str):
    """Regista chamada ao LLM"""
    logger.info(f"🧠 LLM CALL | Agente: {agent_id} | Micro-Agente: {agent_name} | Modelo: {model}")

def log_thinking_step(agent_id: str, micro_agent: str, thought: str, confidence: float, duration: float):
    """Regista cada passo de pensamento dos micro-agentes"""
    preview = thought[:200] + "..." if thought and len(thought) > 200 else (thought or "")
    logger.info(f"🧠 PENSAMENTO | Agente: {agent_id} | Micro-Agente: {micro_agent} | Confidence: {confidence:.2f} | Duration: {duration:.3f}s | Thought: {preview}")
