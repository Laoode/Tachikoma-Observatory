"""Charts row: radar (category accuracy) and error-breakdown donut."""

import reflex as rx

from observatory.components.panels import glass_panel, panel_title
from observatory.state.run_state import RunState
from observatory.state.structs import ModelCol
from observatory.theme import tokens as t

AXIS_STYLE = {"font_size": "11px", "fill": t.TEXT_MUTED}


def _radar_series(col: ModelCol) -> rx.Component:
    return rx.recharts.radar(
        data_key=col.name,
        stroke=col.color,
        fill=col.color,
        fill_opacity=0.12,
    )


def radar_panel() -> rx.Component:
    """Tool Selection Accuracy radar over the 5 categories."""
    return glass_panel(
        panel_title(
            "Tool Selection Accuracy",
            "Category score per model (METHODOLOGY.md weights)",
        ),
        rx.hstack(
            rx.recharts.radar_chart(
                rx.recharts.polar_grid(stroke="rgba(74,222,128,0.1)"),
                rx.recharts.polar_angle_axis(data_key="category"),
                rx.foreach(RunState.cols, _radar_series),
                data=RunState.radar_data,
                width="100%",
                height=260,
            ),
            rx.vstack(
                rx.foreach(
                    RunState.cols,
                    lambda c: rx.hstack(
                        rx.box(
                            width="8px",
                            height="8px",
                            border_radius="50%",
                            background=c.color,
                        ),
                        rx.text(c.name, font_size="12px", color=t.TEXT_SECONDARY),
                        align="center",
                        spacing="2",
                    ),
                ),
                spacing="2",
                min_width="140px",
            ),
            width="100%",
            align="center",
        ),
        flex="1",
    )


def error_breakdown_panel() -> rx.Component:
    """Error taxonomy donut with legend."""
    return glass_panel(
        panel_title("Error Breakdown", "Error tags across all models in this run"),
        rx.cond(
            RunState.error_total > 0,
            rx.hstack(
                rx.box(
                    rx.recharts.pie_chart(
                        rx.recharts.pie(
                            data=RunState.error_data,
                            data_key="value",
                            name_key="name",
                            inner_radius="65%",
                            outer_radius="90%",
                            stroke="none",
                        ),
                        width=200,
                        height=220,
                    ),
                    rx.vstack(
                        rx.text(
                            RunState.error_total,
                            font_family=t.FONT_MONO,
                            font_size="24px",
                            font_weight="700",
                            color=t.TEXT_PRIMARY,
                        ),
                        rx.text("Errors", font_size="11px", color=t.TEXT_MUTED),
                        spacing="0",
                        align="center",
                        position="absolute",
                        top="50%",
                        left="100px",
                        transform="translate(-50%, -50%)",
                    ),
                    position="relative",
                ),
                rx.vstack(
                    rx.foreach(
                        RunState.error_data,
                        lambda item: rx.hstack(
                            rx.box(
                                width="8px",
                                height="8px",
                                border_radius="2px",
                                background=item["fill"],
                            ),
                            rx.text(
                                item["name"],
                                font_size="12px",
                                color=t.TEXT_SECONDARY,
                            ),
                            rx.spacer(),
                            rx.text(
                                item["value"],
                                font_family=t.FONT_MONO,
                                font_size="12px",
                                color=t.TEXT_PRIMARY,
                            ),
                            width="100%",
                            align="center",
                            spacing="2",
                        ),
                    ),
                    spacing="2",
                    flex="1",
                ),
                width="100%",
                align="center",
                spacing="4",
            ),
            rx.box(
                rx.text(
                    "No errors recorded", font_size="13px", color=t.TEXT_MUTED
                ),
                display="flex",
                align_items="center",
                justify_content="center",
                height="220px",
            ),
        ),
        flex="1",
    )


def charts_row() -> rx.Component:
    """Radar + error breakdown side by side."""
    return rx.hstack(
        radar_panel(),
        error_breakdown_panel(),
        spacing="4",
        width="100%",
        align="stretch",
    )
