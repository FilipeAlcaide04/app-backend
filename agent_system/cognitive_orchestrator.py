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

        existing_types = set()
        for instance in instances:
            try:
                agent_type = self.db.query(MicroAgentType).filter(
                    MicroAgentType.id == instance.type_id
                ).first()
                if not agent_type:
                    continue
                existing_types.add(agent_type.name)
                micro_agent = create_micro_agent(
                    agent_id=self.agent_id,
                    micro_agent_id=instance.id,
                    thinking_type=agent_type.name,
                    db=self.db,
                )
                micro_agents[agent_type.name] = micro_agent
            except Exception as e:
                logger.error(f"Erro ao inicializar micro-agente {instance.id}: {e}")

        # Auto-add missing builtin micro-agents
        required = ["memory_curator", "imagination"]
        for type_name in required:
            if type_name not in existing_types:
                try:
                    agent_type = self.db.query(MicroAgentType).filter(
                        MicroAgentType.name == type_name
                    ).first()
                    if agent_type:
                        from uuid import uuid4
                        new_instance = MicroAgent(
                            id=str(uuid4()),
                            agent_id=self.agent_id,
                            type_id=agent_type.id,
                            custom_weight=agent_type.default_weight,
                            activation_enabled=True,
                        )
                        self.db.add(new_instance)
                        self.db.flush()
                        micro_agent = create_micro_agent(
                            agent_id=self.agent_id,
                            micro_agent_id=new_instance.id,
                            thinking_type=type_name,
                            db=self.db,
                        )
                        micro_agents[type_name] = micro_agent
                        logger.info(f"[init] Auto-added missing micro-agent: {type_name}")
                except Exception as e:
                    logger.warning(f"[init] Failed to auto-add {type_name}: {e}")

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

        logger.info(f"[think] agente={self.agent_id} query=\"{query[:60]}...\"")
        context = context or {}
        start_time = datetime.utcnow()
        context["latest_user_query"] = query

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
        context["conversation_memory"] = conv_context.get("live_memory", {})
        context["conversation_thread"] = self._build_conversation_thread(context["conversation_history"])

        # Estado da última sessão (para continuidade emocional)
        last_state = self.conversations.get_last_session_state(user_id or "default_user")
        if last_state:
            context["last_session"] = last_state

        # === FASE 1: RELEVÂNCIA ===
        relevance_scores = self.relevance_evaluator.evaluate_all_micro_agents(query, context)
        relevant_agents = {
            k: v for k, v in relevance_scores.items() if v.get("should_execute")
        }

        logger.info(f"[FASE 1] RELEVÂNCIA: Avaliando {len(self.micro_agents)} micro-agentes")
        for agent_name, score_info in relevance_scores.items():
            logger.debug(f"  • {agent_name}: score={score_info.get('score', 0):.2f}, relevante={score_info.get('should_execute', False)}, razão={score_info.get('reason', 'N/A')}")

        if not relevant_agents:
            relevant_agents = self.micro_agents
            logger.debug(f"[FASE 1] Nenhum agente específico relevante. Usando todos: {list(self.micro_agents.keys())}")
        else:
            self.micro_agents = {
                k: v for k, v in self.micro_agents.items() if k in relevant_agents
            }
            logger.info(f"[FASE 1] ✓ Selecionados {len(self.micro_agents)} agentes para pensar: {list(self.micro_agents.keys())}")

        # === FASE 2: DOCUMENTOS ===
        doc_context = {}
        if self.document_awareness.should_consult_documents(query):
            logger.info(f"[FASE 2] DOCUMENTOS: Consultando base de documentos...")
            doc_context = self.document_awareness.get_document_context_for_agent(query)
            if doc_context.get("has_documents"):
                context["documents"] = doc_context
                logger.info(f"[FASE 2] ✓ Documentos encontrados: {doc_context.get('document_count', 0)} docs, relevância={doc_context.get('relevance_score', 0):.2f}")
                logger.debug(f"[FASE 2]   Contexto: {doc_context.get('context_text', '')[:200]}...")
            else:
                logger.debug(f"[FASE 2] Nenhum documento relevante encontrado")
        else:
            logger.debug(f"[FASE 2] DOCUMENTOS: Não necessário consultar documentos para esta pergunta")

        # === FASE 3: MEMÓRIAS ===
        conversation_memory_text = json.dumps(context.get("conversation_memory", {}), ensure_ascii=False)
        memory_query = f"{conversation_memory_text}\n{context.get('conversation_thread', '')}\n{query}".strip()
        memory_awareness = self.memory_manager.build_memory_awareness(
            query=query,
            conversation_context=memory_query,
        )
        memories = memory_awareness.get("memories", [])
        context["memory"] = [
            {
                "id": mem.id, "title": mem.title, "content": mem.content,
                "memory_type": mem.type.name if mem.type else "unknown",
                "importance_score": mem.importance_score,
                "emotional_valence": mem.emotional_valence,
            }
            for mem in memories
        ]
        context["existing_memories"] = context["memory"]
        context["memory_awareness"] = memory_awareness.get("summary", "")

        logger.info(
            f"[FASE 3] MEMÓRIAS: Recuperadas {len(memories)} memórias relevantes "
            f"({memory_awareness.get('total_considered', len(memories))} consideradas)"
        )
        if context["memory_awareness"]:
            logger.info(f"[FASE 3] Consciência de memória:\n{context['memory_awareness']}")
        for i, mem in enumerate(memories, 1):
            logger.info(f"  {i}. [{mem.type.name if mem.type else '?'}] {mem.title}")
            logger.debug(f"     - Importância: {mem.importance_score:.2f}, Valência Emocional: {mem.emotional_valence}")
            logger.debug(f"     - Conteúdo: {mem.content[:100]}...")
        
        if not memories:
            logger.debug(f"[FASE 3] Nenhuma memória relevante encontrada para: '{query[:50]}...'")

        # Identidade e estado
        context["agent_identity"] = self.get_agent_identity()

        # Relação com o utilizador (disponível para todos os micro-agentes)
        if user_id:
            context["relationship_snapshot"] = self.identity.get_relationship_snapshot(user_id)
            context["user_id"] = user_id

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

        logger.info(f"[FASE 4] EMOCIONAL: Emoção detectada = {emotional_reaction.get('emotional_reaction', 'neutro')}")
        logger.info(f"  - Intensidade: {emotional_reaction.get('intensity', 0):.0%}")
        logger.info(f"  - Humor atual: {emotional_reaction.get('current_mood', 'N/A')}")
        logger.info(f"  - Modificador de resposta: {emotional_reaction.get('response_modifier', 'nenhum')}")
        logger.debug(f"[FASE 4] Contexto emocional: {json.dumps(emotional_context, ensure_ascii=False)[:150]}...")

        # === FASE 5: REDE NEURAL ===
        neural_modifiers = self.neural_network.get_micro_agent_modifiers(query, context)
        logger.info(f"[FASE 5] REDE NEURAL: Modificadores calculados")
        for agent_name, modifiers in neural_modifiers.items():
            logger.debug(f"  • {agent_name}: {json.dumps(modifiers, ensure_ascii=False)}")

        # Registar processo
        if record_process:
            self.thought_process = ThoughtProcess(
                agent_id=self.agent_id,
                conversation_id=session.id,
                query=query,
                context=context,
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
        live_mem = context.get("conversation_memory", {})
        self.conversations.update_session_metadata(
            session,
            topic=live_mem.get("current_topic") or None,
            emotional_tone=emotional_reaction.get("current_mood"),
            unresolved=live_mem.get("pending_user_question") or None,
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
            logger.info(f"[FASE 10] APRENDIZAGEM: Interação registada (ID: {interaction_id})")
        except Exception as e:
            logger.warning(f"[FASE 10] Erro ao registar aprendizagem: {e}")

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Adicionar metadata
        final_response["duration_ms"] = duration_ms
        final_response["interaction_id"] = interaction_id
        final_response["emotional_state"] = self.emotions.get_emotional_summary()
        final_response["emotional_reaction"] = emotional_reaction.get("emotional_reaction")
        final_response["conversation_id"] = session.id
        final_response["persona_state"] = self.persona.get_state_summary() if self.persona.has_persona else None

        # === RESUMO FINAL ===
        logger.info(f"✅ PROCESSO COMPLETO")
        logger.info(f"   ⏱️  Tempo total: {duration_ms}ms")
        logger.info(f"   📊 Memórias usadas: {len(memories)} de {len(context.get('memory', []))}")
        logger.info(f"   🧠 Micro-agentes: {len(thinking_results)} pensando em paralelo")
        logger.info(f"   💬 Resposta final completa:\n{agent_response_text}")
        logger.info(f"   🎯 Confiança: {final_response.get('confidence', 0):.0%}")

        return final_response

    def _build_conversation_thread(self, messages: List[Dict[str, Any]], limit: int = 6) -> str:
        if not messages:
            return ""

        persona_name = self.agent.name or "Persona"
        recent = messages[-limit:]
        parts = []
        for msg in recent:
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            label = "Utilizador" if role == "user" else persona_name if role == "assistant" else role
            parts.append(f"{label}: {content[:240]}")
        return "\n".join(parts)

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

        logger.info(f"[FASE 6.1] PENSAMENTO PARALELO: Iniciando {len(self.micro_agents)} micro-agentes em paralelo")
        
        tasks = {}
        for agent_type, micro_agent in self.micro_agents.items():
            modifier = neural_modifiers.get(agent_type, {})
            logger.debug(f"  ⚙️  {agent_type}: inicializado (peso_base={micro_agent.get_weight():.2f}, modificador={modifier.get('weight_modifier', 1.0):.2f}x)")
            tasks[agent_type] = asyncio.create_task(
                self._think_async_enhanced(micro_agent, query, context, modifier)
            )

        results = {}
        for agent_type, task in tasks.items():
            try:
                result = await task
                results[agent_type] = result
                logger.info(f"[FASE 6.1] ✓ {agent_type} pensamento completo: confiança={result.get('confidence', 0):.2f}, peso={result.get('weight', 1.0):.2f}")
                logger.info(
                    f"[FASE 6.1][OUTPUT COMPLETO] {agent_type}\n"
                    f"{result.get('perspective', 'N/A')}"
                )
            except Exception as e:
                logger.error(f"[FASE 6.1] ✗ Erro em {agent_type}: {e}")
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
            logger.debug(f"[PENSAMENTO] {micro_agent.thinking_type.value}: ativadas {neural_modifier['memory_count']} memórias")

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
            "language": self.agent.language,
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
