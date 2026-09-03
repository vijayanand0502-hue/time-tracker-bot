# Time Tracker Bot — Project Context

> **For any LLM picking up this project:** Read this entire file first. It contains everything needed to continue work without losing context. Last updated: 2026-09-04. **Status: deployed and running 24/7 on Railway.**

## 🔒 SECURITY INSTRUCTIONS FOR AI TOOLS

- **Never read the contents of `.env`.** Reference `.env.example` instead to understand structure.
- **Never echo actual API key values in chat responses.** Use placeholders like `<TELEGRAM_TOKEN>` in examples.
- **Never paste real keys into example code.** Always use placeholder text.
- If you need to know an env variable's format, ask the owner to share it in redacted form.

---

## 1. Project Owner

- **Name:** Vijay
- **Role:**  working toward AI Architect
- **Environment:** MacBook Air, Python via Anaconda (base), VS Code
- **OS constraint:** macOS + Google Drive (be aware Google Drive strips leading dots from filenames and caches stale versions of `.env` — real bugs were hit because of this)
- **Skill level:** Comfortable technical, wants to LEARN how things are built, not just use them blindly
- **Communication preference:** Direct, honest, no fluff. Call out failure modes and tradeoffs plainly. Flag uncertainty explicitly ("I'm not certain, verify at…"). Never invent facts, URLs, or sources.

---

## 2. What This Project Is

A personal time-tracking system that captures the owner's activities through voice or text messages sent to a Telegram bot. AI transcribes, categorizes, and logs each entry to a Notion database. Sends an automated nightly summary at 10 PM with insights.

**The core problem it solves:** Understanding where time actually goes each day — deep work vs meals vs doom scrolling vs unaccounted gaps.

**Explicit non-goals right now:** Not building this as a product for others. Personal-use only. Validate the habit first, then consider productizing.

---

## 3. Current Status (as of 2026-09-04)

**Phases 1–3 are complete. The bot is live on Railway, running 24/7, independent of the laptop.**

- ✅ Telegram bot created via @BotFather
- ✅ Notion database created (Time Log) under Life OS with all views
- ✅ Notion "Time Tracker Bot" connection created and connected to database
- ✅ Groq API key active (free tier)
- ✅ Local bot working end-to-end: text + voice → transcription → parse → Notion log → Telegram confirmation
- ✅ Notion entries confirmed appearing correctly
- ✅ **Nightly summary bug found and fixed** — it could never have fired (see Section 12)
- ✅ Timezone handling added (`Asia/Kolkata`) — required before Railway, which runs in UTC
- ✅ `/summary` command added; verified working end-to-end against real Notion data
- ✅ Code in git, pushed to GitHub: `vijayanand0502-hue/time-tracker-bot` (private)
- ✅ **Deployed to Railway — running 24/7**, no longer tied to the laptop
- ⚠️ The 10 PM automatic summary has been verified by code path and by `/summary`,
  but has not yet been *observed* firing on its own schedule on Railway. Confirm this
  on the first night, then tick it off here.
- ⚠️ Local runs now conflict with Railway — only one poller per Telegram token

---

## 4. Tech Stack

