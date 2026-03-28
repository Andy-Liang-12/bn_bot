"""Reactive State Machine for Battle Nations automation"""

import logging
import time
import json
import sys
import os
from dotenv import load_dotenv
from enum import Enum, auto
from typing import Optional, Tuple, Dict, Any, List

import pyautogui
import numpy as np
from pynput import keyboard

from config import (
    STATE_CHECK_INTERVAL, SHORT_DELAY, 
    LONG_DELAY, STUCK_DETECTION_THRESHOLD
)
from window_capture import WindowCapture
from template_matcher import TemplateMatcher, MatchResult

# Constants
EXIT_KEY = keyboard.Key.esc
PAUSE_KEY = 'p'
UNPAUSE_KEY = 'u'

def setup_logging():
    # 1. Load settings (Assumes load_dotenv() was called before this!)
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_to_console = os.getenv("LOG_TO_CONSOLE", "True").lower() == "true"
    log_to_file = os.getenv("LOG_TO_FILE", "False").lower() == "true"
    log_file_path = os.getenv("LOG_FILE_PATH", "logs/state_machine.log")
    
    level = getattr(logging, log_level_str, logging.INFO)
    handlers = []
    
    # 2. Add Console Handler
    if log_to_console:
        handlers.append(logging.StreamHandler(sys.stdout))
        
    # 3. Handle File Logging Logic
    if log_to_file:
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):
            # No logger.info here yet because logging isn't configured!
            os.makedirs(log_dir)
            
        handlers.append(logging.FileHandler(log_file_path))

    # 4. Final configuration
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

logger = logging.getLogger(__name__)

class BattleState(Enum):
    """Possible states for the battle FSM."""
    UNKNOWN = auto()
    PRE_BATTLE = auto()     # Deployment/Fight button visible
    SCANNING = auto()       # Waiting for turn / UI settling
    EXECUTE_MOVE = auto()   # Turn started, can act
    ANIMATING = auto()      # Busy, no UI or high variance
    POST_BATTLE = auto()    # Victory/Defeat screen

