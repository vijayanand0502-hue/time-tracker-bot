# ⏱️ Time Tracker Bot

A personal Telegram bot that captures your daily activities via voice or text, uses AI to parse and categorise them, logs everything to Notion, and sends you a daily summary at 10 PM.

## 📁 Files in this project

| File | Purpose |
|---|---|
| `main.py` | The bot code — handles messages, transcription, parsing, Notion logging, and nightly summary |
| `requirements.txt` | Python packages needed |
| `.env` | Your secret API keys (never commit this) |
| `.gitignore` | Tells Git to ignore secrets and cache files |
| `README.md` | This file |

## 🔑 Setup — fill in your `.env`

Open `.env` and replace each `PASTE_YOUR_..._HERE` with your actual value:

1. **TELEGRAM_TOKEN** — from @BotFather when you created the bot
2. **GROQ_API_KEY** — from console.groq.com/keys
3. **NOTION_API_KEY** — from your Notion connection "Time Tracker Bot"
4. **NOTION_DATABASE_ID** — already filled in
5. **TELEGRAM_CHAT_ID** — send your bot a message, then visit `https://api.telegram.org/bot<YOUR_TELEGRAM_TOKEN>/getUpdates` and find `"chat":{"id":XXXXXXXXX}`

## 🧪 Test locally (optional)

```bash
pip install -r requirements.txt
python main.py
```

Then message your bot on Telegram.

## 🚀 Deploy to Railway (for 24/7 running)

Coming next — will be added to instructions.

## 📊 What it does

- **Voice message** → Groq Whisper transcribes it
- **Text or transcript** → Groq Llama parses intent (START/END, activity, category)
- **Notion database** → new row logged with timestamp
- **10 PM daily** → AI summary of your day sent to Telegram
