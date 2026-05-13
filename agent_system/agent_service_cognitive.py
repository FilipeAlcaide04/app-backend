"""
Agent Service - Gestão de agentes (pessoas artificiais)
Operações CRUD e integração com sistema cognitivo
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import (
    Agent, MicroAgent, MicroAgentType, Memory, MemoryType,
    AuditLog, ThoughtProcess
)
from agent_system.memory_manager_cognitive import MemoryManager, MemoryTypeEnum
from agent_system.cognitive_orchestrator import CognitiveOrchestrator
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import uuid4
import json
import logging

logger = logging.getLogger(__name__)


class AgentServiceCognitive:
    """Serviço para gestão de agentes humanos artificiais"""
    
    def __init__(self, db: Session):
        self.db = db
        self._ensure_default_micro_agent_types()
    
    def _ensure_default_micro_agent_types(self):
        """Cria tipos de micro-agentes padrão se não existirem"""
        
        default_types = [
            {
                "name": "logical",
                "category": "thinking_type",
                "description": "Pensamento racional e análise lógica",
                "system_prompt": "Você é um micro-agente focado em análise lógica. Analise o problema com rigor matemático e racional.",
                "cognitive_objective": "Alcançar conclusões racionalmente fundamentadas",
                "thinking_framework": "Dedução lógica, análise sistemática",
                "default_weight": 1.2,
                "response_style": "analytical",
                "is_builtin": True,
            },
            {
                "name": "emotional",
                "category": "thinking_type",
                "description": "Processamento emocional e empatia",
                "system_prompt": "Você é um micro-agente focado em processar dimensões emocionais. Considere sentimentos e relações humanas.",
                "cognitive_objective": "Considerar bem-estar e valores emocionais",
                "thinking_framework": "Empatia, compreensão emocional",
                "default_weight": 1.0,
                "response_style": "empathetic",
                "is_builtin": True,
            },
            {
                "name": "critical",
                "category": "thinking_type",
                "description": "Pensamento crítico e questionamento",
                "system_prompt": "Você é um micro-agente crítico. Questione premissas, procure por falhas, desafie conclusões óbvias.",
                "cognitive_objective": "Identificar fraquezas e riscos",
                "thinking_framework": "Pensamento crítico, análise de premissas",
                "default_weight": 1.1,
                "response_style": "questioning",
                "is_builtin": True,
            },
            {
                "name": "creative",
                "category": "thinking_type",
                "description": "Pensamento criativo e inovador",
                "system_prompt": "Você é um micro-agente criativo. Procure soluções inovadoras, conexões não-óbvias, ideias fora da caixa.",
                "cognitive_objective": "Gerar novas perspectivas e ideias",
                "thinking_framework": "Pensamento divergente, criatividade",
                "default_weight": 0.9,
                "response_style": "innovative",
                "is_builtin": True,
            },
            {
                "name": "ethical",
                "category": "thinking_type",
                "description": "Considerações éticas e morais",
                "system_prompt": "Você é um micro-agente ético. Avalie implicações morais e éticas. Considere valores e princípios.",
                "cognitive_objective": "Garantir alinhamento ético",
                "thinking_framework": "Ética, valores, justiça",
                "default_weight": 1.1,
                "response_style": "principled",
                "is_builtin": True,
            },
            {
                "name": "social",
                "category": "thinking_type",
                "description": "Dinâmica social e interpessoal",
                "system_prompt": "Você é um micro-agente social. Considere dinâmica de grupo, relações sociais, impacto nas pessoas.",
                "cognitive_objective": "Compreender e navegar dinâmicas sociais",
                "thinking_framework": "Inteligência social, empatia",
                "default_weight": 1.0,
                "response_style": "diplomatic",
                "is_builtin": True,
            },
        ]
        
        for type_data in default_types:
            existing = self.db.query(MicroAgentType).filter(
                MicroAgentType.name == type_data["name"]
            ).first()
            
            if not existing:
                agent_type = MicroAgentType(**type_data)
                self.db.add(agent_type)
        
        self.db.commit()
    
    # ========== CRIAR AGENTE ==========
    
    def create_agent(
        self,
        name: str,
        description: Optional[str] = None,
        personality_traits: Optional[Dict] = None,
        base_values: Optional[Dict] = None,
        background_story: Optional[str] = None,
        life_experiences: Optional[Dict] = None,
        thinking_style: str = "balanced",
        decision_making_approach: str = "collaborative",
        debate_intensity: float = 0.7,
        initial_memories: Optional[List[Dict]] = None,
        micro_agent_types: Optional[List[str]] = None,
        avatar: str = "👤",
        micro_agents_config: Optional[Dict] = None,
        owner_id: Optional[str] = None,
    ) -> Agent:
        """
        Cria novo agente (pessoa artificial)
        
        Args:
            micro_agents_config: Dict com custom prompts/weights por tipo
                {
                    "logical": {
                        "custom_prompt": "seu prompt aqui",
                        "custom_weight": 1.5,
                        "activation_enabled": True
                    },
                    ...
                }
        """
        
        # Gerar ID único
        agent_id = str(uuid4())
        
        # Criar agente
        agent = Agent(
            id=agent_id,
            owner_id=owner_id,
            name=name,
            description=description,
            avatar=avatar,
            personality_traits=personality_traits or {},
            base_values=base_values or {},
            background_story=background_story,
            life_experiences=life_experiences or {},
            thinking_style=thinking_style,
            decision_making_approach=decision_making_approach,
            debate_intensity=debate_intensity,
            current_emotional_state={},
            is_active=True,
        )
        
        self.db.add(agent)
        self.db.flush()
        
        # Criar micro-agentes
        self._create_agent_micro_agents(agent_id, micro_agent_types, micro_agents_config)
        
        # Criar memórias iniciais
        if initial_memories:
            memory_manager = MemoryManager(self.db, agent_id)
            memory_manager.create_initial_memories(initial_memories)
        
        self.db.commit()
        
        # Auditoria
        self._audit_action(agent_id, "create", "agent", agent_id)
        
        logger.info(f"[agent] criado: {name} ({agent_id})")
        
        return agent
    
    def _create_agent_micro_agents(self, agent_id: str, types: Optional[List[str]] = None, config: Optional[Dict] = None):
        """
        Cria instâncias de micro-agentes para o agente
        Sempre cria os 6 tipos padrão. Se o usuário não fornecer customizações, usa os valores padrão.
        
        Args:
            types: Lista de tipos a criar (se None, usa os 6 padrão)
            config: Dict com customizações por tipo
                {
                    "logical": {
                        "custom_prompt": "seu prompt aqui",
                        "custom_weight": 1.5,
                        "activation_enabled": True
                    },
                    ...
                }
        """
        
        # SEMPRE usar os 6 tipos padrão
        default_types = ["logical", "emotional", "critical", "creative", "ethical", "social"]
        types_to_create = types or default_types
        
        config = config or {}
        created_agents = []
        failed_agents = []
        
        for type_name in types_to_create:
            try:
                # Buscar tipo no banco
                agent_type = self.db.query(MicroAgentType).filter(
                    MicroAgentType.name == type_name
                ).first()
                
                if not agent_type:
                    logger.warning(f"[micro-agent] tipo '{type_name}' não existe")
                    failed_agents.append(type_name)
                    continue
                
                # Obter config customizada se fornecida pelo usuário
                type_config = config.get(type_name, {})
                custom_prompt = type_config.get("custom_prompt")  # None se não fornecido = usa padrão
                custom_weight = type_config.get("custom_weight")  # None se não fornecido = usa padrão
                activation_enabled = type_config.get("activation_enabled", True)
                
                # Criar instância do micro-agente
                micro_agent = MicroAgent(
                    agent_id=agent_id,
                    type_id=agent_type.id,
                    custom_prompt=custom_prompt,  # Salva custom prompt se fornecido pelo usuário
                    custom_weight=custom_weight,  # Salva custom weight se fornecido pelo usuário
                    activation_enabled=activation_enabled,
                    confidence_level=0.5,
                )
                self.db.add(micro_agent)
                created_agents.append(type_name)
                
            except Exception as e:
                logger.error(f"[micro-agent] erro ao criar '{type_name}': {e}")
                failed_agents.append(type_name)
        
        self.db.commit()
        
        # Log informativo
        logger.info(f"[micro-agent] {agent_id}: {len(created_agents)} criados ({', '.join(created_agents)})")
        if failed_agents:
            logger.warning(f"[micro-agent] {agent_id}: {len(failed_agents)} falharam ({', '.join(failed_agents)})")
    
    # ========== OBTER AGENTE ==========
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Obtém agente por ID"""
        return self.db.query(Agent).filter(Agent.id == agent_id).first()
    
    def get_agent_by_name(self, name: str) -> Optional[Agent]:
        """Obtém agente por nome"""
        return self.db.query(Agent).filter(Agent.name == name).first()
    
    def list_agents(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
        owner_id: Optional[str] = None,
    ) -> List[Agent]:
        """Lista agentes. Se owner_id for passado, filtra apenas os do utilizador."""

        query = self.db.query(Agent)

        if active_only:
            query = query.filter(Agent.is_active == True)

        if owner_id is not None:
            query = query.filter(Agent.owner_id == owner_id)

        return query.order_by(Agent.created_at.desc()).limit(limit).offset(offset).all()
    
    # ========== ATUALIZAR AGENTE ==========
    
    def update_agent(
        self,
        agent_id: str,
        **updates,
    ) -> Optional[Agent]:
        """Atualiza agente"""
        
        agent = self.get_agent(agent_id)
        if not agent:
            return None
        
        # Permitir atualização de campos específicos
        allowed_fields = {
            'name', 'description', 'avatar', 'personality_traits',
            'base_values', 'background_story', 'life_experiences',
            'thinking_style', 'decision_making_approach', 'debate_intensity',
            'current_emotional_state', 'is_active'
        }
        
        for field, value in updates.items():
            if field in allowed_fields:
                setattr(agent, field, value)
        
        agent.updated_at = datetime.utcnow()
        self.db.commit()
        
        self._audit_action(agent_id, "update", "agent", agent_id, updates)
        
        return agent
    
    # ========== DELETAR AGENTE ==========
    
    def delete_agent(self, agent_id: str) -> bool:
        """Deleta agente (soft delete)"""
        
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        agent.is_active = False
        agent.deleted_at = datetime.utcnow()
        self.db.commit()
        
        self._audit_action(agent_id, "delete", "agent", agent_id)
        
        return True
    
    # ========== MICRO-AGENTES ==========
    
    def get_agent_micro_agents(self, agent_id: str) -> List[Dict[str, Any]]:
        """Obtém micro-agentes de um agente com informações de prompts"""
        
        micro_agents = self.db.query(MicroAgent).filter(
            MicroAgent.agent_id == agent_id
        ).all()
        
        result = []
        for ma in micro_agents:
            # Determinar qual prompt está sendo usado
            active_prompt = ma.custom_prompt if ma.custom_prompt else ma.type.system_prompt
            is_custom_prompt = ma.custom_prompt is not None
            
            result.append({
                "id": ma.id,
                "type": ma.type.name,
                "type_description": ma.type.description,
                "confidence": ma.confidence_level,
                "weight": ma.custom_weight or ma.type.default_weight,
                "is_active": ma.activation_enabled,
                "current_focus": ma.current_focus,
                "system_prompt": ma.type.system_prompt,  # Prompt padrão
                "custom_prompt": ma.custom_prompt,  # Prompt customizado (null se padrão)
                "is_custom_prompt": is_custom_prompt,  # Flag indicando se é customizado
                "active_prompt": active_prompt,  # O prompt que está sendo usado
            })
        
        return result
    
    def enable_micro_agent(self, agent_id: str, type_name: str) -> bool:
        """Ativa micro-agente para um agente"""
        
        agent_type = self.db.query(MicroAgentType).filter(
            MicroAgentType.name == type_name
        ).first()
        
        if not agent_type:
            return False
        
        # Verificar se já existe
        existing = self.db.query(MicroAgent).filter(
            MicroAgent.agent_id == agent_id,
            MicroAgent.type_id == agent_type.id
        ).first()
        
        if existing:
            existing.activation_enabled = True
        else:
            micro_agent = MicroAgent(
                agent_id=agent_id,
                type_id=agent_type.id,
                activation_enabled=True,
            )
            self.db.add(micro_agent)
        
        self.db.commit()
        return True
    
    def disable_micro_agent(self, agent_id: str, type_name: str) -> bool:
        """Desativa micro-agente"""
        
        agent_type = self.db.query(MicroAgentType).filter(
            MicroAgentType.name == type_name
        ).first()
        
        if not agent_type:
            return False
        
        micro_agent = self.db.query(MicroAgent).filter(
            MicroAgent.agent_id == agent_id,
            MicroAgent.type_id == agent_type.id
        ).first()
        
        if micro_agent:
            micro_agent.activation_enabled = False
            self.db.commit()
            return True
        
        return False
    
    # ========== PENSAMENTO E DECISÃO ==========
    
    async def think(
        self,
        agent_id: str,
        query: str,
        context: Optional[Dict] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executa pensamento cognitivo HUMANIZADO com nova arquitetura
        
        Parâmetros:
            agent_id: ID do agente
            query: Query do utilizador
            context: Contexto adicional
            user_id: ID do utilizador (para personalização)
            conversation_id: ID da conversa (para contexto)
        """
        
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agente {agent_id} não encontrado")
        
        orchestrator = CognitiveOrchestrator(self.db, agent_id)
        result = await orchestrator.think(
            query,
            context=context,
            user_id=user_id,
            conversation_id=conversation_id,
            record_process=True
        )
        
        return result
    
    # ========== MEMÓRIAS ==========
    
    def get_agent_memories(self, agent_id: str, limit: int = 50) -> List[Dict]:
        """Obtém memórias de um agente"""
        
        memories = self.db.query(Memory).filter(
            Memory.agent_id == agent_id
        ).order_by(Memory.importance_score.desc()).limit(limit).all()
        
        return [self._memory_to_dict(m) for m in memories]
    
    def _memory_to_dict(self, memory: Memory) -> Dict:
        """Converte memória para dict"""
        
        return {
            "id": memory.id,
            "title": memory.title,
            "type": memory.type.name if memory.type else "unknown",
            "importance": memory.importance_score,
            "emotional_valence": memory.emotional_valence,
            "created_at": memory.created_at.isoformat() if memory.created_at else None,
            "accessed_at": memory.last_accessed.isoformat() if memory.last_accessed else None,
        }
    
    # ========== AUDITORIA ==========
    
    def _audit_action(self, agent_id: str, action: str, resource_type: str, resource_id: str, changes: Optional[Dict] = None):
        """Registra ação em auditoria"""
        
        audit = AuditLog(
            agent_id=agent_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            new_values=changes,
        )
        self.db.add(audit)
        self.db.commit()
    
    # ========== CONVERSÃO PARA DICT ==========
    
    def agent_to_dict(self, agent: Agent) -> Dict[str, Any]:
        """Converte agente para dict"""
        
        return {
            "id": agent.id,
            "owner_id": agent.owner_id,
            "name": agent.name,
            "description": agent.description,
            "avatar": agent.avatar,
            "background_story": agent.background_story,
            "personality_traits": agent.personality_traits,
            "base_values": agent.base_values,
            "thinking_style": agent.thinking_style,
            "decision_making_approach": agent.decision_making_approach,
            "debate_intensity": agent.debate_intensity,
            "micro_agents_count": len(agent.micro_agents),
            "memories_count": len(agent.memories),
            "documents_count": len(agent.documents),
            "is_active": agent.is_active,
            "last_interaction": agent.last_interaction.isoformat() if agent.last_interaction else None,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        }
