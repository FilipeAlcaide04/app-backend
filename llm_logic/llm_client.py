

"""
Cliente LLM para Ollama
"""
from typing import List, Dict, Optional
from openai import OpenAI
from config.config import settings
import os
import logging
import requests

logger = logging.getLogger(__name__)


class LLMClient:
    """Cliente LLM para Ollama"""

    def __init__(self):
        self.provider = "ollama"

        # Configuração do Ollama
        ollama_base_url = settings.ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        # Se não tem http/https, adiciona
        if not ollama_base_url.startswith("http"):
            ollama_base_url = "http://" + ollama_base_url
        
        # Remove trailing slash
        ollama_base_url = ollama_base_url.rstrip('/')
        
        # Guarda ambas as versões (com e sem /v1)
        self.ollama_base_url = ollama_base_url  # http://localhost:11434
        self.ollama_base_url_v1 = ollama_base_url + '/v1'  # http://localhost:11434/v1
        
        ollama_api_key = settings.ollama_api_key or os.getenv("OLLAMA_API_KEY", "ollama")
        
        # Define modelo padrão
        default_model = settings.ollama_model or os.getenv("OLLAMA_MODEL", "llama2")
        self.model = settings.llm_model or os.getenv("LLM_MODEL", default_model)
        
        # Usa endpoint compatível com OpenAI
        try:
            self.client = OpenAI(
                base_url=self.ollama_base_url_v1,
                api_key=ollama_api_key
            )
        except Exception as e:
            # Fallback para endpoint nativo do Ollama
            self.client = OpenAI(
                base_url=self.ollama_base_url,
                api_key=ollama_api_key
            )

        # Query Ollama for available models and pick a compatible one if needed
        try:
            # Tenta endpoint compatível com OpenAI primeiro
            models_endpoint = self.ollama_base_url_v1 + '/models'
            resp = requests.get(models_endpoint, timeout=3)
            
            # Se falhar, tenta endpoint nativo do Ollama
            if not resp.ok or resp.status_code == 404:
                models_endpoint = self.ollama_base_url + '/api/tags'
                resp = requests.get(models_endpoint, timeout=3)
            
            if resp.ok:
                data = resp.json()
                models_list = []
                
                # Parse de endpoint /v1/models
                if isinstance(data, dict) and 'data' in data:
                    for m in data['data']:
                        if isinstance(m, dict) and 'id' in m:
                            models_list.append(m['id'])
                
                # Parse de endpoint /api/tags (Ollama nativo)
                elif isinstance(data, dict) and 'models' in data:
                    for m in data['models']:
                        if isinstance(m, dict) and 'name' in m:
                            models_list.append(m['name'])
                elif isinstance(data, list):
                    for m in data:
                        if isinstance(m, str):
                            models_list.append(m)
                        elif isinstance(m, dict) and 'name' in m:
                            models_list.append(m['name'])

                if models_list:
                    logger.debug(f"Modelos Ollama: {models_list}")
                    if self.model not in models_list:
                        chosen = models_list[0]
                        logger.info(f"Modelo '{self.model}' indisponível, usando '{chosen}'")
                        self.model = chosen
        except Exception:
            pass

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Cria uma completion de chat

        Args:
            messages: Lista de mensagens no formato [{"role": "system/user/assistant", "content": "..."}]
            temperature: Temperatura para sampling
            max_tokens: Número máximo de tokens
            model: Nome do modelo (usa self.model se None)

        Returns:
            Conteúdo da resposta
        """
        model_name = model or self.model

        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            err_text = str(e).lower()
            if "not found" in err_text or "404" in err_text:
                try:
                    fallback = settings.ollama_model or os.getenv("OLLAMA_MODEL", "llama2")
                    if fallback and fallback != model_name:
                        logger.warning(f"Modelo '{model_name}' não encontrado, fallback '{fallback}'")
                        response = self.client.chat.completions.create(
                            model=fallback,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens
                        )
                        self.model = fallback
                        return response.choices[0].message.content
                except Exception:
                    pass
            raise Exception(f"LLM erro ({self.provider}): {e}")

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Gera texto a partir de um prompt.

        Args:
            prompt: Texto do prompt (vai como role=user)
            max_tokens: Máximo de tokens
            temperature: Temperatura para sampling
            model: Modelo a usar (padrão: self.model)
            system_prompt: Se fornecido, usa como mensagem system em vez do default

        Returns:
            Texto gerado
        """
        system_content = system_prompt or "You are an intelligent, human-centered assistant."
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt}
        ]

        return self.chat_completion(messages, temperature=temperature, max_tokens=max_tokens, model=model)

    def get_model_name(self) -> str:
        """Retorna o nome do modelo atual"""
        return self.model

    def get_provider(self) -> str:
        """Retorna o provider atual"""
        return self.provider

# Instância global do cliente
_llm_client = None

def get_llm_client() -> LLMClient:
    """Retorna instância singleton do cliente LLM"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
