"""Configuration settings for Battle Nations automation."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
LOGS_DIR = PROJECT_ROOT / "logs"

WINDOW_NAME = "Battle Nations"

DEFAULT_MATCH_THRESHOLD = 0.8
MIN_MATCH_THRESHOLD = 0.6
MAX_MATCH_THRESHOLD = 0.95

SCREENSHOT_FORMAT = "png"
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

CLICK_DELAY = 0.07 # Time (s) to hold mouse down for a click
SHORT_DELAY = 0.2
LONG_DELAY = 0.4
STATE_CHECK_INTERVAL = 0.2
MAX_STATE_RETRIES = 10
STUCK_DETECTION_THRESHOLD = 20.0

TEMPLATES = {
    # Battle setup and flow
    "fight_button": {"category": "battle", "threshold": 0.92},
    "finish_ok": {"category": "battle", "threshold": 0.92},
    # no reason to search for victory, assume defeat is impossible
    # "victory": {"category": "battle", "threshold": 0.85},
    # "defeat": {"category": "battle", "threshold": 0.85},
    "sp_ok": {"category": "battle", "threshold": 0.92},
    "opp_tile": {"category": "battle", "threshold": 0.92},
    "pass_active": {"category": "battle", "threshold": 0.92},
    "pass_inactive_gantas": {"category": "battle", "threshold": 0.92},
    "pass_inactive_sarin": {"category": "battle", "threshold": 0.92},

    # Troops
    "heavy": {"category": "troops", "threshold": 0.90},
    "soldier": {"category": "troops", "threshold": 0.88},
    "tk": {"category": "troops", "threshold": 0.88},
    "heavy_tank": {"category": "troops", "threshold": 0.90},
    "wimp": {"category": "troops", "threshold": 0.95},
    # "field_agent": {"category": "troops", "threshold": 0.85},

    # Enemies
    "mammoth": {"category": "enemies", "threshold": 0.85},
    "wild_boar": {"category": "enemies", "threshold": 0.85},
    "dustwalker1": {"category": "enemies", "threshold": 0.85},
    "firebreather": {"category": "enemies", "threshold": 0.85},
    "raider_warrior": {"category": "enemies", "threshold": 0.85},
    "boom_boom": {"category": "enemies", "threshold": 0.85},
    "raider_canoneer": {"category": "enemies", "threshold": 0.85},
}


def get_template_path(name: str) -> Path:
    """Get the file path for a template."""
    if name not in TEMPLATES:
        raise KeyError(f"Unknown template: {name}")
    category = TEMPLATES[name]["category"]
    return TEMPLATES_DIR / category / f"{name}.{SCREENSHOT_FORMAT}"


def get_template_threshold(name: str) -> float:
    """Get the matching threshold for a template."""
    if name not in TEMPLATES:
        raise KeyError(f"Unknown template: {name}")
    return TEMPLATES[name]["threshold"]
