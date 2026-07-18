"""Scenario Detail panel: overview, trace timeline, metrics, raw logs."""

import reflex as rx

from observatory.components.panels import (
    caption,
    glass_panel,
    metric_row,
    mono_value,
    outcome_badge,
)
from observatory.state.run_state import RunState
from observatory.state.structs import TraceRow
from observatory.theme import tokens as t


# macOS-style neutral glass card: hairline border + soft inner top light,
# no colored accent stripes (status is conveyed by the outcome badge only).
CARD_STYLE = {
    "background": "rgba(255,255,255,0.04)",
    "border": "1px solid rgba(255,255,255,0.08)",
    "border_radius": "10px",
    "box_shadow": "inset 0 1px 0 rgba(255,255,255,0.06)",
    "backdrop_filter": "blur(20px) saturate(1.4)",
    "padding": "10px 12px",
    "width": "100%",
}

# Descendant styling for model-authored markdown so it matches the panel.
MARKDOWN_STYLE = {
    "font_size": "13px",
    "color": t.TEXT_PRIMARY,
    "& p": {"margin": "0 0 6px 0", "line_height": "1.5"},
    "& p:last-child": {"margin_bottom": "0"},
    "& strong": {"color": t.TEXT_PRIMARY, "font_weight": "600"},
    "& ul, & ol": {"margin": "4px 0", "padding_left": "18px"},
    "& li": {"margin": "2px 0"},
    "& code": {
        "font_family": t.FONT_MONO,
        "font_size": "12px",
        "background": "rgba(255,255,255,0.06)",
        "border_radius": "4px",
        "padding": "1px 4px",
    },
}


def _framed(title: str, body: rx.Component) -> rx.Component:
    """Titled sub-block inside the detail panel."""
    return rx.box(
        caption(title, margin_bottom="6px"),
        body,
        style=CARD_STYLE,
    )


def _model_markdown(text: rx.Var) -> rx.Component:
    """Model-authored text rendered as markdown."""
    return rx.box(rx.markdown(text), style=MARKDOWN_STYLE)


def _trace_node(event: TraceRow) -> rx.Component:
    """One timeline entry."""
    icon = rx.cond(
        event.is_ok,
        rx.icon("circle_check", size=14, color=t.STATUS_PASS),
        rx.icon("circle_x", size=14, color=t.STATUS_FAIL),
    )
    return rx.box(
        rx.hstack(
            icon,
            rx.text(
                event.title,
                font_family=t.FONT_MONO,
                font_size="12px",
                color=t.TEXT_PRIMARY,
            ),
            rx.spacer(),
            rx.text(
                event.time_str,
                font_size="11px",
                color=t.TEXT_MUTED,
            ),
            align="center",
            spacing="2",
            width="100%",
        ),
        rx.cond(
            event.error_text != "",
            rx.text(
                f"Error: {event.error_text}",
                font_size="11px",
                color=t.STATUS_FAIL,
                margin_left="22px",
            ),
            rx.fragment(),
        ),
        border_left="1px solid rgba(255,255,255,0.08)",
        padding="6px 0 6px 10px",
        margin_left="6px",
        width="100%",
    )


def _overview_tab() -> rx.Component:
    return rx.vstack(
        _framed(
            "User Prompt",
            rx.text(
                RunState.detail.user_prompt, font_size="13px", color=t.TEXT_PRIMARY
            ),
        ),
        _framed(
            "Expected Behavior",
            rx.text(
                RunState.detail.expected, font_size="13px", color=t.TEXT_SECONDARY
            ),
        ),
        _framed(
            "Model Response",
            rx.vstack(
                rx.text(
                    RunState.detail.verdict,
                    font_size="12px",
                    color=t.TEXT_SECONDARY,
                    font_style="italic",
                ),
                _model_markdown(RunState.detail.final_answer),
                spacing="2",
                align="start",
            ),
        ),
        caption("Tool Call Trace", margin_top="8px"),
        rx.vstack(
            rx.foreach(RunState.detail.events, _trace_node),
            spacing="0",
            width="100%",
        ),
        spacing="3",
        width="100%",
    )


