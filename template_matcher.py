"""Template matching utilities for UI detection."""

import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass
import numpy as np
import cv2

from config import TEMPLATES, get_template_path, get_template_threshold

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of a template match."""
    name: str
    confidence: float
    location: Tuple[int, int]
    size: Tuple[int, int]
    
    @property
    def center(self) -> Tuple[int, int]:
        """Get center point of the match."""
        x, y = self.location
        w, h = self.size
        return (x + w // 2, y + h // 2)
    
    @property
    def rectangle(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """Get top-left and bottom-right points."""
        x, y = self.location
        w, h = self.size
        return ((x, y), (x + w, y + h))


class TemplateMatcher:
    """Handles template matching operations optimized for grayscale speed."""
    
    def __init__(self):
        self._template_cache = {}
    
    def _load_template(self, name: str) -> Optional[np.ndarray]:
        """Load and cache a template image in grayscale."""
        if name in self._template_cache:
            return self._template_cache[name]
        
        template_path = get_template_path(name)
        if not template_path.exists():
            logger.warning(f"Template not found: {template_path}")
            return None
        
        try:
            # Load as grayscale for significant performance boost
            template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
            if template is None:
                logger.error(f"Failed to load template: {template_path}")
                return None
            
            self._template_cache[name] = template
            logger.debug(f"Loaded template (Grayscale): {name} ({template.shape[1]}x{template.shape[0]})")
            return template
            
        except Exception as e:
            logger.error(f"Error loading template {name}: {e}")
            return None

    def _get_grayscale(self, image: np.ndarray) -> np.ndarray:
        """Helper to ensure an image is grayscale."""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image
    
    def match_template(self, 
                      screenshot: np.ndarray, 
                      name: str) -> Optional[MatchResult]:
        """Match a single template against the screenshot."""
        template = self._load_template(name)
        if template is None:
            return None
        
        if screenshot.shape[0] < template.shape[0] or screenshot.shape[1] < template.shape[1]:
            logger.warning(f"Screenshot smaller than template {name}")
            return None
        
        try:
            # Ensure both are grayscale for matching
            gray_screenshot = self._get_grayscale(screenshot)
            
            result = cv2.matchTemplate(gray_screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            threshold = get_template_threshold(name)
            if max_val >= threshold:
                return MatchResult(
                    name=name,
                    confidence=float(max_val),
                    location=max_loc,
                    size=(template.shape[1], template.shape[0])
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error matching template {name}: {e}")
            return None

    def match_multiple(self, 
                      screenshot: np.ndarray, 
                      name: str, 
                      threshold: Optional[float] = None) -> List[MatchResult]:
        """Find all instances of a template using NMS to avoid overlapping matches."""
        template = self._load_template(name)
        if template is None:
            return []
            
        if threshold is None:
            threshold = get_template_threshold(name)
            
        try:
            # Ensure grayscale for matching
            gray_screenshot = self._get_grayscale(screenshot)
            
            res = cv2.matchTemplate(gray_screenshot, template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= threshold)
            
            matches = []
            h, w = template.shape[:2]
            
            pts = []
            for pt in zip(*loc[::-1]):
                pts.append((pt[0], pt[1], float(res[pt[1], pt[0]])))
            
            pts.sort(key=lambda x: x[2], reverse=True)
            
            while pts:
                best = pts.pop(0)
                matches.append(MatchResult(
                    name=name,
                    confidence=best[2],
                    location=(best[0], best[1]),
                    size=(w, h)
                ))
                pts = [p for p in pts if abs(p[0] - best[0]) > w/2 or abs(p[1] - best[1]) > h/2]
                
            return matches
            
        except Exception as e:
            logger.error(f"Error in match_multiple for {name}: {e}")
            return []

    def match_category(self, screenshot: np.ndarray, category: str) -> List[MatchResult]:
        """Find all matches for templates in a specific category."""
        results = []
        # Pre-convert screenshot to grayscale once per category scan for efficiency
        gray_screenshot = self._get_grayscale(screenshot)
        
        for name, info in TEMPLATES.items():
            if info["category"] == category:
                if category in ["enemies", "troops"]:
                    # match_multiple will handle its own grayscale but passing gray_screenshot is fine
                    results.extend(self.match_multiple(gray_screenshot, name))
                else:
                    match = self.match_template(gray_screenshot, name)
                    if match:
                        results.append(match)
        return results
    
    def match_all_templates(self, screenshot: np.ndarray) -> List[MatchResult]:
        """Match all registered templates against the screenshot."""
        matches = []
        gray_screenshot = self._get_grayscale(screenshot)
        
        for name in TEMPLATES.keys():
            match = self.match_template(gray_screenshot, name)
            if match:
                matches.append(match)
        
        return matches
    
    def find_best_match(self, 
                       screenshot: np.ndarray, 
                       template_names: List[str]) -> Optional[MatchResult]:
        """Find the best match among specified templates."""
        best_match = None
        gray_screenshot = self._get_grayscale(screenshot)
        
        for name in template_names:
            if name not in TEMPLATES:
                logger.warning(f"Unknown template: {name}")
                continue
            
            match = self.match_template(gray_screenshot, name)
            if match and (best_match is None or match.confidence > best_match.confidence):
                best_match = match
        
        return best_match
    
    def draw_matches(self, 
                    screenshot: np.ndarray, 
                    matches: List[MatchResult],
                    color: Tuple[int, int, int] = (0, 255, 0),
                    thickness: int = 2) -> np.ndarray:
        """Draw rectangles around matches on the screenshot."""
        result = screenshot.copy()
        
        for match in matches:
            top_left, bottom_right = match.rectangle
            cv2.rectangle(result, top_left, bottom_right, color, thickness)
            
            label = f"{match.name} ({match.confidence:.2f})"
            label_pos = (top_left[0], top_left[1] - 10)
            cv2.putText(result, label, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, color, thickness)
        
        return result
