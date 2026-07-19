"""Settings page: endpoint status and model registry."""

import reflex as rx

from observatory.components.panels import glass_panel, panel_title
from observatory.components.shell import app_shell
from observatory.state.settings_state import SettingsState
from observatory.state.structs import RegistryRow
from observatory.theme import tokens as t


def endpoint_panel() -> rx.Component:
    """LiteLLM endpoint status."""
    return glass_panel(
        panel_title("LLM Endpoint", "LiteLLM proxy (OpenAI-compatible)"),
        rx.hstack(
            rx.box(
                width="8px",
                height="8px",
                border_radius="50%",
                background=rx.cond(
                    SettingsState.endpoint_configured, t.ACCENT, t.STATUS_FAIL
                ),
            ),
            rx.text(
                SettingsState.endpoint_display,
                font_family=t.FONT_MONO,
                font_size="13px",
                color=t.TEXT_PRIMARY,
            ),
            align="center",
            spacing="2",
            margin_top="10px",
        ),
        rx.cond(
            ~SettingsState.endpoint_configured,
            rx.text(
                SettingsState.env_hint,
                font_family=t.FONT_MONO,
                font_size="12px",
                color=t.STATUS_HALF,
                margin_top="8px",
            ),
            rx.fragment(),
        ),
        width="100%",
    )


def _registry_row(row: RegistryRow) -> rx.Component:
    return rx.table.row(
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
                row.model_id,
                font_family=t.FONT_MONO,
                font_size="12px",
                color=t.TEXT_SECONDARY,
            )
        ),
        rx.table.cell(
            rx.cond(
                row.is_active,
                rx.text("active", font_size="12px", color=t.ACCENT),
                rx.text("inactive", font_size="12px", color=t.TEXT_MUTED),
            )
        ),
        rx.table.cell(
            rx.switch(
                checked=row.is_enabled,
                on_change=lambda value: SettingsState.toggle_model(
                    row.entry_id, value
                ),
            )
        ),
        rx.table.cell(
            rx.tooltip(
                rx.select(
                    ["none", "vllm", "groq"],
                    value=row.no_think,
                    on_change=lambda value: SettingsState.set_no_think(
                        row.entry_id, value
                    ),
                    size="1",
                ),
                content=(
                    "Reasoning suppression sent with every request: "
                    "vllm = chat_template_kwargs.enable_thinking=false, "
                    "groq = reasoning_effort=none, "
                    "none = endpoint already configured server-side"
                ),
            )
        ),
        rx.table.cell(_delete_dialog(row)),
    )


def _delete_dialog(row: RegistryRow) -> rx.Component:
    """Trash button with a confirmation dialog."""
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            rx.icon_button(
                rx.icon("trash_2", size=14),
                background="transparent",
                border=f"1px solid {t.BORDER_SOFT}",
                color=t.STATUS_FAIL,
                cursor="pointer",
                _hover={"background": "rgba(248,113,113,0.1)"},
            )
        ),
        rx.alert_dialog.content(
            rx.alert_dialog.title(f"Delete {row.name}?"),
            rx.alert_dialog.description(
                "This removes the model and its entire benchmark history: "
                "matrix column, traces, and analytics contributions. "
                "This cannot be undone."
            ),
            rx.flex(
                rx.alert_dialog.cancel(rx.button("Cancel", variant="soft")),
                rx.alert_dialog.action(
                    rx.button(
                        "Delete",
                        color_scheme="red",
                        on_click=SettingsState.delete_model(row.entry_id),
                    )
                ),
                spacing="3",
                justify="end",
                margin_top="16px",
            ),
        ),
    )


def registry_panel() -> rx.Component:
    """Model registry with sync and enable toggles."""
    return glass_panel(
        rx.hstack(
            panel_title(
                "Model Registry",
                "Enabled models participate in benchmark runs",
            ),
            rx.spacer(),
            rx.button(
                rx.icon("refresh_cw", size=14),
                "Sync from endpoint",
                on_click=SettingsState.sync_models,
                loading=SettingsState.is_syncing,
                background="transparent",
                border=f"1px solid {t.ACCENT}",
                color=t.ACCENT,
                border_radius=t.RADIUS_CONTROL,
                cursor="pointer",
                _hover={"background": t.SURFACE_3},
            ),
            width="100%",
            align="center",
        ),
        rx.cond(
            SettingsState.registry.length() > 0,
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
                            "Model", "ID", "Status", "Enabled", "No-Think", "",
                        ]
                        ]
                    )
                ),
                rx.table.body(
                    rx.foreach(SettingsState.registry, _registry_row)
                ),
                width="100%",
            ),
            rx.text(
                "No models registered. Sync from the endpoint to get started.",
                font_size="13px",
                color=t.TEXT_MUTED,
                margin_top="12px",
            ),
        ),
        width="100%",
        margin_top="16px",
    )


@rx.page(route="/settings", title="Settings — Tachikoma-Observatory",
         on_load=SettingsState.load_settings)
def settings() -> rx.Component:
    """Endpoint and registry management."""
    return app_shell(
        endpoint_panel(),
        registry_panel(),
        active="/settings",
    )