def _trace_tab() -> rx.Component:
    return rx.vstack(
        rx.foreach(
            RunState.detail.events,
            lambda event: rx.vstack(
                _trace_node(event),
                rx.box(
                    rx.el.pre(
                        event.payload,
                        font_family=t.FONT_MONO,
                        font_size="11px",
                        color=t.TEXT_SECONDARY,
                        white_space="pre-wrap",
                        margin="0",
                    ),
                    style={**CARD_STYLE, "padding": "8px", "margin_left": "16px"},
                ),
                spacing="1",
                width="100%",
            ),
        ),
        spacing="2",
        width="100%",
    )


def _metrics_tab() -> rx.Component:
    return rx.vstack(
        metric_row("timer", "Latency", mono_value(RunState.detail.latency)),
        metric_row("coins", "Total Tokens", mono_value(RunState.detail.tokens)),
        metric_row("wrench", "Tool Calls", mono_value(RunState.detail.tool_calls)),
        metric_row("target", "Points", mono_value(RunState.detail.points)),
        metric_row(
            "flag",
            "Outcome",
            outcome_badge(RunState.detail.status, RunState.detail.status_label),
        ),
        spacing="3",
        width="100%",
    )


def _logs_tab() -> rx.Component:
    return rx.box(
        rx.el.pre(
            RunState.detail.logs_json,
            font_family=t.FONT_MONO,
            font_size="11px",
            color=t.TEXT_SECONDARY,
            white_space="pre-wrap",
            margin="0",
        ),
        style={
            **CARD_STYLE,
            "padding": "10px",
            "max_height": "400px",
            "overflow_y": "auto",
        },
    )


def detail_panel() -> rx.Component:
    """The right-column Scenario Detail panel."""
    return rx.cond(
        RunState.detail.visible,
        glass_panel(
            rx.hstack(
                caption("Scenario Detail"),
                rx.spacer(),
                rx.icon(
                    "x",
                    size=16,
                    color=t.TEXT_MUTED,
                    cursor="pointer",
                    on_click=RunState.close_detail,
                ),
                width="100%",
                align="center",
            ),
            rx.hstack(
                rx.text(
                    RunState.detail.scenario_key,
                    font_family=t.FONT_MONO,
                    font_size="20px",
                    font_weight="700",
                    color=t.TEXT_PRIMARY,
                ),
                rx.spacer(),
                outcome_badge(RunState.detail.status, RunState.detail.status_label),
                width="100%",
                align="center",
                margin_top="6px",
            ),
            rx.text(
                RunState.detail.name, font_size="13px", color=t.TEXT_SECONDARY
            ),
            rx.hstack(
                rx.vstack(
                    caption("Category"),
                    rx.text(
                        RunState.detail.category,
                        font_size="13px",
                        color=t.TEXT_PRIMARY,
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.vstack(
                    caption("Difficulty"),
                    rx.text(
                        RunState.detail.difficulty,
                        font_size="13px",
                        color=t.TEXT_PRIMARY,
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.vstack(
                    caption("Model"),
                    rx.text(
                        RunState.detail.model_name,
                        font_size="13px",
                        color=t.TEXT_PRIMARY,
                    ),
                    spacing="1",
                    align="start",
                ),
                spacing="6",
                margin="10px 0",
            ),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Overview", value="overview"),
                    rx.tabs.trigger("Trace", value="trace"),
                    rx.tabs.trigger("Metrics", value="metrics"),
                    rx.tabs.trigger("Logs", value="logs"),
                ),
                rx.tabs.content(_overview_tab(), value="overview", padding_top="12px"),
                rx.tabs.content(_trace_tab(), value="trace", padding_top="12px"),
                rx.tabs.content(_metrics_tab(), value="metrics", padding_top="12px"),
                rx.tabs.content(_logs_tab(), value="logs", padding_top="12px"),
                default_value="overview",
                width="100%",
            ),
            rx.button(
                "Replay Execution",
                rx.icon("play", size=14),
                on_click=RunState.replay_execution,
                width="100%",
                margin_top="14px",
                background="transparent",
                border=f"1px solid {t.ACCENT}",
                color=t.ACCENT,
                border_radius=t.RADIUS_CONTROL,
                cursor="pointer",
                _hover={"background": t.SURFACE_3, "box_shadow": t.ACCENT_GLOW},
            ),
            width="340px",
            min_width="340px",
            max_height="calc(100vh - 120px)",
            overflow_y="auto",
        ),
        rx.fragment(),
    )
