"""App shell: nav rail, header with run controls, footer status bar."""

import reflex as rx

from observatory.state.run_state import RunState
from observatory.theme import tokens as t

NAV_ITEMS = [
    ("layout_grid", "/", "Dashboard"),
    ("chart_line", "/analytics", "Analytics"),
    ("file_text", "/scenarios", "Scenarios"),
    ("settings", "/settings", "Settings"),
]

APP_VERSION = "v0.1.0"


def _nav_icon(icon: str, href: str, label: str, active: str) -> rx.Component:
    """One rail icon with tooltip and active state."""
    is_active = href == active
    return rx.tooltip(
        rx.link(
            rx.box(
                rx.icon(
                    icon,
                    size=20,
                    color=t.ACCENT if is_active else t.TEXT_MUTED,
                ),
                padding="10px",
                border_radius=t.RADIUS_CONTROL,
                background=t.SURFACE_3 if is_active else "transparent",
                border_left=(
                    f"2px solid {t.ACCENT}" if is_active else "2px solid transparent"
                ),
                box_shadow=t.ACCENT_GLOW if is_active else "none",
                _hover={"background": t.SURFACE_2},
                transition="background 150ms",
            ),
            href=href,
        ),
        content=label,
        side="right",
    )


def nav_rail(active: str) -> rx.Component:
    """Fixed 64px icon rail."""
    return rx.vstack(
        *[_nav_icon(icon, href, label, active) for icon, href, label in NAV_ITEMS],
        rx.spacer(),
        width="64px",
        min_width="64px",
        height="100vh",
        padding="16px 8px",
        align="center",
        spacing="2",
        background=t.SURFACE_1,
        border_right=f"1px solid {t.BORDER_SOFT}",
        backdrop_filter=t.GLASS_BLUR,
        position="sticky",
        top="0",
    )


def _status_chip() -> rx.Component:
    """Pulsing run-status indicator."""
    color = rx.match(
        RunState.run_status,
        ("running", t.ACCENT),
        ("complete", t.ACCENT),
        ("aborted", t.STATUS_FAIL),
        ("error", t.STATUS_FAIL),
        t.TEXT_MUTED,
    )
    return rx.hstack(
        rx.box(
            width="8px",
            height="8px",
            border_radius="50%",
            background=color,
            animation=rx.cond(
                RunState.is_running, "pulse 1.6s ease-in-out infinite", "none"
            ),
        ),
        rx.text(
            RunState.status_label,
            font_size="12px",
            font_weight="500",
            color=color,
        ),
        align="center",
        spacing="2",
    )


def _progress_bar() -> rx.Component:
    """Header run progress."""
    return rx.hstack(
        rx.box(
            rx.box(
                height="8px",
                width=f"{RunState.progress_pct}%",
                border_radius="999px",
                background=f"linear-gradient(90deg, {t.ACCENT_DIM}, {t.ACCENT})",
                box_shadow=t.ACCENT_GLOW,
                transition="width 300ms cubic-bezier(0.16, 1, 0.3, 1)",
            ),
            width="220px",
            height="8px",
            border_radius="999px",
            background=t.SURFACE_3,
        ),
        rx.text(
            f"{RunState.progress_pct}%",
            font_family=t.FONT_MONO,
            font_size="12px",
            color=t.TEXT_SECONDARY,
        ),
        align="center",
        spacing="3",
    )


def _run_button() -> rx.Component:
    """Start Run (idle) / Stop Run (running)."""
    return rx.cond(
        RunState.is_running,
        rx.button(
            rx.icon("square", size=14),
            "Stop Run",
            on_click=RunState.stop_run,
            background="transparent",
            border=f"1px solid {t.ACCENT}",
            color=t.ACCENT,
            border_radius=t.RADIUS_CONTROL,
            cursor="pointer",
            _hover={"background": t.SURFACE_3, "box_shadow": t.ACCENT_GLOW},
        ),
        rx.tooltip(
            rx.button(
                rx.icon("play", size=14),
                "Start Run",
                on_click=RunState.start_run,
                disabled=~RunState.can_run,
                background=t.ACCENT,
                color="#06130A",
                font_weight="600",
                border_radius=t.RADIUS_CONTROL,
                cursor="pointer",
                _hover={"box_shadow": t.ACCENT_GLOW},
                _disabled={
                    "background": t.SURFACE_3,
                    "color": t.TEXT_MUTED,
                    "cursor": "not-allowed",
                },
            ),
            content=rx.cond(
                RunState.can_run,
                "Run the selected target",
                "Selected model is inactive on the current endpoint",
            ),
        ),
    )


