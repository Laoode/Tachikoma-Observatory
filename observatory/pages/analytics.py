"""Analytics page: historical performance chart and leaderboard."""

import reflex as rx

from observatory.components.panels import glass_panel, panel_title
from observatory.components.shell import app_shell
from observatory.state.analytics_state import AnalyticsState
from observatory.state.structs import LeaderRow, ModelCol
from observatory.theme import tokens as t


def _history_line(col: ModelCol) -> rx.Component:
    return rx.recharts.line(
        data_key=col.name,
        stroke=col.color,
        stroke_width=2,
        type_="monotone",
        dot=True,
    )


def history_panel() -> rx.Component:
    """Final score across runs, one line per model."""
    return glass_panel(
        panel_title("Overall Performance", "Final score per run (last 50 runs)"),
        rx.cond(
            AnalyticsState.history_data.length() > 0,
            rx.recharts.line_chart(
                rx.recharts.cartesian_grid(
                    stroke="rgba(74,222,128,0.06)", vertical=False
                ),
                rx.recharts.x_axis(data_key="run"),
                rx.recharts.y_axis(domain=[0, 100]),
                rx.foreach(AnalyticsState.history_series, _history_line),
                data=AnalyticsState.history_data,
                width="100%",
                height=300,
            ),
            rx.box(
                rx.text("No runs recorded", font_size="13px", color=t.TEXT_MUTED),
                display="flex",
                align_items="center",
                justify_content="center",
                height="300px",
            ),
        ),
        width="100%",
    )


def _leader_row(row: LeaderRow) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(
                row.rank,
                font_family=t.FONT_MONO,
                font_size="13px",
                color=t.TEXT_MUTED,
            )
        ),
        rx.table.cell(
            rx.hstack(
                rx.box(
                    width="8px", height="8px",
                    border_radius="50%", background=row.color,
                ),
                rx.text(row.name, font_size="13px", color=t.TEXT_PRIMARY),
                align="center",
                spacing="2",
            )
        ),
        rx.table.cell(
            rx.text(
                row.final_score,
                font_family=t.FONT_MONO,
                font_size="13px",
                font_weight="600",
                color=t.ACCENT,
            )
        ),
        rx.table.cell(
            rx.text(row.stars, font_size="13px", color=t.STATUS_HALF)
        ),
        rx.table.cell(
            rx.text(row.tier, font_size="13px", color=t.TEXT_SECONDARY)
        ),
        rx.table.cell(
            rx.text(
                f"{row.pass_rate}%",
                font_family=t.FONT_MONO,
                font_size="13px",
                color=t.TEXT_PRIMARY,
            )
        ),
        rx.table.cell(
            rx.text(
                row.halluc_rate,
                font_family=t.FONT_MONO,
                font_size="13px",
                color=t.TEXT_SECONDARY,
            )
        ),
        rx.table.cell(
            rx.text(
                row.tokens,
                font_family=t.FONT_MONO,
                font_size="13px",
                color=t.TEXT_SECONDARY,
            )
        ),
        rx.table.cell(
            rx.text(
                row.latency,
                font_family=t.FONT_MONO,
                font_size="13px",
                color=t.TEXT_SECONDARY,
            )
        ),
        rx.table.cell(
            rx.text(row.run_label, font_size="12px", color=t.TEXT_MUTED)
        ),
    )


def leaderboard_panel() -> rx.Component:
    """Model ranking table."""
    return glass_panel(
        rx.hstack(
            panel_title("Leaderboard", "Models ranked by final score"),
            rx.spacer(),
            rx.select(
                ["Latest run", "Best run"],
                value=AnalyticsState.rank_by,
                on_change=AnalyticsState.set_rank_by,
                size="1",
            ),
            width="100%",
            align="center",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    *[
                        rx.table.column_header_cell(
                            rx.text(
                                h,
                                font_size="11px",
                                text_transform="uppercase",
                                color=t.TEXT_MUTED,
                            )
                        )
                        for h in [
                            "#", "Model", "Score", "Tier", "Rating",
                            "Pass Rate", "Halluc.", "Tokens", "Latency", "Run",
                        ]
                    ]
                )
            ),
            rx.table.body(
                rx.foreach(AnalyticsState.leaderboard, _leader_row)
            ),
            width="100%",
        ),
        width="100%",
        margin_top="16px",
    )


@rx.page(route="/analytics", title="Analytics — Tachikoma-Observatory",
         on_load=AnalyticsState.load_analytics)
def analytics() -> rx.Component:
    """Historical trends and rankings."""
    return app_shell(
        history_panel(),
        leaderboard_panel(),
        active="/analytics",
    )
