"""Test script for template matching with visual feedback."""

import logging
import sys
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np
from pynput import keyboard

from config import (
    SCREENSHOTS_DIR, TEMPLATES_DIR,
    SCREENSHOT_FORMAT, TIMESTAMP_FORMAT, LOGS_DIR
)
from window_capture import WindowCapture, WindowCaptureError
from template_matcher import TemplateMatcher

# Constants
TEST_KEY = 't'
MULTIPLE_TEST_KEY = 'm'
EXIT_KEY = 'esc'
COORD_KEY = 'c'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'test_matching.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class MatchTestApp:
    """Application for testing template matching."""
    
    MATCH_COLOR = (0, 255, 0)
    NO_MATCH_COLOR = (0, 0, 255)
    RECT_THICKNESS = 2
    
    def __init__(self):
        self.window_capture = WindowCapture()
        self.matcher = TemplateMatcher()
        self.running = True
        
    def on_press(self, key):
        """Handle key press events."""
        try:
            if hasattr(key, 'char'):
                if key.char == TEST_KEY:
                    self._run_matching_test()
                    return
                elif key.char == MULTIPLE_TEST_KEY:
                    self._run_multiple_matching_test()
                    return
                elif key.char == COORD_KEY:
                    import pyautogui
                    x, y = pyautogui.position()
                    logger.info(f"\n[CURSOR] Screen Coordinates: ({x}, {y})")
                    return
            
            if key == keyboard.Key.esc:
                logger.info("Exit key pressed")
                self.running = False
                return False
                
        except Exception as e:
            logger.error(f"Error handling key press: {e}")

    def _run_multiple_matching_test(self):
        """Test match_multiple/match_category by finding all units on board."""
        try:
            logger.info("Running multiple matching test...")
            print("\n" + "=" * 60)
            print("Running Multiple Match Test (Board Scan)")
            print("=" * 60)
            
            screenshot = self.window_capture.capture()
            if screenshot is None:
                print("✗ Failed to capture screenshot")
                return

            # Scan for categories
            enemies = self.matcher.match_category(screenshot, "enemies")
            troops = self.matcher.match_category(screenshot, "troops")
            all_units = enemies + troops

            if not all_units:
                print("\n✗ No units found on board!")
                return

            print(f"\n✓ Found {len(enemies)} enemy(ies) and {len(troops)} troop(s):\n")
            
            for unit in all_units:
                category = "Enemy" if unit in enemies else "Troop"
                print(f"  • [{category}] {unit.name}")
                print(f"    Confidence: {unit.confidence:.3f}")
                print(f"    Location: {unit.location}")
            
            annotated = self.matcher.draw_matches(screenshot, all_units, 
                                                  self.MATCH_COLOR, 
                                                  self.RECT_THICKNESS)
            
            output_path = self._save_debug_image(annotated, all_units, "multiple")
            print(f"\nAnnotated screenshot saved: {output_path}")
            self._show_image_window(annotated, "Multiple Matches")

        except Exception as e:
            logger.exception(f"Multiple match test failed: {e}")
    
    def _run_matching_test(self):
        """Run template matching test on current screenshot."""
        try:
            logger.info("Running template matching test...")
            print("\n" + "=" * 60)
            print("Running Template Matching Test")
            print("=" * 60)
            
            screenshot = self.window_capture.capture()
            if screenshot is None:
                print("✗ Failed to capture screenshot")
                return
            
            print(f"Screenshot captured: {screenshot.shape[1]}x{screenshot.shape[0]}")
            
            matches = self.matcher.match_all_templates(screenshot)
            
            if not matches:
                print("\n✗ No templates matched!")
                print(f"  Checked templates in: {TEMPLATES_DIR}")
                print(f"  Make sure template images are cropped and saved in the correct folders")
                self._save_debug_image(screenshot, [], "no_matches")
                return
            
            print(f"\n✓ Found {len(matches)} match(es):\n")
            for match in matches:
                print(f"  • {match.name}")
                print(f"    Confidence: {match.confidence:.3f}")
                print(f"    Location: {match.location}")
                print(f"    Center: {match.center}")
                print()
            
            annotated = self.matcher.draw_matches(screenshot, matches, 
                                                  self.MATCH_COLOR, 
                                                  self.RECT_THICKNESS)
            
            output_path = self._save_debug_image(annotated, matches, "matches")
            print(f"Annotated screenshot saved: {output_path}")
            print(f"Opening visualization window (press any key to close)...")
            
            self._show_image_window(annotated, "Template Matches")
            
        except WindowCaptureError as e:
            logger.error(f"Capture failed: {e}")
            print(f"\n✗ Error: {e}")
            print(f"  Make sure '{self.window_capture.window_name}' window is open")
        except Exception as e:
            logger.exception(f"Test failed: {e}")
            print(f"\n✗ Test failed: {e}")
    
    def _save_debug_image(self, image: np.ndarray, matches, suffix: str) -> str:
        """Save debug image with timestamp."""
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        filename = f"test_{suffix}_{timestamp}.{SCREENSHOT_FORMAT}"
        filepath = SCREENSHOTS_DIR / filename
        cv2.imwrite(str(filepath), image)
        return str(filepath)
    
    def _show_image_window(self, image: np.ndarray, window_name: str):
        """Display image in OpenCV window."""
        try:
            cv2.imshow(window_name, image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        except Exception as e:
            logger.warning(f"Could not display window: {e}")
            print(f"  (Could not open display window - image saved to file)")
    
    def _check_templates_exist(self) -> bool:
        """Check if any template files exist."""
        template_files = list(TEMPLATES_DIR.rglob(f"*.{SCREENSHOT_FORMAT}"))
        return len(template_files) > 0
    
    def run(self):
        """Run the test application."""
        print("=" * 60)
        print("Battle Nations - Template Matching Test Tool")
        print("=" * 60)
        print(f"\nWindow name: {self.window_capture.window_name}")
        print(f"Templates directory: {TEMPLATES_DIR}")
        print(f"Results saved to: {SCREENSHOTS_DIR}")
        
        if not self._check_templates_exist():
            print("\nWARNING: No template images found!")
            print("Create templates by:")
            print("  1. Run capture.py and press 's' to capture screenshots")
            print("  2. Crop button/UI regions from screenshots")
            print(f"  3. Save cropped images to {TEMPLATES_DIR}/[category]/")
        
        print("\nControls:")
        print(f"  [{TEST_KEY}] - Run matching test")
        print(f"  [{MULTIPLE_TEST_KEY}] - Run multiple match test")
        print(f"  [{COORD_KEY}] - Get coordinate of cursor")
        print(f"  [{EXIT_KEY.upper()}] - Exit")
        print("\nWaiting for input...\n")
        
        if not self.window_capture.find_window():
            print(f"WARNING: Window '{self.window_capture.window_name}' not found!")
            print("Make sure the game is running and visible.\n")
            sys.exit(1)
        
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()
        
        logger.info("Test application stopped")
        print("\nTest tool stopped.")


def main():
    """Entry point for the test script."""
    try:
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        app = MatchTestApp()
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("\nInterrupted by user.")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        print(f"\nFatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
