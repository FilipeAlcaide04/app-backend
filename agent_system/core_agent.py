"""
Core Agent - Agente central que pondera e sintetiza respostas dos micro-agentes
Garante uma resposta coesa, humanizada e genuinamente envolvente
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import Agent, MicroAgent, Memory, ThoughtProcess, ThoughtContribution
from llm_logic.llm_client import LLMClient
from agent_system.memory_manager_cognitive import MemoryManager
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class CoreAgent:
    """
    Agente central que orquestra a síntese de respostas
    Responsável por:
    1. Ponderar respostas dos micro-agentes
    2. Resolver conflitos e consensos
    3. Garantir humanização genuína
    4. Manter coesão com memória pessoal
    """
    
    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.agent = self._load_agent()
        self.llm_client = LLMClient()
        self.memory_manager = MemoryManager(db, agent_id)
    
    def _load_agent(self) -> Agent:
        """Carrega agente do banco"""
        agent = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
        if not agent:
            raise ValueError(f"Agente {self.agent_id} não encontrado")
        return agent
    
    def synthesize_response(
        self,
        micro_agent_responses: Dict[str, Dict],
        query: str,
        context: Optional[Dict] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sintetiza respostas de micro-agentes em uma ÚNICA resposta humanizada
        
        IMPORTANTE: Retorna UMA resposta coesa, não perspectivas individuais!
        """
        
        context = context or {}
        
        logger.info(f"Core Agent {self.agent_id} sintetizando {len(micro_agent_responses)} perspectivas")
        
        # 1. Analisar consensos e conflitos
        consensus_analysis = self._analyze_consensus(micro_agent_responses)
        
        # 2. Ponderar respostas
        weighted_perspectives = self._weight_perspectives(
            micro_agent_responses,
            query,
            consensus_analysis
        )
        
        # 3. Resolver conflitos inteligentemente
        resolved_perspective = self._resolve_conflicts(
            weighted_perspectives,
            consensus_analysis
        )
        
        # 4. Infundir personalidade e humanização
        humanized_response = self._humanize_response(
            resolved_perspective.get("main_response", ""),
            query,
            user_id,
            context
        )
        
        # 5. Calcular confiança final ponderada
        final_confidence = self._calculate_final_confidence(weighted_perspectives)
        
        # 6. Registrar interação na memória
        if user_id:
            self._record_interaction_memory(
                user_id,
                query,
                humanized_response,
                final_confidence
            )
        
        # 7. Construir resposta FINAL ÚNICA
        final_response_text = self._build_final_response(
            humanized_response,
            context,
            resolved_perspective
        )
        
        return {
            "response": final_response_text,
            "confidence": final_confidence,
            "reasoning": resolved_perspective.get("reasoning", ""),
            "perspectives_count": len(micro_agent_responses),
            "consensus_level": consensus_analysis.get("consensus_score", 0.5),
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": self.agent_id,
            "user_id": user_id,
            "conversation_id": conversation_id
        }
    
    def _build_final_response(
        self,
        humanized_response: str,
        context: Dict,
        resolved_perspective: Dict
    ) -> str:
        """
        Constrói a resposta final ÚNICA e coesa
        Remove toda menção a nomes de agentes
        INCLUI DOCUMENTOS OBRIGATORIAMENTE na resposta
        """
        
        # Usar a resposta humanizada como base
        final_text = humanized_response
        
        # CRÍTICO: Adicionar informação de documentos DENTRO da resposta se disponível
        documents = context.get("documents", {})
        
        logger.info(f"Build final response - documents structure: {documents.get('has_documents', False)}")
        
        if documents and documents.get("has_documents"):
            docs_list = documents.get("documents", [])
            
            logger.info(f"Build final response - found {len(docs_list)} documents")
            
            if docs_list:
                # Montar lista de documentos com links
                docs_text = "\n\n📚 **Documentos consultados:**\n"
                for i, doc in enumerate(docs_list[:3], 1):  # Top 3 documentos
                    filename = doc.get("filename", "Documento Desconhecido")
                    similarity = doc.get("similarity_score", 0)
                    description = doc.get("description", "Sem descrição disponível")
                    
                    # Garantir que temos informação relevante
                    relevance_pct = int(similarity * 100) if isinstance(similarity, float) else int(float(similarity) * 100) if isinstance(similarity, str) else 0
                    
                    docs_text += f"  {i}. **{filename}** (Relevância: {relevance_pct}%) - {description}\n"
                    
                    logger.info(f"Added document: {filename} ({relevance_pct}%)")
                
                final_text += docs_text
                logger.info("Documents successfully added to response")
            else:
                logger.warning("Documents list is empty despite has_documents being True")
        else:
            logger.info("No documents in context or has_documents is False")
        
        return final_text
    
    def _analyze_consensus(self, responses: Dict[str, Dict]) -> Dict[str, Any]:
        """Analisa nível de consenso entre micro-agentes"""
        
        if not responses:
            return {"consensus_score": 0.0, "agreement_count": 0, "conflict_count": 0}
        
        confidences = [r.get("confidence", 0.5) for r in responses.values()]
        avg_confidence = sum(confidences) / len(confidences)
        
        # Consenso alto quando confiança é alta e consistente
        std_dev = self._calculate_std_dev(confidences)
        consensus_score = max(0, avg_confidence - (std_dev * 0.2))
        
        # Contar argumentos pró e contra
        agreement_count = sum(1 for r in responses.values() if r.get("confidence", 0.5) > 0.7)
        conflict_count = sum(1 for r in responses.values() if r.get("confidence", 0.5) < 0.4)
        
        return {
            "consensus_score": consensus_score,
            "agreement_count": agreement_count,
            "conflict_count": conflict_count,
            "avg_confidence": avg_confidence,
            "std_dev": std_dev
        }
    
    def _weight_perspectives(
        self,
        responses: Dict[str, Dict],
        query: str,
        consensus: Dict
    ) -> List[Tuple[str, Dict, float]]:
        """
        Pondera cada perspectiva
        Retorna: [(agent_type, response, final_weight), ...]
        """
        
        weighted = []
        
        for agent_type, response in responses.items():
            # Weight base (do agente)
            base_weight = response.get("weight", 1.0)
            
            # Ajuste por confiança (agentes confiantes tem mais peso)
            confidence = response.get("confidence", 0.5)
            confidence_factor = 0.8 + (confidence * 0.4)  # 0.8 a 1.2
            
            # Ajuste por consenso (se todos concordam, aumentar; se conflita, diminuir)
            if consensus.get("conflict_count", 0) > 0:
                consensus_factor = 0.8 if response.get("confidence", 0.5) > 0.6 else 0.7
            else:
                consensus_factor = 1.2
            
            # Ajuste por relevância histórica
            relevance = self._get_agent_relevance_history(agent_type, query)
            relevance_factor = 0.9 + (relevance * 0.2)
            
            # Calcular peso final
            final_weight = base_weight * confidence_factor * consensus_factor * relevance_factor
            
            weighted.append((agent_type, response, final_weight))
        
        # Normalizar pesos
        total_weight = sum(w for _, _, w in weighted)
        if total_weight > 0:
            weighted = [(t, r, w/total_weight) for t, r, w in weighted]
        
        return sorted(weighted, key=lambda x: x[2], reverse=True)
    
    def _resolve_conflicts(
        self,
        weighted_perspectives: List[Tuple[str, Dict, float]],
        consensus: Dict
    ) -> Dict[str, Any]:
        """
        Resolve conflitos entre perspectivas
        Estratégia: integra conflitos de forma humanizada, não apenas maioria
        """
        
        if not weighted_perspectives:
            return {"reasoning": "Sem perspectivas disponíveis"}
        
        # Se alta discordância, apresentar nuances
        if consensus.get("conflict_count", 0) > len(weighted_perspectives) / 2:
            return self._resolve_with_nuance(weighted_perspectives)
        
        # Se consenso forte, usar perspectiva dominante
        if consensus.get("consensus_score", 0) > 0.7:
            return self._resolve_with_consensus(weighted_perspectives)
        
        # Se consenso moderado, integrar ambos os lados
        return self._resolve_with_balance(weighted_perspectives)
    
    def _resolve_with_nuance(
        self,
        weighted_perspectives: List[Tuple[str, Dict, float]]
    ) -> Dict[str, Any]:
        """Resolve com nuances - apresenta múltiplas perspectivas válidas"""
        
        perspectives_text = []
        reasoning_points = []
        
        for agent_type, response, weight in weighted_perspectives[:4]:  # Top 4
            perspective = response.get("perspective", "")
            if perspective:
                perspectives_text.append(f"({agent_type}): {perspective}")
            
            support = response.get("supporting_arguments", [])
            if support:
                reasoning_points.extend(support)
        
        reasoning = f"Considerando múltiplas perspectivas válidas: {', '.join(reasoning_points)}"
        
        return {
            "main_response": "\n".join(perspectives_text),
            "reasoning": reasoning,
            "approach": "nuanced"
        }
    
    def _resolve_with_consensus(
        self,
        weighted_perspectives: List[Tuple[str, Dict, float]]
    ) -> Dict[str, Any]:
        """Resolve com perspectiva dominante quando há consenso"""
        
        dominant_type, dominant_response, dominant_weight = weighted_perspectives[0]
        
        main_text = dominant_response.get("perspective", "")
        reasoning_points = dominant_response.get("supporting_arguments", [])
        
        # Adicionar perspectivas complementares
        complementary = []
        for agent_type, response, weight in weighted_perspectives[1:3]:
            if weight > 0.1:
                complement = response.get("perspective", "")
                if complement:
                    complementary.append(f"Adicionalmente ({agent_type}): {complement}")
        
        full_response = main_text
        if complementary:
            full_response += "\n\n" + "\n".join(complementary)
        
        reasoning = f"Baseado em análise {dominant_type}: {'; '.join(reasoning_points)}"
        
        return {
            "main_response": full_response,
            "reasoning": reasoning,
            "approach": "consensus"
        }
    
    def _resolve_with_balance(
        self,
        weighted_perspectives: List[Tuple[str, Dict, float]]
    ) -> Dict[str, Any]:
        """Resolve equilibrando perspectivas"""
        
        main_response = weighted_perspectives[0][1].get("perspective", "")
        
        # Incluir perspectivas contrárias de forma equilibrada
        opposing_points = []
        for agent_type, response, weight in weighted_perspectives[1:]:
            opposing = response.get("opposing_arguments", [])
            if opposing and weight > 0.1:
                opposing_points.extend([f"({agent_type}) {opp}" for opp in opposing[:1]])
        
        full_response = main_response
        if opposing_points:
            full_response += f"\n\nContudo, é importante considerar: {'; '.join(opposing_points)}"
        
        reasoning = "Balanceando múltiplas perspectivas válidas"
        
        return {
            "main_response": full_response,
            "reasoning": reasoning,
            "approach": "balanced"
        }
    
    def _humanize_response(
        self,
        base_response: str,
        query: str,
        user_id: Optional[str],
        context: Dict
    ) -> str:
        """
        Transforma resposta em algo genuinamente HUMANO
        - Remove tokens de agentes (social), (logical), etc
        - Adiciona conversação natural
        - Personaliza baseado em contexto
        """
        
        # 1. Remover todos os marcadores de agentes
        response_cleaned = self._remove_agent_markers(base_response)
        
        # 2. Adicionar contexto pessoal do agente
        personal_context = self._get_personal_context(user_id)
        
        # 3. Infundir tom conversacional
        conversational = self._make_conversational(response_cleaned, personal_context)
        
        # 4. Refinar com LLM se possível
        refined = self._refine_with_llm(conversational, query, personal_context)
        
        return refined
    
    def _remove_agent_markers(self, response: str) -> str:
        """Remove menção a agentes (logical), (emotional), etc"""
        
        import re
        
        # Remover padrões como "(logical):", "(emotional):", etc
        cleaned = re.sub(r'\s*\([a-z]+\):\s*', ' ', response)
        
        # Remover "Adicionalmente" repetido
        cleaned = re.sub(r'\s*Adicionalmente\s+', ' ', cleaned)
        
        # Limpar espaços múltiplos
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def _make_conversational(self, text: str, personal_context: Dict) -> str:
        """Torna texto mais conversacional e natural"""
        
        import random
        
        # Se conhece o utilizador, adicionar referência pessoal
        if personal_context.get("user_known"):
            openings = [
                "Com base no que conversámos antes, ",
                "Considerando nosso histórico, ",
                "Lembrando do que falamos, ",
            ]
            text = random.choice(openings) + text
        
        # Adicionar frase de abertura humanizada
        openings = [
            "Deixe-me explicar: ",
            "Ótima pergunta! ",
            "Acho importante mencionar que ",
            "Baseado no que vejo, ",
            "Interessante questão - ",
        ]
        
        # Adicionar só se não começar com maiúscula de certeza
        if not text[0].isupper():
            text = random.choice(openings) + text
        
        return text
    
    def _refine_with_llm(
        self,
        response: str,
        query: str,
        personal_context: Dict
    ) -> str:
        """
        Refina resposta usando LLM para máxima humanização
        """
        
        try:
            # Construir prompt de refinamento humanizado
            prompt = f"""Você é {self.agent.name}, {self.agent.description or 'um assistente inteligente'}.

Seu estilo de comunicação: natural, conversacional, genuinamente interessado.

Query do utilizador: "{query}"

Sua resposta atual:
{response}

Tarefa: Melhore essa resposta mantendo TODO o conteúdo mas tornando-a:
1. Mais natural e conversacional (como se fosse uma pessoa real)
2. Com expressões pessoais genuínas
3. Mostrando interesse real no tópico
4. Sem parecer IA ou robô
5. Sem mencionar nomes de processos (não mencione "micro-agentes", "análise", etc)

Resposta refinada:"""
            
            # Chamar LLM
            refined = self.llm_client.generate(
                prompt,
                max_tokens=800,
                temperature=0.8
            )
            
            return refined.strip()
        
        except Exception as e:
            logger.debug(f"Erro ao refinar com LLM: {e}. Retornando resposta original.")
            return response
    
    def _get_personal_context(self, user_id: Optional[str]) -> Dict[str, Any]:
        """Obtém contexto pessoal do utilizador se disponível"""
        
        if not user_id:
            return {}
        
        # Buscar memórias sobre este utilizador
        memories = self.memory_manager.recall_relevant_memories(
            f"utilizador {user_id}",
            limit=3
        )
        
        if memories:
            return {
                "user_known": True,
                "memories": [m.content for m in memories],
                "interaction_history": len(memories)
            }
    
    def _get_personal_context(self, user_id: Optional[str]) -> Dict[str, Any]:
        """Obtém contexto pessoal do utilizador se disponível"""
        
        if not user_id:
            return {}
        
        # Buscar memórias sobre este utilizador
        memories = self.memory_manager.recall_relevant_memories(
            f"utilizador {user_id}",
            limit=3
        )
        
        if memories:
            return {
                "user_known": True,
                "memories": [m.content for m in memories],
                "interaction_history": len(memories)
            }
        
        return {"user_known": False}
    
    def _get_agent_relevance_history(self, agent_type: str, query: str) -> float:
        """Obtém histórico de relevância do micro-agente"""
        
        from data.schema_cognitive import ThoughtContribution, MicroAgent
        
        # Buscar micro-agente
        micro_agent = self.db.query(MicroAgent).filter(
            MicroAgent.agent_id == self.agent_id
        ).first()
        
        if not micro_agent:
            return 0.5
        
        # Buscar contribuições recentes
        contributions = self.db.query(ThoughtContribution).filter(
            ThoughtContribution.micro_agent_id == micro_agent.id
        ).order_by(ThoughtContribution.id.desc()).limit(10).all()
        
        if not contributions:
            return 0.5
        
        # Calcular relevância: quantas vezes foi decisive
        decisive = sum(1 for c in contributions if c.was_decisive)
        return decisive / len(contributions)
    
    def _calculate_final_confidence(
        self,
        weighted_perspectives: List[Tuple[str, Dict, float]]
    ) -> float:
        """Calcula confiança final ponderada"""
        
        if not weighted_perspectives:
            return 0.3
        
        total_confidence = 0.0
        total_weight = 0.0
        
        for agent_type, response, weight in weighted_perspectives:
            confidence = response.get("confidence", 0.5)
            total_confidence += confidence * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.5
        
        return total_confidence / total_weight
    
    def _record_interaction_memory(
        self,
        user_id: str,
        query: str,
        response: str,
        confidence: float
    ):
        """Registra interação na memória do agente"""
        
        try:
            # Determinar tipo de memória
            memory_type = "episodic" if confidence > 0.7 else "short_term"
            
            memory_title = f"Conversa com {user_id[:12]}"
            memory_content = f"Query: {query}\nResposta (resumida): {response[:200]}..."
            
            # Calcular valência emocional
            emotional_valence = confidence - 0.5  # -0.5 a 0.5
            
            self.memory_manager.create_memory(
                title=memory_title,
                content=memory_content,
                memory_type=memory_type,
                importance_score=confidence,
                emotional_valence=emotional_valence,
                relates_to_topics=["conversation", "interaction", "user_engagement"]
            )
        
        except Exception as e:
            logger.warning(f"Erro ao registrar memória de interação: {e}")
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calcula desvio padrão"""
        
        if not values:
            return 0.0
        
        avg = sum(values) / len(values)
        variance = sum((x - avg) ** 2 for x in values) / len(values)
        
        import math
        return math.sqrt(variance)
