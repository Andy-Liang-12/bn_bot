## SETUP INSTRUCTIONS

### SETUP VIRTUAL ENVIRONMENT
python -m venv bn_venv
.\bn_venv\Scripts\activate

deactivate

### INSTALL DEPENDENCIES
pip install opencv-python pillow pyautogui numpy pywin32

# Battle Nations Bot

Automation framework for Battle Nations using OpenCV template matching and PyAutoGUI.

## Project Structure

```
battle_nations_bot/
├── config.py              # Configuration and constants
├── window_capture.py      # Window detection and screenshot capture
├── template_matcher.py    # Template matching logic
├── capture.py            # Screenshot capture tool
├── test_matching.py      # Template matching test tool
├── requirements.txt      # Python dependencies
├── templates/            # Template images organized by category
│   ├── battle/
│   ├── rewards/
│   ├── collection/
│   └── common/
├── screenshots/          # Captured screenshots and test results
└── logs/                # Application logs
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure the game window title matches the configured name in `config.py`:
   - Default: `"Battle Nations"`
   - Modify `WINDOW_NAME` if needed

## Workflow

### Phase 1: Capture Templates

1. Launch the game and position the window so it's visible
2. Run the capture tool:
```bash
python capture.py
```

3. Navigate to different game screens (battle, rewards, collection)
4. Press `s` to capture screenshots of each screen
5. Press `ESC` to exit

6. Crop template regions from screenshots:
   - Open captured screenshots in an image editor
   - Crop button/UI elements you want to detect
   - Save cropped images to appropriate template folders:
     - `templates/battle/` - Battle screen elements
     - `templates/rewards/` - Reward screen elements  
     - `templates/collection/` - Collection screen elements
     - `templates/common/` - Elements that appear on multiple screens
   - Name files descriptively (e.g., `battle_start_button.png`)

### Phase 2: Test Template Matching

1. Register your templates in `config.py` using `register_template()`:
```python
register_template("battle_start_button", "battle", 0.85)
```

2. Run the test tool:
```bash
python test_matching.py
```

3. Navigate to a game screen with elements you want to detect
4. Press `t` to run template matching
5. View results:
   - Console output shows matched templates and confidence scores
   - Annotated screenshot saved to `screenshots/` folder
   - Visual window displays matches (if display available)
6. Adjust thresholds in `config.py` if needed
7. Press `ESC` to exit

### Phase 3: Build Automation (Next Step)

Once template matching is validated, implement the automation flow using the matched elements.

## Configuration

### Window Name
Set in `config.py`:
```python
WINDOW_NAME = "Battle Nations"
```

### Template Thresholds
Adjust matching sensitivity per template:
```python
register_template("button_name", "category", threshold=0.85)
```
- Higher threshold (0.9-0.95): Stricter matching, fewer false positives
- Lower threshold (0.7-0.8): More lenient, may catch variations

### Keyboard Shortcuts
- Capture tool: `s` to capture, `ESC` to exit
- Test tool: `t` to test, `ESC` to exit

Modify in `config.py`:
```python
CAPTURE_KEY = 's'
TEST_KEY = 't'
```

## Tips

1. **Template Quality**: Crop templates tightly around the element without extra padding
2. **Consistency**: Capture templates at the same game resolution you'll use for automation
3. **Unique Elements**: Choose UI elements that are visually distinct and don't change
4. **Multiple Scales**: If the game window can resize, you may need templates at different scales
5. **Lighting/Effects**: Avoid elements with animations or changing colors
6. **Test Thoroughly**: Verify templates match across different game states

## Logging

Logs are saved to:
- `logs/capture.log` - Screenshot capture events
- `logs/test_matching.log` - Template matching test results

## Troubleshooting

**Window not found:**
- Verify the game is running
- Check window title matches `WINDOW_NAME` in config
- Try listing all windows: `import pygetwindow as gw; print(gw.getAllTitles())`

**Templates not matching:**
- Lower the threshold in `config.py`
- Ensure template was cropped from same resolution
- Check template file exists in correct folder
- Verify file format is PNG
