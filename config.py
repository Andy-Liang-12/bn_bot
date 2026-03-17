"""Configuration settings for Battle Nations automation."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
LOGS_DIR = PROJECT_ROOT / "logs"

CAPTURE_KEY = 's'
TEST_KEY = 't'
EXIT_KEY = 'esc'

WINDOW_NAME = "Battle Nations"

DEFAULT_MATCH_THRESHOLD = 0.8
MIN_MATCH_THRESHOLD = 0.6
MAX_MATCH_THRESHOLD = 0.95

SCREENSHOT_FORMAT = "png"
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

CLICK_DELAY = 0.1
ACTION_DELAY = 0.5
BATTLE_ACTION_DELAY = 1.0
STATE_CHECK_INTERVAL = 0.5
MAX_STATE_RETRIES = 10
STUCK_DETECTION_THRESHOLD = 30.0

TEMPLATES = {
    # Battle setup and flow
    "fight_button": {"category": "battle", "threshold": 0.85},
    "finish_ok": {"category": "battle", "threshold": 0.85},
    "victory": {"category": "battle", "threshold": 0.85},
    "defeat": {"category": "battle", "threshold": 0.85},
    "sp_ok": {"category": "battle", "threshold": 0.85},
    "opp_tile": {"category": "battle", "threshold": 0.85},
    "pass_button": {"category": "battle", "threshold": 0.85},

    # Troops
    "heavy_sl": {"category": "troops", "threshold": 0.85},

    # Enemies
    "mammoth": {"category": "enemies", "threshold": 0.85},
    "wild_boar": {"category": "enemies", "threshold": 0.85},
    "dustwalker": {"category": "enemies", "threshold": 0.85},
    "dustwalker2": {"category": "enemies", "threshold": 0.85},
    "dustwalker3": {"category": "enemies", "threshold": 0.85},
    "firebreather": {"category": "enemies", "threshold": 0.85},
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