# ===============================================================
#  File: main.py
#  Description: Entry point orchestrating the Blimsey assistant
#
#  Author: ac.craft8
#  Created: 2025-06-24
#  License: MIT
# ===============================================================

# ================================
#  Module and Library Imports
# ================================
import traceback
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

from config_loader import load_model_from_settings, load_telegram_token, load_whitelist
from core.logger import setup_logging
from handlers.telegram_handler import handle_message
from handlers.command_handler import reload_command
from core.ai_engine import MAX_RESPONSE_LENGTH
from handlers.telegram_handler import DEBOUNCE_DELAY_SECONDS


# ================================
#  Main Orchestration
# ================================

def main():
    """Start the Telegram bot and register handlers"""
    model_name = load_model_from_settings()
    token = load_telegram_token()
    whitelist, user_whitelist = load_whitelist()
    setup_logging()

    if not token:
        print("ERROR: Cannot start bot without Telegram token.")
        return

    print("=== Telegram Assistant Bot Starting ===")
    print(f"Model: {model_name}")
    print(f"Whitelist enabled: {whitelist}")
    if whitelist:
        print(f"Authorized users: {user_whitelist}")
    print(f"Max response length: {MAX_RESPONSE_LENGTH} characters")
    print(f"Debounce delay: {DEBOUNCE_DELAY_SECONDS} seconds")
    print("Summary system: ENABLED")

    try:
        updater = Updater(token=token, use_context=True)
        dp = updater.dispatcher
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
