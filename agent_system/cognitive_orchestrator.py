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

from sqlalchemy.orm import Session, sessionmaker
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
        self._session_factory = sessionmaker(bind=db.get_bind())
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
        Pipeline optimizado com fases paralelas onde possível.
        """

        logger.info(f"[think] agente={self.agent_id} query=\"{query[:60]}...\"")
        context = context or {}
        start_time = datetime.utcnow()
        context["latest_user_query"] = query
        loop = asyncio.get_event_loop()

        # === FASE 0: CONTEXTO DE CONVERSA (rápido, só DB) ===
        session = self.conversations.get_or_create_session(
            conversation_id=conversation_id,
            user_id=user_id or "default_user"
        )
        self.conversations.add_message(session, "user", query)

        # Carregar mensagens e sessões anteriores (DB only, rápido)
        current_messages = self.conversations.get_recent_context(session, n_messages=15)
        context["conversation_history"] = current_messages
        context["conversation_thread"] = self._build_conversation_thread(current_messages)

        last_state = self.conversations.get_last_session_state(user_id or "default_user")
        if last_state:
            context["last_session"] = last_state

        # Sessões anteriores (DB only)
        from data.schema_cognitive import ConversationSession
        previous = self.db.query(ConversationSession).filter(
            ConversationSession.agent_id == self.agent_id,
            ConversationSession.user_id == session.user_id,
            ConversationSession.id != session.id,
            ConversationSession.is_active == False
        ).order_by(ConversationSession.ended_at.desc()).limit(3).all()
        context["previous_sessions"] = [
            {"date": p.ended_at.isoformat() if p.ended_at else "?",
             "summary": p.summary, "topic": p.current_topic,
             "tone": p.emotional_tone, "messages": p.message_count or 0}
            for p in previous if p.summary
        ]

        # Identidade e estado (rápido, só leitura)
        context["agent_identity"] = self.get_agent_identity()
        if user_id:
            context["relationship_snapshot"] = self.identity.get_relationship_snapshot(user_id)
            context["user_id"] = user_id

        # ============================================================
        # BLOCO PARALELO 1: Live Memory (LLM) + Relevância (embeddings) + Documentos (embeddings) + Emocional (LLM)
        # Todas independentes entre si neste ponto
        # ============================================================
        logger.info(f"[PARALELO 1] Lançando: live_memory + relevância + documentos + emocional")

        async def _live_memory():
            def _run():
                thread_db = self._session_factory()
                try:
                    cm = ConversationManager(thread_db, self.agent_id)
                    return cm.build_live_conversation_memory(current_messages)
                finally:
                    thread_db.close()
            return await loop.run_in_executor(None, _run)

        async def _relevance():
            def _run():
                thread_db = self._session_factory()
                try:
                    re = RelevanceEvaluator(thread_db, self.agent_id)
                    return re.evaluate_all_micro_agents(query, context)
                finally:
                    thread_db.close()
            return await loop.run_in_executor(None, _run)

        async def _documents():
            if not self.document_awareness.should_consult_documents(query):
                return {}
            def _run():
                thread_db = self._session_factory()
                try:
                    da = DocumentAwareness(thread_db, self.agent_id)
                    return da.get_document_context_for_agent(query)
                finally:
                    thread_db.close()
            return await loop.run_in_executor(None, _run)

        async def _emotional():
            def _run():
                thread_db = self._session_factory()
                try:
                    em = EmotionalEngine(thread_db, self.agent_id)
                    return em.process_interaction(query, "", user_id)
                finally:
                    thread_db.close()
            return await loop.run_in_executor(None, _run)

        live_mem_task = asyncio.create_task(_live_memory())
        relevance_task = asyncio.create_task(_relevance())
        documents_task = asyncio.create_task(_documents())
        emotional_task = asyncio.create_task(_emotional())

        conversation_memory, relevance_scores, doc_context, emotional_reaction = await asyncio.gather(
            live_mem_task, relevance_task, documents_task, emotional_task
        )

        # Processar resultados do bloco paralelo 1
        context["conversation_memory"] = conversation_memory or {}

        # Relevância
        relevant_agents = {k: v for k, v in relevance_scores.items() if v.get("should_execute")}
        logger.info(f"[FASE 1] RELEVÂNCIA: Avaliando {len(self.micro_agents)} micro-agentes")
        if not relevant_agents:
            relevant_agents = self.micro_agents
        else:
            self.micro_agents = {k: v for k, v in self.micro_agents.items() if k in relevant_agents}
        logger.info(f"[FASE 1] ✓ Selecionados {len(self.micro_agents)} agentes: {list(self.micro_agents.keys())}")

        # Documentos
        if doc_context.get("has_documents"):
            context["documents"] = doc_context
            context["documents_context"] = doc_context.get("context_text", "")
            logger.info(f"[FASE 2] ✓ Documentos: {doc_context.get('document_count', 0)} encontrados")

        # Emocional
        emotional_context = self.emotions.get_emotional_context_for_prompt(
            response_modifier=emotional_reaction.get("response_modifier")
        )
        context["emotional_context"] = emotional_context
        context["emotional_modifiers"] = self.emotions.get_emotional_modifiers()
        context["emotional_reaction"] = emotional_reaction
        logger.info(f"[FASE 4] EMOCIONAL: {emotional_reaction.get('emotional_reaction', 'neutro')} "
                     f"({emotional_reaction.get('intensity', 0):.0%}), humor={emotional_reaction.get('current_mood', 'N/A')}")

        # ============================================================
        # BLOCO PARALELO 2: Memory Awareness (LLM) + Neural Modifiers (embeddings)
        # Memory awareness precisa do conversation_memory que já temos
        # ============================================================
        logger.info(f"[PARALELO 2] Lançando: memory_awareness + rede_neural")

        conversation_memory_text = json.dumps(context.get("conversation_memory", {}), ensure_ascii=False)
        memory_query = f"{conversation_memory_text}\n{context.get('conversation_thread', '')}\n{query}".strip()

        async def _memory_awareness():
            def _run():
                thread_db = self._session_factory()
                try:
                    mm = MemoryManager(thread_db, self.agent_id)
                    return mm.build_memory_awareness(query, memory_query)
                finally:
                    thread_db.close()
            return await loop.run_in_executor(None, _run)

        async def _neural_modifiers():
            def _run():
                thread_db = self._session_factory()
                try:
                    nn = NeuralNetworkLayer(thread_db, self.agent_id)
                    return nn.get_micro_agent_modifiers(query, context)
                finally:
                    thread_db.close()
            return await loop.run_in_executor(None, _run)

        memory_task = asyncio.create_task(_memory_awareness())
        neural_task = asyncio.create_task(_neural_modifiers())

        memory_awareness, neural_modifiers = await asyncio.gather(memory_task, neural_task)

        # Processar memórias
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

        logger.info(f"[FASE 3] MEMÓRIAS: {len(memories)} recuperadas ({memory_awareness.get('total_considered', len(memories))} consideradas)")
        if context["memory_awareness"]:
            logger.info(f"[FASE 3] Consciência de memória:\n{context['memory_awareness']}")
        for i, mem in enumerate(memories, 1):
            logger.info(f"  {i}. [{mem.type.name if mem.type else '?'}] {mem.title}")

        logger.info(f"[FASE 5] REDE NEURAL: Modificadores calculados")

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

        # === FASE 6: PENSAMENTO PARALELO DOS MICRO-AGENTES ===
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

        live_mem = context.get("conversation_memory", {})
        self.conversations.update_session_metadata(
            session,
            topic=live_mem.get("current_topic") or None,
            emotional_tone=emotional_reaction.get("current_mood"),
            unresolved=live_mem.get("pending_user_question") or None,
        )

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # === FASE 9+10: REGISTAR PROCESSO + APRENDIZAGEM (async, não bloqueia resposta) ===
        interaction_id = None
        try:
            interaction_id = self.learning.record_interaction(
                query=query, response=agent_response_text,
                user_id=user_id, context=context
            )
        except Exception as e:
            logger.warning(f"[APRENDIZAGEM] Erro ao registar: {e}")

        async def _post_response_tasks():
            try:
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

                def _background_memory_and_learning():
                    thread_db = self._session_factory()
                    try:
                        # 1. Auto-gerar memórias (nome, factos, emocionais)
                        bg_core = CoreAgent(thread_db, self.agent_id)
                        bg_core._auto_generate_memories(query, agent_response_text, context, user_id)

                        # 2. Auto-reflexão
                        bg_core._self_reflect(query, agent_response_text, context, user_id)

                        # 3. Learning memory
                        nn = NeuralNetworkLayer(thread_db, self.agent_id)
                        nn.create_learning_memory(
                            "reasoning",
                            final_response.get("confidence", 0.5) > 0.6,
                            query, agent_response_text,
                            final_response.get("confidence", 0.5),
                            {"user_id": user_id}
                        )
                    finally:
                        thread_db.close()

                await loop.run_in_executor(None, _background_memory_and_learning)
                logger.info(f"[ASYNC] Memórias + reflexão + aprendizagem registados (ID: {interaction_id})")
            except Exception as e:
                logger.warning(f"[ASYNC] Erro em tarefas pós-resposta: {e}")

        asyncio.create_task(_post_response_tasks())

        # Adicionar metadata
        final_response["duration_ms"] = duration_ms
        final_response["interaction_id"] = interaction_id
        final_response["emotional_state"] = self.emotions.get_emotional_summary()
        final_response["emotional_reaction"] = emotional_reaction.get("emotional_reaction")
        final_response["conversation_id"] = session.id
        final_response["persona_state"] = self.persona.get_state_summary() if self.persona.has_persona else None

        # Micro-agent thoughts for frontend brain visualization
        final_response["thought_contributions"] = [
            {
                "agent_type": agent_type,
                "perspective": result.get("perspective", ""),
                "confidence": result.get("confidence", 0.5),
                "weight": result.get("weight", 1.0),
                "supporting_arguments": result.get("supporting_arguments", []),
                "opposing_arguments": result.get("opposing_arguments", []),
            }
            for agent_type, result in thinking_results.items()
        ]

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
        def _run():
            thread_db = self._session_factory()
            try:
                thread_agent = create_micro_agent(
                    self.agent_id, micro_agent.micro_agent_id,
                    micro_agent.thinking_type.value, thread_db
                )
                return thread_agent.think(query, enhanced_context)
            finally:
                thread_db.close()
        result = await loop.run_in_executor(None, _run)

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
