#!/usr/bin/env python3
"""
📊 INDEX DE FICHEIROS DE BASE DE DADOS
========================================

Este ficheiro lista e descreve TODOS os ficheiros relacionados com BD
"""

# ============================================================================
# FICHEIROS CRIADOS/MODIFICADOS
# ============================================================================

FICHEIROS = {
    # ========================================================================
    # 🚀 SCRIPTS PRINCIPAIS
    # ========================================================================
    
    "setup_database.py": {
        "tipo": "🚀 Python Script",
        "tamanho": "~450 linhas",
        "descrição": "Script Python PRINCIPAL para setup completo da BD",
        "o_que_faz": [
            "✅ Verifica conexão com BD",
            "✅ Cria todas as 3 tabelas",
            "✅ Aplica migrações",
            "✅ Popula dados iniciais (3 agentes)",
            "✅ Verifica integridade",
            "✅ Mostra resumo com cores"
        ],
        "como_usar": [
            "python setup_database.py              # Setup completo",
            "python setup_database.py --drop       # Reset completo",
            "python setup_database.py --migrate    # Apenas migração",
            "python setup_database.py --seed       # Seed dados",
            "python setup_database.py --verify     # Verificar"
        ],
        "tempo": "~5 segundos",
        "prioridade": "⭐⭐⭐⭐⭐ MAIOR"
    },
    
    "quick_setup.py": {
        "tipo": "⚡ Python Script Rápido",
        "tamanho": "~350 linhas",
        "descrição": "Setup + Demo + Testes em um único script",
        "o_que_faz": [
            "✅ Setup completo da BD",
            "✅ Insere dados iniciais",
            "✅ Executa queries de exemplo",
            "✅ Mostra estatísticas",
            "✅ Executa testes (opcional)"
        ],
        "como_usar": [
            "python quick_setup.py                 # Setup + demo",
            "python quick_setup.py --setup         # Apenas setup",
            "python quick_setup.py --demo          # Apenas demo",
            "python quick_setup.py --tests         # Com testes",
            "python quick_setup.py --clean         # Limpar"
        ],
        "tempo": "~5 segundos",
        "prioridade": "⭐⭐⭐⭐ MUITO ALTA"
    },
    
    # ========================================================================
    # 🪟 SCRIPTS PARA WINDOWS
    # ========================================================================
    
    "setup_database.bat": {
        "tipo": "🪟 Batch Script (Windows)",
        "tamanho": "~200 linhas",
        "descrição": "Facilitador para Windows - chama setup_database.py",
        "o_que_faz": [
            "✅ Interface amigável no Windows",
            "✅ Verifica se Python está instalado",
            "✅ Pede confirmação para operações destrutivas",
            "✅ Mostra ajuda"
        ],
        "como_usar": [
            "setup_database.bat                    # Setup completo",
            "setup_database.bat --drop             # Reset",
            "setup_database.bat --migrate          # Migração",
            "setup_database.bat --seed             # Seed",
            "setup_database.bat --help             # Ajuda"
        ],
        "tempo": "~5 segundos",
        "so": "🪟 Windows apenas",
        "prioridade": "⭐⭐⭐ ALTA"
    },
    
    # ========================================================================
    # 🐧 SCRIPTS PARA LINUX/MAC
    # ========================================================================
    
    "setup_database.sh": {
        "tipo": "🐧 Bash Script (Linux/Mac)",
        "tamanho": "~150 linhas",
        "descrição": "Facilitador para Unix/Linux/Mac",
        "o_que_faz": [
            "✅ Interface amigável no terminal",
            "✅ Verifica se Python3 está instalado",
            "✅ Suporta todas as opções",
            "✅ Mostra ajuda"
        ],
        "como_usar": [
            "chmod +x setup_database.sh            # Tornar executável",
            "./setup_database.sh                   # Setup completo",
            "./setup_database.sh --drop            # Reset",
            "./setup_database.sh --help            # Ajuda"
        ],
        "tempo": "~5 segundos",
        "so": "🐧 Linux/Mac apenas",
        "prioridade": "⭐⭐⭐ ALTA"
    },
    
    # ========================================================================
    # 📄 FICHEIROS SQL
    # ========================================================================
    
    "schema_complete.sql": {
        "tipo": "📄 SQL Puro",
        "tamanho": "~150 linhas",
        "descrição": "Schema completo em SQL puro",
        "o_que_contem": [
            "✅ 3 Tabelas (memories, agent_prompts, agents)",
            "✅ 10+ Índices para performance",
            "✅ Constraints",
            "✅ 2 Views úteis",
            "✅ Dados iniciais (3 agentes)"
        ],
        "como_usar": [
            "psql -f schema_complete.sql           # PostgreSQL",
            "mysql < schema_complete.sql           # MySQL"
        ],
        "uso": "Quando quer fazer setup manual",
        "prioridade": "⭐⭐ MÉDIA"
    },
    
    # ========================================================================
    # 📚 DOCUMENTAÇÃO
    # ========================================================================
    
    "README_DATABASE.md": {
        "tipo": "📚 Documentação Completa",
        "tamanho": "~400 linhas",
        "descrição": "Guia completo e detalhado de setup de BD",
        "contém": [
            "✅ Quick start",
            "✅ Instruções cenário por cenário",
            "✅ Estrutura de dados",
            "✅ Troubleshooting",
            "✅ Exemplos de código",
            "✅ Checklist"
        ],
        "leia_quando": "Quer entender tudo em detalhe",
        "prioridade": "⭐⭐⭐⭐ MUITO ALTA"
    },
    
    "SCRIPTS_RESUMO.md": {
        "tipo": "📋 Resumo Visual",
        "tamanho": "~300 linhas",
        "descrição": "Resumo visual de todos os scripts",
        "contém": [
            "✅ Resumo de cada script",
            "✅ Exemplo de outputs",
            "✅ Recomendações de uso",
            "✅ SQL útil",
            "✅ Checklist"
        ],
        "leia_quando": "Quer uma visão rápida",
        "prioridade": "⭐⭐⭐⭐ MUITO ALTA"
    },
    
    "QUICK_START.md": {
        "tipo": "⚡ Quick Start",
        "tamanho": "~200 linhas",
        "descrição": "Guia rápido - localização e uso imediato",
        "contém": [
            "✅ Localização exata de cada ficheiro",
            "✅ Guia rápido (3 opções)",
            "✅ Checklist",
            "✅ Troubleshooting"
        ],
        "leia_quando": "Quer começar AGORA",
        "prioridade": "⭐⭐⭐⭐⭐ CRÍTICA"
    },
    
    # ========================================================================
    # 🔧 FICHEIROS EXISTENTES (NÃO CRIADOS)
    # ========================================================================
    
    "database.py": {
        "tipo": "🔧 ORM (Existente)",
        "descrição": "Definição das tabelas com SQLAlchemy",
        "contém": [
            "✅ Class Agent",
            "✅ Class Memory",
            "✅ Class AgentPrompt",
            "✅ Connection engine"
        ],
        "importante": "Não modificar exceto para adicionar novas tabelas"
    },
    
    "migrate_db.py": {
        "tipo": "🔧 Migração Legada (Existente)",
        "descrição": "Script antigo de migração",
        "nota": "Use setup_database.py em vez deste"
    },
    
    "migrate_db_sql.sql": {
        "tipo": "🔧 Migração SQL Legada (Existente)",
        "descrição": "SQL antigo de migração",
        "nota": "Agora integrado em schema_complete.sql"
    }
}

