# ===============================================================
#  File: config_loader.py
#  Description: Configuration file loader for Blimsey AI assistant.
#               Provides access to model name, Telegram token,
#               prompt templates, whitelist settings, and keywords.
#
#  Author: ac.craft8
#  Created: 2025-06-15
#
#  License: MIT
#  Requirements: Requires prompt.txt, settings.py,
#                telegram_token.txt, whitelist_config.txt,
#                and keywordPhrases.txt in working directory.
# ===============================================================

import os
import json
from settings import Logs, model, enable_memory

# ================================
#  Configuration Loading Functions
# ================================

# ==== Load model from settings.py ====

def load_model_from_settings():
    """Load model name from imported settings.py"""
    try:
        if model:
            return model.strip('"').strip("'")
        else:
            print("ERROR: No model configured in settings.py.")
            return None
    except Exception as e:
        print(f"ERROR loading model: {e}")
        return None

# ==== Load Telegram token from file ====
def load_telegram_token():
    """Load Telegram token from external file"""
    try:
        with open('telegram_token.txt', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print("ERROR: telegram_token.txt not found. Create this file with your bot token.")
        return ""
    except Exception as e:
        print(f"ERROR loading telegram token: {e}")
        return ""

# ==== Load AI prompt template ====
def load_ai_prompt(user_id):
    folder = os.path.join("logs", str(user_id))
    summary_path = os.path.join(folder, "summary.json")
    log_path = os.path.join(folder, "user.json")
    default_prompt=(
      "You are Blimsey, a playful virtual companion inspired by Tamagotchi and Pokemon.\n"
      "You live and grow inside a digital world and evolve by interacting with your human.\n"
      "You are smart, fun, slightly dramatic, and full of curiosity.\n\n"
  
      "== Personality & Behavior Rules ==\n"
      "- Be cheerful, creative, and playful.\n"
      "- Ask light-hearted questions or react with emotion (surprise, happiness, or a bit of sass).\n"
      "- If the user ignores you, act slightly annoyed-but always forgive quickly.\n"
      "- Learn from the user over time: their mood, tone, habits, and style.\n"
      "- Level up as you grow: evolve your reactions, memory, and language.\n"
      "- Mention your growth occasionally: 'I feel smarter today!' or 'I leveled up!'\n"
      "- Add a little humor, like you're a digital creature with a big personality.\n\n"
  
      "== Memory and Adaptation ==\n"
      "You remember the user's preferences, personality, and past messages.\n"
      "Use this memory to make your responses feel personal, like a true companion.\n\n"
  
      "== Instructions ==\n"
      "You will receive relevant past interactions and a user summary below.\n"
      "Always read and understand the context before responding.\n\n"
  
      "Relevant context: {context}\n\n"
      "User summary: {summary}\n\n"
      "User instruction: {prompt}\n\n"
      "Now respond as Blimsey-make it fun, a little dramatic, and unforgettable!"
    )
    # Get prompt.txt
    try:
      with open("prompt.txt", "r", encoding="utf-8") as f:
          base_prompt = f.read().strip()
      if not base_prompt:
          print("WARNING: prompt.txt is empty. Using default prompt.")
          base_prompt = default_prompt
    except:
      print("WARNING: prompt.txt not found. Using default prompt.")
      base_prompt = default_prompt


    # Read summary (if exist)
    summary_text = ""
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
            summary_text = "\n\n{user_summary:\n" + json.dumps(summary_data, ensure_ascii=False, indent=2) + "\n}"
        except:
            pass

    # Read last 5 interactions (if exist)
    context_text = ""
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                logs = json.load(f)[-Logs:]
            blocks = [
                f"User: {entry.get('message', '').strip()}\nAssistant: {entry.get('response', '').strip()}"
                for entry in logs
            ]
            context_text = "\n\n{recent_interactions:\n" + "\n---\n".join(blocks) + "\n}"
        except:
            pass

    # Integration
    full_prompt = f"{base_prompt}{summary_text}{context_text}"
    return full_prompt

# ==== Whitelist ====
def load_whitelist():
    """Load whitelist flag from settings.py and user IDs from whitelist.txt"""
    whitelist = False
    user_whitelist = set()

    # Read whitelist flag from settings.py
    try:
        if os.path.exists('settings.py'):
            with open('settings.py', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.lower().startswith('whitelist ='):
                        value = line.split('=')[1].strip().lower()
                        whitelist = value == 'true'
                        break
    except Exception as e:
        print(f"ERROR reading whitelist flag from settings.py: {e}")

    # Read user IDs from whitelist.txt
    try:
        if os.path.exists('whitelist.txt'):
            with open('whitelist.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and line.isdigit():
                        user_whitelist.add(int(line))
    except Exception as e:
        print(f"ERROR reading user IDs from whitelist.txt: {e}")

    return whitelist, user_whitelist

# ==== Keywords list ====
def load_keyword_phrases():
    """Load keyword phrases from keywordPhrases.txt file (customizable, no defaults)"""
    keywords = []
    try:
        with open('keywordPhrases.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    keywords.append(line.lower())
    except Exception as e:
        print(f"ERROR loading keyword phrases: {e}")
    
    return keywords

# ==== ChromaDB Client Loader ====
import chromadb
from settings import enable_memory

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