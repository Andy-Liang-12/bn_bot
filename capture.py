"""Main script for capturing screenshots and cropping templates."""

import logging
import sys
from pathlib import Path
from datetime import datetime
import cv2
from pynput import keyboard

from config import (
    CAPTURE_KEY, EXIT_KEY, SCREENSHOTS_DIR, 
    SCREENSHOT_FORMAT, TIMESTAMP_FORMAT, LOGS_DIR
)
from window_capture import WindowCapture, WindowCaptureError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'capture.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class CaptureApp:
    """Application for capturing game screenshots."""
    
    def __init__(self):
        self.window_capture = WindowCapture()
        self.running = True
        self.crop_mode = False
        self.crop_start = None
        self.current_image = None
        self.current_screenshot_path = None
        
    def on_press(self, key):
        """Handle key press events."""
        try:
            if hasattr(key, 'char'):
                if key.char == CAPTURE_KEY:
                    self._capture_screenshot()
                    return
            
            if key == keyboard.Key.esc:
                logger.info("Exit key pressed")
                self.running = False
                return False
                
        except Exception as e:
            logger.error(f"Error handling key press: {e}")
    
    def _capture_screenshot(self):
        """Capture and save a screenshot."""
        try:
            logger.info("Capturing screenshot...")
            filepath = self.window_capture.save_screenshot("capture")
            
            if filepath:
                logger.info(f"Screenshot saved: {filepath}")
                print(f"\n✓ Screenshot saved: {filepath}")
                print(f"  Open this file to crop template regions")
                self.current_screenshot_path = filepath
            else:
                print(f"\n✗ Failed to capture screenshot")
                
        except WindowCaptureError as e:
            logger.error(f"Capture failed: {e}")
            print(f"\n✗ Error: {e}")
            print(f"  Make sure '{self.window_capture.window_name}' window is open and visible")
    
    def run(self):
        """Run the capture application."""
        print("=" * 60)
        print("Battle Nations - Screenshot Capture Tool")
        print("=" * 60)
        print(f"\nWindow name: {self.window_capture.window_name}")
        print(f"Screenshots saved to: {SCREENSHOTS_DIR}")
        print("\nControls:")
        print(f"  [{CAPTURE_KEY}] - Capture screenshot")
        print(f"  [ESC] - Exit")
        print("\nWaiting for input...\n")
        
        if not self.window_capture.find_window():
            print(f"WARNING: Window '{self.window_capture.window_name}' not found!")
            print("Make sure the game is running and the window title matches.")
            print("Continuing anyway - window will be detected on first capture attempt.\n")
        
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()
        
        logger.info("Capture application stopped")
        print("\nCapture tool stopped.")


def main():
    """Entry point for the capture script."""
    try:
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        app = CaptureApp()
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