
# ===============================================================
#  File: main.py
#  Description: Local AI assistant engine for lightweight systems.
#               Handles user memory, Telegram bot interface,
#               summarization, and persistent learning.
#
#  Author: ac.craft8
#  Created: 2025-06-15
#
#  License: MIT
#  Requirements: See requirements.txt for dependencies.
# ===============================================================

# ================================
#  Module and Library Imports
# ================================

# ===== Standard Library Imports =====
import json
import logging
import os
import re
import subprocess
import threading
import time
import traceback
from datetime import datetime

# ===== Third-Party Library Imports =====
import chromadb
import ollama
from telegram import ParseMode
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

# ===== Local Module Imports =====
from config_loader import (
    load_model_from_settings,
    load_telegram_token,
    load_ai_prompt,
    load_whitelist,
    load_keyword_phrases,
)
import bootstrap
bootstrap.ensure_required_files()
from messages import processing_lock_message
from config_loader import load_chroma_client


# ================================
#  Configuration Constants
# ================================
LOCK_TIMEOUT_SECONDS = 1000
MAX_RESPONSE_LENGTH = 4000
DEBOUNCE_DELAY_SECONDS = 5 

# ================================
#  Global Variables
# ================================
locks = {}
lock_timeouts = {}
pending_prompts = {}
user_timers = {}
user_pending_messages = {}

# ================================
#  Initialize ChromaDB Client
# ================================
client = load_chroma_client()


def is_model_installed(model_name):
    """Check if the specified Ollama model is installed locally"""
    try:
        result = subprocess.check_output(["ollama", "list"], stderr=subprocess.DEVNULL).decode()
        return any(model_name.split(":")[0] in line for line in result.splitlines())
    except Exception as e:
        print(f"ERROR checking installed models: {e}")
        return False

# Load configurations

MODEL_NAME = load_model_from_settings()
TELEGRAM_TOKEN = load_telegram_token()
WHITELIST, USER_WHITELIST = load_whitelist()

