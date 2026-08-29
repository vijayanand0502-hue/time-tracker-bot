# Time Tracker Bot — Project Context

> **For any LLM picking up this project:** Read this entire file first. It contains everything needed to continue work without losing context. Last updated: 2026-08-28 (pre-deploy hardening pass).

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

## 3. Current Status (as of 2026-08-28)

- ✅ Telegram bot created via @BotFather
- ✅ Notion database created (Time Log) under Life OS with all views
- ✅ Notion "Time Tracker Bot" connection created and connected to database
- ✅ Groq API key active (free tier)
- ✅ Local bot working end-to-end: text + voice → transcription → parse → Notion log → Telegram confirmation
- ✅ Notion entries confirmed appearing correctly
- ✅ **Nightly summary bug found and fixed** — it could never have fired (see Section 12)
- ✅ Timezone handling added (`Asia/Kolkata`) — required before Railway, which runs in UTC
- ✅ `/summary` command added so the summary can be tested on demand, not only at 10 PM
- ✅ Deploy scaffolding created: `Procfile`, `.python-version`, `.env.example`
- ⚠️ Bot runs **locally only** — stops when laptop closes/sleeps
- ⚠️ Nightly summary still not observed firing end-to-end — test with `/summary` first
- ❌ **Not yet deployed to Railway** (next major step)
- ❌ Not yet in git / GitHub

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

### Immediate — Phase 3: Deploy to Railway (~15 min)
Goal: Bot runs 24/7 without laptop needing to be open.

0. **Test `/summary` locally first.** The summary path has never once run end-to-end.
   Debugging it locally is far cheaper than debugging it on Railway.
1. Move project out of Google Drive to `~/Projects/time-tracker/`
2. `git init`, commit, create GitHub repo, push
   — verify `git status` does NOT list `.env` before the first push
3. Sign up at railway.app with GitHub
4. Create new project → Deploy from GitHub repo
5. Add environment variables in Railway UI — the five required ones **plus `TIMEZONE=Asia/Kolkata`**
6. Deploy. Confirm in Railway logs: `Bot running. Timezone=Asia/Kolkata.`
7. Stop the local bot — two instances polling the same token conflict with each other
8. Send `/summary` to confirm the deployed instance is the one answering

### After deployment — Phase 4: Validate habit (1 week)
- Use daily for 7 days
- Note friction points
- Verify nightly summary actually triggers at 10 PM
- Decide: keep it? modify it? productize it?

### Later — Potential Phase 5 improvements
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

```bash
# Navigate to project
cd "/Users/vj/Library/CloudStorage/GoogleDrive-vijayanand.0502@gmail.com/My Drive/Claude Cowork/Time Tracker"

# View hidden files
ls -la

# Install/update dependencies
pip3 install -r requirements.txt --upgrade

# Run bot locally
python3 main.py

# Stop bot
# Press Ctrl + C in Terminal

# View .env structure (redact values before sharing)
cat .env

# Check which Python is being used
which python3

# Check Anaconda Python location
which python  # usually /Applications/anaconda3/bin/python
```

---

*End of context file. This should be sufficient for any LLM to continue the project. If anything is unclear, ask the owner for clarification before making changes.*
