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
    STATE_CHECK_INTERVAL, ACTION_DELAY, 
    BATTLE_ACTION_DELAY, STUCK_DETECTION_THRESHOLD
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
        
        self.mission_config = self._load_config(mission_config_path)
        logger.info(f"Initialized State Machine with mission: {self.mission_config.get('mission_name')}")

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load the mission configuration."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load mission config: {e}")
            return {"troop_priority": [], "enemy_priority": []}

    def on_press(self, key):
        """Handle key press events to stop the state machine."""
        if key == EXIT_KEY:
            logger.info("Exit key pressed. Stopping state machine...")
            self.running = False
            return False  # Stop listener

    def determine_state(self, screenshot: np.ndarray) -> Tuple[BattleState, Optional[MatchResult]]:
        """Identify state and the match that triggered it to avoid redundant matching."""
        
        # 1. Post-Battle Sequence (Priority to buttons)
        for btn_name in ["finish_ok", "sp_ok", "victory", "defeat"]:
            match = self.matcher.match_template(screenshot, btn_name)
            if match:
                return BattleState.POST_BATTLE, match
            
        # 2. Pre-Battle
        match = self.matcher.match_template(screenshot, "fight_button")
        if match:
            return BattleState.PRE_BATTLE, match
            
        # 3. In-Battle (Player Turn)
        match = self.matcher.match_template(screenshot, "pass_active")
        if match:
            # If pass_active is visible, we can act.
            return BattleState.EXECUTE_MOVE, match

        # 4. In-Battle (Animating/Enemy Turn)
        match = self.matcher.match_template(screenshot, "pass_inactive_gantas")
        if match:
            # If pass is inactive, something is happening.
            return BattleState.ANIMATING, match

        # 5. Fallback
        return BattleState.UNKNOWN, None

    def click_match(self, match: MatchResult):
        """Execute a resilient click using mousedown/mouseup."""
        region = self.window_capture.get_window_region()
        if not region:
            logger.error("Cannot click: Window region not found")
            return
        
        left, top, _, _ = region
        x, y = match.center
        screen_x, screen_y = left + x, top + y
        
        logger.info(f"Clicking {match.name} at ({screen_x}, {screen_y})")
        
        # click doesn't work, mousedown/mouseup does
        pyautogui.moveTo(screen_x, screen_y, duration=0.1)
        pyautogui.mouseDown()
        time.sleep(0.1) 
        pyautogui.mouseUp()

    def shoot(self, troop: MatchResult, enemy: MatchResult):
        """Execute a shot from a troop to an enemy."""
        logger.info(f"ACT: {troop.name} attacks {enemy.name}")
        # 1. Select troop
        self.click_match(troop)
        time.sleep(ACTION_DELAY)
        # 2. Select enemy
        self.click_match(enemy)
        time.sleep(BATTLE_ACTION_DELAY)

    def _get_priority_match(self, matches: List[MatchResult], priority_list: List[str]) -> Optional[MatchResult]:
        """Find the match that appears earliest in the priority list."""
        for p_name in priority_list:
            for m in matches:
                # Direct name match or starts with (for variations)
                if m.name == p_name or m.name.startswith(p_name):
                    return m
        return None

    def step(self):
        """Detect state and execute appropriate actions."""
        try:
            screenshot = self.window_capture.capture()
            if screenshot is None:
                return

            new_state, match = self.determine_state(screenshot)
            
            if new_state != self.state:
                match_name = match.name if match else "None"
                logger.info(f"State: {self.state.name} -> {new_state.name} (Trigger: {match_name})")
                self.state = new_state
                self.last_state_change = time.time()
            
            # Stuck Detection
            if time.time() - self.last_state_change > STUCK_DETECTION_THRESHOLD:
                logger.warning(f"STUCK in {self.state.name}! Resetting timer.")
                self.last_state_change = time.time()

            # Execute behavior based on current state
            if self.state == BattleState.PRE_BATTLE and match:
                self.click_match(match)
                time.sleep(ACTION_DELAY)

            elif self.state == BattleState.EXECUTE_MOVE:
                # 1. Identify Board State
                enemies = self.matcher.match_category(screenshot, "enemies")
                troops = self.matcher.match_category(screenshot, "troops")
                
                if enemies:
                    logger.info(f"Found Enemies: {', '.join([e.name for e in enemies])}")
                if troops:
                    logger.info(f"Found Troops: {', '.join([t.name for t in troops])}")

                # 2. Prioritize
                troop_prio = self.mission_config.get("troop_priority", [])
                enemy_prio = self.mission_config.get("enemy_priority", [])
                
                best_troop = self._get_priority_match(troops, troop_prio)
                best_enemy = self._get_priority_match(enemies, enemy_prio)

                if best_troop and best_enemy:
                    self.shoot(best_troop, best_enemy)
                else:
                    if not best_troop: logger.debug("No priority troops detected.")
                    if not best_enemy: logger.debug("No priority enemies detected.")

            elif self.state == BattleState.POST_BATTLE and match:
                if match.name in ["finish_ok", "sp_ok"]:
                    self.click_match(match)
                    time.sleep(ACTION_DELAY)
                
                if match.name == "sp_ok":
                    logger.info("Mission sequence complete.")

            elif self.state == BattleState.ANIMATING:
                time.sleep(STATE_CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"Error in state machine step: {e}")
            time.sleep(1)

    def run(self):
        """Start the main execution loop."""
        if not self.window_capture.find_window():
            logger.error("Window 'Battle Nations' not found. Ensure the game is running.")
            print("\n✗ Error: Window 'Battle Nations' not found.")
            return

        self.running = True
        logger.info("Battle State Machine Active.")
        print("\n" + "=" * 60)
        print("Battle State Machine Active")
        print("Press [ESC] to stop at any time")
        print("=" * 60 + "\n")
        
        # Start the keyboard listener in a non-blocking way
        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()
        
        try:
            while self.running:
                self.step()
                time.sleep(STATE_CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Stopped by user via Ctrl+C.")
        finally:
            self.running = False
            listener.stop()
            logger.info("Battle State Machine stopped.")
            print("\nBattle State Machine stopped.")

if __name__ == "__main__":
    from config import LOGS_DIR
    
    # Ensure logs directory exists
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOGS_DIR / 'state_machine.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    fsm = BattleStateMachine()
    fsm.run()
