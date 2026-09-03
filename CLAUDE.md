# Claude Code Instructions

See **[AGENTS.md](AGENTS.md)** — it is the entry point for all agent tools and this
file exists only so Claude Code picks it up automatically.

Then read **`Time tracker PROJECT_CONTEXT.md`** in full before making any change.

Two rules worth repeating here so they are impossible to miss:

- **Never read or print the contents of `.env`.** It holds live API keys.
- **Check "Invariants worth preserving" (Section 7)** before editing `main.py` —
  timezone handling, job scheduling, and log redaction all have non-obvious
  constraints that were learned by hitting real bugs.
