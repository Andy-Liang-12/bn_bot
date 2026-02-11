"""Configuration settings for Battle Nations automation."""

from pathlib import Path
from dataclasses import dataclass
from typing import Dict

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

# Automation timing constants
CLICK_DELAY = 0.1
ACTION_DELAY = 0.5
BATTLE_ACTION_DELAY = 1.0
STATE_CHECK_INTERVAL = 0.5
MAX_STATE_RETRIES = 10
STUCK_DETECTION_THRESHOLD = 30.0

@dataclass
class TemplateConfig:
    """Configuration for template matching."""
    name: str
    threshold: float
    category: str
    
    @property
    def path(self) -> Path:
        return TEMPLATES_DIR / self.category / f"{self.name}.{SCREENSHOT_FORMAT}"


TEMPLATE_CONFIGS: Dict[str, TemplateConfig] = {}


def register_template(name: str, category: str, threshold: float = DEFAULT_MATCH_THRESHOLD) -> None:
    """Register a template for matching."""
    TEMPLATE_CONFIGS[name] = TemplateConfig(name, threshold, category)


def initialize_default_templates() -> None:
    """Initialize default template configurations."""
    register_template("battle_finish_okay", "battle", 0.85)
    register_template("battle_finish_victory", "battle", 0.85)
    register_template("battle_finish_defeat", "battle", 0.85)
    register_template("battle_heavy_sl_mg", "battle", 0.85)
    register_template("battle_setup_fight", "battle", 0.85)
    register_template("battle_sp_ok", "battle", 0.85)
    register_template("wild_boar", "battle", 0.85)
    register_template("battle_opp_tile2", "battle", 0.85)
    register_template("battle_pass", "battle", 0.85)


initialize_default_templates()