"""
Neural Network Layer - Sistema de memória que funciona como rede neural
Memórias modificam comportamento e respostas dos agentes
Simula um "cérebro" que aprende com as interações
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import Memory, MemoryType, Agent, MicroAgent, MicroAgentType, MemoryEmbedding
from llm_logic.embedding_generator import EmbeddingGenerator
from agent_system.prompt_manager import PromptManager
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import json
import hashlib
import re

logger = logging.getLogger(__name__)


class NeuralNetworkLayer:
    """
    Implementa memória distribuída tipo rede neural
    Cada memória afeta pesos e comportamentos
    """
    
    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.embedding_generator = EmbeddingGenerator()
        self.agent = self._load_agent()
        self.prompts = PromptManager(db)
        self._memory_cache = {}  # Cache de memórias para performance
    
    def _load_agent(self) -> Agent:
        """Carrega agente"""
        agent = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
        if not agent:
            raise ValueError(f"Agente {self.agent_id} não encontrado")
        return agent
    
    def get_micro_agent_modifiers(
        self,
        query: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Dict]:
        """
        Calcula modificadores para cada micro-agente baseado em memórias
        
        Retorna: {
            "logical": {"weight_modifier": 1.2, "temperature_modifier": -0.1, "memories_applied": [...]},
            ...
        }
        """
        
        context = context or {}
        
        # Obter memórias relevantes
        relevant_memories = self._get_relevant_memories(query)
        
        # Obter micro-agentes
        micro_agents = self.db.query(MicroAgent).filter(
            MicroAgent.agent_id == self.agent_id,
            MicroAgent.activation_enabled == True
        ).all()
        
        modifiers = {}
        
        for micro_agent in micro_agents:
            agent_type = self.db.query(MicroAgentType).filter(
                MicroAgentType.id == micro_agent.type_id
            ).first()
            
            if not agent_type:
                continue
            
            # Calcular modificadores para este agente
            modifier = self._calculate_agent_modifiers(
                agent_type,
                relevant_memories,
                context
            )
            
            modifiers[agent_type.name] = modifier
        
        return modifiers
    
    def _calculate_agent_modifiers(
        self,
        agent_type: MicroAgentType,
        memories: List[Memory],
        context: Dict
    ) -> Dict:
        """Calcula modificadores para um específico micro-agente"""
        
        weight_modifier = 1.0
        temperature_modifier = 0.0
        confidence_modifier = 0.0
        applied_memories = []
        
        for memory in memories:
            # Aplicar memória se relevante para este agente
            if self._is_memory_relevant_for_agent(memory, agent_type):
                
                # Modificadores baseados em tipo de memória
                if memory.type.name == "emotional":
                    # Memórias emocionais podem aumentar ou diminuir confiança
                    confidence_modifier += memory.emotional_valence * 0.1
                    temperature_modifier += memory.emotional_valence * 0.05
                
                elif memory.type.name == "episodic":
                    # Memórias episódicas podem aumentar relevância
                    if memory.importance_score > 0.7:
                        weight_modifier += 0.15
                    else:
                        weight_modifier -= 0.05
                
                elif memory.type.name == "relational":
                    # Memórias sobre pessoas/relações afetam abordagem social
                    if agent_type.name == "social":
                        weight_modifier += 0.2
                        confidence_modifier += 0.1
                
                # Impacto de importância
                weight_modifier *= (0.8 + (memory.importance_score * 0.4))
                
                # Contar como aplicada
                applied_memories.append({
                    "memory_id": memory.id,
                    "title": memory.title,
                    "impact": "weight" if weight_modifier != 1.0 else "temperature"
                })
        
        # Normalizar modificadores
        weight_modifier = max(0.5, min(2.0, weight_modifier))  # 0.5x a 2.0x
        temperature_modifier = max(-0.5, min(0.5, temperature_modifier))
        confidence_modifier = max(-0.5, min(0.5, confidence_modifier))
        
        return {
            "weight_modifier": weight_modifier,
            "temperature_modifier": temperature_modifier,
            "confidence_modifier": confidence_modifier,
            "memories_applied": applied_memories,
            "memory_count": len(applied_memories)
        }
    
    def _is_memory_relevant_for_agent(self, memory: Memory, agent_type: MicroAgentType) -> bool:
        """Verifica se memória é relevante para micro-agente"""
        
        # Mapeamento: tipo de memória -> agentes que se beneficiam
        relevance_map = {
            "emotional": ["emotional", "social", "ethical"],
            "episodic": ["critical", "logical", "social"],
            "relational": ["social", "emotional", "ethical"],
            "autobiographical": ["emotional", "social"],
            "procedural": ["logical", "strategic"],
            "semantic": ["logical", "critical"],
            "aspirational": ["creative", "ethical"],
        }
        
        memory_type = memory.type.name if memory.type else "semantic"
        relevant_agents = relevance_map.get(memory_type, ["logical"])
        
        return agent_type.name in relevant_agents
    
    def _get_relevant_memories(
        self,
        query: str,
        limit: int = 5,
        recency_weight: float = 0.3
    ) -> List[Memory]:
        """
        Obtém memórias relevantes para query
        Pondera por relevância, importância e recência
        """
        
        try:
            # Gerar embedding da query
            query_embedding = self.embedding_generator.generate_embedding(query)
            
            if not query_embedding:
                # Fallback: buscar por recência
                return self._get_recent_memories(limit)
        
        except Exception as e:
            logger.warning(f"Erro ao gerar embedding: {e}")
            return self._get_recent_memories(limit)
        
        # Buscar todas as memórias do agente
        all_memories = self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            Memory.is_blocked == False  # Ignorar memórias traumáticas bloqueadas
        ).all()
        
        query_words = {
            w for w in re.findall(r"\w+", (query or "").lower())
            if len(w) >= 4
        }

        # Calcular scores de relevância
        memory_scores = []
        
        for memory in all_memories:
            if self._is_noisy_memory(memory):
                continue

            # Score semântico (se houver embedding)
            semantic_score = 0.0
            
            if memory.embeddings:
                for emb in memory.embeddings:
                    if emb.embedding:
                        similarity = self._cosine_similarity(query_embedding, emb.embedding)
                        semantic_score = max(semantic_score, similarity)

            memory_text = " ".join([
                memory.title or "",
                memory.content or "",
                " ".join(str(t) for t in (memory.relates_to_topics or [])),
            ]).lower()
            text_overlap = bool(query_words and any(w in memory_text for w in query_words))
            if semantic_score < 0.16 and not text_overlap:
                continue
            
            # Score de recência
            time_diff = (datetime.utcnow() - memory.created_at).days
            recency_score = 1.0 / (1.0 + time_diff * 0.1)  # Decay over time
            
            # Score de importância
            importance_score = memory.importance_score
            
            # Score de acesso frequente
            access_score = min(1.0, memory.access_count / 10.0)
            
            # Combinar scores
            total_score = (
                semantic_score * 0.4 +
                importance_score * 0.3 +
                recency_score * recency_weight +
                access_score * 0.1
            )
            
            if total_score > 0.1:  # Threshold mínimo
                memory_scores.append((memory, total_score))
        
        # Ordenar por score e pegar top N
        memory_scores.sort(key=lambda x: x[1], reverse=True)
        relevant_memories = [m for m, score in memory_scores[:limit]]
        
        # Atualizar access_count e last_accessed
        for memory in relevant_memories:
            memory.access_count = (memory.access_count or 0) + 1
            memory.last_accessed = datetime.utcnow()
        
        self.db.commit()
        
        return relevant_memories

    def _is_noisy_memory(self, memory: Memory) -> bool:
        topics = memory.relates_to_topics or []
        if isinstance(topics, str):
            topics = [topics]
        topic_set = {str(t).lower() for t in topics}
        title = (memory.title or "").lower()

        if "imagined" in topic_set or "generated" in topic_set:
            return "autobiographical_imagination" not in topic_set

        return (
            title.startswith("aprendizado:")
            or title.startswith("learning:")
            or "learning" in topic_set
        )
    
    def _get_recent_memories(self, limit: int = 5) -> List[Memory]:
        """Obtém memórias recentes como fallback"""
        
        return self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            Memory.is_blocked == False
        ).order_by(Memory.created_at.desc()).limit(limit).all()
    
    def create_learning_memory(
        self,
        interaction_type: str,
        success: bool,
        query: str,
        response: str,
        confidence: float,
        user_context: Optional[Dict] = None
    ) -> Optional[Memory]:
        """
        Creates a learning memory only when the interaction produced a genuine insight.
        Uses AI to extract the actual lesson instead of storing boilerplate.
        """

        from agent_system.memory_manager_cognitive import MemoryManager

        memory_manager = MemoryManager(self.db, self.agent_id)

        if self._is_trivial_interaction(query):
            return None

        signature = self._learning_signature(interaction_type, query)

        duplicate = self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            Memory.content.like(f"%{signature}%"),
            Memory.created_at >= datetime.utcnow() - timedelta(days=7),
            Memory.is_blocked == False,
        ).first()
        if duplicate:
            return duplicate

        try:
            from llm_logic.llm_client import get_llm_client
            prompt = (
                f"I just had a conversation. The person said: \"{query[:400]}\"\n"
                f"I replied: \"{response[:400]}\"\n"
                f"Confidence: {confidence:.0%}. Outcome: {'worked well' if success else 'could improve'}.\n\n"
                f"Extract a concrete, reusable lesson I can apply to future conversations. "
                f"Not a summary of what happened — a genuine insight about how to handle similar situations.\n\n"
                f"If there is no real lesson (trivial exchange, greeting, etc.), respond with just: NONE\n"
                f"Otherwise respond with just the lesson in one sentence, starting with: LESSON:"
            )
            raw = get_llm_client().generate(prompt, max_tokens=100, temperature=0.2).strip()

            if raw.startswith("NONE") or "LESSON:" not in raw:
                return None

            lesson = raw.split("LESSON:")[1].strip()
            if len(lesson) < 10:
                return None

            memory_title = f"Learned: {lesson[:60]}"
            memory_content = f"{lesson}\n[sig:{signature}]"

            if not memory_manager.should_store_memory(memory_title, memory_content, "semantic"):
                return None

            memory = memory_manager.create_memory(
                title=memory_title,
                content=memory_content,
                memory_type="semantic",
                importance_score=0.55 if success else 0.65,
                emotional_valence=0.3 if success else -0.2,
                relates_to_topics=["learning", interaction_type]
            )
            return memory

        except Exception as e:
            logger.debug(f"[learning] create_learning_memory failed: {e}")
            return None

    def _is_trivial_interaction(self, query: str) -> bool:
        text = (query or "").strip()
        if len(text) < 6:
            return True
        try:
            from llm_logic.llm_client import get_llm_client
            prompt = self.prompts.render(
                "learning.should_store_interaction",
                message=text[:1000],
            )
            raw = get_llm_client().generate(prompt, max_tokens=120, temperature=0.1).strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                start = raw.find("{")
                end = raw.rfind("}")
                parsed = json.loads(raw[start:end + 1]) if start >= 0 and end > start else {}
            if "should_store" in parsed:
                return not bool(parsed.get("should_store"))
        except Exception as e:
            logger.debug(f"[learning] filtro semântico falhou: {e}")
        return False

    def _extract_query_topic(self, query: str) -> str:
        words = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", (query or "").lower())
        significant = [w for w in words if len(w) >= 4][:6]
        if not significant:
            return "geral"
        return " ".join(significant)

    def _learning_signature(self, interaction_type: str, query: str) -> str:
        normalized = " ".join(re.findall(r"[a-zA-ZÀ-ÿ0-9]+", (query or "").lower()))
        raw = f"{interaction_type}:{normalized[:220]}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    
    def adjust_micro_agent_weights(
        self,
        performance_history: Dict[str, List[float]]
    ) -> Dict[str, float]:
        """
        Ajusta pesos dos micro-agentes baseado em histórico de desempenho
        Permite que o sistema aprenda qual agente é melhor em que situação
        """
        
        micro_agents = self.db.query(MicroAgent).filter(
            MicroAgent.agent_id == self.agent_id
        ).all()
        
        adjustments = {}
        
        for micro_agent in micro_agents:
            agent_type = self.db.query(MicroAgentType).filter(
                MicroAgentType.id == micro_agent.type_id
            ).first()
            
            if not agent_type or agent_type.name not in performance_history:
                continue
            
            # Calcular score de desempenho
            performances = performance_history[agent_type.name]
            
            if not performances:
                continue
            
            avg_performance = sum(performances) / len(performances)
            
            # Calcular novo peso
            # Se performance alta, aumentar peso; se baixa, diminuir
            weight_adjustment = 1.0 + ((avg_performance - 0.5) * 0.2)
            weight_adjustment = max(0.5, min(2.0, weight_adjustment))
            
            # Atualizar micro-agente
            micro_agent.custom_weight = weight_adjustment
            adjustments[agent_type.name] = weight_adjustment
            
            logger.debug(f"Ajuste de peso para {agent_type.name}: {weight_adjustment:.2f}")
        
        self.db.commit()
        
        return adjustments
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcula similaridade cosseno entre vetores"""
        
        import math
        
        if len(vec1) != len(vec2) or len(vec1) == 0:
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def get_network_state(self) -> Dict:
        """Retorna estado actual da rede neural de memórias"""
        
        # Contar memórias por tipo
        memory_types = self.db.query(MemoryType.name, Memory.id).join(
            Memory, Memory.type_id == MemoryType.id
        ).filter(Memory.agent_id == self.agent_id).group_by(MemoryType.name).all()
        
        memory_counts = {name: count for name, count in memory_types}
        
        # Calcular saúde geral
        total_memories = sum(memory_counts.values())
        avg_importance = self.db.query(Memory.importance_score).filter(
            Memory.agent_id == self.agent_id
        ).all()
        avg_importance = sum(i[0] for i in avg_importance) / len(avg_importance) if avg_importance else 0.5
        
        return {
            "agent_id": self.agent_id,
            "total_memories": total_memories,
            "memory_types_distribution": memory_counts,
            "average_importance": avg_importance,
            "network_health": "healthy" if total_memories > 10 and avg_importance > 0.5 else "developing",
            "timestamp": datetime.utcnow().isoformat()
        }
