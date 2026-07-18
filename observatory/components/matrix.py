"""Scenario Matrix: toolbar, results table, per-model status cells."""

import reflex as rx

from observatory.components.panels import (
    difficulty_badge,
    glass_panel,
    panel_title,
    status_icon,
)
from observatory.state.run_state import RunState
from observatory.state.structs import Cell, Row
from observatory.theme import tokens as t


def _toolbar() -> rx.Component:
    """Search, category filter, export."""
    return rx.hstack(
        rx.input(
            placeholder="Search scenario…",
            value=RunState.search,
            on_change=RunState.set_search,
            width="240px",
            background=t.SURFACE_2,
            border=f"1px solid {t.BORDER_SOFT}",
            color=t.TEXT_PRIMARY,
        ),
        rx.spacer(),
        rx.select(
            RunState.category_options,
            value=RunState.category_filter,
            on_change=RunState.set_category_filter,
            size="2",
        ),
        rx.tooltip(
            rx.icon_button(
                rx.icon("download", size=16),
                on_click=RunState.export_csv,
                background="transparent",
                border=f"1px solid {t.BORDER_SOFT}",
                color=t.TEXT_SECONDARY,
                cursor="pointer",
                _hover={"background": t.SURFACE_3},
            ),
            content="Export CSV",
        ),
        width="100%",
        align="center",
        spacing="3",
        margin="12px 0",
    )


def _header_cell(text: rx.Var | str) -> rx.Component:
    return rx.table.column_header_cell(
        rx.text(
            text,
            font_size="11px",
            text_transform="uppercase",
            letter_spacing="0.08em",
            color=t.TEXT_MUTED,
        )
    )


def _result_cell(row: Row, cell: Cell) -> rx.Component:
    """Clickable status icon cell."""
    return rx.table.cell(
        rx.box(
            status_icon(cell.status),
            cursor="pointer",
            display="flex",
            justify_content="center",
            on_click=RunState.select_cell(row.key, cell.model_id),
        ),
        text_align="center",
    )


def _scenario_row(row: Row) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(
                row.key,
                font_family=t.FONT_MONO,
                font_size="12px",
                color=t.TEXT_SECONDARY,
            )
        ),
        rx.table.cell(
            rx.text(row.name, font_size="13px", color=t.TEXT_PRIMARY)
        ),
        rx.table.cell(
            rx.text(row.category, font_size="13px", color=t.TEXT_SECONDARY)
        ),
        rx.table.cell(difficulty_badge(row.difficulty)),
        rx.foreach(row.cells, lambda cell: _result_cell(row, cell)),
        _hover={"background": t.SURFACE_3},
    )


def scenario_matrix() -> rx.Component:
    """The full matrix panel."""
    return glass_panel(
        panel_title(
            "Scenario Matrix",
            "Latest result per scenario and model; click a cell for details",
        ),
        _toolbar(),
        rx.box(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        _header_cell("Scenario ID"),
                        _header_cell("Scenario Name"),
                        _header_cell("Category"),
                        _header_cell("Difficulty"),
                        rx.foreach(RunState.cols, lambda c: _header_cell(c.name)),
                    )
                ),
                rx.table.body(
                    rx.foreach(RunState.filtered_rows, _scenario_row)
                ),
                width="100%",
            ),
            overflow_x="auto",
            width="100%",
        ),
        rx.text(
            f"Showing {RunState.filtered_rows.length()} of {RunState.rows.length()} scenarios",
            font_size="12px",
            color=t.TEXT_MUTED,
            margin_top="10px",
        ),
        width="100%",
    )
