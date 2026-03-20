"""Reactive State Machine for Battle Nations automation"""

import logging
import time
import json
import sys
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
    
    def __init__(self, mission_config_path: str = "mission_config.json"):
        self.window_capture = WindowCapture()
        self.matcher = TemplateMatcher()
        self.state = BattleState.UNKNOWN
        self.last_state_change = time.time()
        self.running = False
        
        # Configuration
        self.mission_config = self._load_config(mission_config_path)
        self.troop_data = self._load_config("troops.json")
        
        # State Tracking
        self.deployed_troops = []  # List of dicts: {"name", "pos", "cooldowns", "has_acted"}
        self.troops_discovered = False
        self.was_animating = False # Used to detect turn transitions
        self.pending_action = None # Used to confirm cooldowns only after animation starts
        
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
        """Handle key press events to stop the state machine."""
        if key == EXIT_KEY:
            logger.info("Exit key pressed. Stopping state machine...")
            self.running = False
            return False

    def determine_state(self, screenshot: np.ndarray) -> Tuple[BattleState, Optional[MatchResult]]:
        """Identify state and the match that triggered it."""
                    
        match = self.matcher.match_template(screenshot, "pass_active")
        if match:
            return BattleState.EXECUTE_MOVE, match
            
        for btn_name in ["finish_ok", "sp_ok"]:
            match = self.matcher.match_template(screenshot, btn_name)
            if match:
                return BattleState.POST_BATTLE, match
            
        match = self.matcher.match_template(screenshot, "fight_button")
        if match:
            return BattleState.PRE_BATTLE, match

        match = self.matcher.match_template(screenshot, "pass_inactive_gantas")
        if match:
            return BattleState.ANIMATING, match

        return BattleState.UNKNOWN, None

    def click_coords(self, coords: Tuple[int, int], name: str = "Coordinate"):
        """Execute a resilient click on absolute coordinates relative to the window."""
        region = self.window_capture.get_window_region()
        if not region: return
        
        left, top, _, _ = region
        x, y = coords
        screen_x, screen_y = left + x, top + y
        
        logger.info(f"Clicking {name} at ({screen_x}, {screen_y})")
        pyautogui.moveTo(screen_x, screen_y, duration=0.1)
        pyautogui.mouseDown()
        time.sleep(0.1) 
        pyautogui.mouseUp()

    def click_match(self, match: MatchResult):
        """Wrapper for click_coords using a MatchResult."""
        self.click_coords(match.center, match.name)

    def _discover_troops(self, screenshot: np.ndarray):
        """Scan board once to identify friendly unit positions."""
        logger.info("Discovery Phase: Scanning for friendly units...")
        matches = self.matcher.match_category(screenshot, "troops")
        
        self.deployed_troops = []
        for m in matches:
            logger.info(f"Discovered [{m.name}] at {m.center}")
            self.deployed_troops.append({
                "name": m.name,
                "pos": m.center,
                "cooldowns": {"1": 0, "2": 0, "3": 0},
                "has_acted": False
            })
        self.troops_discovered = True

    def _reset_battle_state(self):
        """Reset temporary battle variables for a new encounter."""
        logger.info("--- Resetting battle state for new encounter ---")
        self.pending_action = None
        self.was_animating = False
        for troop in self.deployed_troops:
            troop["has_acted"] = False
            for skill_id in troop["cooldowns"]:
                troop["cooldowns"][skill_id] = 0

    def _on_turn_start(self):
        """Reset troop 'has_acted' flags and decrement cooldowns."""
        logger.info("--- New Player Turn Started ---")
        for troop in self.deployed_troops:
            troop["has_acted"] = False
            for skill_id in list(troop["cooldowns"].keys()):
                if troop["cooldowns"][skill_id] > 0:
                    troop["cooldowns"][skill_id] -= 1
                    logger.info(f"  [{troop['name']}] Skill {skill_id} CD reduced to {troop['cooldowns'][skill_id]}")

    def shoot(self, troop_dict: Dict, enemy: MatchResult, skill_id: str):
        """Execute attack and prepare for cooldown confirmation."""
        logger.info(f"ACT: {troop_dict['name']} (Skill {skill_id}) -> {enemy.name}")
        
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
            logger.info(f"  Action pending confirmation for {troop_dict['name']}")
            
        time.sleep(LONG_DELAY)

    def step(self):
        """Main Observe-Think-Act iteration."""
        try:
            screenshot = self.window_capture.capture()
            if screenshot is None: return

            new_state, match = self.determine_state(screenshot)
            
            # State Transition Logging
            if new_state != self.state:
                match_name = match.name if match else "None"
                logger.info(f"State: {self.state.name} -> {new_state.name} (Trigger: {match_name})")
                
                # Reset state when a new battle is detected
                if new_state == BattleState.PRE_BATTLE:
                    self._reset_battle_state()

                # Confirm Pending Action if we enter ANIMATING
                if new_state == BattleState.ANIMATING and self.pending_action:
                    troop = self.pending_action["troop"]
                    skill_id = self.pending_action["skill_id"]
                    base_cd = self.pending_action["base_cd"]
                    
                    troop["cooldowns"][skill_id] = base_cd
                    logger.info(f"  CONFIRMED: {troop['name']} Skill {skill_id} CD set to {base_cd}")
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

            elif self.state == BattleState.EXECUTE_MOVE:
                # 1. Discover troops if needed
                if not self.troops_discovered:
                    self._discover_troops(screenshot)
                    self._on_turn_start() # Initialize flags for Turn 1

                # 2. Identify Enemies
                enemies = self.matcher.match_category(screenshot, "enemies")
                if enemies:
                    logger.debug(f"Detected Enemies: {', '.join([e.name for e in enemies])}")

                # 3. Find first ready troop that hasn't acted
                enemy_prio = self.mission_config.get("enemy_priority", [])
                best_enemy = self._get_priority_match(enemies, enemy_prio)

                if best_enemy:
                    for troop in self.deployed_troops:
                        if not troop["has_acted"]:
                            # Check preferred skill (currently first in priority list)
                            prio_skills = self.mission_config.get("skill_priorities", {}).get(troop["name"], ["1"])
                            skill_id = str(prio_skills[0])
                            
                            if troop["cooldowns"].get(skill_id, 0) == 0:
                                self.shoot(troop, best_enemy, skill_id)
                                return # Finish step to allow state to settle
                            else:
                                logger.debug(f"[{troop['name']}] Skill {skill_id} on cooldown, skipping...")
                                troop["has_acted"] = True # Skip for this turn

            elif self.state == BattleState.POST_BATTLE and match:
                if match.name in ["finish_ok", "sp_ok"]:
                    # Two buttons to click in the same place. No need to template match both
                    self.click_match(match)
                    time.sleep(0.1)
                    self.click_match(match)
                    time.sleep(SHORT_DELAY)

        except Exception as e:
            logger.error(f"Error in state machine step: {e}")
            time.sleep(1)

    def _get_priority_match(self, matches: List[MatchResult], priority_list: List[str]) -> Optional[MatchResult]:
        for p_name in priority_list:
            for m in matches:
                if m.name == p_name or m.name.startswith(p_name):
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

if __name__ == "__main__":
    from config import LOGS_DIR
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.FileHandler(LOGS_DIR / 'state_machine.log'), logging.StreamHandler(sys.stdout)])
    BattleStateMachine().run()
