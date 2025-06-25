# ===============================================================
#  File: memory_manager.py
#  Description: Memory management module for Blimsey AI assistant.
#               Handles user memory operations, including querying,
#               storing interactions, and managing backups.
#
#  Author: ac.craft8
#  Created: 2025-06-24
#
#  License: MIT
# ===============================================================

# ================================
#  Module and Library Imports
# ================================
import os
import time
import json
import re
import chromadb
from settings import enable_memory

# ================================
#  Memory Management Functions
# ================================

def load_chroma_client():
    """Initialize ChromaDB client if memory is enabled"""
    if enable_memory:
        try:
            client = chromadb.Client(
                settings=chromadb.config.Settings(
                    persist_directory="./chroma_memoria"
                )
            )
            print("[Memory] ChromaDB memory system ENABLED.")
            return client
        except Exception as e:
            print(f"[Memory] ERROR initializing ChromaDB: {e}")
            return None
    else:
        print("[Memory] ChromaDB memory system DISABLED in settings.py.")
        return None

def get_memory_key(user_id):
    """Generate memory key for user"""
    return f"user_{user_id}"

def get_user_memory(user_id, client):
    """Get or create user memory collection if enabled"""
    if not client:
        return None
    return client.get_or_create_collection(name=get_memory_key(user_id))

def query_memory(memory, prompt):
    """Query user memory for relevant context"""
    if not memory:
        return "Memory is disabled."
    try:
        result = memory.query(query_texts=[prompt], n_results=5, include=['documents'])
        documents = [doc for sublist in result['documents'] for doc in sublist if doc.strip()]
        return "\n---\n".join(documents[:5]) if documents else "No relevant previous context found."
    except Exception as e:
        print(f"ERROR querying memory: {e}")
        return "Memory query failed."

def get_last_interaction(memory):
    """Get the most recent interaction from memory"""
    if not memory:
        return "Memory is disabled."
    try:
        data = memory.get()
        return data["documents"][-1] if data["documents"] else "No previous conversation history."
    except Exception as e:
        print(f"ERROR getting last interaction: {e}")
        return "Could not retrieve last interaction."

def store_in_memory(memory, prompt, response, model_name, user_id):
    """Store interaction in memory and create backups"""
    if not memory:
        print("[Memory] Skipped storing interaction - memory is disabled.")
        return
    try:
        memory.add(
            documents=[f"User: {prompt}\nAssistant: {response}"],
            ids=[str(time.time())]
        )
        user_dir = f"./user_backups_{model_name.replace(':', '_').replace('.', '_')}"
        os.makedirs(user_dir, exist_ok=True)
        backup_file = os.path.join(user_dir, f"{get_memory_key(user_id)}.json")

        all_data = memory.get()
        backup = [{"id": id_, "text": doc} for id_, doc in zip(all_data['ids'], all_data['documents'])]

        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)

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
