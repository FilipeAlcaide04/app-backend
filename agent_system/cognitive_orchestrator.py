"""
Cognitive Orchestrator v2 - Integra persona completa no processo de pensamento

Pipeline:
1. Carregar persona + estado dinâmico
2. Avaliar relevância de micro-agentes
3. Consultar documentos se relevante
4. Activar memórias + contexto emocional
5. Análise emocional com persona completa
6. Rede neural + modificadores
7. Pensamento paralelo dos micro-agentes
8. Síntese pelo Core Agent (com pensamento autónomo)
9. Actualizar estado dinâmico
10. Registar aprendizagem + memórias automáticas
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import (
    Agent, MicroAgent, MicroAgentType, ThoughtProcess, ThoughtContribution,
    Memory, MemoryType
)
from agent_system.base_micro_agent import create_micro_agent, BaseMicroAgent
from agent_system.memory_manager_cognitive import MemoryManager
from agent_system.relevance_evaluator import RelevanceEvaluator
from agent_system.core_agent import CoreAgent
from agent_system.document_awareness import DocumentAwareness
from agent_system.neural_network_layer import NeuralNetworkLayer
from agent_system.identity_builder import IdentityBuilder
from agent_system.learning_engine import LearningEngine
from agent_system.emotional_engine import EmotionalEngine
from agent_system.persona_engine import PersonaEngine
from agent_system.conversation_manager import ConversationManager
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class CognitiveOrchestrator:
    """Orquestra pensamento cognitivo com persona completa"""

    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.agent = self._load_agent()
        self.memory_manager = MemoryManager(db, agent_id)
        self.micro_agents = self._initialize_micro_agents()
        self.thought_process = None

        # Componentes core
        self.relevance_evaluator = RelevanceEvaluator(db, agent_id)
        self.core_agent = CoreAgent(db, agent_id)
        self.document_awareness = DocumentAwareness(db, agent_id)
        self.neural_network = NeuralNetworkLayer(db, agent_id)

        # Componentes persona
        self.identity = IdentityBuilder(db, agent_id)
        self.learning = LearningEngine(db, agent_id)
        self.emotions = EmotionalEngine(db, agent_id)
        self.persona = PersonaEngine(db, agent_id)
        self.conversations = ConversationManager(db, agent_id)

    def _load_agent(self) -> Agent:
        agent = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
        if not agent:
            raise ValueError(f"Agente {self.agent_id} não encontrado")
        return agent

    def _initialize_micro_agents(self) -> Dict[str, BaseMicroAgent]:
        micro_agents = {}
        instances = self.db.query(MicroAgent).filter(
            MicroAgent.agent_id == self.agent_id,
            MicroAgent.activation_enabled == True
        ).all()

        for instance in instances:
            try:
                agent_type = self.db.query(MicroAgentType).filter(
                    MicroAgentType.id == instance.type_id
                ).first()
                if not agent_type:
                    continue
                micro_agent = create_micro_agent(
                    agent_id=self.agent_id,
                    micro_agent_id=instance.id,
                    thinking_type=agent_type.name,
                    db=self.db,
                )
                micro_agents[agent_type.name] = micro_agent
            except Exception as e:
                logger.error(f"Erro ao inicializar micro-agente {instance.id}: {e}")

        return micro_agents

    async def think(
        self,
        query: str,
        context: Optional[Dict] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        record_process: bool = True
    ) -> Dict[str, Any]:
        """
        Processo de pensamento cognitivo COMPLETO com persona.
        """

        logger.info(f"Agente {self.agent_id} iniciando pensamento")
        context = context or {}
        start_time = datetime.utcnow()

        # === FASE 0: CONTEXTO DE CONVERSA ===
        # Obter sessão de conversa e contexto de sessões anteriores
        session = self.conversations.get_or_create_session(
            conversation_id=conversation_id,
            user_id=user_id or "default_user"
        )

        # Adicionar mensagem do user à sessão
        self.conversations.add_message(session, "user", query)

        # Carregar contexto de conversa
        conv_context = self.conversations.build_conversation_context(session)
        context["conversation_history"] = conv_context.get("current_messages", [])
        context["previous_sessions"] = conv_context.get("previous_sessions", [])

        # Estado da última sessão (para continuidade emocional)
        last_state = self.conversations.get_last_session_state(user_id or "default_user")
        if last_state:
            context["last_session"] = last_state

        # === FASE 1: RELEVÂNCIA ===
        relevance_scores = self.relevance_evaluator.evaluate_all_micro_agents(query, context)
        relevant_agents = {
            k: v for k, v in relevance_scores.items() if v.get("should_execute")
        }

        if not relevant_agents:
            relevant_agents = self.micro_agents
        else:
            self.micro_agents = {
                k: v for k, v in self.micro_agents.items() if k in relevant_agents
            }

        # === FASE 2: DOCUMENTOS ===
        doc_context = {}
        if self.document_awareness.should_consult_documents(query):
            doc_context = self.document_awareness.get_document_context_for_agent(query)
            if doc_context.get("has_documents"):
                context["documents"] = doc_context

        # === FASE 3: MEMÓRIAS ===
        memories = self.memory_manager.recall_relevant_memories(query, limit=5)
        context["memory"] = [
            {
                "id": mem.id, "title": mem.title, "content": mem.content,
                "memory_type": mem.type.name if mem.type else "unknown",
                "importance_score": mem.importance_score,
                "emotional_valence": mem.emotional_valence,
            }
            for mem in memories
        ]

        # Identidade e estado
        context["agent_identity"] = self.get_agent_identity()

        if doc_context.get("has_documents"):
            context["documents_context"] = doc_context.get("context_text", "")

        # === FASE 4: ANÁLISE EMOCIONAL ===
        emotional_reaction = self.emotions.process_interaction(
            user_message=query,
            agent_response="",
            user_id=user_id
        )

        emotional_context = self.emotions.get_emotional_context_for_prompt(
            response_modifier=emotional_reaction.get("response_modifier")
        )

        context["emotional_context"] = emotional_context
        context["emotional_modifiers"] = self.emotions.get_emotional_modifiers()
        context["emotional_reaction"] = emotional_reaction

        if emotional_reaction.get("intensity", 0) > 0.3:
            logger.info(f"Reacção emocional: {emotional_reaction.get('emotional_reaction')} "
                       f"(intensidade: {emotional_reaction.get('intensity', 0):.0%})")

        # === FASE 5: REDE NEURAL ===
        neural_modifiers = self.neural_network.get_micro_agent_modifiers(query, context)

        # Registar processo
        if record_process:
            self.thought_process = ThoughtProcess(
                agent_id=self.agent_id,
                query=query,
                status="thinking",
                start_time=start_time,
            )
            self.db.add(self.thought_process)
            self.db.flush()

        # === FASE 6: PENSAMENTO PARALELO ===
        thinking_results = await self._run_micro_agents_parallel_enhanced(
            query, context, neural_modifiers
        )

        if record_process and self.thought_process:
            self.thought_process.status = "synthesizing"
            self.db.commit()

        # === FASE 7: SÍNTESE PELO CORE AGENT ===
        final_response = self.core_agent.synthesize_response(
            thinking_results, query, context, user_id, conversation_id
        )

        # === FASE 8: REGISTAR NA CONVERSA ===
        agent_response_text = final_response.get("response", "")
        self.conversations.add_message(
            session, "assistant", agent_response_text,
            detected_emotion=emotional_reaction.get("emotional_reaction"),
            importance=final_response.get("confidence", 0.5)
        )

        # Actualizar metadata da sessão
        self.conversations.update_session_metadata(
            session,
            emotional_tone=emotional_reaction.get("current_mood"),
        )

        # === FASE 9: REGISTAR PROCESSO ===
        if record_process and self.thought_process:
            self.thought_process.status = "completed"
            self.thought_process.end_time = datetime.utcnow()
            self.thought_process.final_response = agent_response_text
            self.thought_process.confidence = final_response.get("confidence")
            self.thought_process.reasoning = final_response.get("reasoning")
            self.db.commit()

            for i, (agent_type, result) in enumerate(thinking_results.items()):
                contribution = ThoughtContribution(
                    thought_process_id=self.thought_process.id,
                    micro_agent_id=self._get_micro_agent_id(agent_type),
                    thinking_step=i,
                    perspective=result.get("perspective", ""),
                    confidence=result.get("confidence", 0.5),
                    supporting_arguments=result.get("supporting_arguments", []),
                    opposing_arguments=result.get("opposing_arguments", []),
                    weight_in_decision=result.get("weight", 1.0),
                    was_decisive=result.get("was_decisive", False),
                )
                self.db.add(contribution)
            self.db.commit()

        # === FASE 10: APRENDIZAGEM ===
        interaction_id = None
        try:
            interaction_id = self.learning.record_interaction(
                query=query,
                response=agent_response_text,
                user_id=user_id,
                context=context
            )
            self.neural_network.create_learning_memory(
                interaction_type="reasoning",
                success=final_response.get("confidence", 0.5) > 0.6,
                query=query,
                response=agent_response_text,
                confidence=final_response.get("confidence", 0.5),
                user_context={"user_id": user_id}
            )
        except Exception as e:
            logger.warning(f"Erro ao registrar aprendizado: {e}")

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Adicionar metadata
        final_response["duration_ms"] = duration_ms
        final_response["interaction_id"] = interaction_id
        final_response["emotional_state"] = self.emotions.get_emotional_summary()
        final_response["emotional_reaction"] = emotional_reaction.get("emotional_reaction")
        final_response["conversation_id"] = session.id
        final_response["persona_state"] = self.persona.get_state_summary() if self.persona.has_persona else None

        return final_response

    def process_feedback(
        self,
        interaction_id: str,
        feedback_type: str,
        feedback_score: float = 0.0,
        feedback_text: Optional[str] = None
    ) -> Dict[str, Any]:
        return self.learning.process_feedback(
            interaction_id=interaction_id,
            feedback_type=feedback_type,
            feedback_score=feedback_score,
            feedback_text=feedback_text
        )

    async def _run_micro_agents_parallel_enhanced(
        self, query: str, context: Dict, neural_modifiers: Dict
    ) -> Dict[str, Dict]:

        tasks = {}
        for agent_type, micro_agent in self.micro_agents.items():
            modifier = neural_modifiers.get(agent_type, {})
            tasks[agent_type] = asyncio.create_task(
                self._think_async_enhanced(micro_agent, query, context, modifier)
            )

        results = {}
        for agent_type, task in tasks.items():
            try:
                result = await task
                results[agent_type] = result
            except Exception as e:
                logger.error(f"Erro em {agent_type}: {e}")
                results[agent_type] = self._error_result(e)

        return results

    async def _think_async_enhanced(
        self, micro_agent: BaseMicroAgent, query: str, context: Dict, neural_modifier: Dict
    ) -> Dict:

        enhanced_context = context.copy()
        if neural_modifier.get("memory_count", 0) > 0:
            enhanced_context["neural_prompt"] = (
                f"Influenciado por {neural_modifier['memory_count']} memória(s). "
                f"Peso: {neural_modifier.get('weight_modifier', 1.0):.1f}x"
            )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, micro_agent.think, query, enhanced_context)

        base_weight = micro_agent.get_weight()
        result["weight"] = base_weight * neural_modifier.get("weight_modifier", 1.0)
        result["confidence"] = max(0.0, min(1.0,
            result.get("confidence", 0.5) + neural_modifier.get("confidence_modifier", 0.0)))
        result["agent_type"] = micro_agent.thinking_type.value

        return result

    def _get_micro_agent_id(self, agent_type: str) -> str:
        if agent_type in self.micro_agents:
            return self.micro_agents[agent_type].micro_agent_id
        return "unknown"

    def _error_result(self, error: Exception) -> Dict:
        return {
            "perspective": f"Erro: {str(error)}",
            "confidence": 0.0,
            "supporting_arguments": [],
            "opposing_arguments": [],
            "error": True,
        }

    def get_agent_identity(self) -> Dict[str, Any]:
        base = {
            "id": self.agent.id,
            "name": self.agent.name,
            "personality_traits": self.agent.personality_traits,
            "base_values": self.agent.base_values,
            "thinking_style": self.agent.thinking_style,
            "micro_agents_count": len(self.micro_agents),
            "active_micro_agents": list(self.micro_agents.keys()),
        }

        if self.persona.has_persona:
            base["has_full_persona"] = True
            base["persona_state"] = self.persona.get_state_summary()

        return base

    def update_emotional_state(self, emotions: Dict[str, float]):
        self.agent.current_emotional_state = emotions
        self.agent.updated_at = datetime.utcnow()
        self.db.commit()
