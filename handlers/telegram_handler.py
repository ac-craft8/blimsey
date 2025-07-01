# ===============================================================
#  File: telegram_handler.py
#  Description: Telegram message handling for Blimsey
#
#  Author: ac.craft8
#  Created: 2025-06-24
#  License: MIT
# ===============================================================

# ================================
#  Module and Library Imports
# ================================
import threading
import logging
import traceback
from telegram import ParseMode

from config_loader import load_whitelist
from core.ai_engine import generate_response
from messages import processing_lock_message

# ================================
#  Configuration and State
# ================================
LOCK_TIMEOUT_SECONDS = 1000
DEBOUNCE_DELAY_SECONDS = 5

locks = {}
lock_timeouts = {}
user_timers = {}
user_pending_messages = {}

WHITELIST, USER_WHITELIST = load_whitelist()

# ================================
#  Function Definitions
# ================================

def reset_lock(user_id):
    """Reset user lock after timeout"""
    if locks.get(user_id):
        print(f"[Telegram] Lock timeout for user {user_id}. Resetting lock.")
        locks[user_id] = False


def process_debounced_messages(user_id, update):
    """Process accumulated messages after debounce delay"""
    if user_id in user_pending_messages:
        messages = user_pending_messages[user_id]
        combined_prompt = "\n".join(messages)
        del user_pending_messages[user_id]
        process_user_message(user_id, combined_prompt, update)


def schedule_debounced_response(user_id, message, update):
    """Schedule or reschedule debounced response"""
    if user_id in user_timers:
        user_timers[user_id].cancel()
    if user_id not in user_pending_messages:
        user_pending_messages[user_id] = []
    user_pending_messages[user_id].append(message)
    timer = threading.Timer(DEBOUNCE_DELAY_SECONDS, process_debounced_messages, args=(user_id, update))
    user_timers[user_id] = timer
    timer.start()
    print(f"[{user_id}] Message queued. Debounce timer set for {DEBOUNCE_DELAY_SECONDS} seconds.")


def process_user_message(user_id, prompt, update):
    """Process user message and generate response"""
    if locks.get(user_id, False):
        return

    def reply():
        try:
            locks[user_id] = True
            lock_timeouts[user_id] = threading.Timer(LOCK_TIMEOUT_SECONDS, reset_lock, args=(user_id,))
            lock_timeouts[user_id].start()
            print(f"[{user_id}] Processing prompt: {prompt[:100]}...")
            update.message.reply_text("Pensando...", parse_mode=ParseMode.MARKDOWN)
            response = generate_response(user_id, prompt)
            MAX_MESSAGE_LENGTH = 4096
            for i in range(0, len(response), MAX_MESSAGE_LENGTH):
                chunk = response[i:i+MAX_MESSAGE_LENGTH]
                update.message.reply_text(chunk, parse_mode=None)
            logging.info(f"User {user_id}: {prompt}")
            print(f"[{user_id}] Response sent.")
        except Exception as e:
            update.message.reply_text(f"Error al procesar el mensaje: {str(e)}")
            print(f"[{user_id}] ERROR in reply thread: {e}")
            traceback.print_exc()
        finally:
            if lock_timeouts.get(user_id):
                lock_timeouts[user_id].cancel()
            locks[user_id] = False

    threading.Thread(target=reply, daemon=True).start()


def handle_message(update, context):
    """Handle incoming Telegram messages"""
    user_id = update.effective_user.id
    message = update.message.text.strip()
    if WHITELIST and user_id not in USER_WHITELIST:
        update.message.reply_text("No tienes autorización para usar este asistente.")
        return
    if locks.get(user_id, False):
        update.message.reply_text(processing_lock_message)
        return
    schedule_debounced_response(user_id, message, update)
