"""Dashboard page: KPI row, scenario matrix, charts, detail panel."""

import reflex as rx

from observatory.components.charts import charts_row
from observatory.components.detail import detail_panel
from observatory.components.kpi import kpi_row
from observatory.components.matrix import scenario_matrix
from observatory.components.shell import app_shell
from observatory.state.run_state import RunState


@rx.page(route="/", title="Tachikoma-Observatory", on_load=RunState.load_dashboard)
def dashboard() -> rx.Component:
    """Main operator console."""
    return app_shell(
        rx.hstack(
            rx.vstack(
                kpi_row(),
                scenario_matrix(),
                charts_row(),
                spacing="4",
                width="100%",
            ),
            detail_panel(),
            spacing="4",
            align="start",
            width="100%",
        ),
        active="/",
    )
