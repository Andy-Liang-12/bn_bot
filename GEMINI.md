# **Battle Nations Auto-Battler Project Plan**

## **1\. Project Overview**

The goal is to develop a resilient, reactive auto-battler for Battle Nations that can reliably farm resources. The system is designed to handle the game's inherent unpredictability—such as variable animation times and RNG-based combat results (dodges/crits)—by treating every turn as a fresh "observation" rather than following a hard-coded script.

## ---

**2\. Architecture**

The project is split into three modular layers to ensure portability and ease of debugging:

* **Vision Engine:** The "Eyes." Responsible for template matching, finding all enemy instances, and identifying UI anchors based on existing code. capture.py, template_matcher.py, and window_capture.py make up the vision engine. test_matching.py demonstrates usage.  
* **Reactive State Machine:** The "Brain." A robust loop that determines the game state and executes moves based on visual cues rather than fixed timers.  
* **Mission Configs:** The "Data." JSON-based configurations that define troop priority and deployment for specific farm spots.

## ---

**3\. Reactive State Machine**

To solve timing and RNG issues, the bot uses a **Finite State Machine (FSM)**. It never "assumes" a unit is dead or a turn is over; it must verify the state visually to proceed.

### **Core States:**

| State | Trigger (Visual Cue) | Action |
| :---- | :---- | :---- |
| **PRE\_BATTLE** | Detects "Fight" button or Deployment UI. | Deploys troops and clicks "Fight." |
| **SCANNING** | No animations detected \+ "Pass" button visible. | Identifies all remaining enemies and friendly units. |
| **SELECT\_UNIT** | Detects Blue Highlight on a friendly unit. | If no unit is highlighted, clicks the next available troop. |
| **EXECUTE\_MOVE** | Ability icons visible \+ Active unit identified. | Clicks skill → Clicks highest priority target tile. |
| **ANIMATING** | Screen pixel variance is high / UI elements missing. | Wait/Poll until the board "settles." |
| **POST\_BATTLE** | Detects "Victory," "Defeat," or "Redo" buttons. | Navigates back to the start and resets the loop. |

### **Resiliency Logic:**

* **State Verification:** Before every click, the bot re-verifies the state. If a click fails to transition the state within a reasonable timeout, the bot retries.  
* **Observation-First:** Because attacks can be dodged, the bot re-scans the board every single turn to identify remaining HP/targets instead of tracking damage internally.

## ---

**4\. Configuration & Targeting Logic**

Instead of hardcoding the logic for every battle, we use a mission\_config.json. This allows the bot to handle different encounters without changing the core engine.

### **Config Structure:**

* **Priority Queue:** A ranked list of enemy templates (e.g., \[mammoth, artillery, grunt\]). The bot always attacks the highest-ranked unit visible on the board.  
* **Ability Mapping:** Defines which skill (1, 2, or 3\) should be used for specific unit types or situations.  
* **Deployment Mapping:** Specific tiles to place troops during the setup phase.

### **Targeting Heuristic:**

1. **Identity:** Scan all enemies using the Vision Engine's match\_all functionality.  
2. **Filter:** Cross-reference found enemies with the Priority Queue in the mission config.  
3. **Target:** Click the tile of the highest-priority enemy that is still alive.

## ---

**5\. Development Roadmap**

1. **Template Gathering:** Use the capture.py utility to build a library of UI buttons and unit sprites.  
2. **State Identification:** Fine-tune the "Wait for Turn" detection (Blue highlight vs. UI anchors).  
3. **Heuristic Implementation:** Build the logic that selects the "best" target from the config list.  
4. **Error Recovery:** Implement "Fail-Safe" states to handle game crashes or potential network disconnects.

---

Avoid changing file and variable names unless the user has explicitly told you to do so.