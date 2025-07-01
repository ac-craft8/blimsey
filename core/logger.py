# ===============================================================
#  File: logger.py
#  Description: Logging utilities for Blimsey
#
#  Author: ac.craft8
#  Created: 2025-06-24
#  License: MIT
# ===============================================================

# ================================
#  Module and Library Imports
# ================================
import json
import logging
import os
from datetime import datetime


# ================================
#  Function Definitions
# ================================

def setup_logging():
    """Initialize logging system and return response logger"""
    os.makedirs('logs', exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        handlers=[
            logging.FileHandler('messages.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    response_logger = logging.getLogger('responses')
    handler = logging.FileHandler('responses.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    response_logger.addHandler(handler)
    response_logger.setLevel(logging.INFO)
    return response_logger


def log_user_interaction(user_id, message, response):
    """Log user interaction to per-user JSON file"""
    user_dir = os.path.join('logs', str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    user_log = os.path.join(user_dir, 'user.json')

    interaction = {
        'timestamp': datetime.now().isoformat(),
        'message': message,
        'response': response
    }

    try:
        if os.path.exists(user_log):
            with open(user_log, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        else:
            logs = []
        logs.append(interaction)
        with open(user_log, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"ERROR logging user interaction for {user_id}: {e}")
