"""
Cognitive Orchestrator - Orquestra micro-agentes funcionando em paralelo
Simula debate interno e processo de decisão humana com NOVA arquitetura humanizada
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
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class CognitiveOrchestrator:
    """Orquestra pensamento cognitivo completo de um agente com arquitetura humanizada"""
    
    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.agent = self._load_agent()
        self.memory_manager = MemoryManager(db, agent_id)
        self.micro_agents = self._initialize_micro_agents()
        self.thought_process = None
        
        # Componentes da nova arquitetura
        self.relevance_evaluator = RelevanceEvaluator(db, agent_id)
        self.core_agent = CoreAgent(db, agent_id)
        self.document_awareness = DocumentAwareness(db, agent_id)
        self.neural_network = NeuralNetworkLayer(db, agent_id)
    
    def _load_agent(self) -> Agent:
        """Carrega agente do banco"""
        agent = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
        if not agent:
            raise ValueError(f"Agente {self.agent_id} não encontrado")
        return agent
    
    def _initialize_micro_agents(self) -> Dict[str, BaseMicroAgent]:
        """Carrega micro-agentes deste agente"""
        micro_agents = {}
        
        instances = self.db.query(MicroAgent).filter(
            MicroAgent.agent_id == self.agent_id,
            MicroAgent.activation_enabled == True
        ).all()
        
        for instance in instances:
            try:
                # Buscar tipo de micro-agente
                agent_type = self.db.query(MicroAgentType).filter(
                    MicroAgentType.id == instance.type_id
                ).first()
                
                if not agent_type:
                    continue
                
                # Criar instância
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
        Executa processo de pensamento cognitivo HUMANIZADO e inteligente
        
        NOVA ARQUITETURA:
        1. Avaliação de Relevância - Determina quais agentes executar
        2. Consulta de Documentos - Se relevante, busca documentos
        3. Pensamento Paralelo - Agentes escolhidos pensam em paralelo
        4. Modificação Neural - Memórias modificam pesos e respostas
        5. Síntese pelo Core Agent - Resposta humanizada e ponderada
        6. Gravação em Memória - Aprendizado para futuras interações
        """
        
        logger.info(f"🧠 Agente {self.agent_id} iniciando processo de pensamento")
        
        context = context or {}
        start_time = datetime.utcnow()
        
        # === FASE 1: AVALIAÇÃO DE RELEVÂNCIA ===
        logger.debug("Fase 1: Avaliando relevância de micro-agentes...")
        relevance_scores = self.relevance_evaluator.evaluate_all_micro_agents(query, context)
        
        # Filtrar apenas agentes relevantes
        relevant_agents = {
            agent_type: score for agent_type, score in relevance_scores.items()
            if score["should_execute"]
        }
        
        logger.info(f"✓ {len(relevant_agents)} de {len(relevance_scores)} agentes são relevantes")
        
        if not relevant_agents:
            logger.warning("Nenhum agente relevante! Usando todos.")
            relevant_agents = self.micro_agents
        else:
            # Filtrar micro_agents para apenas os relevantes
            self.micro_agents = {
                k: v for k, v in self.micro_agents.items()
                if k in relevant_agents
            }
        
        # === FASE 2: CONSULTA DE DOCUMENTOS ===
        doc_context = {}
        if self.document_awareness.should_consult_documents(query):
            logger.debug("Fase 2: Consultando documentos relevantes...")
            doc_context = self.document_awareness.get_document_context_for_agent(query)
            if doc_context.get("has_documents"):
                logger.info(f"✓ Encontrados {doc_context['documents_count']} documentos relevantes")
                context["documents"] = doc_context
        
        # === FASE 3: ATIVAR MEMÓRIAS E CONTEXTO ===
        logger.debug("Fase 3: Ativando memórias e documentos relevantes...")
        memories = self.memory_manager.recall_relevant_memories(query, limit=5)
        context["memory"] = [
            {
                "id": mem.id,
                "title": mem.title,
                "content": mem.content,
                "memory_type": mem.type.name if mem.type else "unknown",
                "importance_score": mem.importance_score,
                "emotional_valence": mem.emotional_valence,
            }
            for mem in memories
        ]
        context["emotional_state"] = self.agent.current_emotional_state or {}
        context["agent_identity"] = self.get_agent_identity()
        
        # ADICIONAR contexto de documentos aos agentes
        if doc_context.get("has_documents"):
            context["documents_context"] = doc_context.get("context_text", "")
            context["documents_info"] = f"Você tem acesso a {doc_context['documents_count']} documento(s) relevante(s)"
            # IMPORTANTE: Passar também a estrutura completa de documentos para CoreAgent
            context["documents"] = doc_context  # Assim CoreAgent terá acesso ao doc_context completo
        
        # === FASE 4: REDE NEURAL - MODIFICADORES DE MEMÓRIA ===
        logger.debug("Fase 4: Aplicando modificadores neurais baseado em memória...")
        neural_modifiers = self.neural_network.get_micro_agent_modifiers(query, context)
        
        # Registrar processo
        if record_process:
            self.thought_process = ThoughtProcess(
                agent_id=self.agent_id,
                query=query,
                context=context,
                status="thinking",
                start_time=start_time,
            )
            self.db.add(self.thought_process)
            self.db.flush()
        
        # === FASE 5: PENSAMENTO PARALELO === 
        logger.info(f"Fase 5: Executando pensamento paralelo com {len(self.micro_agents)} micro-agentes...")
        
        thinking_results = await self._run_micro_agents_parallel_enhanced(
            query,
            context,
            neural_modifiers
        )
        
        logger.info(f"✓ Todos os {len(thinking_results)} micro-agentes completaram pensamento")
        
        if record_process and self.thought_process:
            self.thought_process.status = "synthesizing"
            self.db.commit()
        
        # === FASE 6: SÍNTESE PELO CORE AGENT ===
        logger.debug("Fase 6: Core Agent sintetizando respostas...")
        final_response = self.core_agent.synthesize_response(
            thinking_results,
            query,
            context,
            user_id,
            conversation_id
        )
        
        # === FASE 7: GRAVAÇÃO EM MEMÓRIA ===
        logger.debug("Fase 7: Registrando interação em memória...")
        
        if record_process and self.thought_process:
            self.thought_process.status = "completed"
            self.thought_process.end_time = datetime.utcnow()
            self.thought_process.final_response = final_response.get("response")
            self.thought_process.confidence = final_response.get("confidence")
            self.thought_process.reasoning = final_response.get("reasoning")
            self.db.commit()
            
            # Gravar contribuições de cada micro-agente
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
        
        # Gravar aprendizado
        try:
            self.neural_network.create_learning_memory(
                interaction_type="reasoning",
                success=final_response.get("confidence", 0.5) > 0.6,
                query=query,
                response=final_response.get("response", ""),
                confidence=final_response.get("confidence", 0.5),
                user_context={"user_id": user_id, "documents": doc_context.get("has_documents", False)}
            )
        except Exception as e:
            logger.warning(f"Erro ao registrar aprendizado: {e}")
        
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        logger.info(f"✓ Processo completado em {duration_ms}ms com confiança {final_response.get('confidence', 0):.0%}")
        
        # Adicionar dados de debugging
        final_response["thinking_steps"] = [
            f"Relevância avaliada: {len(relevant_agents)} agentes",
            f"Documentos consultados: {doc_context.get('documents_count', 0)}",
            f"Modificadores neurais aplicados: {sum(1 for m in neural_modifiers.values() if m.get('memory_count', 0) > 0)}",
            f"Micro-agentes executados: {len(thinking_results)}",
            f"Síntese humanizada aplicada",
        ]
        final_response["duration_ms"] = duration_ms
        
        return final_response
    
    
    async def _run_micro_agents_parallel_enhanced(
        self,
        query: str,
        context: Dict,
        neural_modifiers: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """
        Executa micro-agentes em paralelo COM modificadores neurais
        Memórias afetam pesos, confiança e temperatura de cada agente
        """
        
        tasks = {}
        
        for agent_type, micro_agent in self.micro_agents.items():
            modifier = neural_modifiers.get(agent_type, {})
            
            tasks[agent_type] = asyncio.create_task(
                self._think_async_enhanced(
                    micro_agent,
                    query,
                    context,
                    modifier
                )
            )
        
        results = {}
        
        for agent_type, task in tasks.items():
            try:
                result = await task
                results[agent_type] = result
                logger.debug(f"✓ {agent_type}: Completado com confiança {result.get('confidence', 0):.0%}")
            except Exception as e:
                logger.error(f"✗ Erro em {agent_type}: {e}")
                results[agent_type] = self._error_result(e)
        
        return results
    
    async def _think_async_enhanced(
        self,
        micro_agent: BaseMicroAgent,
        query: str,
        context: Dict,
        neural_modifier: Dict
    ) -> Dict:
        """
        Executa pensamento com modificadores neurais
        Adiciona contexto de memória e documentos ao agente
        """
        
        # Preparar contexto melhorado
        enhanced_context = context.copy()
        
        # Adicionar instruções de modificação neural
        if neural_modifier.get("memory_count", 0) > 0:
            enhanced_context["neural_prompt"] = (
                f"Nota: Suas respostas são influenciadas por {neural_modifier['memory_count']} "
                f"memória(s) relevante(s). Peso de resposta: "
                f"{neural_modifier.get('weight_modifier', 1.0):.1f}x"
            )
        
        # Wrapper para executar em thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            micro_agent.think,
            query,
            enhanced_context
        )
        
        # Aplicar modificadores
        base_weight = micro_agent.get_weight()
        weight_modifier = neural_modifier.get("weight_modifier", 1.0)
        confidence_modifier = neural_modifier.get("confidence_modifier", 0.0)
        temperature_modifier = neural_modifier.get("temperature_modifier", 0.0)
        
        result["weight"] = base_weight * weight_modifier
        result["confidence"] = max(0.0, min(1.0, result.get("confidence", 0.5) + confidence_modifier))
        result["agent_type"] = micro_agent.thinking_type.value
        result["neural_influence"] = neural_modifier.get("memory_count", 0) > 0
        
        return result
    
    async def _run_micro_agents_parallel(
        self,
        query: str,
        context: Dict
    ) -> Dict[str, Dict]:
        """Executa todos os micro-agentes em paralelo (fallback antigo)"""
        
        tasks = {}
        for agent_type, micro_agent in self.micro_agents.items():
            tasks[agent_type] = asyncio.create_task(
                self._think_async(micro_agent, query, context)
            )
        
        results = {}
        for agent_type, task in tasks.items():
            try:
                result = await task
                results[agent_type] = result
                logger.debug(f"Micro-agente {agent_type} completou pensamento")
            except Exception as e:
                logger.error(f"Erro em micro-agente {agent_type}: {e}")
                results[agent_type] = self._error_result(e)
        
        return results
    
    async def _think_async(
        self,
        micro_agent: BaseMicroAgent,
        query: str,
        context: Dict
    ) -> Dict:
        """Executa pensamento de micro-agente de forma assíncrona"""
        
        # Wrapper para executar synchronous think em thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            micro_agent.think,
            query,
            context
        )
        
        # Adicionar peso
        result["weight"] = micro_agent.get_weight()
        result["agent_type"] = micro_agent.thinking_type.value
        
        return result
    
    def _debate_and_consolidate(self, thinking_results: Dict[str, Dict]) -> Dict[str, Any]:
        """Simula debate entre micro-agentes"""
        
        # Agrupar por perspectivas similares
        perspectives_pro = []
        perspectives_con = []
        
        for agent_type, result in thinking_results.items():
            perspectives_pro.extend(result.get("supporting_arguments", []))
            perspectives_con.extend(result.get("opposing_arguments", []))
        
        return {
            "supporting": perspectives_pro,
            "opposing": perspectives_con,
            "debate_points": len(thinking_results),
        }
    
    def _make_final_decision(
        self,
        thinking_results: Dict[str, Dict],
        consolidated: Dict
    ) -> Dict[str, Any]:
        """Sintetiza resultado final ponderado"""
        
        # Calcular confiança média ponderada
        total_weight = sum(r.get("weight", 1.0) for r in thinking_results.values())
        weighted_confidence = 0.0
        
        for result in thinking_results.values():
            confidence = result.get("confidence", 0.5)
            weight = result.get("weight", 1.0)
            weighted_confidence += confidence * weight
        
        if total_weight > 0:
            weighted_confidence /= total_weight
        
        # Construir resposta
        response_parts = []
        
        # Se não há micro-agentes, usar fallback
        if not thinking_results:
            response_parts.append(f"Desculpe, o sistema de pensamento cognitivo não está totalmente inicializado. Por favor, tente novamente.")
            logger.warning(f"Nenhum micro-agente disponível para o agente {self.agent_id}")
        else:
            for agent_type, result in thinking_results.items():
                perspective = result.get('perspective', '')
                if perspective:
                    response_parts.append(f"({agent_type}): {perspective}")
                else:
                    response_parts.append(f"({agent_type}): [sem perspectiva gerada]")
        
        # Formular recomendação
        recommendation = self._formulate_recommendation(thinking_results, consolidated)
        
        # Gravar memória da decisão
        try:
            self.memory_manager.create_memory(
                title=f"Processo de Decisão: {consolidated['debate_points']} perspectivas",
                content=json.dumps({
                    "query": self.thought_process.query if self.thought_process else "",
                    "perspectives": response_parts,
                    "recommendation": recommendation,
                    "confidence": weighted_confidence,
                }),
                memory_type="semantic",
                importance_score=0.6,
            )
        except Exception as e:
            logger.error(f"Erro ao gravar memória de decisão: {e}")
        
        return {
            "response": "\n".join(response_parts),
            "recommendation": recommendation,
            "confidence": weighted_confidence,
            "reasoning": self._generate_reasoning(thinking_results),
            "supporting_arguments": consolidated["supporting"],
            "opposing_arguments": consolidated["opposing"],
            "perspectives_count": len(thinking_results),
        }
    
    def _formulate_recommendation(
        self,
        thinking_results: Dict[str, Dict],
        consolidated: Dict
    ) -> str:
        """Formula recomendação final"""
        
        # Coletar recomendações de todos os micro-agentes
        recommendations = [
            result.get("recommended_action", "")
            for result in thinking_results.values()
            if result.get("recommended_action")
        ]
        
        # Síntese
        if not recommendations:
            return "Recomendação: Aguardar mais informações"
        
        return f"Recomendação: {'; '.join(recommendations)}"
    
    def _generate_reasoning(self, thinking_results: Dict[str, Dict]) -> str:
        """Gera explicação do raciocínio"""
        
        reasoning_parts = []
        
        for agent_type, result in thinking_results.items():
            reasoning_parts.append(
                f"• {agent_type.upper()}: Confiança {result.get('confidence', 0):.0%}"
            )
        
        return "Raciocínio:\n" + "\n".join(reasoning_parts)
    
    def _get_micro_agent_id(self, agent_type: str) -> str:
        """Obtém ID do micro-agente pelo tipo"""
        if agent_type in self.micro_agents:
            return self.micro_agents[agent_type].micro_agent_id
        return "unknown"
    
    def _error_result(self, error: Exception) -> Dict:
        """Retorna resultado de erro estruturado"""
        return {
            "perspective": f"Erro no processamento: {str(error)}",
            "confidence": 0.0,
            "supporting_arguments": [],
            "opposing_arguments": [],
            "error": True,
        }
    
    def get_agent_identity(self) -> Dict[str, Any]:
        """Retorna identidade completa do agente para contexto"""
        
        return {
            "id": self.agent.id,
            "name": self.agent.name,
            "personality_traits": self.agent.personality_traits,
            "base_values": self.agent.base_values,
            "thinking_style": self.agent.thinking_style,
            "emotional_state": self.agent.current_emotional_state,
            "micro_agents_count": len(self.micro_agents),
            "active_micro_agents": list(self.micro_agents.keys()),
        }
    
    def update_emotional_state(self, emotions: Dict[str, float]):
        """Atualiza estado emocional do agente"""
        self.agent.current_emotional_state = emotions
        self.agent.updated_at = datetime.utcnow()
        self.db.commit()