def header() -> rx.Component:
    """Top bar: identity left, run controls right."""
    return rx.hstack(
        rx.hstack(
            rx.icon("bot", size=30, color=t.ACCENT),
            rx.vstack(
                rx.text(
                    "TACHIKOMA-OBSERVATORY",
                    font_family=t.FONT_DISPLAY,
                    font_size="20px",
                    font_weight="700",
                    letter_spacing="0.06em",
                    color=t.TEXT_PRIMARY,
                ),
                rx.text(
                    "Comprehensive benchmark for LLM tool calling capabilities",
                    font_size="12px",
                    color=t.TEXT_SECONDARY,
                ),
                spacing="0",
                align="start",
            ),
            align="center",
            spacing="3",
        ),
        rx.spacer(),
        rx.hstack(
            rx.vstack(
                rx.text("Model", font_size="10px", color=t.TEXT_MUTED),
                rx.select(
                    RunState.target_options,
                    value=RunState.target,
                    on_change=RunState.set_target,
                    disabled=RunState.is_running,
                    size="1",
                ),
                spacing="0",
                align="start",
            ),
            _status_chip(),
            _progress_bar(),
            _run_button(),
            align="center",
            spacing="5",
            background=t.SURFACE_1,
            border=f"1px solid {t.BORDER_SOFT}",
            border_radius=t.RADIUS_PANEL,
            padding="10px 16px",
        ),
        width="100%",
        align="center",
        padding="16px 0",
    )


def footer() -> rx.Component:
    """Bottom status bar."""
    return rx.hstack(
        caption_text("System Status"),
        rx.hstack(
            rx.box(
                width="7px",
                height="7px",
                border_radius="50%",
                background=rx.cond(
                    RunState.endpoint_ok, t.ACCENT, t.STATUS_FAIL
                ),
            ),
            rx.text(
                rx.cond(
                    RunState.endpoint_ok,
                    "All Systems Operational",
                    "Endpoint Unreachable",
                ),
                font_size="12px",
                color=rx.cond(RunState.endpoint_ok, t.ACCENT, t.STATUS_FAIL),
            ),
            align="center",
            spacing="2",
        ),
        caption_text("Last Updated"),
        rx.text(
            RunState.last_updated,
            font_family=t.FONT_MONO,
            font_size="12px",
            color=t.TEXT_SECONDARY,
        ),
        rx.spacer(),
        rx.text(
            f"TACHIKOMA-OBSERVATORY {APP_VERSION}",
            font_family=t.FONT_MONO,
            font_size="12px",
            color=t.ACCENT,
        ),
        width="100%",
        height="36px",
        align="center",
        spacing="4",
        padding="0 20px",
        background=t.SURFACE_1,
        border_top=f"1px solid {t.BORDER_SOFT}",
    )


def caption_text(text: str) -> rx.Component:
    """Small muted footer label."""
    return rx.text(
        text,
        font_size="11px",
        text_transform="uppercase",
        letter_spacing="0.08em",
        color=t.TEXT_MUTED,
    )


def app_shell(*children, active: str = "/") -> rx.Component:
    """Page wrapper: rail + scrolling content column + footer."""
    return rx.box(
        rx.hstack(
            nav_rail(active),
            rx.vstack(
                rx.box(
                    header(),
                    *children,
                    width="100%",
                    padding="0 20px 20px 20px",
                    max_width="1800px",
                ),
                rx.spacer(),
                footer(),
                width="100%",
                min_height="100vh",
                spacing="0",
            ),
            spacing="0",
            align="start",
            width="100%",
        ),
        background=t.BG_VOID,
        background_image=t.BG_VOID_GLOW,
        min_height="100vh",
        font_family=t.FONT_BODY,
    )
