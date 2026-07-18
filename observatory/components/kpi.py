"""KPI row: Model Under Test, Benchmark Status, Token Usage, Tool Efficiency."""

import reflex as rx

from observatory.components.panels import (
    caption,
    glass_panel,
    metric_row,
    mono_value,
    panel_title,
)
from observatory.state.run_state import RunState
from observatory.theme import tokens as t


def _labeled(label: str, value: rx.Var) -> rx.Component:
    """Caption over mono value."""
    return rx.vstack(
        caption(label),
        mono_value(value),
        spacing="1",
        align="start",
    )


def model_under_test() -> rx.Component:
    """Focused model identity card."""
    return glass_panel(
        panel_title("Model Under Test", "Model currently focused in the KPI cards"),
        rx.hstack(
            rx.box(
                rx.icon("sparkles", size=20, color=t.ACCENT),
                padding="8px",
                background="rgba(74,222,128,0.1)",
                border_radius=t.RADIUS_CONTROL,
            ),
            rx.text(
                RunState.kpi.model_name,
                font_family=t.FONT_DISPLAY,
                font_size="16px",
                font_weight="600",
                color=t.TEXT_PRIMARY,
            ),
            align="center",
            spacing="3",
            margin_top="12px",
        ),
        rx.hstack(
            _labeled("Provider", RunState.kpi.provider),
            _labeled("Context", RunState.kpi.context),
            _labeled("Temperature", "0.0"),
            _labeled("Tool Mode", "Function Calling"),
            spacing="5",
            margin_top="14px",
        ),
        flex="1",
    )


def _pass_ring() -> rx.Component:
    """Conic-gradient pass-rate ring with centered percentage."""
    angle = RunState.kpi.pass_rate * 3.6
    return rx.box(
        rx.box(
            rx.vstack(
                rx.text(
                    f"{RunState.kpi.pass_rate}%",
                    font_family=t.FONT_MONO,
                    font_size="22px",
                    font_weight="700",
                    color=t.TEXT_PRIMARY,
                ),
                caption("Pass Rate"),
                spacing="0",
                align="center",
            ),
            width="76px",
            height="76px",
            border_radius="50%",
            background="#0B120D",
            display="flex",
            align_items="center",
            justify_content="center",
        ),
        width="96px",
        height="96px",
        border_radius="50%",
        background=f"conic-gradient({t.ACCENT} {angle}deg, {t.SURFACE_3} 0deg)",
        display="flex",
        align_items="center",
        justify_content="center",
        filter="drop-shadow(0 0 8px rgba(74,222,128,0.3))",
    )


def benchmark_status() -> rx.Component:
    """Pass-rate ring plus scenario counters."""
    return glass_panel(
        panel_title("Benchmark Status", "Weighted score per METHODOLOGY.md"),
        rx.hstack(
            _pass_ring(),
            rx.vstack(
                _labeled(
                    "Scenarios",
                    f"{RunState.kpi.done} / {RunState.kpi.total}",
                ),
                rx.vstack(
                    caption("Tests Passed"),
                    mono_value(RunState.kpi.passed.to_string(), t.ACCENT),
                    spacing="1",
                    align="start",
                ),
                rx.vstack(
                    caption("Tests Failed"),
                    mono_value(RunState.kpi.failed.to_string(), t.STATUS_FAIL),
                    spacing="1",
                    align="start",
                ),
                spacing="2",
                align="start",
            ),
            spacing="5",
            align="center",
            margin_top="12px",
        ),
        flex="1",
    )


def token_usage() -> rx.Component:
    """Token counters with a per-scenario sparkline."""
    return glass_panel(
        panel_title("Token Usage", "Tokens consumed by the focused model"),
        rx.vstack(
            metric_row(
                "message_square", "Prompt Tokens",
                mono_value(RunState.kpi.prompt_tokens),
            ),
            metric_row(
                "message_circle_reply", "Completion Tokens",
                mono_value(RunState.kpi.completion_tokens),
            ),
            metric_row(
                "coins", "Total Tokens", mono_value(RunState.kpi.total_tokens)
            ),
            spacing="2",
            width="100%",
            margin_top="12px",
        ),
        rx.recharts.area_chart(
            rx.recharts.area(
                data_key="tokens",
                stroke=t.ACCENT,
                fill="rgba(74,222,128,0.2)",
                type_="monotone",
            ),
            data=RunState.spark_data,
            width="100%",
            height=44,
            margin={"top": 4, "bottom": 0, "left": 0, "right": 0},
        ),
        flex="1",
    )


def _rate_value(value: rx.Var) -> rx.Component:
    """Error-rate value: green at 0%, red otherwise."""
    return rx.text(
        value,
        font_family=t.FONT_MONO,
        font_size="13px",
        font_weight="600",
        color=rx.cond(
            (value == "0%") | (value == "0.0%"), t.ACCENT, t.STATUS_FAIL
        ),
    )


def tool_efficiency() -> rx.Component:
    """Tool-use quality rates."""
    return glass_panel(
        panel_title("Tool Efficiency", "Tool-use quality of the focused model"),
        rx.vstack(
            metric_row(
                "wrench", "Average Tool Calls",
                mono_value(RunState.kpi.avg_tool_calls),
            ),
            metric_row(
                "ghost", "Hallucinated Calls",
                _rate_value(RunState.kpi.halluc_rate),
            ),
            metric_row(
                "braces", "Invalid JSON Rate",
                _rate_value(RunState.kpi.invalid_json_rate),
            ),
            metric_row(
                "refresh_cw_off", "Loop Detected",
                _rate_value(RunState.kpi.loop_rate),
            ),
            spacing="3",
            width="100%",
            margin_top="12px",
        ),
        flex="1",
    )


def kpi_row() -> rx.Component:
    """The four KPI cards."""
    return rx.hstack(
        model_under_test(),
        benchmark_status(),
        token_usage(),
        tool_efficiency(),
        spacing="4",
        width="100%",
        align="stretch",
    )
