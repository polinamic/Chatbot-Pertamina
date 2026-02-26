"""
LLM Service menggunakan Ollama dengan model Llama 3.8b
Pastikan Ollama service sudah running dengan: ollama serve
"""

import logging
import requests

logger = logging.getLogger(__name__)

# Konfigurasi Ollama
OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "llama3:8b"


def is_ollama_running():
    """Check apakah Ollama service sedang running"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def generate_response(prompt: str, context: str = "") -> str:
    """
    Generate response menggunakan Llama 3.8b via Ollama
    
    Args:
        prompt (str): User prompt
        context (str): Additional context untuk RAG
        
    Returns:
        str: Generated response dari LLM
    """
    
    if not is_ollama_running():
        logger.error("Ollama service tidak running. Silakan jalankan: ollama serve")
        return "Maaf, LLM service sedang tidak tersedia. Silakan hubungi administrator."
    
    try:
        # Prepare full prompt dengan context jika ada
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        # Call Ollama API
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": full_prompt,
                "stream": False,
                "temperature": 0.7,
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', 'Tidak ada response').strip()
        else:
            logger.error(f"Ollama error: {response.status_code}")
            return "Terjadi kesalahan dalam processing LLM."
            
    except requests.exceptions.Timeout:
        logger.error("Ollama request timeout")
        return "Request timeout. Silakan coba lagi."
    except Exception as e:
        logger.error(f"LLM service error: {str(e)}")
        return f"Error: {str(e)}"


def chat_completion(messages: list) -> str:
    """
    Chat dengan Ollama menggunakan format messages
    
    Args:
        messages (list): List of message dicts dengan 'role' dan 'content'
        
    Returns:
        str: Response message
    """
    
    if not is_ollama_running():
        logger.error("Ollama service tidak running")
        return "LLM service tidak tersedia."
    
    try:
        # Build prompt dari messages
        prompt = ""
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'user':
                prompt = content  # Take the last user message
        
        return generate_response(prompt)
        
    except Exception as e:
        logger.error(f"Chat completion error: {str(e)}")
        return "Error dalam chat completion."