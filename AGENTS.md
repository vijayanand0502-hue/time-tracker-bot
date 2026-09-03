# Agent / LLM Instructions

**Read `Time tracker PROJECT_CONTEXT.md` in full before doing anything.** It is the
single source of truth for this project: current status, architecture, design
decisions, invariants that must not be broken, and a debug log of real bugs already
hit and fixed. Section 14 covers how to pick the project up.

## Hard rules

- **Never read or print the contents of `.env`.** It holds live API keys and is
  intentionally not in this repo. Use `.env.example` to learn the structure.
- **Never echo real key values.** Use placeholders like `<TELEGRAM_TOKEN>`.
- Do not invent Groq model names, Notion API shapes, or Railway steps. Verify them.
- See "Invariants worth preserving" in Section 7 of the context file before editing
  `main.py` — particularly around timezones, job scheduling, and logging.

## Owner preferences

Direct, honest, no fluff. Call out failure modes and tradeoffs plainly. Flag
uncertainty explicitly rather than guessing. The owner wants to understand how
things are built, not just be handed a result — explain the reasoning.
