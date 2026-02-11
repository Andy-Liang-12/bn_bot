"""Window capture utilities for Battle Nations automation."""

import logging
from typing import Optional, Tuple
import numpy as np
import cv2
import pyautogui
from datetime import datetime

try:
    import pygetwindow as gw
except ImportError:
    gw = None

from config import WINDOW_NAME, SCREENSHOTS_DIR, SCREENSHOT_FORMAT, TIMESTAMP_FORMAT

logger = logging.getLogger(__name__)


class WindowCaptureError(Exception):
    """Raised when window capture fails."""
    pass


class WindowCapture:
    """Handles window detection and screenshot capture."""
    
    def __init__(self, window_name: str = WINDOW_NAME):
        self.window_name = window_name
        self._window = None
        self._verify_dependencies()
    
    def _verify_dependencies(self) -> None:
        """Verify required dependencies are available."""
        if gw is None:
            raise WindowCaptureError(
                "pygetwindow is required for window capture. "
                "Install with: pip install pygetwindow"
            )
    
    def find_window(self) -> bool:
        """Find and cache the game window."""
        try:
            windows = gw.getWindowsWithTitle(self.window_name)
            if not windows:
                logger.warning(f"No window found with title: {self.window_name}")
                return False
            
            self._window = windows[0]
            logger.info(f"Found window: {self._window.title} at ({self._window.left}, {self._window.top})")
            return True
            
        except Exception as e:
            logger.error(f"Error finding window: {e}")
            return False
    
    def get_window_region(self) -> Optional[Tuple[int, int, int, int]]:
        """Get window region as (left, top, width, height)."""
        if not self._window:
            if not self.find_window():
                return None
        
        try:
            return (self._window.left, self._window.top, 
                   self._window.width, self._window.height)
        except Exception as e:
            logger.error(f"Error getting window region: {e}")
            return None
    
    def capture(self) -> Optional[np.ndarray]:
        """Capture screenshot of the game window."""
        region = self.get_window_region()
        if not region:
            raise WindowCaptureError(f"Cannot find window: {self.window_name}")
        
        try:
            screenshot = pyautogui.screenshot(region=region)
            return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}")
            raise WindowCaptureError(f"Failed to capture window: {e}")
    
    def save_screenshot(self, prefix: str = "screenshot") -> Optional[str]:
        """Capture and save a screenshot with timestamp."""
        try:
            screenshot = self.capture()
            if screenshot is None:
                return None
            
            timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
            filename = f"{prefix}_{timestamp}.{SCREENSHOT_FORMAT}"
            filepath = SCREENSHOTS_DIR / filename
            
            cv2.imwrite(str(filepath), screenshot)
            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving screenshot: {e}")
            return None