# **Battle Nations Auto-Battler Project Plan**

## **1\. Project Overview**

The goal is to develop a resilient, reactive auto-battler for Battle Nations that can reliably farm resources. The system is designed to handle the game's inherent unpredictability—such as variable animation times and RNG-based combat results (dodges/crits)—by treating every turn as a fresh "observation" rather than following a hard-coded script.

## ---

**2\. Architecture**

The project is split into modular layers to ensure portability and ease of debugging:

* **Vision Engine:** The "Eyes." Responsible for template matching, finding all enemy instances, and identifying UI anchors. Components: `capture.py`, `template_matcher.py` (with ROI caching), and `window_capture.py`.  
* **Reactive State Machine:** The "Brain." A robust loop in `state_machine.py` that determines the game state and executes moves based on visual cues.  
* **Configuration:** The "Data." 
    * `config.py`: Global settings, match thresholds, and template categories.
    * `battle_configs/*.json`: Mission-specific troop priority, enemy priority, and deployment.
    * `troops.json`: Unit-specific data including skill cooldowns and attack types (click vs. drag).

## ---

**3\. Reactive State Machine**

To solve timing and RNG issues, the bot uses a **Finite State Machine (FSM)**. It never "assumes" a unit is dead or a turn is over; it must verify the state visually to proceed.

### **Core States:**

| State | Trigger (Visual Cue) | Action |
| :---- | :---- | :---- |
| **PRE\_BATTLE** | Detects "Fight" button or Deployment UI. | Deploys troops and clicks "Fight." |
| **SCANNING** | No animations detected \+ "Pass" button visible. | Identifies all remaining enemies and friendly units. |
| **EXECUTE\_MOVE** | "Pass" button active \+ Turn started. | Executes initial moves OR selects troop → clicks skill → clicks target. |
| **ANIMATING** | Screen pixel variance is high / "Pass" button inactive. | Wait/Poll until the board "settles." |
| **POST\_BATTLE** | Detects "Victory," "Defeat," or "OK" buttons. | Navigates back to the start and resets the loop. |

### **Resiliency Logic:**

* **ROI Caching:** To increase speed, once a UI element (like the "Pass" button) is found, the bot caches its Region of Interest (ROI) and checks there first in subsequent frames.
* **Pending Action Confirmation:** Cooldowns for skills are only registered if the bot detects an `ANIMATING` state immediately after an action, confirming the move was accepted by the game.
* **Observation-First:** Because attacks can be dodged, the bot re-scans the board every single turn to identify remaining HP/targets instead of tracking damage internally.

## ---

**4\. Configuration & Targeting Logic**

The bot is driven by the `MISSION_CONFIG` environment variable, which points to a specific file in the `battle_configs/` directory.

### **Config Structure:**

* **Initial Moves:** A sequence of hardcoded moves (troop, skill, target) to execute at the start of a battle (e.g., openers).
* **Priority Queues:** 
    * `troop_priority`: The order in which friendly units are selected to act.
    * `enemy_priority`: The order in which enemy targets are prioritized.
* **Skill Mapping:** Defines the preferred skill order (1, 2, or 3) for each unit type.

### **Targeting Heuristic:**

1. **Identity:** Scan all enemies using the Vision Engine's `match_whitelist` functionality.  
2. **Filter:** Cross-reference found enemies with the `enemy_priority` in the mission config.  
3. **Target:** Select the highest-priority enemy and the first available troop (based on `troop_priority`) whose skill is not on cooldown.

## ---

**5\. Development Roadmap**

1. **Template Gathering:** Use the `capture.py` utility to build a library of UI buttons and unit sprites. (Completed)
2. **State Identification:** Fine-tune the "Wait for Turn" detection (ROI caching and variance checks). (Completed)
3. **Heuristic Implementation:** Build the logic that selects the "best" target from the config list. (Completed)
4. **Error Recovery:** Implement "Fail-Safe" states to handle game crashes or potential network disconnects. (In Progress)

---

Avoid changing file and variable names unless the user has explicitly told you to do so.