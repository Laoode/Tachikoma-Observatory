"""Reusable glass-panel primitives (DESIGN.md section 2)."""

import reflex as rx

from observatory.theme import tokens as t


def glass_panel(*children, **props) -> rx.Component:
    """A liquid-glass surface panel."""
    style = {
        "background": t.SURFACE_1,
        "border": f"1px solid {t.BORDER_SOFT}",
        "border_radius": t.RADIUS_PANEL,
        "backdrop_filter": t.GLASS_BLUR,
        "box_shadow": "inset 0 1px 0 rgba(255,255,255,0.04)",
        "padding": "16px",
    }
    style.update(props.pop("style", {}))
    return rx.box(*children, style=style, **props)


def caption(text: str | rx.Var, **props) -> rx.Component:
    """11px uppercase muted label."""
    return rx.text(
        text,
        font_family=t.FONT_BODY,
        font_size="11px",
        text_transform="uppercase",
        letter_spacing="0.08em",
        color=t.TEXT_MUTED,
        **props,
    )


def panel_title(title: str, info: str = "") -> rx.Component:
    """Panel heading row with an optional info tooltip."""
    heading = rx.text(
        title,
        font_family=t.FONT_DISPLAY,
        font_size="14px",
        font_weight="600",
        color=t.TEXT_PRIMARY,
    )
    if not info:
        return heading
    return rx.hstack(
        heading,
        rx.tooltip(
            rx.icon("info", size=14, color=t.TEXT_MUTED),
            content=info,
        ),
        align="center",
        spacing="2",
    )


def mono_value(value: str | rx.Var, color: str = t.TEXT_PRIMARY, size: str = "13px") -> rx.Component:
    """Monospace metric value."""
    return rx.text(
        value,
        font_family=t.FONT_MONO,
        font_size=size,
        font_weight="600",
        color=color,
    )


def metric_row(icon: str, label: str, value: rx.Component) -> rx.Component:
    """Icon + label left, value right."""
    return rx.hstack(
        rx.icon(icon, size=14, color=t.TEXT_MUTED),
        rx.text(label, font_size="12px", color=t.TEXT_SECONDARY),
        rx.spacer(),
        value,
        align="center",
        width="100%",
        spacing="2",
    )


def difficulty_badge(difficulty: rx.Var) -> rx.Component:
    """Easy/Medium/Hard tinted badge."""
    color = rx.match(
        difficulty,
        ("Easy", t.STATUS_PASS),
        ("Medium", t.STATUS_HALF),
        ("Hard", t.STATUS_FAIL),
        t.TEXT_MUTED,
    )
    background = rx.match(
        difficulty,
        ("Easy", "rgba(74,222,128,0.12)"),
        ("Medium", "rgba(245,158,11,0.12)"),
        ("Hard", "rgba(248,113,113,0.12)"),
        "rgba(92,114,100,0.12)",
    )
    return rx.box(
        rx.text(difficulty, font_size="11px", font_weight="500", color=color),
        background=background,
        border_radius=t.RADIUS_BADGE,
        padding="2px 8px",
        display="inline-block",
    )


def status_icon(status: rx.Var, size: int = 18) -> rx.Component:
    """Matrix/detail status glyph."""
    return rx.match(
        status,
        ("pass", rx.icon("circle_check", size=size, color=t.STATUS_PASS)),
        ("half", rx.icon("circle_alert", size=size, color=t.STATUS_HALF)),
        ("fail", rx.icon("circle_x", size=size, color=t.STATUS_FAIL)),
        ("error", rx.icon("circle_off", size=size, color=t.STATUS_FAIL)),
        (
            "running",
            rx.box(
                rx.icon("loader_circle", size=size, color=t.ACCENT),
                animation="spin 1.2s linear infinite",
            ),
        ),
        rx.icon("circle_dashed", size=size, color=t.STATUS_PENDING),
    )


def outcome_badge(status: rx.Var, label: rx.Var) -> rx.Component:
    """Passed/Half Credit/Failed pill for the detail panel."""
    color = rx.match(
        status,
        ("pass", t.STATUS_PASS),
        ("half", t.STATUS_HALF),
        ("fail", t.STATUS_FAIL),
        ("error", t.STATUS_FAIL),
        t.TEXT_MUTED,
    )
    background = rx.match(
        status,
        ("pass", "rgba(74,222,128,0.12)"),
        ("half", "rgba(245,158,11,0.12)"),
        ("fail", "rgba(248,113,113,0.12)"),
        ("error", "rgba(248,113,113,0.12)"),
        "rgba(92,114,100,0.12)",
    )
    return rx.box(
        rx.text(label, font_size="12px", font_weight="600", color=color),
        background=background,
        border_radius=t.RADIUS_BADGE,
        padding="2px 10px",
        display="inline-block",
    )
