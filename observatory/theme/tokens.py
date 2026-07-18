"""Design tokens from DESIGN.md section 2. Single source for all styling."""

BG_VOID = "#050807"
BG_VOID_GLOW = (
    "radial-gradient(1200px at 85% 0%, rgba(52,211,153,0.07), transparent 60%)"
)
SURFACE_1 = "rgba(13, 20, 16, 0.72)"
SURFACE_2 = "rgba(20, 30, 23, 0.85)"
SURFACE_3 = "rgba(30, 44, 34, 0.9)"
BORDER_SOFT = "rgba(74, 222, 128, 0.12)"
BORDER_STRONG = "rgba(74, 222, 128, 0.35)"
GLASS_BLUR = "blur(14px)"

ACCENT = "#4ADE80"
ACCENT_BRIGHT = "#86FCB1"
ACCENT_DIM = "#166534"
ACCENT_GLOW = "0 0 12px rgba(74,222,128,0.45)"

STATUS_PASS = "#4ADE80"
STATUS_HALF = "#F59E0B"
STATUS_FAIL = "#F87171"
STATUS_PENDING = "#3D4A41"

TEXT_PRIMARY = "#E8F5EC"
TEXT_SECONDARY = "#9DB4A4"
TEXT_MUTED = "#5C7264"

MODEL_PALETTE = [
    "#4ADE80",
    "#38BDF8",
    "#F87171",
    "#FBBF24",
    "#A78BFA",
    "#F472B6",
    "#2DD4BF",
    "#FB923C",
]

ERROR_COLORS = {
    "invalid_tool": "#38BDF8",
    "wrong_parameter": "#4ADE80",
    "hallucinated_tool": "#F87171",
    "json_format_error": "#FBBF24",
    "other": "#A78BFA",
}

FONT_DISPLAY = "'Chakra Petch', sans-serif"
FONT_BODY = "'Inter', sans-serif"
FONT_MONO = "'JetBrains Mono', monospace"

RADIUS_PANEL = "12px"
RADIUS_CONTROL = "8px"
RADIUS_BADGE = "6px"

FONTS_STYLESHEET = (
    "https://fonts.googleapis.com/css2"
    "?family=Chakra+Petch:wght@600;700"
    "&family=Inter:wght@400;500;600"
    "&family=JetBrains+Mono:wght@400;600"
    "&display=swap"
)

GLASS_PANEL = {
    "background": SURFACE_1,
    "border": f"1px solid {BORDER_SOFT}",
    "border_radius": RADIUS_PANEL,
    "backdrop_filter": GLASS_BLUR,
    "box_shadow": "inset 0 1px 0 rgba(255,255,255,0.04)",
}

CAPTION = {
    "font_family": FONT_BODY,
    "font_size": "11px",
    "text_transform": "uppercase",
    "letter_spacing": "0.08em",
    "color": TEXT_MUTED,
}


def model_color(index: int) -> str:
    """Chart color for a model by registration order.

    Args:
        index: Zero-based model position.

    Returns:
        Hex color from the palette, cycling.
    """
    return MODEL_PALETTE[index % len(MODEL_PALETTE)]
