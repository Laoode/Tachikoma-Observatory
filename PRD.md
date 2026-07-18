# Tachikoma-Observatory — PRD & Implementation Plan

**Status: canonical implementation plan.** All feature work must trace back to a
requirement in this file. Companion docs:

| Doc | Role |
|---|---|
| `DESIGN.md` | UI/visual source of truth (replaces the mockup images) |
| `METHODOLOGY.md` | Frozen benchmark spec: ToolCall-15 v1.0 (scenarios, tools, scoring) — do not modify; new scenarios mean a new suite version |
| `REFLEX.md` | Reflex framework coding conventions reference |
| `MEMORY.md` | Cross-session durable memory; update via `/handoff` |

---

## 1. Summary

Tachikoma-Observatory is a **personal, self-hosted benchmark harness +
dashboard for LLM tool-calling capability**, targeting small language models
served through the owner's LiteLLM proxy (OpenAI-compatible, single base URL +
single master key, fronting multiple vLLM backends).

It runs the ToolCall-15 suite (METHODOLOGY.md) against one or many models,
persists every run to its own local database, scores results automatically, and
renders a live operator console (DESIGN.md) with per-scenario traces, error
taxonomy, category radar, historical trends, and a model leaderboard.

## 2. Goals / Non-Goals

**Goals**

1. One-click benchmark runs: a single selected model, a chosen subset, or all
   registered models at once.
2. Lockstep multi-model execution (see §6.2) so cross-model comparison per
   scenario is apples-to-apples and live on screen.
3. Deterministic, reproducible scoring aligned exactly with METHODOLOGY.md
   (points 2/1/0, category weights, star tiers).
4. Own database: full history — every run, every tool call, every token count —
   survives restarts; rankings accumulate over time.
5. Dynamic model registry: new models appear by syncing LiteLLM `/v1/models`;
   no code change to benchmark a new model.
6. Live, high-quality UI per DESIGN.md (Reflex → React).

**Non-Goals (v1)**

- Real tool execution (all tool results are the mocked responses defined in
  METHODOLOGY.md).
- Multi-user auth/tenancy — single local operator.
- Statistical rigor (n>1 aggregation, confidence intervals) — supported later
  via repeated runs, not required for v1.
- Editing scenarios in the UI (suite is frozen per METHODOLOGY versioning;
  browsing is enough for v1).

## 3. Users & Context

Single user: the repo owner, benchmarking personal SLM deployments. Runs
locally (`reflex run`) on macOS. The LiteLLM endpoint URL and master key are
provided at deploy time via environment variables and are **never committed**.

## 4. Assumptions

ASSUMPTIONS I'M MAKING (recorded so any session can re-verify):

1. LiteLLM proxy is OpenAI-compatible: `GET /v1/models` lists model IDs;
   `POST /v1/chat/completions` supports `tools` + `tool_choice="auto"` and
   returns standard `tool_calls`. Tested with the `openai` Python SDK
   (`AsyncOpenAI(base_url=..., api_key=master_key)`).
2. All benchmarked models support OpenAI-style function calling (image shows
   "Tool Mode: Function Calling"). Models that don't will simply score 0s.
3. Temperature 0.0 for all runs (METHODOLOGY reproducibility rule).
4. "Rank" = weighted Final Score from METHODOLOGY (fallback tiebreak: pass
   rate, then avg latency).
5. Tool results are injected from METHODOLOGY mocked responses; a scenario
   conversation is a bounded multi-turn loop (max 8 assistant turns) — turns
   beyond the cap count as "Loop Detected" and fail the scenario.
6. Some METHODOLOGY verdicts are judgment-calls ("explains gracefully",
   "reasonable title"). v1 scores these with deterministic rule-based checkers
   (documented per scenario in code); an optional LLM-judge is a Phase-6
   enhancement, off by default.

## 5. Tech Stack

- Python 3.13, `uv` for env/deps (venv already exists at `.venv`).
- **Reflex** (latest stable) — app framework, UI, websocket live updates,
  background events for the runner.
- **openai** SDK (async client) against the LiteLLM proxy.
- **SQLite** via Reflex's built-in `rx.Model` (SQLModel/SQLAlchemy) +
  `reflex db` (Alembic) migrations. DB file: `tachikoma.db` (gitignored).
- `rx.recharts` for all charts (line, radar, donut/pie, sparkline area).
- pytest (+ pytest-asyncio) for tests; scorer and runner are pure-Python and
  fully unit-testable without the UI.

Config (env only, validated at startup — fail fast with a clear message):

