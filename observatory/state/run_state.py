"""Dashboard state, model-centric: one merged matrix of every benchmarked
model (latest result per cell across all runs), one target select that both
picks what to run and which model the KPI cards focus on.

Runs still exist as DB rows underneath (analytics, history, attempt
grouping); the dashboard just presents the merged latest-per-model view.
"""

import datetime
import json

import reflex as rx

from observatory.config import load_llm_config
from observatory.engine.executor import execute_scenario
from observatory.engine.runner import RunEvent, run_benchmark
from observatory.llm.client import LLMClient
from observatory.models import repo
from observatory.models.tables import Execution
from observatory.scoring.aggregate import ExecutionSummary, aggregate_model
from observatory.scoring.checkers import score_trace
from observatory.state.structs import (
    Cell,
    Detail,
    Kpi,
    ModelCol,
    Row,
    TraceRow,
    fmt_compact,
)
from observatory.suite.toolcall15 import CATEGORIES, SCENARIOS, SCENARIOS_BY_KEY

ALL_MODELS = "All Active Models"
INACTIVE_SUFFIX = " (inactive)"

ERROR_LABELS = {
    "invalid_tool": "Invalid Tool",
    "wrong_parameter": "Wrong Parameter",
    "hallucinated_tool": "Hallucinated Tool",
    "json_format_error": "JSON Format Error",
    "loop_detected": "Loop Detected",
    "unnecessary_tool": "Unnecessary Tool",
    "missed_call": "Missed Call",
    "other": "Other Errors",
}

ERROR_CHART_COLORS = {
    "Invalid Tool": "#38BDF8",
    "Wrong Parameter": "#4ADE80",
    "Hallucinated Tool": "#F87171",
    "JSON Format Error": "#FBBF24",
    "Loop Detected": "#F472B6",
    "Unnecessary Tool": "#2DD4BF",
    "Missed Call": "#FB923C",
    "Other Errors": "#A78BFA",
}

# Process-local stop flags; background tasks cannot mutate state outside
# `async with self`, so graceful stop is signalled out-of-band per run.
_STOP_FLAGS: dict[int, bool] = {}


def _status_of(execution: Execution) -> str:
    """Matrix cell status for a stored execution."""
    if execution.status == "error":
        return "error"
    return {2: "pass", 1: "half", 0: "fail"}[execution.points]


def _summary_of(execution: Execution) -> ExecutionSummary:
    """Aggregation input from a stored execution."""
    return ExecutionSummary(
        scenario_key=execution.scenario_key,
        points=execution.points,
        error_tags=tuple(execution.error_tags),
        tool_call_count=execution.tool_call_count,
        prompt_tokens=execution.prompt_tokens,
        completion_tokens=execution.completion_tokens,
        latency_ms=execution.latency_ms,
    )