class BattleStateMachine:
    """Orchestrates the battle loop using efficient visual feedback."""
    
    def __init__(self):
        self.window_capture = WindowCapture()
        self.matcher = TemplateMatcher()
        self.state = BattleState.UNKNOWN
        self.last_state_change = time.time()
        self.start_time = time.time()
        self.running = False
        self.paused = False
        self.run_count = 0
        
        # Determine mission config path from environment or default
        mission_config = os.getenv("MISSION_CONFIG")
        if mission_config is None:
            logger.warning("MISSION_CONFIG not found in .env file.")
            sys.exit(1)
        
        mission_config_path = os.path.join("battle_configs", f"{mission_config}.json")
        # Configuration
        self.mission_config = self._load_config(mission_config_path)
        self.troop_data = self._load_config("troops.json")
        self.rewards_config = self.mission_config.get("rewards", {})
        self.pass_button_type = self.mission_config.get("pass_button")

        logger.debug(f"Mission Config Loaded: {self.mission_config.get('mission_name', 'Missing')}")
        logger.debug(f"Troop Data Loaded: {len(self.troop_data)} units")
        logger.debug(f"Pass Button Type: {self.pass_button_type}")

        if not self.mission_config or not self.troop_data or not self.pass_button_type:
            logger.warning("Config values are missing. Check config name and contents.")
            sys.exit(1)
        
        # Pre-load and validate priority lists
        self.troop_prio = self.mission_config.get("troop_priority", [])
        self.enemy_prio = self.mission_config.get("enemy_priority", [])
        self.skill_prio = self.mission_config.get("skill_priorities", {})
        
        if not self.troop_prio or not self.enemy_prio or not self.skill_prio:
            logger.warning("WARNING: priority lists are empty!")
            sys.exit(1)
        
        # State Tracking
        self.deployed_troops = []  # List of dicts: {"name", "pos", "cooldowns", "has_acted"}
        self.troops_discovered = False
        self.was_animating = False # Used to detect turn transitions
        self.pending_action = None # Used to confirm cooldowns only after animation starts
        
        # Performance Optimizations
        self.ui_roi_cache = {}    # Stores (x, y, w, h) for static buttons
        self.roi_padding = 20     # Padding factor for search boxes
        
        logger.info(f"Initialized State Machine with mission: {self.mission_config.get('mission_name')}")

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load a JSON configuration file."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config {path}: {e}")
            return {}

    def on_press(self, key):
        """Handle key press events to stop or pause the state machine."""
        if key == EXIT_KEY:
            logger.info("Exit key pressed. Stopping state machine...")
            self.running = False
            return False
        
        elif hasattr(key, 'char') and key.char:
            char = key.char.lower()

            if char == PAUSE_KEY and not self.paused:
                self.paused = True
                logger.info("Bot PAUSED. Press 'u' to resume.")
                print("\n!! Bot PAUSED. Press 'u' to resume.")
            elif char == UNPAUSE_KEY and self.paused:
                self.paused = False
                logger.info("Bot RESUMED.")
                print("\n>> Bot RESUMED.")

    def _check_cached_roi(self, screenshot: np.ndarray, name: str) -> Optional[MatchResult]:
        """Attempt a fast match using only the cached ROI."""
        roi = self.ui_roi_cache.get(name)
        if roi:
            return self.matcher.match_template(screenshot, name, roi=roi)
        return None

    def _full_scan_and_cache(self, screenshot: np.ndarray, name: str) -> Optional[MatchResult]:
        """Perform a full-screen scan and cache the location if found."""
        match = self.matcher.match_template(screenshot, name, roi=None)
        if match:
            mx, my = match.location
            mw, mh = match.size
            sh, sw = screenshot.shape[:2]
            rx = max(0, mx - self.roi_padding)
            ry = max(0, my - self.roi_padding)
            rw = min(mw + 2 * self.roi_padding, sw - rx)
            rh = min(mh + 2 * self.roi_padding, sh - ry)
            self.ui_roi_cache[name] = (rx, ry, rw, rh)
            logger.debug(f"Cached ROI for {name} at {self.ui_roi_cache[name]}")
        return match

    def determine_state(self, screenshot: np.ndarray) -> Tuple[BattleState, Optional[MatchResult]]:
        """Identify state by prioritizing overlays over backgrounds to prevent shadowing."""
        
        overlays = [
            ("finish_ok", BattleState.POST_BATTLE),
            ("sp_ok", BattleState.POST_BATTLE),
            ("fight_button", BattleState.PRE_BATTLE)
        ]
        
        backgrounds = [
            ("pass_active", BattleState.EXECUTE_MOVE),
            (self.pass_button_type, BattleState.ANIMATING)
        ]

        # 1. Check Overlays First
        for name, state in overlays:
            if name in self.ui_roi_cache:
                match = self._check_cached_roi(screenshot, name)
            else:
                match = self._full_scan_and_cache(screenshot, name)
            
            if match:
                return state, match

        # 2. Check Backgrounds
        for name, state in backgrounds:
            if name in self.ui_roi_cache:
                match = self._check_cached_roi(screenshot, name)
            else:
                match = self._full_scan_and_cache(screenshot, name)
                
            if match:
                return state, match

        logger.debug("Nothing found.")
        return BattleState.UNKNOWN, None

    def click_coords(self, coords: Tuple[int, int], name: str = "Coordinate"):
        """Execute a resilient click on absolute coordinates relative to the window."""
        region = self.window_capture.get_window_region()
        if not region: return
        
        left, top, _, _ = region
        x, y = coords
        screen_x, screen_y = left + x, top + y
        
        logger.debug(f"Clicking {name} at ({screen_x}, {screen_y})")
        pyautogui.moveTo(screen_x, screen_y, duration=0.1)
        pyautogui.mouseDown()
        time.sleep(0.1) 
        pyautogui.mouseUp()

    def click_match(self, match: MatchResult):
        """Wrapper for click_coords using a MatchResult."""
        self.click_coords(match.center, match.name)

    def _discover_troops(self, screenshot: np.ndarray):
        """Scan board once to identify friendly unit positions."""
        logger.info(f"Discovery Phase: Scanning for {self.troop_prio}...")
        matches = self.matcher.match_whitelist(screenshot, self.troop_prio, multiple=True)
        
        self.deployed_troops = []
        for m in matches:
            logger.debug(f"Discovered [{m.name}] at {m.center} with confidence {m.confidence:.2f}")
            self.deployed_troops.append({
                "name": m.name,
                "pos": m.center,
                "cooldowns": {"1": 0, "2": 0, "3": 0},
                "has_acted": False
            })
        if not self.deployed_troops:
            logger.info("Discovery failed: No troops from the whitelist were found on screen.")
        else:
            logger.info(f"Discovered {len(self.deployed_troops)} troops.")
        self.troops_discovered = True

    def _reset_battle_state(self):
        """Reset temporary battle variables for a new encounter."""
        logger.debug("--- Resetting battle state for new encounter ---")
        self.pending_action = None
        self.was_animating = False
        for troop in self.deployed_troops:
            troop["has_acted"] = False
            for skill_id in troop["cooldowns"]:
                troop["cooldowns"][skill_id] = 0

    def _on_turn_start(self):
        """Reset troop 'has_acted' flags and decrement cooldowns."""
        logger.debug("--- New Player Turn Started ---")
        for troop in self.deployed_troops:
            troop["has_acted"] = False
            for skill_id in list(troop["cooldowns"].keys()):
                if troop["cooldowns"][skill_id] > 0:
                    troop["cooldowns"][skill_id] -= 1
                    logger.debug(f"  [{troop['name']}] Skill {skill_id} CD reduced to {troop['cooldowns'][skill_id]}")

    def shoot(self, troop_dict: Dict, enemy: MatchResult, skill_id: str):
        """Execute attack and prepare for cooldown confirmation."""
        logger.debug(f"ACT: {troop_dict['name']} (Skill {skill_id}) -> {enemy.name}")
        
        # 1. Execute clicks
        self.click_coords(troop_dict["pos"], troop_dict["name"])
        time.sleep(SHORT_DELAY)
        # (Assuming skill selection logic will go here once templates are available)
        self.click_match(enemy)
        
        # 2. Mark as acted
        troop_dict["has_acted"] = True
        
        # 3. Prepare Pending Action (Confirm CD only if we see ANIMATING)
        unit_data = self.troop_data.get(troop_dict["name"], {})
        base_cd = unit_data.get("skills", {}).get(skill_id, {}).get("cooldown", 0)
        
        if base_cd > 0:
            self.pending_action = {
                "troop": troop_dict,
                "skill_id": skill_id,
                "base_cd": base_cd
            }
            logger.debug(f"  Action pending confirmation for {troop_dict['name']}")
            
        time.sleep(LONG_DELAY)

    def step(self):
        """Main Observe-Think-Act iteration."""
        if self.paused:
            return

        try:
            screenshot = self.window_capture.capture()
            if screenshot is None: return

            new_state, match = self.determine_state(screenshot)
            
            # State Transition Logging
            if new_state != self.state:
                match_name = match.name if match else "None"
                roi_tag = " (ROI used)" if match and match.roi_used else ""
                logger.info(f"State: {self.state.name} -> {new_state.name} (Trigger: {match_name}{roi_tag})")
                
                # Reset state when a new battle is detected
                if new_state == BattleState.PRE_BATTLE:
                    self._reset_battle_state()

                # Confirm Pending Action if we enter ANIMATING
                if new_state == BattleState.ANIMATING and self.pending_action:
                    troop = self.pending_action["troop"]
                    skill_id = self.pending_action["skill_id"]
                    base_cd = self.pending_action["base_cd"]
                    
                    troop["cooldowns"][skill_id] = base_cd
                    logger.debug(f"  CONFIRMED: {troop['name']} Skill {skill_id} CD set to {base_cd}")
                    self.pending_action = None

                # Turn Start Detection: Transitioning from Animating (Enemy) back to Move (Player)
                if new_state == BattleState.EXECUTE_MOVE and self.was_animating:
                    self._on_turn_start()
                
                self.was_animating = (new_state == BattleState.ANIMATING)
                self.state = new_state
                self.last_state_change = time.time()

            # Execute behavior
            if self.state == BattleState.PRE_BATTLE and match:
                self.click_match(match)
                time.sleep(SHORT_DELAY)

            elif self.state == BattleState.EXECUTE_MOVE and match:
                # prevent race conditions if lag, do nothing while waiting for a previous attack to register
                # commenting this out, hangs the program sometimes
                # if self.pending_action is not None:
                #     logger.debug("pending action + execute_move pass")
                #     return

                # 1. Discover troops if needed
                if not self.troops_discovered:
                    self._discover_troops(screenshot)
                    self._on_turn_start() # Initialize flags for Turn 1

                # 2. Identify Enemies
                # enemies = self.matcher.match_category(screenshot, "enemies")
                enemies = self.matcher.match_whitelist(
                    screenshot, 
                    self.enemy_prio, 
                    multiple=True
                )
                
                if enemies:
                    logger.debug(f"Detected Enemies: {', '.join([e.name for e in enemies])}")

                # 3. Find first ready troop that hasn't acted (using pre-loaded priority)
                best_enemy = self._get_priority_match(enemies, self.enemy_prio)

                if best_enemy:
                    # Sort troops by pre-loaded priority list
                    def get_prio(troops):
                        try: return self.troop_prio.index(troops["name"])
                        except ValueError: return 999
                        
                    prioritized_troops = sorted(self.deployed_troops, key=get_prio)

                    for troop in prioritized_troops:
                        if not troop["has_acted"]:
                            # Check preferred skill using pre-loaded priority
                            prio_skills = self.skill_prio.get(troop["name"], ["1"])
                            skill_id = str(prio_skills[0])
                            
                            if troop["cooldowns"].get(skill_id, 0) == 0:
                                self.shoot(troop, best_enemy, skill_id)
                                return # Finish step to allow state to settle
                            else:
                                logger.debug(f"[{troop['name']}] Skill {skill_id} on cooldown, skipping...")
                                troop["has_acted"] = True # Skip for this turn
                    
                    # If we reach here, all troops are exhausted
                    logger.debug("All troops exhausted. Passing turn.")
                    self.click_match(match)
                    time.sleep(SHORT_DELAY)
                else:
                    logger.debug("No enemies found. Shouldn't get here")

            elif self.state == BattleState.POST_BATTLE and match:
                if match.name in ["finish_ok", "sp_ok"]:
                    # Two buttons to click in the same place. No need to template match both
                    self.click_match(match)
                    time.sleep(0.1)
                    self.click_match(match)
                    
                    # Increment run count
                    self.run_count += 1
                    logger.info(f"Battle #{self.run_count} completed.")
                    
                    time.sleep(SHORT_DELAY)

            else:
                if self.state == BattleState.ANIMATING:
                    logger.debug("Currently animating... waiting for state change.")
                else:
                    logger.info("No matching template found.")
                time.sleep(SHORT_DELAY)

        except Exception as e:
            logger.error(f"Error in state machine step: {e}")
            time.sleep(1)

    def _print_summary(self):
        """Print a summary of the session gains and duration."""
        duration = time.time() - self.start_time
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        print("\n" + "=" * 60)
        print("BATTLE SUMMARY")
        print("=" * 60)
        print(f"Total Runs: {self.run_count}")
        print(f"Elapsed Time: {hours:02d}:{minutes:02d}:{seconds:02d}")
        print("-" * 60)
        
        if self.rewards_config:
            print("Total Rewards Gained:")
            for resource, amount in self.rewards_config.items():
                total = amount * self.run_count
                print(f"  • {resource.capitalize()}: {total:,}")
        else:
            print("No rewards configured for this mission.")
            
        print("=" * 60 + "\n")

    def _get_priority_match(self, matches: List[MatchResult], priority_list: List[str]) -> Optional[MatchResult]:
        for p_name in priority_list:
            for m in matches:
                if m.name == p_name: #  or m.name.startswith(p_name)
                    return m
        return None

    def run(self):
        if not self.window_capture.find_window(): return
        self.running = True
        logger.info("Battle State Machine Active. Press [ESC] to stop.")
        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()
        try:
            while self.running:
                self.step()
                time.sleep(STATE_CHECK_INTERVAL)
        finally:
            self.running = False
            listener.stop()
            self._print_summary()

if __name__ == "__main__":
    load_dotenv(override=True)
    setup_logging()
    BattleStateMachine().run()
