"""
Time Tracker Bot
─────────────────────────────────────────────
A Telegram bot that captures your daily activities via voice or text,
uses Groq (Whisper + LLM) to transcribe and parse them,
and logs everything to a Notion database for analysis.

Sends an automated daily summary at 10 PM local time.
Send /summary any time to generate it on demand.
"""

import os
import json
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from groq import Groq
from notion_client import Client as NotionClient

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# httpx logs the full Telegram API URL at INFO — which embeds the bot token.
# Silencing it keeps the token out of terminal output AND Railway deploy logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
REQUIRED_ENV = [
    "TELEGRAM_TOKEN",
    "GROQ_API_KEY",
    "NOTION_API_KEY",
    "NOTION_DATABASE_ID",
    "TELEGRAM_CHAT_ID",
]

# The server (Railway) runs in UTC. Everything user-facing must use YOUR timezone,
# otherwise timestamps are 5.5h off and the "10 PM" job fires at 3:30 AM.
LOCAL_TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Kolkata"))

SUMMARY_HOUR = int(os.getenv("SUMMARY_HOUR", "22"))
SUMMARY_MINUTE = int(os.getenv("SUMMARY_MINUTE", "0"))

# Must match the Select options in the Notion database exactly.
CATEGORIES = [
    "Deep Work", "Routine", "Meals", "Fitness", "Leisure",
    "Sleep", "Doom Scrolling", "Travel", "Social",
]
DEFAULT_CATEGORY = "Routine"

PARSE_MODEL = os.getenv("GROQ_PARSE_MODEL", "openai/gpt-oss-20b")
TRANSCRIBE_MODEL = os.getenv("GROQ_TRANSCRIBE_MODEL", "whisper-large-v3-turbo")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
notion = NotionClient(auth=os.getenv("NOTION_API_KEY"))
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")


def check_env():
    """Fail fast with a readable error instead of a cryptic one 3 layers deep."""
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise SystemExit(
            "Missing required environment variables: "
            + ", ".join(missing)
            + "\nSet them in .env locally, or in Railway → Variables when deployed."
        )


def now_local() -> datetime:
    """Timezone-aware 'now'. Never use datetime.now() bare in this project."""
    return datetime.now(LOCAL_TZ)


# ─────────────────────────────────────────────
# STEP 1: Transcribe voice note using Groq Whisper
# ─────────────────────────────────────────────
def transcribe_voice(file_path: str) -> str:
    """Sends audio file to Groq's hosted Whisper model. Returns transcribed text."""
    with open(file_path, "rb") as audio_file:
        transcript = groq_client.audio.transcriptions.create(
            file=(file_path, audio_file.read()),
            model=TRANSCRIBE_MODEL,
        )
    return transcript.text


# ─────────────────────────────────────────────
# STEP 2: Parse intent using Groq LLM
# ─────────────────────────────────────────────
def parse_activity(text: str, timestamp: str) -> dict:
    """
    Extracts event type (START/END), activity, and category from free text.
    The timestamp is OURS — the model's echo of it is ignored, so a
    hallucinated date can never reach Notion.
    """
    completion = groq_client.chat.completions.create(
        model=PARSE_MODEL,
        messages=[{
            "role": "user",
            "content": f"""You are a time tracking assistant.
Parse this message and return ONLY a JSON object with no extra text, no markdown formatting.

Message: "{text}"

Return this exact JSON structure:
{{
  "event_type": "START or END",
  "activity": "short activity name (max 4 words)",
  "category": "one of: {', '.join(CATEGORIES)}"
}}

Examples:
- "going to take a bath" -> START, Morning Hygiene, Routine
- "done with bath" -> END, Morning Hygiene, Routine
- "starting sprint planning" -> START, Sprint Planning, Deep Work
- "watching youtube" -> START, YouTube, Doom Scrolling"""
        }],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = json.loads(completion.choices[0].message.content.strip())

    # Clamp model output to the schema Notion actually accepts. Without this,
    # an off-list category silently creates a new Select option in the database.
    event_type = str(raw.get("event_type", "")).strip().upper()
    if event_type not in ("START", "END"):
        event_type = "START"

    category = str(raw.get("category", "")).strip()
    if category not in CATEGORIES:
        logger.warning("Model returned unknown category %r — using %s", category, DEFAULT_CATEGORY)
        category = DEFAULT_CATEGORY

    activity = str(raw.get("activity", "")).strip() or text[:60]

    return {
        "event_type": event_type,
        "activity": activity[:200],
        "category": category,
        "timestamp": timestamp,
    }


# ─────────────────────────────────────────────
# STEP 3: Log entry to Notion database
# ─────────────────────────────────────────────
def log_to_notion(parsed: dict, raw_text: str):
    """Writes a new row to the Notion time tracking database."""
    notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "Activity": {"title": [{"text": {"content": parsed["activity"]}}]},
            "Event Type": {"select": {"name": parsed["event_type"]}},
            "Category": {"select": {"name": parsed["category"]}},
            "Timestamp": {"date": {"start": parsed["timestamp"]}},
            # Notion rejects rich_text content longer than 2000 characters.
            "Raw Input": {"rich_text": [{"text": {"content": raw_text[:2000]}}]},
        },
    )


