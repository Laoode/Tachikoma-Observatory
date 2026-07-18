"""Scenarios page: static browser for the frozen ToolCall-15 suite."""

import reflex as rx

from observatory.components.panels import difficulty_badge, glass_panel, panel_title
from observatory.components.shell import app_shell
from observatory.suite.toolcall15 import CATEGORIES, SCENARIOS, SUITE_VERSION
from observatory.theme import tokens as t


def _scenario_card(scenario) -> rx.Component:
    """One scenario summary card (suite data is static; rendered at compile)."""
    return glass_panel(
        rx.hstack(
            rx.text(
                scenario.key,
                font_family=t.FONT_MONO,
                font_size="13px",
                font_weight="600",
                color=t.ACCENT,
            ),
            rx.text(
                scenario.name,
                font_size="14px",
                font_weight="600",
                color=t.TEXT_PRIMARY,
            ),
            rx.spacer(),
            rx.text(
                CATEGORIES[scenario.category],
                font_size="12px",
                color=t.TEXT_SECONDARY,
            ),
            difficulty_badge(scenario.difficulty.capitalize()),
            width="100%",
            align="center",
            spacing="3",
        ),
        rx.text(
            f'"{scenario.user_message}"',
            font_size="13px",
            color=t.TEXT_SECONDARY,
            font_style="italic",
            margin_top="8px",
        ),
        rx.text(
            scenario.expected_behavior,
            font_size="12px",
            color=t.TEXT_MUTED,
            margin_top="6px",
        ),
        width="100%",
    )


@rx.page(route="/scenarios", title="Scenarios — Tachikoma-Observatory")
def scenarios() -> rx.Component:
    """Suite browser."""
    return app_shell(
        glass_panel(
            panel_title(
                f"ToolCall-15 Suite ({SUITE_VERSION})",
                "Frozen per METHODOLOGY.md; new scenarios require a new version",
            ),
            width="100%",
            margin_bottom="16px",
        ),
        rx.vstack(
            *[_scenario_card(s) for s in SCENARIOS],
            spacing="3",
            width="100%",
        ),
        active="/scenarios",
    )
