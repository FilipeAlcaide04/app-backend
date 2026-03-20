from sqlalchemy.orm import Session
from sqlalchemy import desc
from sqlalchemy import or_
from data.database import Memory, Agent
import json
from typing import List, Dict
from config.logger import log_memory_retrieved
from llm_logic.llm_client import get_llm_client
from data.prompt_logger import PromptLogger
from config.logger import log_llm_call


class MemoryAgent:
    """Recupera memórias relevantes"""

    def __init__(self, db: Session, persona_id: str):
        self.db = db
        self.persona_id = persona_id
        self.all_memories = self.get_all_memories()

    def get_all_memories(self) -> List[Dict]:
        """Retorna todas as memórias do agente"""
        memories = self.db.query(Memory).filter(Memory.persona_id == self.persona_id).all()
        result = [
            {
                "content": memory.content,
                "memory_type": memory.memory_type,
                "category": memory.category,
                "created_at": memory.created_at.isoformat() if memory.created_at else None
            }
            for memory in memories
        ]
        return result
  
    def get_related_memories_text(self, query: str) -> dict:
        """Faz uma call ao LLM para obter memórias relacionadas baseado na query"""
        try:
            llm = get_llm_client()
            
            # Busca todas as memórias
            all_memories = self.all_memories
            memories_text = json.dumps(all_memories, ensure_ascii=False, indent=2)
            
            messages = [
                {"role": "system", "content": "Você é um assistente que filtra memórias relevantes.\n\nTodas as memórias disponíveis:\n" + memories_text},
                {"role": "user", "content": f"Com base nesta query: {query}\nRetorna apenas as memórias mais relacionadas em formato de lista separada por vírgulas."}
            ]

            response = llm.chat_completion(
                messages=messages,
                max_tokens=400,
                temperature=0.1
            )

            log_llm_call(self.persona_id, "logic_memory_retrieval", llm.get_model_name())

            return {
                "related_memories": response,
                "type": "memory_retrieval"
            }
        except Exception as e:
            return {
                "error": f"Erro ao obter memórias relacionadas: {str(e)}"
            }


       
