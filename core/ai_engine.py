# ===============================================================
#  File: ai_engine.py
#  Description: Response generation engine for Blimsey
#
#  Author: ac.craft8
#  Created: 2025-06-24
#  License: MIT
# ===============================================================

# ================================
#  Module and Library Imports
# ================================
import time
import traceback
import re
import ollama

from config_loader import load_model_from_settings, load_ai_prompt
from memory_manager import (
    load_chroma_client,
    get_user_memory,
    store_in_memory
)
from core.logger import log_user_interaction
from core.summary_manager import update_user_summary

# ================================
#  Configuration
# ================================
MODEL_NAME = load_model_from_settings()
MAX_RESPONSE_LENGTH = 4000
client = load_chroma_client()

# ================================
#  Function Definitions
# ================================

def extract_final_response(full_response):
    """Extract only the final response from the model output"""
    patterns = [
        r"(?:Responde|Response|Final response|Respuesta final):\s*(.*?)$",
        r"<respuesta>(.*?)</respuesta>",
        r"<response>(.*?)</response>",
        r"(?:^|\n)(?:Mi respuesta es|La respuesta es|Respuesta):\s*(.*?)$"
    ]
    for pattern in patterns:
        match = re.search(pattern, full_response, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()

    lines = full_response.split('\n')
    indicators = ['thinking:', 'let me think', 'i need to', 'first,', 'hmm,', 'well,', 'so,']
    response_lines = [l.strip() for l in lines if not any(ind in l.lower() for ind in indicators)]
    if response_lines:
        return '\n'.join(response_lines[-3:]).strip()
    return full_response.strip()


def generate_response(user_id, prompt):
    """Generate AI response using Ollama"""
    memory = get_user_memory(user_id, client)
    base_prompt = load_ai_prompt(user_id)
    full_prompt = f"{base_prompt}\n\nUser instruction: {prompt}"
    try:
        print(f"[{user_id}] Calling Ollama model '{MODEL_NAME}'...")
        start_time = time.time()
        full_response = ollama.generate(model=MODEL_NAME, prompt=full_prompt)['response']
        duration = time.time() - start_time
        response = extract_final_response(full_response)
        if len(response) > MAX_RESPONSE_LENGTH:
            response = response[:MAX_RESPONSE_LENGTH] + "\n\n[Response truncated due to length limit]"
        print(f"[{user_id}] Response received in {duration:.2f} seconds.")
        store_in_memory(memory, prompt, response, MODEL_NAME, user_id)
        log_user_interaction(user_id, prompt, response)
        update_user_summary(user_id, prompt, response)
        return response
    except Exception as e:
        error_msg = f"Ha ocurrido un error durante el procesamiento: {str(e)}"
        print(f"[{user_id}] ERROR during generation:")
        traceback.print_exc()
        return error_msg
