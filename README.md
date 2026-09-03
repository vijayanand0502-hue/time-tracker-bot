# ⏱️ Time Tracker Bot

A personal Telegram bot that captures daily activities by voice or text, transcribes and
categorises them with AI, logs each one to Notion, and sends an honest summary of the day
at 10 PM.

**Status:** deployed and running 24/7 on Railway.

The problem it solves: understanding where the day actually goes — deep work vs meals vs
doom scrolling vs unaccounted gaps — without the friction of opening an app and filling in
a form. Talking to a Telegram bot takes three seconds.

---

## How it works

```
Telegram (voice or text)
        │
        ▼
Groq Whisper ──── transcribes voice notes to text
        │
        ▼
Groq LLM ──────── extracts { event_type, activity, category }
        │
        ▼
Notion ────────── one row per event, timestamped in Asia/Kolkata
        │
        ▼
10 PM daily ───── LLM reads the day's rows, sends a summary to Telegram
```

Send `"starting sprint planning"` and it logs a **START** / *Sprint Planning* / **Deep Work**
row. Send `"done with lunch"` and it logs the matching **END**. The nightly summary pairs
them up and tells you where the time went.

## Commands

| Command | What it does |
|---|---|
| *(any text or voice)* | Logs an activity |
| `/summary` | Today's summary on demand, without waiting for 10 PM |
| `/start` | Confirms the bot is alive and shows the schedule |

---

## Tech stack

| Layer | Tool |
|---|---|
| Capture | Telegram Bot API (`python-telegram-bot`) |
| Transcription | Groq — `whisper-large-v3-turbo` |
| Parsing + summaries | Groq — `openai/gpt-oss-20b` |
| Storage | Notion (`notion-client`) |
| Scheduling | `python-telegram-bot[job-queue]` |
| Hosting | Railway (deploys from `main` on push) |

Groq's free tier covers personal usage comfortably. Notion was chosen because it was
already the owner's system of record, so there was no migration cost.

## Files

| File | Purpose |
|---|---|
| `main.py` | The whole bot — transcription, parsing, Notion writes, summaries |
| `Time tracker PROJECT_CONTEXT.md` | Full project context: architecture, decisions, invariants, debug log |
| `AGENTS.md` / `CLAUDE.md` | Entry points for AI coding tools |
| `requirements.txt` | Pinned dependencies |
| `Procfile` | Tells Railway how to start the worker |
| `.python-version` | Pins Python 3.13 for the build |
| `.env.example` | Template for local secrets — **`.env` itself is never committed** |

---

## Running it yourself

**1. Clone and install**

```bash
git clone https://github.com/vijayanand0502-hue/time-tracker-bot.git
cd time-tracker-bot
pip3 install -r requirements.txt
```

**2. Create the Notion database** with these properties — names and Select options must
match exactly, or writes will fail:

- `Activity` — Title
- `Event Type` — Select: `START`, `END`
- `Category` — Select: `Deep Work`, `Routine`, `Meals`, `Fitness`, `Leisure`, `Sleep`, `Doom Scrolling`, `Travel`, `Social`
- `Timestamp` — Date (with time)
- `Raw Input` — Rich text

Create a Notion integration and connect it to the database, or the API returns 404.

**3. Configure secrets**

```bash
cp .env.example .env
```

Fill in `TELEGRAM_TOKEN`, `GROQ_API_KEY`, `NOTION_API_KEY`, `NOTION_DATABASE_ID`,
`TELEGRAM_CHAT_ID`. Keep `TIMEZONE` set to your own zone.

**4. Run**

```bash
python3 main.py
```

## Deploying to Railway

New project → Deploy from GitHub repo → add the five secrets **plus `TIMEZONE`** in the
Variables tab → deploy. Confirm the logs show:

```
Bot running. Timezone=Asia/Kolkata. Nightly summary at 22:00.
```

Railway may warn that no port is exposed. That's expected — this is a polling worker, not
a web service.

> ⚠️ **Only one instance may poll a given Telegram token.** Running locally while Railway
> is live produces `Conflict: terminated by other getUpdates request` and both instances
> misbehave. Pause the Railway service before debugging locally.

---

## Notes for anyone extending this

Four constraints in `main.py` are load-bearing and were each learned by hitting a real bug.
Full detail is in Section 7 and the debug log of the context file.

- **Never use bare `datetime.now()`** — use `now_local()`. Railway containers run in UTC,
  which silently shifts every Notion timestamp and moves the "10 PM" job to 03:30 IST.
- **Schedule through `app.job_queue`, never a standalone `AsyncIOScheduler`.** A scheduler
  started before `run_polling()` binds to an event loop that never runs, and the job simply
  never fires — no crash, no log line.
- **Don't trust the model's echoed timestamp.** The code stamps its own, so a hallucinated
  date can't reach Notion. Category and event type are clamped to the existing Select
  options, since off-list values silently create new ones.
- **Keep `httpx` logging at WARNING.** It logs the full Telegram API URL, which embeds the
  bot token — that would otherwise leak into Railway's deploy logs.

## Roadmap

Currently in **Phase 4** — using it daily for a week to find out whether the habit holds
before building anything further. Possible next steps (weekly summaries, automatic
duration calculation, multi-activity parsing) are deliberately gated on that.

---

*Personal project. Not intended as a product.*