| Layer | Tool | Notes |
|---|---|---|
| Capture interface | Telegram Bot | Free forever. Bot: (owner's bot username) |
| Backend runtime | Python 3.13 (Anaconda base) | Currently local; will move to Railway |
| Voice-to-text | Groq Whisper (`whisper-large-v3-turbo`) | Free tier: 20 RPM, 2K/day |
| Text parsing + summary | Groq LLM (`openai/gpt-oss-20b`) | Free tier: 30 RPM, 1K/day |
| Storage | Notion (via `notion-client` Python SDK) | Uses internal integration |
| Scheduler | PTB `JobQueue` (wraps APScheduler) | For 10 PM nightly summary. Must NOT be a standalone `AsyncIOScheduler` — see Section 12 |
| Hosting (planned) | Railway | Free tier ($5 credit/month) |

### Python dependencies (`requirements.txt`)

```
python-telegram-bot[job-queue]==21.7
groq==0.13.0
notion-client==2.2.1
python-dotenv==1.0.0
apscheduler==3.10.4
```

> The `[job-queue]` extra matters: scheduling now goes through PTB's own `JobQueue`
> rather than a hand-rolled `AsyncIOScheduler`. See Section 12.

**Version notes learned the hard way:**
- `python-telegram-bot==20.7` breaks on Python 3.13 — must use 21.7+
- `groq==0.11.0` fails with newer `httpx` (`proxies` kwarg removed) — must use 0.13.0+
- Model `llama-3.3-70b-versatile` is not on Groq's free tier — use `openai/gpt-oss-20b` instead
- Model `llama-3.1-8b-instant` is also not on the free tier despite being listed on the general Models page

---

## 5. File Structure

Located at: `/Users/vj/Library/CloudStorage/GoogleDrive-vijayanand.0502@gmail.com/My Drive/Claude Cowork/Time Tracker/`

```
Time Tracker/
├── main.py              # The bot code (see Section 7)
├── main.py.bak          # Pre-fix backup — delete once the new version is trusted
├── requirements.txt     # Python dependencies
├── Procfile             # Tells Railway how to start: `worker: python main.py`
├── .python-version      # Pins Python 3.13 for the Railway builder
├── .env                 # Secret API keys (NEVER commit)
├── .env.example         # Committed template, no real values
├── .gitignore           # Ignores .env; explicitly un-ignores .env.example
├── README.md            # Basic setup instructions
└── Time tracker PROJECT_CONTEXT.md   # This file
```

**⚠️ Known folder issues:**
- Google Drive sometimes creates duplicate files (`env` alongside `.env`, `gitignore` alongside `.gitignore`) because dotfiles get their dots stripped on unzip/upload. Check with `ls -la` — if duplicates exist, use `mv env .env` and `rm` the duplicate.
- Google Drive can serve stale cached versions of small text files, causing `.env` changes to not be picked up. Fix: delete via Terminal (`rm .env`), recreate in VS Code, wait 10 seconds.
- **Recommendation:** Move project OUT of Google Drive to `~/Projects/time-tracker/` before deployment. Use GitHub for version control instead.

---

## 6. Environment Variables (`.env` structure)

```
TELEGRAM_TOKEN=<from @BotFather — format: NUMBERS:LETTERS>
GROQ_API_KEY=<from console.groq.com/keys — starts with gsk_>
NOTION_API_KEY=<from Notion connection page — starts with ntn_>
NOTION_DATABASE_ID=1c62a940-fc44-4d5a-8a18-c121dd6db671
TELEGRAM_CHAT_ID=<numeric — get via @userinfobot or getUpdates URL>
```

**Format rules:** No spaces around `=`. No quotes. One key per line. No trailing commas.

---

## 7. Code Architecture (`main.py`)

The code is organized in 5 clear sections:

1. **`transcribe_voice()`** — Sends audio file to Groq Whisper, returns text
2. **`parse_activity()`** — Sends text to Groq LLM with prompt to extract JSON:
   - `event_type`: START or END
   - `activity`: short name (max 4 words)
   - `category`: one of predefined categories
   - Uses `response_format={"type": "json_object"}` to guarantee valid JSON
3. **`log_to_notion()`** — Writes row to Notion database
4. **`handle_message()`** — Telegram message handler (routes voice vs text)
5. **`fetch_today_entries()` / `build_summary()` / `send_summary()`** — split out of the old
   `send_nightly_summary()`. Driven by two entry points:
   - `nightly_summary_job()` — registered via `app.job_queue.run_daily(...)` at 22:00 `Asia/Kolkata`
   - `summary_command()` — the `/summary` command, for testing on demand

### Invariants worth preserving

- **Never call bare `datetime.now()`.** Use `now_local()`. Railway runs in UTC; naive
  timestamps land in Notion 5.5 hours off.
- **Never trust the model's echoed timestamp.** `parse_activity()` ignores it and stamps
  our own, so a hallucinated date can't reach Notion.
- **Category and event type are clamped** to the lists Notion's Select fields already have.
  Without clamping, an off-list value silently creates a new Select option.
- **Scheduling goes through `app.job_queue`,** never a standalone scheduler.
- **`httpx` logging is pinned to WARNING** because it logs the full Telegram API URL,
  token included — that would otherwise leak into Railway's deploy logs.

### Prompt used for parsing

```python
"""You are a time tracking assistant.
Parse this message and return ONLY a JSON object with no extra text, no markdown formatting.

Message: "{text}"
Timestamp: {timestamp}

Return this exact JSON structure:
{
  "event_type": "START or END",
  "activity": "short activity name (max 4 words)",
  "category": "one of: Deep Work, Routine, Meals, Fitness, Leisure, Sleep, Doom Scrolling, Travel, Social",
  "timestamp": "{timestamp}"
}

Examples:
- "going to take a bath" -> START, Morning Hygiene, Routine
- "done with bath" -> END, Morning Hygiene, Routine
- "starting sprint planning" -> START, Sprint Planning, Deep Work
- "watching youtube" -> START, YouTube, Doom Scrolling"""
```

### Nightly summary prompt

```
Analyse this person's day and give honest, direct insights.

Today's time log:
{entries}

Provide:
1. Total time per category (calculate from START/END pairs)
2. Biggest time blocks
3. Unaccounted gaps
4. Honest assessment: was this a productive day?
5. One specific suggestion for tomorrow

Be direct and concise. No fluff.
```

---

## 8. Notion Database Schema

**Location:** Under "🚀 Life Operating System" page (page ID: `3807d70e-8543-814e-bd27-fe123de3c7c3`)
**Database name:** "⏱️ Time Log"
**Database ID:** `1c62a940-fc44-4d5a-8a18-c121dd6db671`
**Data source ID:** `0362ece7-1e4e-491a-aeb5-7a9676c49b4b`

### Columns

| Property | Type | Options |
|---|---|---|
| Activity | Title | — |
| Event Type | Select | START (green), END (red) |
| Category | Select | Deep Work (blue), Routine (gray), Meals (orange), Fitness (purple), Leisure (pink), Sleep (brown), Doom Scrolling (red), Travel (yellow), Social (green) |
| Timestamp | Date (with time) | — |
| Raw Input | Rich Text | Stores original message for debugging |
| Created | Created Time (auto) | — |

### Views

- **📅 Recent Entries** — table, sorted by Timestamp DESC (default)
- **🏷️ By Category** — kanban board grouped by Category
- **📆 Calendar** — calendar view by Timestamp

---

## 9. What's Next (Prioritized)

### ✅ Phase 3: Deploy to Railway — DONE (2026-09-04)
Bot runs 24/7 on Railway, deployed from the GitHub repo. Environment variables are set
in Railway's Variables tab, including `TIMEZONE=Asia/Kolkata`. Pushing to `main` on
GitHub triggers an automatic redeploy.

### Immediate — Phase 4: Validate the habit (7 days)
Goal: find out whether this tool actually gets used, before investing in more features.

1. **Confirm the 10 PM summary fires on its own** on the first night. This is the last
   thing not yet observed in production.
2. Use it daily for 7 days. Log start AND end events — the summary is only as good as
   the pairs it can match.
3. Note friction points as they happen: messages that parse wrong, categories that don't
   fit, moments you *didn't* log and why. The "didn't log" cases matter most.
4. After 7 days, decide honestly: keep it, change it, or drop it. Do not skip to Phase 5
   before making this call — building more features on an unused tool is the failure mode.

### Later — Potential Phase 5 improvements
*(Gated on Phase 4 actually validating the habit. Do not start these early.)*
- Weekly summary (Sunday nights) with week-over-week trends
- Charts/visualizations in Notion (embedded from Python)
- Improve category detection with feedback loop (learn from user corrections)
- Handle unclear messages (bot asks clarifying questions)
- Multi-activity parsing ("finished work, going for a walk")
- Duration calculation (auto-pair START/END events)

### Not doing (explicitly deferred)
- Publishing to Play Store / App Store — considered and rejected. Personal tool first, validate habit, then reconsider productizing much later.
- Building a custom mobile app — Telegram already solves capture perfectly.

---

## 10. Key Design Decisions & Rationale

| Decision | Why |
|---|---|
| Telegram instead of custom app | Zero UI work, free, native voice support, works everywhere. Owner is fine with it. |
| Groq instead of OpenAI/Anthropic | Free tier covers personal usage completely. Trade-off: Llama/gpt-oss slightly less capable than Claude Sonnet — acceptable for this simple parsing. |
| Notion for storage | Already central to owner's Life OS. Zero migration friction. |
| Python + Railway (not serverless) | Owner wants to learn how backends work. Serverless would hide too much. |
| No user accounts, no database beyond Notion | Personal tool. No need for auth, user isolation, or Postgres. |
| Groq for both transcription and LLM | One API to learn, one key to manage. Simpler. |

---

## 11. Owner's Broader Context (from memory)

- Three parallel life goals: Become AI Architect, Build Personal Brand, Build AI Agency
- Hard constraint: 20 hours/week across all three, max 3 active projects
- Primary failure mode identified: motivation decay and course-hopping, NOT time scarcity
- Prefers: draft and propose while owner reviews (not full delegation)
- Prefers: understand how things are built (not black-box tools)
- This project is under "Learn AI Agents" active project

### Uses for validating this project
- Prove the AI-backend build pattern (Telegram + LLM + Notion) — reusable for other projects
- Deploy real code to real cloud infrastructure (Railway)
- Real portfolio piece for AI Architect positioning

---

## 12. Debug Log — Real Issues Hit and Fixed

| Issue | Root cause | Fix |
|---|---|---|
| `AttributeError: 'Updater' object has no attribute '_Updater__polling_cleanup_cb'` | `python-telegram-bot 20.7` incompatible with Python 3.13 | Upgrade to `21.7` |
| `TypeError: Client.__init__() got unexpected keyword argument 'proxies'` | `groq 0.11.0` uses old httpx API | Upgrade to `groq 0.13.0` |
| `telegram.error.InvalidToken: token rejected` | Only half of token pasted (missing numeric prefix + colon) | Get fresh token from BotFather, copy entire string |
| `ModuleNotFoundError: No module named 'dotenv'` | VS Code using system Python (`/usr/local/bin/python3`) instead of Anaconda | Either select Anaconda interpreter in VS Code, or `pip install` to system Python |
| Old API key being used despite `.env` update | Google Drive serving stale cache + duplicate `env` file (no dot) alongside `.env` | Delete via Terminal, recreate in VS Code, wait 10s before running |
| `Model llama-3.3-70b-versatile does not exist` | Model not on free tier (Enterprise-tagged) | Use `openai/gpt-oss-20b` instead |
| `.env` not visible in Finder | macOS hides dotfiles by default | Normal — use `Cmd+Shift+.` to toggle, or just use VS Code |
| **Nightly summary never fired** | `AsyncIOScheduler()` was started inside the *sync* `main()`, before `run_polling()` existed. `run_polling()` creates its own event loop via `asyncio.run()`, so the scheduler stayed bound to a loop that never ran. Reproduced: job silently never executes, only a `DeprecationWarning: There is no current event loop` at start. | Use PTB's built-in `app.job_queue.run_daily(...)`, which starts with the application on the same loop. Requires `python-telegram-bot[job-queue]`. |
| Bot token appearing in terminal logs (repeatedly, over setup) | `httpx` logs every request URL at INFO level, and the Telegram API embeds the token in the path (`/bot<TOKEN>/getMe`) | `logging.getLogger("httpx").setLevel(logging.WARNING)` in `main.py`. This also keeps the token out of Railway's deploy logs. |
| `.env.example` would not have been committed | `.gitignore` pattern `.env.*` matches `.env.example` | Added `!.env.example` exception below it |

---

## 13. Security Notes

- Telegram token has been revoked and regenerated multiple times during setup after being exposed in terminal logs
- When sharing terminal output, always redact `bot<TOKEN>` from Telegram API URLs
- `.env` must be in `.gitignore` before pushing to GitHub — verify before every push
- Consider using a secrets manager (Railway environment variables, GitHub Secrets) for deployment

---

## 14. How to Continue This Project — Instructions for the Next LLM

When picking this up:

1. **Read this whole file first** — don't skip sections
2. **Check the actual current state** by running `ls -la` in the project folder and `cat .env` (structure only, redact values)
3. **Verify the bot still runs locally** before making changes: `python3 main.py`
4. **If deploying to Railway is next:** owner wants to LEARN the deployment process, not just have it done. Explain each step and why.
5. **Respect owner's preferences from Section 1** — direct, honest, no fluff, flag uncertainty
6. **Don't invent Groq model names, Railway steps, or API endpoints.** Verify at official docs.
7. **When in doubt about what's next:** Section 9 ("What's Next") is the roadmap

---

## 15. Quick Reference — Commands

### Everyday use (now that it is deployed)

The bot is running on Railway. You do not need to start anything.

- Send a voice note or text to the bot in Telegram to log an activity
- `/summary` — get today's summary on demand
- Automatic summary lands at 22:00 Asia/Kolkata

### Shipping a change

```bash
cd "/Users/vj/Library/CloudStorage/GoogleDrive-vijayanand.0502@gmail.com/My Drive/Claude Cowork/Time Tracker"
git add -A
git commit -m "describe the change"
git push                 # Railway redeploys automatically on push to main
```

Then watch the Railway deploy logs for `Bot running. Timezone=Asia/Kolkata.`

### Running locally (only when you need to debug)

> ⚠️ **Pause the Railway service first.** Telegram allows one poller per token; running
> both gives `Conflict: terminated by other getUpdates request` and both misbehave.

```bash
pip3 install -r requirements.txt --upgrade
python3 main.py          # Ctrl+C to stop
```

### Housekeeping

```bash
ls -la                   # show dotfiles
git status               # confirm .env is NOT listed before any push
which python3            # /Applications/anaconda3/bin/python3
```

---

## 16. Working On This From Another Machine or Another LLM

### What the repo carries — and what it deliberately does not

`git clone` gives you **everything except the secrets**: all code, this context file,
`AGENTS.md`/`CLAUDE.md`, and the full commit history. `.env` is intentionally excluded
by `.gitignore` and must be recreated by hand on each machine.

**This means the five secret values live nowhere in the repo.** Keep them in a password
manager (Apple Passwords, 1Password, Bitwarden). Once deployed, Railway's Variables tab
also holds a readable copy, so that is a usable fallback — but a password manager is the
right home. If you lose all copies, every key must be regenerated from scratch.

### Setting up on a new machine

```bash
git clone https://github.com/<your-username>/time-tracker.git
cd time-tracker
cp .env.example .env          # then fill in the 5 values from your password manager
pip3 install -r requirements.txt
python3 main.py
```

> ⚠️ **Do not run `python3 main.py` while Railway is also running the bot.** Telegram
> allows only one poller per token — two instances will throw `Conflict: terminated by
> other getUpdates request` at each other and both behave erratically. On a second
> machine, edit and push; let Railway do the running. To test locally, pause the
> Railway service first.

### Using a different LLM (Codex, Cursor, ChatGPT, etc.)

`AGENTS.md` is the entry point and is picked up automatically by Codex and most agent
tools; `CLAUDE.md` is a symlink to it for Claude Code. Both say the same thing: read this
context file first. For a chat-only LLM with no repo access, paste this file in as the
first message — it was written to be sufficient on its own.

**Keep this file current.** It is the only thing that makes the project portable across
machines, tools, and models. When you change architecture, hit a real bug, or finish a
phase, update the relevant section and the "Last updated" line at the top. A stale context
file is worse than none, because the next reader will trust it.

---

*End of context file. This should be sufficient for any LLM to continue the project. If anything is unclear, ask the owner for clarification before making changes.*
