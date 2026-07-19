"""Dashboard state: run control, live matrix, KPIs, charts, detail panel."""

import asyncio
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


def _run_label(run) -> str:
    """Compact run-history option label, e.g. '#2 · 07-19 20:17 · complete'."""
    when = run.started_at[5:16].replace("T", " ")
    return f"#{run.id} · {when} · {run.status}"


def _status_of(execution: Execution) -> str:
    """Matrix cell status for a stored execution."""
    if execution.status == "error":
        return "error"
    return {2: "pass", 1: "half", 0: "fail"}[execution.points]


class RunState(rx.State):
    """Everything the dashboard page renders and controls."""

    run_status: str = "idle"
    run_id: int = 0
    run_options: list[str] = []
    selected_run: str = ""
    _run_ids: dict[str, int] = {}
    cols: list[ModelCol] = []
    rows: list[Row] = []
    done_cells: int = 0
    total_cells: int = 0
    focused_model: str = ""
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

    @rx.var
    def progress_pct(self) -> int:
        """Run completion percentage for the header bar."""
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

    @rx.var
    def focused_options(self) -> list[str]:
        """Model names for the Current Run select."""
        return [c.name for c in self.cols]

    @rx.var
    def focused_name(self) -> str:
        """Display name of the focused model."""
        for c in self.cols:
            if c.model_id == self.focused_model:
                return c.name
        return ""

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

    @rx.event
    def load_dashboard(self):
        """Page on_load: restore the latest run and ping the endpoint."""
        self._refresh_run_options()
        run = repo.latest_run()
        if run is not None:
            self._show_run(run)
        self.last_updated = datetime.datetime.now().strftime("%H:%M:%S")
        return RunState.ping_endpoint

    @rx.event
    def select_run(self, label: str):
        """Load a historical run into the dashboard (disabled while running)."""
        if self.is_running:
            return
        run = repo.get_run(self._run_ids.get(label, 0))
        if run is None:
            return
        self.detail = Detail()
        self._show_run(run)

    def _show_run(self, run) -> None:
        """Point the dashboard at one run."""
        self.run_id = run.id
        self.run_status = run.status
        self.selected_run = _run_label(run)
        self._load_run(run.id, run.model_ids)

    def _refresh_run_options(self) -> None:
        """Rebuild the run-history select options, newest first."""
        runs = repo.list_runs()
        self._run_ids = {_run_label(r): r.id for r in runs}
        self.run_options = list(self._run_ids)

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
    def set_focused(self, name: str):
        """Switch the model the KPI cards focus on."""
        for c in self.cols:
            if c.name == name:
                self.focused_model = c.model_id
        self._refresh_views()

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
        """Download the current matrix as CSV."""
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
            data="\n".join(lines), filename=f"tachikoma-run-{self.run_id}.csv"
        )

    @rx.event(background=True)
    async def start_run(self):
        """Launch a lockstep benchmark run over all enabled models."""
        config = load_llm_config()
        if config is None:
            yield rx.toast.error(
                "Endpoint not configured: set TACHIKOMA_LLM_BASE_URL and "
                "TACHIKOMA_LLM_API_KEY, then restart."
            )
            return
        entries = repo.list_models(enabled_only=True)
        if not entries:
            yield rx.toast.error(
                "No enabled models. Sync the registry on the Settings page first."
            )
            return

        model_ids = [e.model_id for e in entries]
        run_id = repo.create_run(model_ids)
        _STOP_FLAGS[run_id] = False
        async with self:
            self._refresh_run_options()
            self._show_run(repo.get_run(run_id))

        client = LLMClient(config)
        state_ref = self

        async def on_event(event: RunEvent):
            if event.kind == "execution_started":
                async with state_ref:
                    state_ref._set_cell(event.scenario_key, event.model_id, "running")
            elif event.kind == "execution_finished" and event.trace is not None:
                score = score_trace(event.trace)
                repo.record_execution(run_id, event.trace, score)
                async with state_ref:
                    state_ref._load_run(run_id, model_ids)

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
            self._refresh_run_options()
            self._show_run(repo.get_run(run_id))

    @rx.event(background=True)
    async def replay_execution(self):
        """Re-run the selected scenario x model pair as a new attempt."""
        async with self:
            scenario_key = self.detail.scenario_key
            model_id = self._detail_model_id
            run_id = self.run_id
        if not scenario_key or not model_id or not run_id:
            return
        config = load_llm_config()
        if config is None:
            yield rx.toast.error("Endpoint not configured.")
            return
        async with self:
            self._set_cell(scenario_key, model_id, "running")
        client = LLMClient(config)
        trace = await execute_scenario(
            client, model_id, SCENARIOS_BY_KEY[scenario_key]
        )
        score = score_trace(trace)
        repo.record_execution(run_id, trace, score)
        run = repo.latest_run()
        async with self:
            self._load_run(run_id, run.model_ids if run else [model_id])
            self._load_detail(scenario_key, model_id)

    _detail_model_id: str = ""

    def _load_run(self, run_id: int, model_ids: list[str]):
        """Rebuild all view models from the DB for one run."""
        registry = {e.model_id: e for e in repo.list_models()}
        self.cols = [
            ModelCol(
                model_id=m,
                name=registry[m].display_name if m in registry else m,
                color=registry[m].color if m in registry else "#4ADE80",
            )
            for m in model_ids
        ]
        if self.focused_model not in model_ids:
            self.focused_model = model_ids[0] if model_ids else ""

        executions = repo.latest_executions(run_id)
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
                    for m in model_ids
                ],
            )
            for s in SCENARIOS
        ]
        self.done_cells = len(by_cell)
        self.total_cells = len(SCENARIOS) * len(model_ids)
        self._refresh_views(executions)
        self.last_updated = datetime.datetime.now().strftime("%H:%M:%S")

    def _set_cell(self, scenario_key: str, model_id: str, status: str):
        """Flip one matrix cell status in place (list reassigned for reactivity)."""
        self.rows = [
            Row(
                key=r.key,
                name=r.name,
                category=r.category,
                difficulty=r.difficulty,
                cells=[
                    Cell(model_id=c.model_id, status=status)
                    if r.key == scenario_key and c.model_id == model_id
                    else c
                    for c in r.cells
                ],
            )
            for r in self.rows
        ]

    def _refresh_views(self, executions: list[Execution] | None = None):
        """Recompute KPI cards and chart data for the focused model."""
        if executions is None:
            executions = repo.latest_executions(self.run_id) if self.run_id else []
        focused_execs = [e for e in executions if e.model_id == self.focused_model]
        summaries = [
            ExecutionSummary(
                scenario_key=e.scenario_key,
                points=e.points,
                error_tags=tuple(e.error_tags),
                tool_call_count=e.tool_call_count,
                prompt_tokens=e.prompt_tokens,
                completion_tokens=e.completion_tokens,
                latency_ms=e.latency_ms,
            )
            for e in focused_execs
        ]
        agg = aggregate_model(summaries)
        registry = {e.model_id: e for e in repo.list_models()}
        entry = registry.get(self.focused_model)
        self.kpi = Kpi(
            model_name=entry.display_name if entry else (self.focused_model or "—"),
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
        self._refresh_charts(executions)

    def _refresh_charts(self, executions: list[Execution]):
        """Radar, error-breakdown, and token-sparkline data."""
        radar_rows = []
        for letter, label in CATEGORIES.items():
            entry: dict = {"category": label}
            for col in self.cols:
                col_execs = [
                    ExecutionSummary(
                        scenario_key=e.scenario_key,
                        points=e.points,
                        error_tags=tuple(e.error_tags),
                    )
                    for e in executions
                    if e.model_id == col.model_id
                ]
                agg = aggregate_model(col_execs)
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
            if e.model_id == self.focused_model
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
        executions = repo.latest_executions(self.run_id) if self.run_id else []
        execution = next(
            (
                e
                for e in executions
                if e.model_id == model_id and e.scenario_key == scenario_key
            ),
            None,
        )
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
