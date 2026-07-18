# Project Memory — Tachikoma-Observatory

Durable log for AI sessions. Read this at the start of every session; whatever
model runs next inherits this context cold. Newest entries first. Keep it under
~120 lines: when it grows, move stale entries to `docs/memory-archive.md`.
Update via `/handoff` at the end of each substantial session.

Canonical docs (read before coding):
- `PRD.md` — requirements, architecture, data model, milestones M0–M6
- `DESIGN.md` — full UI spec; replaces the mockup images (never re-read
  `assets/design*.png` unless the spec itself is in question)
- `METHODOLOGY.md` — FROZEN ToolCall-15 v1.0 benchmark spec; never edit,
  version instead
- `REFLEX.md` — Reflex coding conventions reference

## Current state

**2026-07-18 — Planning session (no code yet).**
- Wrote DESIGN.md (from `assets/design-tachikoma.png`, primary mockup; nav icon
  meanings decoded from `assets/design.png` labeled variant) and PRD.md.
- Green-field: `.venv` is bare Python 3.13.5, no Reflex code exists yet despite
  the "refactor to reflex python" commit. Next step = M0 scaffold per PRD §9.
- LLM access: single LiteLLM proxy (OpenAI-compatible) fronting vLLM. One base
  URL + one master key via env `TACHIKOMA_LLM_BASE_URL` /
  `TACHIKOMA_LLM_API_KEY` (user provides at M2; NOT yet available, never
  commit). Model discovery via `GET /v1/models`.
- Key decisions: SQLite via `rx.Model` (own DB, `tachikoma.db`); lockstep
  barrier multi-model runs (all models finish scenario k before k+1 —
  hard requirement from user); temperature 0; mocked tool results from
  METHODOLOGY; scoring is deterministic rule-based checkers (LLM-judge is a
  later opt-in); `engine/` + `scoring/` must stay Reflex-free for testability.

## Lessons

- User wants "clean, no AI slop, liquid glass, ui/ux pro max" — DESIGN.md §1
  hard rules encode this; single phosphor-green accent, semantic-only status
  colors.
- METHODOLOGY.md and REFLEX.md are user-provided reference material — leave
  untouched.
