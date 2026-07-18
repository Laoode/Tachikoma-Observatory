"""App entry: theme, global styles, table creation, page registration."""

import reflex as rx
from reflex.model import get_engine
from sqlmodel import SQLModel

from observatory.pages import analytics, dashboard, scenarios, settings  # noqa: F401
from observatory.theme import tokens as t

GLOBAL_STYLE = {
    "background": t.BG_VOID,
    "font_family": t.FONT_BODY,
    "color": t.TEXT_PRIMARY,
    "@keyframes pulse": {
        "0%, 100%": {"opacity": "1"},
        "50%": {"opacity": "0.4"},
    },
    "@keyframes spin": {
        "from": {"transform": "rotate(0deg)"},
        "to": {"transform": "rotate(360deg)"},
    },
}


def _create_tables() -> None:
    """Create missing tables (idempotent; SQLite-only, PRD section 5)."""
    SQLModel.metadata.create_all(get_engine())


_create_tables()

app = rx.App(
    style=GLOBAL_STYLE,
    stylesheets=[t.FONTS_STYLESHEET],
    theme=rx.theme(appearance="dark", accent_color="green"),
)
