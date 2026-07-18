"""Settings page state: endpoint status and model registry management."""

import reflex as rx

from observatory.config import ENV_API_KEY, ENV_BASE_URL, load_llm_config
from observatory.llm.client import LLMClient
from observatory.models import repo
from observatory.state.structs import RegistryRow


class SettingsState(rx.State):
    """Model registry and endpoint configuration."""

    registry: list[RegistryRow] = []
    endpoint_configured: bool = False
    endpoint_display: str = ""
    is_syncing: bool = False

    @rx.var
    def env_hint(self) -> str:
        """Instruction line shown when the endpoint is unconfigured."""
        return f"export {ENV_BASE_URL}=... and {ENV_API_KEY}=... then restart"

    @rx.event
    def load_settings(self):
        """Page on_load: read env status and the registry."""
        config = load_llm_config()
        self.endpoint_configured = config is not None
        self.endpoint_display = config.base_url if config else "not configured"
        self._reload_registry()

    @rx.event(background=True)
    async def sync_models(self):
        """Pull /v1/models from the proxy and upsert the registry."""
        config = load_llm_config()
        if config is None:
            yield rx.toast.error("Endpoint not configured.")
            return
        async with self:
            self.is_syncing = True
        try:
            model_ids = await LLMClient(config).list_models()
            added = repo.sync_models(model_ids)
            yield rx.toast.success(
                f"Synced {len(model_ids)} models ({added} new)."
            )
        except Exception as exc:
            yield rx.toast.error(f"Sync failed: {exc}")
        async with self:
            self.is_syncing = False
            self._reload_registry()

    @rx.event
    def toggle_model(self, entry_id: int, value: bool):
        """Enable/disable a model for "all models" runs."""
        repo.set_model_enabled(entry_id, value)
        self._reload_registry()

    def _reload_registry(self):
        """Refresh registry rows from the DB."""
        self.registry = [
            RegistryRow(
                entry_id=e.id,
                model_id=e.model_id,
                name=e.display_name,
                color=e.color,
                is_enabled=e.is_enabled,
                is_active=e.is_active,
            )
            for e in repo.list_models()
        ]