# Logging setup
def setup_logging():
    """Initialize logging system"""
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # General logs setup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        handlers=[
            logging.FileHandler('messages.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # Response logger
    response_logger = logging.getLogger('responses')
    response_handler = logging.FileHandler('responses.log', encoding='utf-8')
    response_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    response_logger.addHandler(response_handler)
    response_logger.setLevel(logging.INFO)
    
    return response_logger

response_logger = setup_logging()

def log_user_interaction(user_id, message, response):
    """Log user interaction to individual user JSON file"""
    user_dir = os.path.join('logs', str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    
    user_log_file = os.path.join(user_dir, 'user.json')
    
    interaction = {
        'timestamp': datetime.now().isoformat(),
        'message': message,
        'response': response
    }
    
    try:
        # Load existing logs
        if os.path.exists(user_log_file):
            with open(user_log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        else:
            logs = []
        
        # Append new interaction
        logs.append(interaction)
        
        # Save back to file
        with open(user_log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"ERROR logging user interaction for {user_id}: {e}")

# Summary management functions
def get_user_summary_path(user_id):
    """Get user summary file path"""
    user_dir = os.path.join('logs', str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, 'summary.json')

def load_user_summary(user_id):
    """Load user summary from file"""
    summary_path = get_user_summary_path(user_id)
    try:
        if os.path.exists(summary_path):
            with open(summary_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                'personal_info': {},
                'preferences': {},
                'important_topics': [],
                'last_updated': datetime.now().isoformat()
            }
    except Exception as e:
        print(f"ERROR loading summary for user {user_id}: {e}")
        return {
            'personal_info': {},
            'preferences': {},
            'important_topics': [],
            'last_updated': datetime.now().isoformat()
        }

def save_user_summary(user_id, summary):
    """Save user summary to file, cleanly merging data and avoiding duplicates/errors"""
    summary_path = get_user_summary_path(user_id)
    try:
        summary['last_updated'] = datetime.now().isoformat()

        if os.path.exists(summary_path):
            with open(summary_path, 'r', encoding='utf-8') as f:
                existing_summary = json.load(f)
        else:
            existing_summary = {
                'personal_info': {},
                'preferences': {},
                'important_topics': [],
                'contradictions': {},
                'last_updated': datetime.now().isoformat()
            }

        def normalize_to_list(value):
            if isinstance(value, list):
                result = []
                for item in value:
                    if isinstance(item, list):
                        result.extend(item)
                    else:
                        result.append(item)
                return result
            return [value]

        def clean_values(values):
            flat = normalize_to_list(values)
            result = []
            for val in flat:
                if isinstance(val, str):
                    # Split "A, B" into ["A", "B"]
                    split_vals = [v.strip() for v in val.split(',')]
                    result.extend(split_vals)
                else:
                    result.append(str(val).strip())
            # Remove duplicates and empty strings
            return sorted(set(v for v in result if v and v.lower() != "no se proporcionó"))

        # --- Personal Info ---
        for key, value in summary.get('personal_info', {}).items():
            new_vals = clean_values(value)
            old_vals = clean_values(existing_summary['personal_info'].get(key, []))
            merged = sorted(set(old_vals + new_vals))
            if merged:
                existing_summary['personal_info'][key] = merged[0] if len(merged) == 1 else merged

        # --- Preferences ---
        for key, value in summary.get('preferences', {}).items():
            new_vals = clean_values(value)
            old_vals = clean_values(existing_summary['preferences'].get(key, []))
            merged = sorted(set(old_vals + new_vals))
            if merged:
                existing_summary['preferences'][key] = merged[0] if len(merged) == 1 else merged

        # --- Important topics ---
        new_topics = clean_values(summary.get('important_topics', []))
        for topic in new_topics:
            if topic and topic not in existing_summary['important_topics']:
                existing_summary['important_topics'].append(topic)

        existing_summary['important_topics'] = existing_summary['important_topics'][-10:]
        existing_summary['last_updated'] = summary['last_updated']

        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(existing_summary, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"ERROR saving summary for user {user_id}: {e}")

def should_update_summary(prompt, response):
    """Determine if summary should be updated based on content"""
    # Load keywords from file
    important_keywords = load_keyword_phrases()
    
    prompt_lower = prompt.lower()
    response_lower = response.lower()
    
    # Check if any important keyword is present
    for keyword in important_keywords:
        if keyword in prompt_lower:
            return True
    
    # Check for personal information patterns
    personal_patterns = [
        r'\bme llamo \w+', r'\bmi nombre es \w+', r'\bsoy \w+',
        r'\btrabajo en \w+', r'\bvivo en \w+', r'\btengo \d+',
        r'\bmi .+ es \w+', r'\bestoy aprendiendo \w+',
        r'\bme dedico a \w+', r'\bmi profesión es \w+',
        r'\bmi edad es \d+', r'\btengo \d+ años'
    ]
    
    for pattern in personal_patterns:
        if re.search(pattern, prompt_lower):
            return True
    
    # Check if prompt is longer than 20 words (likely contains detailed info)
    if len(prompt.split()) > 20:
        return True
    
    return False

def update_user_summary(user_id, prompt, response):
    """Update user summary with new information"""
    if not should_update_summary(prompt, response):
        print(f"[{user_id}] Summary update not needed - no important keywords detected")
        return

    summary = load_user_summary(user_id)
    print(f"[{user_id}] Summary update triggered - processing...")

    # Create simplified update prompt that works better with most models
    update_prompt = f"""Analiza esta conversación y extrae información importante del usuario:

Conversación:
Usuario: {prompt}
Asistente: {response}

Extrae SOLO información nueva e importante sobre:
- Nombre, edad, ubicación, profesión
- Gustos, preferencias, intereses
- Proyectos, objetivos, metas
- Cualquier dato personal relevante

Responde en formato JSON simple:
{{"personal_info": {{"nombre": "valor", "trabajo": "valor"}}, "preferences": {{"le_gusta": "valor"}}, "important_topics": ["tema"], "changes_made": ["cambio realizado"]}}"""

    try:
        print(f"[{user_id}] Calling AI for summary extraction...")
        ai_response = ollama.generate(model=MODEL_NAME, prompt=update_prompt)['response']
        print(f"[{user_id}] AI Response for summary: {ai_response[:200]}...")

        # Try multiple approaches to extract JSON
        update_data = None

        # Method 1: Look for complete JSON block
        json_patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested JSON
            r'\{.*?\}',  # Simple JSON
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, ai_response, re.DOTALL)
            for match in matches:
                try:
                    update_data = json.loads(match.strip())
                    print(f"[{user_id}] JSON parsed successfully with pattern")
                    break
                except json.JSONDecodeError:
                    continue
            if update_data:
                break

        # Method 2: Manual extraction if JSON parsing fails
        if not update_data:
            print(f"[{user_id}] JSON parsing failed, attempting manual extraction...")
            update_data = {"personal_info": {}, "preferences": {}, "important_topics": [], "changes_made": []}

            # Extract name
            name_match = re.search(r'(?:mi nombre es|me llamo|soy)\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+)', prompt.lower())
            if name_match:
                update_data["personal_info"]["nombre"] = name_match.group(1).strip().title()
                update_data["changes_made"].append(f"Nombre identificado: {name_match.group(1).strip().title()}")

            # Extract work/profession
            work_match = re.search(r'(?:trabajo en|soy|mi trabajo es)\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+)', prompt.lower())
            if work_match and 'nombre' not in work_match.group(1).lower():
                update_data["personal_info"]["trabajo"] = work_match.group(1).strip()
                update_data["changes_made"].append(f"Trabajo identificado: {work_match.group(1).strip()}")

            # Extract preferences
            like_match = re.search(r'(?:me gusta|prefiero|amo)\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+)', prompt.lower())
            if like_match:
                update_data["preferences"]["le_gusta"] = like_match.group(1).strip()
                update_data["changes_made"].append(f"Preferencia identificada: {like_match.group(1).strip()}")

        # Update summary if we have data
        if update_data:
            changes_made = False

            # PERSONAL INFO — append instead of overwrite (modo string)
            if update_data.get('personal_info'):
                for key, value in update_data['personal_info'].items():
                    if isinstance(value, list):
                        incoming_str = ", ".join(str(v).strip() for v in value if v)
                    else:
                        incoming_str = str(value).strip() if value else ""
                    if incoming_str:
                        existing = summary['personal_info'].get(key, "")
                        if existing:
                            summary['personal_info'][key] = f"{existing}, {incoming_str}"
                        else:
                            summary['personal_info'][key] = incoming_str
                        changes_made = True

            # PREFERENCES — append instead of overwrite (modo string)
            if update_data.get('preferences'):
                for key, value in update_data['preferences'].items():
                    if isinstance(value, list):
                        incoming_str = ", ".join(str(v).strip() for v in value if v)
                    else:
                        incoming_str = str(value).strip() if value else ""
                    if incoming_str:
                        existing = summary['preferences'].get(key, "")
                        if existing:
                            summary['preferences'][key] = f"{existing}, {incoming_str}"
                        else:
                            summary['preferences'][key] = incoming_str
                        changes_made = True

            # IMPORTANT TOPICS
            if update_data.get('important_topics'):
                for topic in update_data['important_topics']:
                    if topic and topic.strip() and topic not in summary['important_topics']:
                        summary['important_topics'].append(topic.strip())
                        changes_made = True

            # Keep only last 10 important topics
            summary['important_topics'] = summary['important_topics'][-10:]

            if changes_made:
                save_user_summary(user_id, summary)
                changes = update_data.get('changes_made', ['Información actualizada'])
                print(f"[{user_id}] Summary updated successfully: {changes}")
            else:
                print(f"[{user_id}] No new information to add to summary")
        else:
            print(f"[{user_id}] Could not extract information for summary")

    except Exception as e:
        print(f"ERROR updating summary for user {user_id}: {e}")
        traceback.print_exc()

def get_summary_text(user_id):
    """Get formatted summary text for context"""
    summary = load_user_summary(user_id)
    
    summary_parts = []
    
    if summary['personal_info']:
        info_text = ", ".join([f"{k}: {v}" for k, v in summary['personal_info'].items()])
        summary_parts.append(f"Información personal: {info_text}")
    
    if summary['preferences']:
        pref_text = ", ".join([f"{k}: {v}" for k, v in summary['preferences'].items()])
        summary_parts.append(f"Preferencias: {pref_text}")
    
    if summary['important_topics']:
        topics_text = ", ".join(summary['important_topics'])
        summary_parts.append(f"Temas importantes: {topics_text}")
    
    if summary_parts:
        return ". ".join(summary_parts)
    else:
        return "No hay información de resumen disponible."

# Memory management functions
def get_memory_key(user_id):
    """Generate memory key for user"""
    return f"user_{user_id}"

def get_user_memory(user_id):
    """Get or create user memory collection if enabled"""
    if not client:
        return None
    return client.get_or_create_collection(name=get_memory_key(user_id))


def query_memory(memory, prompt):
    """Query user memory for relevant context"""
    def store_in_memory(memory, prompt, response, model_name, user_id):
            if not memory:
                print("[Memory] Skipped storing interaction - memory is disabled.")
            return   
    print(f"[{time.ctime()}] Querying memory for prompt.")
    try:
        result = memory.query(query_texts=[prompt], n_results=5, include=['documents'])
        documents = [doc for sublist in result['documents'] for doc in sublist if doc.strip()]
        if documents:
            return "\n---\n".join(documents[:5])
        return "No relevant previous context found."
    except Exception as e:
        print(f"ERROR querying memory: {e}")
        return "Memory query failed."

def get_last_interaction(memory):
    """Get the most recent interaction from memory"""
    def store_in_memory(memory, prompt, response, model_name, user_id):
        if not memory:
            print("[Memory] Skipped storing interaction - memory is disabled.")
        return   
    try:
        data = memory.get()
        if not data["documents"]:
            return "No previous conversation history."
        last_doc = data["documents"][-1]
        return f"Last interaction: {last_doc}"
    except Exception as e:
        print(f"ERROR getting last interaction: {e}")
        return "Could not retrieve last interaction."

def store_in_memory(memory, prompt, response, model_name, user_id):
    """Store interaction in memory and create backups"""
    def store_in_memory(memory, prompt, response, model_name, user_id):
        if not memory:
            print("[Memory] Skipped storing interaction - memory is disabled.")
        return    
    print(f"[{time.ctime()}] Storing interaction in memory.")
    try:
        # Store in ChromaDB
        memory.add(
            documents=[f"User: {prompt}\nAssistant: {response}"],
            ids=[str(time.time())]
        )
        
        # Create backup
        user_dir = f"./user_backups_{model_name.replace(':', '_').replace('.', '_')}"
        os.makedirs(user_dir, exist_ok=True)
        backup_file = os.path.join(user_dir, f"{get_memory_key(user_id)}.json")
        
        all_data = memory.get()
        backup = [{"id": id, "text": doc} for id, doc in zip(all_data['ids'], all_data['documents'])]
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
        
        # Extract and save code blocks
        code_blocks = re.findall(r"```python\n(.*?)```", response, re.DOTALL)
        if code_blocks:
            code_dir = os.path.join("./codigo_extraido", get_memory_key(user_id))
            os.makedirs(code_dir, exist_ok=True)
            
            for i, block in enumerate(code_blocks):
                filename = f"respuesta_{int(time.time())}_bloque{i + 1}.py"
                filepath = os.path.join(code_dir, filename)
                with open(filepath, "w", encoding="utf-8") as code_file:
                    code_file.write(block.strip())
                    
    except Exception as e:
        print(f"ERROR storing in memory: {e}")

    
    """Store interaction in memory and create backups"""
    print(f"[{time.ctime()}] Storing interaction in memory.")
    try:
        # Store in ChromaDB
        memory.add(
            documents=[f"User: {prompt}\nAssistant: {response}"],
            ids=[str(time.time())]
        )
        
        # Create backup
        user_dir = f"./user_backups_{model_name.replace(':', '_').replace('.', '_')}"
        os.makedirs(user_dir, exist_ok=True)
        backup_file = os.path.join(user_dir, f"{get_memory_key(user_id)}.json")
        
        all_data = memory.get()
        backup = [{"id": id, "text": doc} for id, doc in zip(all_data['ids'], all_data['documents'])]
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
        
        # Extract and save code blocks
        code_blocks = re.findall(r"```python\n(.*?)```", response, re.DOTALL)
        if code_blocks:
            code_dir = os.path.join("./codigo_extraido", get_memory_key(user_id))
            os.makedirs(code_dir, exist_ok=True)
            
            for i, block in enumerate(code_blocks):
                filename = f"respuesta_{int(time.time())}_bloque{i + 1}.py"
                filepath = os.path.join(code_dir, filename)
                with open(filepath, "w", encoding="utf-8") as code_file:
                    code_file.write(block.strip())
                    
    except Exception as e:
        print(f"ERROR storing in memory: {e}")

def extract_final_response(full_response):
    """Extract only the final response from the model output, removing thinking process"""
    # Si la respuesta contiene markdown para pensamiento (como en algunos modelos)
    # buscamos patrones comunes de separación
    
    # Patrón 1: Buscar después de "Responde:" o similar
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
    
    # Si no encuentra patrones específicos, busca la última línea que no sea pensamiento
    lines = full_response.split('\n')
    
    # Filtrar líneas que parecen ser pensamiento interno
    thinking_indicators = ['thinking:', 'let me think', 'i need to', 'first,', 'hmm,', 'well,', 'so,']
    
    response_lines = []
    for line in lines:
        line_lower = line.lower().strip()
        if not any(indicator in line_lower for indicator in thinking_indicators):
            response_lines.append(line.strip())
    
    if response_lines:
        # Tomar las últimas líneas que no son pensamiento
        return '\n'.join(response_lines[-3:]).strip()
    
    # Si todo falla, devolver la respuesta completa pero limitada
    return full_response.strip()

# AI Response generation
'''def generate_response(user_id, prompt):
    """Generate AI response using Ollama"""
    memory = get_user_memory(user_id)
    context = query_memory(memory, prompt)
    recent_context = get_last_interaction(memory)
    summary = get_summary_text(user_id)
    
    full_context = f"{context}\n\n{recent_context}"
    full_prompt = AI_PROMPT_TEMPLATE.format(context=full_context, summary=summary, prompt=prompt)
    
    try:
        print(f"[{user_id}] Calling Ollama model '{MODEL_NAME}'...")
        start_time = time.time()
        full_response = ollama.generate(model=MODEL_NAME, prompt=full_prompt)['response']
        duration = time.time() - start_time
        
        # Extraer solo la respuesta final, sin el proceso de pensamiento
        response = extract_final_response(full_response)
        
        # Limit response length
        if len(response) > MAX_RESPONSE_LENGTH:
            response = response[:MAX_RESPONSE_LENGTH] + "\n\n[Response truncated due to length limit]"
        
        print(f"[{user_id}] Response received in {duration:.2f} seconds.")
        
        # Store in memory and log
        store_in_memory(memory, prompt, response, MODEL_NAME, user_id)
        log_user_interaction(user_id, prompt, response)
        
        # Update summary if needed
        update_user_summary(user_id, prompt, response)
        
        return response
        
    except Exception as e:
        error_msg = f"Ha ocurrido un error durante el procesamiento: {str(e)}"
        print(f"[{user_id}] ERROR during generation:")
        traceback.print_exc()
        return error_msg'''

def generate_response(user_id, prompt):
    """Generate AI response using Ollama"""
    memory = get_user_memory(user_id)
    base_prompt = load_ai_prompt(user_id)  # <-- nuevo comportamiento
    full_prompt = f"{base_prompt}\n\nUser instruction: {prompt}"

    try:
        print(f"[{user_id}] Calling Ollama model '{MODEL_NAME}'...")
        start_time = time.time()
        full_response = ollama.generate(model=MODEL_NAME, prompt=full_prompt)['response']
        duration = time.time() - start_time

        # Extraer solo la respuesta final, sin el proceso de pensamiento
        response = extract_final_response(full_response)

        # Limitar longitud si excede
        if len(response) > MAX_RESPONSE_LENGTH:
            response = response[:MAX_RESPONSE_LENGTH] + "\n\n[Response truncated due to length limit]"

        print(f"[{user_id}] Response received in {duration:.2f} seconds.")

        # Guardar memoria, logs, y actualizar resumen si aplica
        store_in_memory(memory, prompt, response, MODEL_NAME, user_id)
        log_user_interaction(user_id, prompt, response)
        update_user_summary(user_id, prompt, response)

        return response

    except Exception as e:
        error_msg = f"Ha ocurrido un error durante el procesamiento: {str(e)}"
        print(f"[{user_id}] ERROR during generation:")
        traceback.print_exc()
        return error_msg


# Lock management
def reset_lock(user_id):
    """Reset user lock after timeout"""
    if locks.get(user_id):
        print(f"[Telegram] Lock timeout for user {user_id}. Resetting lock.")
        locks[user_id] = False

# Debouncing mechanism
def process_debounced_messages(user_id, update):
    """Process accumulated messages after debounce delay"""
    if user_id in user_pending_messages:
        # Combine all pending messages
        messages = user_pending_messages[user_id]
        combined_prompt = "\n".join(messages)
        
        # Clear pending messages
        del user_pending_messages[user_id]
        
        # Process the combined prompt
        process_user_message(user_id, combined_prompt, update)

def schedule_debounced_response(user_id, message, update):
    """Schedule or reschedule debounced response"""
    # Cancel existing timer if any
    if user_id in user_timers:
        user_timers[user_id].cancel()
    
    # Add message to pending messages
    if user_id not in user_pending_messages:
        user_pending_messages[user_id] = []
    user_pending_messages[user_id].append(message)
    
    # Schedule new timer
    timer = threading.Timer(DEBOUNCE_DELAY_SECONDS, process_debounced_messages, args=(user_id, update))
    user_timers[user_id] = timer
    timer.start()
    
    print(f"[{user_id}] Message queued. Debounce timer set for {DEBOUNCE_DELAY_SECONDS} seconds.")

def process_user_message(user_id, prompt, update):
    """Process user message and generate response"""
    if locks.get(user_id, False):
        return  # Already processing
    
    def reply():
        try:
            locks[user_id] = True
            lock_timeouts[user_id] = threading.Timer(LOCK_TIMEOUT_SECONDS, reset_lock, args=(user_id,))
            lock_timeouts[user_id].start()
            
            print(f"[{user_id}] Processing prompt: {prompt[:100]}...")
            update.message.reply_text("Pensando...", parse_mode=ParseMode.MARKDOWN)
            
            response = generate_response(user_id, prompt)
            
            # Send response in chunks if needed
            MAX_MESSAGE_LENGTH = 4096
            for i in range(0, len(response), MAX_MESSAGE_LENGTH):
                chunk = response[i:i+MAX_MESSAGE_LENGTH]
                update.message.reply_text(chunk, parse_mode=None)
            
            # Log the interaction
            logging.info(f"User {user_id}: {prompt}")
            response_logger.info(f"Response to {user_id}: {response}")
            
            print(f"[{user_id}] Response sent.")
            
        except Exception as e:
            error_msg = f"Error al procesar el mensaje: {str(e)}"
            update.message.reply_text(error_msg)
            print(f"[{user_id}] ERROR in reply thread: {e}")
            traceback.print_exc()
        finally:
            if lock_timeouts.get(user_id):
                lock_timeouts[user_id].cancel()
            locks[user_id] = False

    threading.Thread(target=reply, daemon=True).start()

# Telegram handlers
def handle_message(update, context):
    """Handle incoming Telegram messages"""
    user_id = update.effective_user.id
    message = update.message.text.strip()
    
    # Check whitelist if enabled
    if WHITELIST and user_id not in USER_WHITELIST:
        update.message.reply_text("No tienes autorización para usar este asistente.")
        return
    
    # Check if user is locked (processing)
    if locks.get(user_id, False):
        update.message.reply_text(processing_lock_message)
        return
    
    # Use debouncing mechanism
    schedule_debounced_response(user_id, message, update)

def reload_command(update, context):
    """Handle reload command"""
    user_id = update.effective_user.id
    
    if WHITELIST and user_id not in USER_WHITELIST:
        update.message.reply_text("No tienes autorización para usar este comando.")
        return
    
    memory = get_user_memory(user_id)
    try:
        if not memory.get()["documents"]:
            update.message.reply_text("No hay nada que persistir: la memoria está vacía.")
        else:
            update.message.reply_text("Comando reload recibido. Backup ya guardado en JSON - no se necesita persistencia adicional.")
    except Exception as e:
        update.message.reply_text(f"Error durante reload: {str(e)}")

def main():
    """Main function to start the bot"""
    if not TELEGRAM_TOKEN:
        print("ERROR: Cannot start bot without Telegram token.")
        return
    
    print("=== Telegram Assistant Bot Starting ===")
    print(f"Model: {MODEL_NAME}")
    print(f"Whitelist enabled: {WHITELIST}")
    if WHITELIST:
        print(f"Authorized users: {USER_WHITELIST}")
    print(f"Max response length: {MAX_RESPONSE_LENGTH} characters")
    print(f"Debounce delay: {DEBOUNCE_DELAY_SECONDS} seconds")
    print("Summary system: ENABLED")
    
    try:
        updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
        dp = updater.dispatcher
        
        # Add handlers
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
        dp.add_handler(CommandHandler("reload", reload_command))
        
        print("Bot handlers configured. Starting polling...")
        updater.start_polling()
        print("Bot is running. Press Ctrl+C to stop.")
        updater.idle()
        
    except Exception as e:
        print(f"ERROR starting bot: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    main()
