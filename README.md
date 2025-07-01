# Blimsey: Your Local Universal AI Assistant

Blimsey is an open-source, offline-first AI assistant that evolves with you. It is designed to run locally on modest hardware (even a simple laptop), supporting versatile extensions such as Telegram, CLI, or custom front-ends.

Think of it as a cross between a personal chatbot, a learning companion, and a modular brain you can grow — one prompt at a time.

---

## ✨ Features

- ✅ **Offline-first**: Runs locally using Ollama + ChromaDB.
- ✅ **Self-improving**: Stores user history, learns preferences, summarizes interactions.
- ✅ **Multi-channel ready**: Starts with Telegram; modular design allows CLI, WhatsApp, Browser, etc.
- ✅ **Customizable personality**: Define behavior and tone using editable prompts.
- ✅ **Modular memory**: Summaries, logs, extracted code, and backups for each user.

---

## ⚡ Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/ac-craft8/blimsey.git
cd blimsey
```

### 2. Create and Activate Virtual Environment (Optional but Recommended)

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Required Libraries

```bash
pip install -r requirements.txt
```

### 4. Download or Pull a Model with Ollama

Blimsey uses local models through [Ollama](https://ollama.com). Start by installing Ollama and downloading a model:

```bash
ollama run mistral
```

Or any other model supported by your system:

```bash
ollama pull llama2
```

> **Note**: The model name must match the one set in `settings.py`.

---

## 🌐 Configuration

### Required Files

Before running, make sure the following files exist:

- `settings.py`: Core configuration (example below).
- `telegram_token.txt`: Your Telegram bot token.
- `prompt.txt`: Custom behavior prompt for Blimsey.
- `whitelist.txt`: (Optional) List of allowed user IDs.
- `keywordPhrases.txt`: Words that trigger summary updates.

### Example: `settings.py`

```python
model = "mistral:latest"      # Ollama model name
Logs = 5                       # Number of past messages to retrieve
whitelist = True              # Enable user access restriction
```

### Example: `prompt.txt`

```text
You are Blimsey, a helpful and charming AI assistant with memory and personality.
Always consider the user's preferences and summarize their habits.

Context: {context}
Summary: {summary}
Prompt: {prompt}
```

> You can replace this with a Tamagotchi-style personality or anything you want.

---

## 📱 Telegram Setup

1. [Create a new bot](https://t.me/BotFather) via Telegram.
2. Copy the API token and save it in a file called `telegram_token.txt`
3. Run the bot:

```bash
python main.py
```

You should see logs indicating the bot is online. Start chatting with it on Telegram!

---

## 📊 Memory and Logging

- Logs are stored per user in the `logs/` folder.
- Memory is managed using ChromaDB and auto-saved in `./chroma_memoria/`
- Backups of all memory are stored in `user_backups_<model>/`
- If the assistant sees keywords like "I am", "my name is", or "I like", it updates summaries.
- Memory management functions reside in `memory_manager.py` for loading, querying, and storing user data.

---

## 🏠 Extending Blimsey

The core system checks for available connection modules in `settings.py`. If new communication channels are defined (e.g. `whatsapp = True`), you can simply create a new file (e.g. `whatsapp_handler.py`) and plug it into `main.py`.

### Example `settings.py` for modularity:

```python
model = "mistral:latest"
Logs = 5
whitelist = False
telegram = True
cli = False
whatsapp = False
```

> In future versions, Blimsey will auto-detect these flags and load modules dynamically.

---

## ⚡ Developer Notes

- Written in **pure Python** for maximum portability.
- Only requires `ollama`, `chromadb`, and `python-telegram-bot`.
- All state is local and editable — JSON logs, backups, prompt injection.
- Fully compatible with private or air-gapped setups.

---

## 📘 License

MIT License. Open-source, free to use and extend. Contributions welcome!

---

## ☕ Support Blimsey

If you like this project and want to support its evolution, consider buying me a coffee!

[![Buy Me a Coffee](https://img.shields.io/badge/-Buy%20me%20a%20coffee-ffdd00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/ac.craft8)


## 🚀 Coming Soon

- CLI interface for terminal users
- WhatsApp and browser modules
- Modular skill packs (productivity, coding, journaling)
- Voice input/output support

---

> Created with love by [@ac.craft8](https://github.com/ac.craft8) ❤ Blimsey will grow with you.

