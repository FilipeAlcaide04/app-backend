"""
Relevance Evaluator - Avalia se cada micro-agente é relevante ANTES de executar
Otimiza recursos e tempo de resposta
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import MicroAgent, MicroAgentType, Agent, Document, Memory
from llm_logic.embedding_generator import EmbeddingGenerator
from llm_logic.llm_client import LLMClient
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RelevanceEvaluator:
    """Avalia relevância de micro-agentes para uma query específica"""
    
    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.embedding_generator = EmbeddingGenerator()
        self.llm_client = LLMClient()
        self.agent = self._load_agent()
    
    def _load_agent(self) -> Agent:
        """Carrega agente"""
        agent = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
        if not agent:
            raise ValueError(f"Agente {self.agent_id} não encontrado")
        return agent
    
    def evaluate_all_micro_agents(
        self,
        query: str,
        context: Optional[Dict] = None,
        relevance_threshold: float = 0.3
    ) -> Dict[str, Dict]:
        """
        Avalia relevância de todos os micro-agentes para uma query
        
        Retorna: {
            "agent_type": {
                "is_relevant": bool,
                "relevance_score": 0.0-1.0,
                "reason": str,
                "activation_conditions": list
            }
        }
        """
        context = context or {}
        
        # Obter todos os micro-agentes ativos
        micro_agents = self.db.query(MicroAgent).filter(
            MicroAgent.agent_id == self.agent_id,
            MicroAgent.activation_enabled == True
        ).all()
        
        evaluations = {}
        
        for micro_agent in micro_agents:
            agent_type = self.db.query(MicroAgentType).filter(
                MicroAgentType.id == micro_agent.type_id
            ).first()
            
            
            if not agent_type:
                continue
            
            # Avaliar relevância
            is_relevant, score, reason, conditions = self._evaluate_single_agent(
                agent_type,
                query,
                context
            )
            
            evaluations[agent_type.name] = {
                "is_relevant": is_relevant,
                "relevance_score": score,
                "reason": reason,
                "activation_conditions": conditions,
                "should_execute": is_relevant and score >= relevance_threshold
            }
        
        logger.info(f"Avaliação de relevância para {self.agent_id}: {sum(1 for e in evaluations.values() if e['should_execute'])} de {len(evaluations)} agentes")
        
        return evaluations
    
    def _evaluate_single_agent(
        self,
        agent_type: MicroAgentType,
        query: str,
        context: Dict
    ) -> Tuple[bool, float, str, List[str]]:
        """Avalia relevância de um único micro-agente"""
        
        score = 0.0
        reasons = []
        activated_conditions = []
        
        # 1. Verificar condições de ativação
        if agent_type.activation_conditions:
            conditions = agent_type.activation_conditions
            
            # Lógica de ativação baseada em palavras-chave
            keywords_match = self._check_keyword_match(query, conditions.get("keywords", []))
            if keywords_match:
                score += 0.4
                activated_conditions.append("keyword_match")
                reasons.append(f"Query contém palavras-chave: {keywords_match}")
            
            # Lógica de ativação baseada em contexto
            context_match = self._check_context_match(context, conditions.get("context_types", []))
            if context_match:
                score += 0.3
                activated_conditions.append("context_match")
                reasons.append(f"Contexto relevante: {context_match}")
        else:
            # Se não há condições, sempre relevante com score base
            score = 0.5
            reasons.append("Agente sempre ativo (sem condições)")
        
        # 2. Verificar histórico de sucesso
        success_rate = self._get_agent_success_rate(agent_type)
        if success_rate > 0.7:
            score += 0.2
            reasons.append(f"Histórico de sucesso: {success_rate*100:.1f}%")
        
        # 3. Verificar tipo de query
        query_type_match = self._evaluate_query_type(query, agent_type)
        score += query_type_match
        if query_type_match > 0.15:
            reasons.append(f"Match com tipo de query: {agent_type.response_style}")
        
        # 4. Análise semântica com embedding
        semantic_score = self._semantic_relevance(query, agent_type)
        score += semantic_score
        if semantic_score > 0.1:
            reasons.append("Alta relevância semântica")
            activated_conditions.append("semantic_match")
        
        # Normalizar score
        score = min(1.0, score)
        
        is_relevant = score >= 0.3
        final_reason = " | ".join(reasons) if reasons else "Score abaixo do limiar"
        
        return is_relevant, score, final_reason, activated_conditions
    
    def _check_keyword_match(self, query: str, keywords: List[str]) -> Optional[str]:
        """Verifica se query contém palavras-chave"""
        query_lower = query.lower()
        
        for keyword in keywords:
            if keyword.lower() in query_lower:
                return keyword
        
        return None
    
    def _check_context_match(self, context: Dict, context_types: List[str]) -> Optional[str]:
        """Verifica se contexto contém tipos relevantes"""
        for ctx_type in context_types:
            if context.get(ctx_type):
                return ctx_type
        
        return None
    
    def _get_agent_success_rate(self, agent_type: MicroAgentType) -> float:
        """Obtém taxa de sucesso histórico do micro-agente"""
        from data.schema_cognitive import ThoughtContribution
        
        contributions = self.db.query(ThoughtContribution).filter(
            ThoughtContribution.micro_agent_id == agent_type.id
        ).limit(20).all()
        
        if not contributions:
            return 0.5  # Default
        
        # Calcular taxa: decisões onde foi decisive / total
        decisive = sum(1 for c in contributions if c.was_decisive)
        return decisive / len(contributions)
    
    def _evaluate_query_type(self, query: str, agent_type: MicroAgentType) -> float:
        """Avalia match entre tipo de query e estilo de resposta"""
        
        # Mapeamento de tipos de query para micro-agentes
        type_scores = {
            "logical": 0.3 if self._is_analytical_query(query) else 0.05,
            "emotional": 0.3 if self._is_emotional_query(query) else 0.05,
            "critical": 0.3 if self._is_critical_query(query) else 0.05,
            "creative": 0.3 if self._is_creative_query(query) else 0.05,
            "ethical": 0.3 if self._is_ethical_query(query) else 0.05,
            "social": 0.3 if self._is_social_query(query) else 0.05,
        }
        
        return type_scores.get(agent_type.name, 0.1)
    
    def _is_analytical_query(self, query: str) -> bool:
        """Detecta queries analíticas"""
        keywords = ["como", "porque", "explica", "analisa", "calcula", "dados", "estatística"]
        return any(kw in query.lower() for kw in keywords)
    
    def _is_emotional_query(self, query: str) -> bool:
        """Detecta queries emocionais"""
        keywords = ["sente", "emoção", "medo", "alegria", "tristeza", "amor", "ódio", "relação"]
        return any(kw in query.lower() for kw in keywords)
    
    def _is_critical_query(self, query: str) -> bool:
        """Detecta queries críticas"""
        keywords = ["problema", "erro", "risco", "falha", "questiona", "desafio", "mas"]
        return any(kw in query.lower() for kw in keywords)
    
    def _is_creative_query(self, query: str) -> bool:
        """Detecta queries criativas"""
        keywords = ["ideia", "novo", "invenção", "criativo", "diferente", "imagine", "sonho"]
        return any(kw in query.lower() for kw in keywords)
    
    def _is_ethical_query(self, query: str) -> bool:
        """Detecta queries éticas"""
        keywords = ["ético", "moral", "direito", "dever", "justiça", "deve", "correto"]
        return any(kw in query.lower() for kw in keywords)
    
    def _is_social_query(self, query: str) -> bool:
        """Detecta queries sociais"""
        keywords = ["pessoas", "grupo", "comunidade", "sociedade", "relação", "dinâmica"]
        return any(kw in query.lower() for kw in keywords)
    
    def _semantic_relevance(self, query: str, agent_type: MicroAgentType) -> float:
        """Calcula relevância semântica usando embeddings"""
        try:
            # Gerar embeddings
            query_embedding = self.embedding_generator.generate_embedding(query)
            objective_embedding = self.embedding_generator.generate_embedding(
                agent_type.cognitive_objective or agent_type.description or ""
            )
            
            if not query_embedding or not objective_embedding:
                return 0.0
            
            # Calcular similaridade cosseno
            similarity = self._cosine_similarity(query_embedding, objective_embedding)
            
            # Normalizar entre 0 e 0.15 (não dominar outras métricas)
            return min(0.15, max(0.0, similarity * 0.15))
        
        except Exception as e:
            logger.warning(f"Erro ao calcular relevância semântica: {e}")
            return 0.0
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcula similaridade cosseno entre dois vetores"""
        import math
        
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