class RunState(rx.State):
    """Everything the dashboard page renders and controls."""

    run_status: str = "idle"
    run_id: int = 0
    cols: list[ModelCol] = []
    rows: list[Row] = []
    done_cells: int = 0
    total_cells: int = 0
    target: str = ALL_MODELS
    kpi: Kpi = Kpi()
    detail: Detail = Detail()
    search: str = ""
    category_filter: str = "All Categories"
    radar_data: list[dict] = []
    error_data: list[dict] = []
    error_total: int = 0
    spark_data: list[dict] = []
    last_updated: str = "—"
    endpoint_ok: bool = False
    _running_cells: list[str] = []
    _run_model_ids: list[str] = []
    _detail_model_id: str = ""

    @rx.var
    def progress_pct(self) -> int:
        """Completion percentage: in-flight run while running, else merged."""
        if self.total_cells == 0:
            return 0
        return int(self.done_cells / self.total_cells * 100)

    @rx.var
    def is_running(self) -> bool:
        """True while a run is in flight."""
        return self.run_status == "running"

    @rx.var
    def status_label(self) -> str:
        """Header chip text."""
        return {
            "idle": "Idle",
            "running": "Running",
            "complete": "Complete",
            "aborted": "Aborted",
            "error": "Error",
        }.get(self.run_status, "Idle")

    target_options: list[str] = [ALL_MODELS]
    can_run: bool = False

    @rx.var
    def filtered_rows(self) -> list[Row]:
        """Matrix rows after search and category filters."""
        rows = self.rows
        if self.search:
            needle = self.search.lower()
            rows = [
                r for r in rows
                if needle in r.name.lower() or needle in r.key.lower()
            ]
        if self.category_filter != "All Categories":
            rows = [r for r in rows if r.category == self.category_filter]
        return rows

    @rx.var
    def category_options(self) -> list[str]:
        """Category filter choices."""
        return ["All Categories", *CATEGORIES.values()]

    def _target_entry(self, entries=None):
        """Registry entry matching the selected target, None for run-all."""
        if self.target == ALL_MODELS:
            return None
        name = self.target.removesuffix(INACTIVE_SUFFIX)
        for entry in entries if entries is not None else repo.list_models():
            if entry.display_name == name:
                return entry
        return None

    def _focus_model_id(self) -> str:
        """Model the KPI cards focus on: the target, else the newest column."""
        entry = self._target_entry()
        if entry is not None:
            return entry.model_id
        return self.cols[-1].model_id if self.cols else ""

    @rx.event
    def load_dashboard(self):
        """Page on_load: build the merged view and ping the endpoint."""
        self._rebuild()
        return RunState.ping_endpoint

    @rx.event(background=True)
    async def ping_endpoint(self):
        """Footer health check against the proxy."""
        config = load_llm_config()
        ok = False
        if config is not None:
            try:
                await LLMClient(config).list_models()
                ok = True
            except Exception:
                ok = False
        async with self:
            self.endpoint_ok = ok

    @rx.event
    def set_search(self, value: str):
        """Matrix search input."""
        self.search = value

    @rx.event
    def set_category_filter(self, value: str):
        """Matrix category filter."""
        self.category_filter = value

    @rx.event
    def set_target(self, value: str):
        """Switch the run target / KPI focus."""
        self.target = value
        self._update_run_gate(repo.list_models())
        self._refresh_views()

    def _update_run_gate(self, entries) -> None:
        """Recompute Start Run availability for the current target."""
        if self.target == ALL_MODELS:
            self.can_run = any(e.is_enabled and e.is_active for e in entries)
        else:
            entry = self._target_entry(entries)
            self.can_run = entry is not None and entry.is_active

    def _refresh_target_options(self, entries) -> None:
        """Rebuild the Model select from the registry; the select is a plain
        state var because computed vars cannot observe DB changes made from
        the Settings page."""
        labels = {
            e.display_name: f"{e.display_name}"
            + ("" if e.is_active else INACTIVE_SUFFIX)
            for e in entries
        }
        self.target_options = [ALL_MODELS, *labels.values()]
        # An active model can turn inactive between syncs (or vice versa);
        # re-point the current selection at its updated label.
        if self.target != ALL_MODELS and self.target not in self.target_options:
            name = self.target.removesuffix(INACTIVE_SUFFIX)
            self.target = labels.get(name, ALL_MODELS)

    @rx.event
    def stop_run(self):
        """Request a graceful abort after the current scenario row."""
        _STOP_FLAGS[self.run_id] = True

    @rx.event
    def close_detail(self):
        """Hide the Scenario Detail panel."""
        self.detail = Detail()

    @rx.event
    def select_cell(self, scenario_key: str, model_id: str):
        """Open the Scenario Detail panel for one cell."""
        self._load_detail(scenario_key, model_id)

    @rx.event
    def export_csv(self):
        """Download the merged matrix as CSV."""
        header = ["scenario", "name", "category", "difficulty"] + [
            c.name for c in self.cols
        ]
        lines = [",".join(header)]
        for row in self.rows:
            lines.append(
                ",".join(
                    [row.key, row.name, row.category, row.difficulty]
                    + [cell.status for cell in row.cells]
                )
            )
        return rx.download(
            data="\n".join(lines), filename="tachikoma-benchmark.csv"
        )

    @rx.event(background=True)
    async def start_run(self):
        """Benchmark the selected target (one model or all active)."""
        config = load_llm_config()
        if config is None:
            yield rx.toast.error(
                "Endpoint not configured: set TACHIKOMA_LLM_BASE_URL and "
                "TACHIKOMA_LLM_API_KEY, then restart."
            )
            return

        entries = repo.list_models()
        if self.target == ALL_MODELS:
            targets = [e for e in entries if e.is_enabled and e.is_active]
        else:
            entry = self._target_entry(entries)
            targets = [entry] if entry is not None and entry.is_active else []
        if not targets:
            yield rx.toast.error(
                "Nothing to run: the selected model is inactive or no active "
                "models are enabled. Sync the registry on Settings first."
            )
            return

        model_ids = [e.model_id for e in targets]
        run_id = repo.create_run(model_ids)
        _STOP_FLAGS[run_id] = False
        async with self:
            self.run_id = run_id
            self.run_status = "running"
            self._run_model_ids = model_ids
            self._running_cells = []
            self.done_cells = 0
            self.total_cells = len(model_ids) * len(SCENARIOS)
            self._rebuild()

        client = LLMClient(config)
        state_ref = self

        async def on_event(event: RunEvent):
            cell_key = f"{event.scenario_key}|{event.model_id}"
            if event.kind == "execution_started":
                async with state_ref:
                    state_ref._running_cells = [
                        *state_ref._running_cells, cell_key
                    ]
                    state_ref._apply_running_cells()
            elif event.kind == "execution_finished" and event.trace is not None:
                score = score_trace(event.trace)
                repo.record_execution(run_id, event.trace, score)
                async with state_ref:
                    state_ref._running_cells = [
                        c for c in state_ref._running_cells if c != cell_key
                    ]
                    state_ref.done_cells += 1
                    state_ref._rebuild()

        try:
            completed = await run_benchmark(
                client,
                model_ids,
                SCENARIOS,
                on_event,
                should_stop=lambda: _STOP_FLAGS.get(run_id, False),
            )
            final_status = "complete" if completed else "aborted"
        except Exception as exc:
            final_status = "error"
            yield rx.toast.error(f"Run failed: {exc}")
        repo.finish_run(run_id, final_status)
        _STOP_FLAGS.pop(run_id, None)
        async with self:
            self.run_status = final_status
            self._running_cells = []
            self._run_model_ids = []
            self._rebuild()

    @rx.event(background=True)
    async def replay_execution(self):
        """Re-run the selected pair as a new attempt in its original run."""
        async with self:
            scenario_key = self.detail.scenario_key
            model_id = self._detail_model_id
        if not scenario_key or not model_id:
            return
        existing = self._latest_for(model_id, scenario_key)
        if existing is None:
            yield rx.toast.error("This cell has never been executed.")
            return
        config = load_llm_config()
        if config is None:
            yield rx.toast.error("Endpoint not configured.")
            return
        cell_key = f"{scenario_key}|{model_id}"
        async with self:
            self._running_cells = [*self._running_cells, cell_key]
            self._apply_running_cells()
        client = LLMClient(config)
        trace = await execute_scenario(
            client, model_id, SCENARIOS_BY_KEY[scenario_key]
        )
        score = score_trace(trace)
        repo.record_execution(existing.run_id, trace, score)
        async with self:
            self._running_cells = [
                c for c in self._running_cells if c != cell_key
            ]
            self._rebuild()
            self._load_detail(scenario_key, model_id)

    @staticmethod
    def _latest_for(model_id: str, scenario_key: str) -> Execution | None:
        """Global latest execution for one cell."""
        for execution in repo.latest_executions_all():
            if (
                execution.model_id == model_id
                and execution.scenario_key == scenario_key
            ):
                return execution
        return None

    def _rebuild(self):
        """Rebuild the merged matrix, KPIs, and charts from the DB.

        Columns are every model with at least one execution, ordered by when
        each was first benchmarked (oldest left, newest right), plus any
        in-flight run participants that have no results yet (appended right).
        """
        executions = repo.latest_executions_all()
        entries = repo.list_models()
        registry = {e.model_id: e for e in entries}
        self._refresh_target_options(entries)
        self._update_run_gate(entries)

        first_seen: dict[str, int] = {}
        for execution in sorted(executions, key=lambda e: e.id):
            first_seen.setdefault(execution.model_id, execution.id)
        ordered_ids = sorted(first_seen, key=lambda m: first_seen[m])
        for model_id in self._run_model_ids:
            if model_id not in first_seen:
                ordered_ids.append(model_id)

        self.cols = [
            ModelCol(
                model_id=m,
                name=registry[m].display_name if m in registry else m,
                color=registry[m].color if m in registry else "#4ADE80",
            )
            for m in ordered_ids
        ]

        by_cell = {(e.model_id, e.scenario_key): e for e in executions}
        self.rows = [
            Row(
                key=s.key,
                name=s.name,
                category=CATEGORIES[s.category],
                difficulty=s.difficulty.capitalize(),
                cells=[
                    Cell(
                        model_id=m,
                        status=(
                            _status_of(by_cell[(m, s.key)])
                            if (m, s.key) in by_cell
                            else "pending"
                        ),
                    )
                    for m in ordered_ids
                ],
            )
            for s in SCENARIOS
        ]
        self._apply_running_cells()
        self._refresh_views(executions)
        self.last_updated = datetime.datetime.now().strftime("%H:%M:%S")

    def _apply_running_cells(self):
        """Overlay in-flight running markers onto the matrix."""
        running = set(self._running_cells)
        if not running and not any(
            c.status == "running" for r in self.rows for c in r.cells
        ):
            return
        self.rows = [
            Row(
                key=r.key,
                name=r.name,
                category=r.category,
                difficulty=r.difficulty,
                cells=[
                    Cell(model_id=c.model_id, status="running")
                    if f"{r.key}|{c.model_id}" in running
                    else (
                        Cell(model_id=c.model_id, status="pending")
                        if c.status == "running"
                        else c
                    )
                    for c in r.cells
                ],
            )
            for r in self.rows
        ]

    def _refresh_views(self, executions: list[Execution] | None = None):
        """Recompute KPI cards and chart data for the focused model."""
        if executions is None:
            executions = repo.latest_executions_all()
        focus = self._focus_model_id()
        summaries = [
            _summary_of(e) for e in executions if e.model_id == focus
        ]
        agg = aggregate_model(summaries)
        registry = {e.model_id: e for e in repo.list_models()}
        entry = registry.get(focus)
        self.kpi = Kpi(
            model_name=entry.display_name if entry else (focus or "—"),
            provider=entry.provider or "—" if entry else "—",
            context=entry.context_window or "—" if entry else "—",
            pass_rate=agg.pass_rate,
            has_data=agg.executed > 0,
            done=agg.executed,
            total=len(SCENARIOS),
            passed=agg.passed,
            failed=agg.failed,
            prompt_tokens=fmt_compact(agg.prompt_tokens),
            completion_tokens=fmt_compact(agg.completion_tokens),
            total_tokens=fmt_compact(agg.total_tokens),
            avg_tool_calls=str(agg.avg_tool_calls),
            halluc_rate=f"{agg.hallucinated_rate}%",
            invalid_json_rate=f"{agg.invalid_json_rate}%",
            loop_rate=f"{agg.loop_rate}%",
        )
        # Idle progress tracks the focused model (0% for a model never
        # benchmarked); during a run the run-scoped counters take over.
        if not self.is_running:
            self.done_cells = agg.executed
            self.total_cells = len(SCENARIOS)
        self._refresh_charts(executions, focus)

    def _refresh_charts(self, executions: list[Execution], focus: str):
        """Radar, error-breakdown, and token-sparkline data."""
        radar_rows = []
        for letter, label in CATEGORIES.items():
            entry: dict = {"category": label}
            for col in self.cols:
                col_summaries = [
                    _summary_of(e)
                    for e in executions
                    if e.model_id == col.model_id
                ]
                agg = aggregate_model(col_summaries)
                entry[col.name] = agg.category_scores.get(letter, 0)
            radar_rows.append(entry)
        self.radar_data = radar_rows

        counts: dict[str, int] = {}
        for e in executions:
            for tag in e.error_tags:
                label = ERROR_LABELS.get(tag, "Other Errors")
                counts[label] = counts.get(label, 0) + 1
        self.error_total = sum(counts.values())
        self.error_data = [
            {
                "name": label,
                "value": count,
                "fill": ERROR_CHART_COLORS.get(label, "#A78BFA"),
            }
            for label, count in sorted(counts.items(), key=lambda x: -x[1])
        ]

        focused = {
            e.scenario_key: e.total_tokens
            for e in executions
            if e.model_id == focus
        }
        self.spark_data = [
            {"scenario": s.key, "tokens": focused.get(s.key, 0)}
            for s in SCENARIOS
            if s.key in focused
        ]

    def _load_detail(self, scenario_key: str, model_id: str):
        """Populate the Scenario Detail panel from the stored execution."""
        scenario = SCENARIOS_BY_KEY[scenario_key]
        self._detail_model_id = model_id
        col_name = next(
            (c.name for c in self.cols if c.model_id == model_id), model_id
        )
        base = Detail(
            visible=True,
            scenario_key=scenario_key,
            name=scenario.name,
            category=CATEGORIES[scenario.category],
            difficulty=scenario.difficulty.capitalize(),
            model_name=col_name,
            user_prompt=scenario.user_message,
            expected=scenario.expected_behavior,
        )
        execution = self._latest_for(model_id, scenario_key)
        if execution is None:
            base.status = "pending"
            base.status_label = "Pending"
            self.detail = base
            return

        base.status = _status_of(execution)
        base.status_label = {
            "pass": "Passed",
            "half": "Half Credit",
            "fail": "Failed",
            "error": "Error",
        }[base.status]
        base.verdict = execution.verdict
        base.final_answer = execution.trace.get("final_answer", "")
        base.latency = f"{execution.latency_ms / 1000:.2f}s"
        base.tokens = fmt_compact(execution.total_tokens)
        base.tool_calls = str(execution.tool_call_count)
        base.points = f"{execution.points} / 2"
        base.events = [
            TraceRow(
                title=ev.get("title", ""),
                kind=ev.get("kind", ""),
                is_ok=ev.get("is_ok", True),
                error_text=ev.get("error_text", ""),
                time_str=datetime.datetime.fromtimestamp(
                    ev.get("ts", 0)
                ).strftime("%H:%M:%S"),
                payload=json.dumps(ev.get("payload", {}), indent=2)[:2000],
            )
            for ev in execution.trace.get("events", [])
        ]
        base.logs_json = json.dumps(execution.trace, indent=2)[:20000]
        self.detail = base