# ============================================================================
# SUMMARY
# ============================================================================

SUMMARY = {
    "ficheiros_criados": 7,
    "ficheiros_novos": [
        "setup_database.py",
        "quick_setup.py",
        "setup_database.bat",
        "setup_database.sh",
        "schema_complete.sql",
        "README_DATABASE.md",
        "SCRIPTS_RESUMO.md",
        "QUICK_START.md"  # Este arquivo
    ],
    "tamanho_total": "~2500 linhas de código + documentação",
    "tempo_setup": "~5 segundos",
    "facilidade": "⭐⭐⭐⭐⭐ Muito Fácil",
    "status": "✅ PRONTO PARA USAR"
}

# ============================================================================
# RECOMENDAÇÕES DE USO
# ============================================================================

RECOMENDACOES = {
    "primeira_vez": {
        "descricao": "Setup completo recomendado",
        "opcoes": [
            "1. python setup_database.py              (Recomendado)",
            "2. python quick_setup.py                 (Com demo)",
            "3. ./setup_database.sh                   (Linux/Mac)",
            "4. setup_database.bat                    (Windows)"
        ]
    },
    
    "desenvolvimento": {
        "descricao": "Reset rápido durante desenvolvimento",
        "opcoes": [
            "python setup_database.py --drop",
            "python setup_database.py"
        ]
    },
    
    "producao": {
        "descricao": "Apenas migração em produção",
        "opcoes": [
            "python setup_database.py --migrate"
        ]
    },
    
    "debug": {
        "descricao": "Quando algo dá errado",
        "opcoes": [
            "python setup_database.py --verify",
            "python quick_setup.py --demo"
        ]
    }
}

# ============================================================================
# PRINT VISUAL
# ============================================================================

def print_index():
    """Print o índice"""
    
    print("\n" + "="*80)
    print("📊 ÍNDICE DE FICHEIROS DE BASE DE DADOS".center(80))
    print("="*80 + "\n")
    
    # Scripts principais
    print("🚀 SCRIPTS PRINCIPAIS")
    print("-" * 80)
    for name, info in FICHEIROS.items():
        if "🚀" in info.get("tipo", "") or "⚡" in info.get("tipo", ""):
            print(f"\n  {name}")
            print(f"  {info.get('descrição', 'N/A')}")
            print(f"  Prioridade: {info.get('prioridade', 'N/A')}")
    
    # Scripts por SO
    print("\n\n🪟/🐧 SCRIPTS POR SISTEMA OPERATIVO")
    print("-" * 80)
    for name, info in FICHEIROS.items():
        if "🪟" in info.get("tipo", "") or "🐧" in info.get("tipo", ""):
            print(f"\n  {name}")
            print(f"  {info.get('descrição', 'N/A')}")
    
    # Documentação
    print("\n\n📚 DOCUMENTAÇÃO")
    print("-" * 80)
    for name, info in FICHEIROS.items():
        if "📚" in info.get("tipo", "") or "📋" in info.get("tipo", "") or "⚡" in info.get("tipo", ""):
            if "README" in name or "SCRIPTS" in name or "QUICK" in name:
                print(f"\n  {name}")
                print(f"  {info.get('descrição', 'N/A')}")
    
    # SQL
    print("\n\n📄 SQL")
    print("-" * 80)
    for name, info in FICHEIROS.items():
        if "📄" in info.get("tipo", ""):
            print(f"\n  {name}")
            print(f"  {info.get('descrição', 'N/A')}")
    
    # Resumo
    print("\n\n" + "="*80)
    print("📊 RESUMO".center(80))
    print("="*80)
    print(f"\n  Ficheiros criados: {SUMMARY['ficheiros_criados']}")
    print(f"  Tamanho total: {SUMMARY['tamanho_total']}")
    print(f"  Tempo de setup: {SUMMARY['tempo_setup']}")
    print(f"  Status: {SUMMARY['status']}")
    print(f"\n  Começe com: python setup_database.py\n")

if __name__ == "__main__":
    print_index()