```
TACHIKOMA_LLM_BASE_URL   # LiteLLM proxy base, e.g. http://host:4000/v1
TACHIKOMA_LLM_API_KEY    # LiteLLM master key
TACHIKOMA_DB_URL         # optional, default sqlite:///tachikoma.db
```

## 6. Functional Requirements

### FR-1 Model Registry

- Sync button (Settings page + first-run) calls `GET /v1/models`, upserts model
  rows; models removed upstream are marked inactive, never deleted (history
  must keep rendering).
- Per-model editable metadata: display name, provider label, context window,
  chart color (auto-assigned from DESIGN palette, overridable), enabled flag.
- Manual add is just a row with a model ID string (for models not listed by
  the proxy).

### FR-2 Scenario Suite

- ToolCall-15 v1.0 seeded into the DB from a Python data module
  (`observatory/suite/toolcall15.py`) that transcribes METHODOLOGY.md: 12 tool
  definitions, 15 scenarios (id, name, category, difficulty, user message,
  expected-behavior text, ordered mocked tool responses, scoring rules).
- Difficulty mapping (not stated in METHODOLOGY; chosen here): Categories A/D
  scenarios = Easy, B = Medium, C/E = Hard — stored per scenario, adjustable in
  seed data.
- Suite is versioned (`suite_version` column). Seeding is idempotent.

### FR-3 Run Engine

- **Run modes:** single model / selected subset / all enabled models.
- **Per-execution flow** (one scenario × one model): build messages
  (METHODOLOGY system prompt + user message), send with full 12-tool list,
  temperature 0. Loop: if the reply contains `tool_calls`, validate + match
  each against the scenario's mock table, append mocked tool results, continue;
  stop at final text answer or the 8-turn cap. Record every turn (raw request
  and response JSON), every tool call (name, args, validity), latency per
  request, prompt/completion tokens from `usage`.
- **Lockstep barrier (multi-model):** scenarios execute strictly in suite
  order. For scenario *k*, all selected models run **concurrently**
  (`asyncio.gather`); the run advances to scenario *k+1* only after every
  model has finished scenario *k* (fast models wait at the barrier). This is a
  hard requirement — it keeps the live matrix filling row-by-row.
- Per-execution timeout (default 120s) → scored as fail with error "timeout";
  transport errors are recorded on the execution, never crash the run.
- Runner executes inside a Reflex **background event** so the UI stays live;
  progress/state is pushed to the frontend as each execution lands.
- **Stop Run:** graceful — finish in-flight scenario row, mark run `aborted`.
- **Replay:** re-run one scenario × model pair; stored as a new attempt,
  latest attempt is what the matrix/scoring shows.

### FR-4 Scoring Engine

- Pure function: `score(execution_trace, scenario) -> ScoreResult(points ∈
  {2,1,0}, verdict_label, error_tags)`; one checker per scenario ID
  implementing that scenario's METHODOLOGY scoring table.
- Error taxonomy tags (drives Error Breakdown + Tool Efficiency): 
  `invalid_tool` (name not in the 12), `wrong_parameter`, `hallucinated_tool`
  / `hallucinated_param` (fabricated values, e.g. invented email),
  `json_format_error` (unparseable arguments), `loop_detected`,
  `unnecessary_tool`, `missed_call`, `other`.
- Aggregates per run × model: pass rate, per-category score (points/6 × 100),
  Final Score (mean of category scores), star tier, avg tool calls per
  scenario, hallucinated/invalid-JSON/loop rates, token totals, avg latency.
- Scoring runs synchronously right after each execution (results appear live),
  and can be re-run offline over stored traces (grader fixes must be able to
  re-score history without re-calling models).

### FR-5 Dashboard (per DESIGN.md)

- Live KPI row, scenario matrix (icons per model column), charts row, scenario
  detail panel with Overview/Trace/Metrics/Logs tabs, footer health bar.
- "Current Run" select switches which model the single-model KPI cards focus
  on during/after a multi-model run.
- CSV export of the current run's matrix.

### FR-6 Analytics & Leaderboard

- Analytics page: Overall Performance line chart across historical runs
  (metric selectable), radar comparison for any chosen run set.
- Leaderboard: rank all models by best (or latest — toggle) Final Score, with
  tier stars, pass rate, error rates, tokens, latency.

### FR-7 Health

- Footer status = result of a lightweight periodic `/v1/models` ping (only
  while the app is open; no cron). Last-updated timestamp from the most recent
  successful DB write or ping.

## 7. Data Model (SQLite)

