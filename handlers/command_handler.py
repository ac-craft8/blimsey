# ===============================================================
#  File: command_handler.py
#  Description: Telegram command handlers for Blimsey
#
#  Author: ac.craft8
#  Created: 2025-06-24
#  License: MIT
# ===============================================================

# ================================
#  Module and Library Imports
# ================================
from config_loader import load_whitelist
from memory_manager import load_chroma_client, get_user_memory

# ================================
#  Configuration
# ================================
client = load_chroma_client()
WHITELIST, USER_WHITELIST = load_whitelist()

# ================================
#  Function Definitions
# ================================

def reload_command(update, context):
    """Handle reload command"""
    user_id = update.effective_user.id
    if WHITELIST and user_id not in USER_WHITELIST:
        update.message.reply_text("No tienes autorización para usar este comando.")
        return
    memory = get_user_memory(user_id, client)
    try:
        if not memory.get()["documents"]:
            update.message.reply_text("No hay nada que persistir: la memoria está vacía.")
        else:
            update.message.reply_text("Comando reload recibido. Backup ya guardado en JSON - no se necesita persistencia adicional.")
    except Exception as e:
        update.message.reply_text(f"Error durante reload: {str(e)}")