# ─────────────────────────────────────────────
# STEP 4: Handle incoming Telegram messages
# ─────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs on every message to the bot. Handles both text and voice notes."""
    timestamp = now_local().isoformat()
    raw_text = ""

    if update.message.voice:
        await update.message.reply_text("Got it, processing...")
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        file_path = f"/tmp/voice_{update.message.message_id}.ogg"
        await voice_file.download_to_drive(file_path)
        try:
            raw_text = transcribe_voice(file_path)
        finally:
            # Runs even if transcription raises, so /tmp doesn't fill up.
            if os.path.exists(file_path):
                os.remove(file_path)

    elif update.message.text:
        raw_text = update.message.text

    if not raw_text.strip():
        return

    try:
        parsed = parse_activity(raw_text, timestamp)
        log_to_notion(parsed, raw_text)
        await update.message.reply_text(
            f"✅ Logged\n"
            f"📌 {parsed['event_type']}: {parsed['activity']}\n"
            f"🏷️ {parsed['category']}\n"
            f"🕐 {parsed['timestamp'][:16].replace('T', ' ')}"
        )
    except Exception as e:
        logger.exception("Error processing message")
        await update.message.reply_text(f"⚠️ Something went wrong: {str(e)[:200]}")


# ─────────────────────────────────────────────
# STEP 5: Daily summary — 10 PM local, or on demand via /summary
# ─────────────────────────────────────────────
def _prop_text(props: dict, name: str, kind: str) -> str:
    """Read one Notion property defensively — a half-filled row must not kill the summary."""
    prop = props.get(name) or {}
    if kind == "title":
        items = prop.get("title") or []
        return items[0]["text"]["content"] if items else "(untitled)"
    if kind == "select":
        sel = prop.get("select") or {}
        return sel.get("name") or "(none)"
    if kind == "date":
        date = prop.get("date") or {}
        start = date.get("start") or ""
        return start[:16].replace("T", " ")
    return ""


def fetch_today_entries() -> list[str]:
    """Returns today's log lines, oldest first, in local time."""
    start_of_day = now_local().replace(hour=0, minute=0, second=0, microsecond=0)

    entries, cursor = [], None
    while True:
        results = notion.databases.query(
            database_id=NOTION_DATABASE_ID,
            filter={
                "property": "Timestamp",
                "date": {"on_or_after": start_of_day.isoformat()},
            },
            sorts=[{"property": "Timestamp", "direction": "ascending"}],
            start_cursor=cursor,
            page_size=100,
        )
        for page in results["results"]:
            props = page["properties"]
            entries.append(
                f"{_prop_text(props, 'Timestamp', 'date')} | "
                f"{_prop_text(props, 'Event Type', 'select')} | "
                f"{_prop_text(props, 'Activity', 'title')} | "
                f"{_prop_text(props, 'Category', 'select')}"
            )
        if not results.get("has_more"):
            break
        cursor = results.get("next_cursor")

    return entries


def build_summary(entries: list[str]) -> str:
    completion = groq_client.chat.completions.create(
        model=PARSE_MODEL,
        messages=[{
            "role": "user",
            "content": f"""Analyse this person's day and give honest, direct insights.

Today's time log:
{chr(10).join(entries)}

Provide:
1. Total time per category (calculate from START/END pairs)
2. Biggest time blocks
3. Unaccounted gaps (large gaps between entries)
4. Honest assessment: was this a productive day?
5. One specific suggestion for tomorrow

Be direct and concise. No fluff."""
        }],
        temperature=0.3,
    )
    return completion.choices[0].message.content


async def send_summary(bot, chat_id: str):
    entries = fetch_today_entries()
    if not entries:
        await bot.send_message(chat_id=chat_id, text="No entries logged today.")
        return

    summary = build_summary(entries)
    text = f"📊 Daily Summary\n\n{summary}"

    # Sent as PLAIN TEXT deliberately. The model emits standard `**bold**`, but
    # Telegram's legacy Markdown mode expects `*bold*` — it renders mangled rather
    # than erroring. Stray _ and * in LLM prose can also make the message fail outright.
    # Telegram caps messages at 4096 chars, so split rather than lose the tail.
    for i in range(0, len(text), 4000):
        await bot.send_message(chat_id=chat_id, text=text[i:i + 4000])


async def nightly_summary_job(context: ContextTypes.DEFAULT_TYPE):
    """Scheduled by PTB's JobQueue, so it runs on the bot's own event loop."""
    try:
        await send_summary(context.bot, os.getenv("TELEGRAM_CHAT_ID"))
    except Exception:
        logger.exception("Nightly summary failed")


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/summary — generate the daily summary now instead of waiting for 10 PM."""
    await update.message.reply_text("Crunching today's log...")
    try:
        await send_summary(context.bot, str(update.effective_chat.id))
    except Exception as e:
        logger.exception("On-demand summary failed")
        await update.message.reply_text(f"⚠️ Summary failed: {str(e)[:200]}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Time Tracker is running.\n\n"
        "Send a voice note or text like \"starting sprint planning\" or \"done with lunch\".\n"
        f"/summary — today's summary now\n"
        f"Automatic summary daily at {SUMMARY_HOUR:02d}:{SUMMARY_MINUTE:02d} ({LOCAL_TZ})."
    )


# ─────────────────────────────────────────────
# MAIN — Start the bot
# ─────────────────────────────────────────────
def main():
    check_env()

    app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("summary", summary_command))
    # ~filters.COMMAND so /start and /summary aren't logged as activities.
    app.add_handler(MessageHandler((filters.TEXT & ~filters.COMMAND) | filters.VOICE, handle_message))

    # PTB's own JobQueue — it starts with the application, on the same event loop.
    # A bare AsyncIOScheduler started before run_polling() binds to a loop that
    # never runs, which is why the 10 PM summary never fired.
    app.job_queue.run_daily(
        nightly_summary_job,
        time=time(hour=SUMMARY_HOUR, minute=SUMMARY_MINUTE, tzinfo=LOCAL_TZ),
        name="nightly_summary",
    )

    logger.info(
        "Bot running. Timezone=%s. Nightly summary at %02d:%02d.",
        LOCAL_TZ, SUMMARY_HOUR, SUMMARY_MINUTE,
    )
    app.run_polling()


if __name__ == "__main__":
    main()