```
models(id PK, model_id TEXT unique, display_name, provider, context_window,
       color, is_enabled, is_active, created_at)

scenarios(id PK, suite_version, scenario_key TEXT e.g. 'TC-01', name,
          category, difficulty, user_message, system_prompt,
          expected_behavior, mock_responses JSON, sort_order)

runs(id PK, started_at, finished_at, status ENUM(running|complete|aborted|error),
     suite_version, notes)

run_models(id PK, run_id FK, model_id FK)            -- participants

executions(id PK, run_id FK, model_id FK, scenario_id FK, attempt INT,
           status ENUM(pending|running|complete|error|timeout),
           points INT, verdict TEXT, error_tags JSON,
           latency_ms, prompt_tokens, completion_tokens, total_tokens,
           turns INT, tool_call_count INT, started_at, finished_at)

trace_events(id PK, execution_id FK, seq INT,
             kind ENUM(user_prompt|assistant_text|tool_call|tool_result|error|final_answer),
             tool_name, payload JSON, ts, is_ok BOOL, error_text)
```

Latest-attempt-wins views feed the UI; aggregates are computed in Python from
executions (15 scenarios × N models is tiny — no need for materialized stats).

## 8. Architecture & Repo Layout

```
rxconfig.py
observatory/
  observatory.py        # app entry, page routing, theme injection
  config.py             # env loading + startup validation
  theme/tokens.py       # DESIGN.md tokens as constants/CSS vars
  models/               # rx.Model tables (one file per aggregate)
  suite/toolcall15.py   # suite data transcribed from METHODOLOGY.md
  suite/seed.py         # idempotent DB seeding
  llm/client.py         # AsyncOpenAI wrapper (list_models, chat with tools)
  engine/runner.py      # lockstep orchestration (pure asyncio, UI-agnostic)
  engine/executor.py    # single scenario×model conversation loop
  scoring/checkers.py   # per-scenario checkers TC-01..TC-15
  scoring/aggregate.py  # run/model aggregates, tiers
  state/                # Reflex states (dashboard, run controller, detail, settings)
  pages/                # dashboard, analytics, scenarios, settings, health
  components/           # shell, kpi cards, matrix, charts, detail panel, footer
assets/                 # mockups, mascot, fonts
tests/units/            # scorer, runner barrier, suite integrity, aggregates
```

Key boundary: **`engine/` and `scoring/` import nothing from Reflex** — the
runner reports progress through a callback the Reflex background event
provides. This keeps the benchmark core unit-testable and reusable as a CLI
later.

## 9. Milestones

Each phase ends green: tests pass, `reflex run` works, committed
(conventional commits).

- **M0 — Scaffold.** uv project, Reflex init, config module w/ env validation,
  theme tokens, empty shell layout (rail/header/footer) matching DESIGN.md.
- **M1 — Data core.** rx.Model tables + migrations, ToolCall-15 seed module +
  suite integrity tests (15 scenarios, 12 tools, weights sum to 100%).
- **M2 — Engine.** LLM client, executor loop with mock injection, lockstep
  runner with barrier semantics + stop/timeout. Unit tests with a fake client
  (incl. barrier ordering test: slow model delays scenario advance).
- **M3 — Scoring.** 15 checkers + aggregates, tested against handcrafted
  traces for every scoring-table row in METHODOLOGY.md. Re-score command.
- **M4 — Dashboard.** KPI row, matrix table view (live updates), run
  start/stop, scenario detail panel (Overview/Trace/Metrics/Logs), replay.
- **M5 — Charts, analytics, leaderboard.** Charts row, analytics page,
  leaderboard page, CSV export, health ping.
- **M6 — Polish.** Heatmap view, motion pass, empty states, mascot asset,
  optional LLM-judge flag, README.

First live end-to-end test against the real LiteLLM endpoint happens at M2
(user provides `TACHIKOMA_LLM_BASE_URL` / `TACHIKOMA_LLM_API_KEY` then).

## 10. Risks & Open Questions

1. **SLMs with weak/nonstandard tool-call output** (e.g. tool JSON in plain
   text): v1 treats it as `json_format_error`/fail, which is *by design* —
   that's what's being measured. Judges may later soften this.
2. **Reflex background-event throughput:** 15×N concurrent executions is
   small; no issue expected, but runner is UI-decoupled so it can move to a
   worker if needed.
3. **Half-credit visual language** for matrix cells is specced (amber dot) —
   confirm it reads clearly at 20px.
4. **Open:** should the leaderboard rank by best run or latest run by default?
   (v1 default: latest, toggle for best.)
5. **Open:** LLM-judge model choice for subjective verdicts (Phase 6, off by
   default; would use a strong model via the same proxy).
