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
    location: Tuple[int, int]  # Always global (relative to full screenshot)
    size: Tuple[int, int]
    roi_used: bool = False
    
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
    """Handles template matching operations optimized for grayscale speed and ROI scanning."""
    
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
                      name: str,
                      roi: Optional[Tuple[int, int, int, int]] = None) -> Optional[MatchResult]:
        """
        Match a single template against the screenshot.
        roi: Optional (x, y, w, h) bounding box to restrict search.
        """
        template = self._load_template(name)
        if template is None:
            return None
        
        target = screenshot
        offset_x, offset_y = 0, 0
        roi_flag = False

        if roi:
            rx, ry, rw, rh = roi
            sh, sw = screenshot.shape[:2]
            # Ensure ROI is within bounds
            rx = max(0, min(rx, sw - 1))
            ry = max(0, min(ry, sh - 1))
            rw = max(1, min(rw, sw - rx))
            rh = max(1, min(rh, sh - ry))
            
            target = screenshot[ry:ry+rh, rx:rx+rw]
            offset_x, offset_y = rx, ry
            roi_flag = True
        
        if target.shape[0] < template.shape[0] or target.shape[1] < template.shape[1]:
            # ROI is too small for template
            return None
        
        try:
            gray_target = self._get_grayscale(target)
            
            result = cv2.matchTemplate(gray_target, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            threshold = get_template_threshold(name)
            if max_val >= threshold:
                return MatchResult(
                    name=name,
                    confidence=float(max_val),
                    location=(max_loc[0] + offset_x, max_loc[1] + offset_y),
                    size=(template.shape[1], template.shape[0]),
                    roi_used=roi_flag
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error matching template {name}: {e}")
            return None

    def match_multiple(self, 
                      screenshot: np.ndarray, 
                      name: str, 
                      threshold: Optional[float] = None,
                      roi: Optional[Tuple[int, int, int, int]] = None) -> List[MatchResult]:
        template = self._load_template(name)
        if template is None: return []
        
        # 1. THE BOUNDS CHECK (Clamping the ROI)
        target = screenshot
        offset_x, offset_y = 0, 0
        if roi:
            rx, ry, rw, rh = roi
            sh, sw = screenshot.shape[:2]
            
            # Clamp starting points
            x1 = max(0, min(rx, sw - 1))
            y1 = max(0, min(ry, sh - 1))
            # Clamp ending points
            x2 = max(0, min(rx + rw, sw))
            y2 = max(0, min(ry + rh, sh))
            
            target = screenshot[y1:y2, x1:x2]
            offset_x, offset_y = x1, y1

        # 2. TEMPLATE SIZE CHECK (Scrutiny: Prevents crash if ROI < Template)
        th, tw = template.shape[:2]
        if target.shape[0] < th or target.shape[1] < tw:
            return []

        try:
            # 3. GRAYSCALE
            gray_target = self._get_grayscale(target)
            res = cv2.matchTemplate(gray_target, template, cv2.TM_CCOEFF_NORMED)
            
            # 4. NMS PREP
            actual_threshold = threshold or get_template_threshold(name)
            loc = np.where(res >= actual_threshold)
            
            rects = []
            for pt in zip(*loc[::-1]):
                # groupRectangles requires each rect twice to preserve singletons
                rects.append([int(pt[0]), int(pt[1]), int(tw), int(th)])
                rects.append([int(pt[0]), int(pt[1]), int(tw), int(th)])

            if not rects: return []

            # 5. NATIVE NMS
            # groupThreshold=1 means "need 1 overlap" (satisfied by double-append)
            # eps=0.2 means 20% distance tolerance for grouping
            rects, _ = cv2.groupRectangles(rects, groupThreshold=1, eps=0.2)
            
            matches = []
            for (x, y, w, h) in rects:
                # Find best confidence in the grouped area
                conf = float(np.max(res[y:y+h, x:x+w]))
                matches.append(MatchResult(
                    name=name,
                    confidence=conf,
                    location=(x + offset_x, y + offset_y),
                    size=(w, h),
                    roi_used=bool(roi)
                ))
            return matches

        except Exception as e:
            logger.error(f"Error in match_multiple for {name}: {e}")
            return []

    def match_category(self, screenshot: np.ndarray, category: str) -> List[MatchResult]:
        """Find all matches for templates in a specific category."""
        results = []
        
        for name, info in TEMPLATES.items():
            if info["category"] == category:
                if category in ["enemies", "troops"]:
                    results.extend(self.match_multiple(screenshot, name))
                else:
                    match = self.match_template(screenshot, name)
                    if match:
                        results.append(match)
        return results
    
    def match_whitelist(self, 
                        screenshot: np.ndarray, 
                        names: List[str], 
                        multiple: bool = False) -> List[MatchResult]:
        """
        Only matches templates provided in the names list.
        Uses the Master Registry (TEMPLATES) for thresholds and paths.
        More efficient than match_category if we only care about a few specific templates
        """
        results = []
        # Optimization: match_multiple and match_template already convert to grayscale, but we don't want to convert multiple times 
        gray_screenshot = self._get_grayscale(screenshot)

        for name in names:
            if name not in TEMPLATES:
                logger.warning(f"Template '{name}' in mission config but not in registry!")
                continue

            if multiple:
                # For enemies/troops where there might be more than one
                matches = self.match_multiple(gray_screenshot, name)
                results.extend(matches)
            else:
                # For single UI elements
                match = self.match_template(gray_screenshot, name)
                if match:
                    results.append(match)
        
        return results

    def match_all_templates(self, screenshot: np.ndarray) -> List[MatchResult]:
        """Match all registered templates against the screenshot."""
        matches = []
        
        for name in TEMPLATES.keys():
            match = self.match_template(screenshot, name)
            if match:
                matches.append(match)
        
        return matches
    
    # Currently unused
    def find_best_match(self, 
                       screenshot: np.ndarray, 
                       template_names: List[str]) -> Optional[MatchResult]:
        """Find the best match among specified templates."""
        best_match = None
        
        for name in template_names:
            if name not in TEMPLATES:
                logger.warning(f"Unknown template: {name}")
                continue
            
            match = self.match_template(screenshot, name)
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
            
            roi_tag = " (ROI)" if match.roi_used else ""
            label = f"{match.name}{roi_tag} ({match.confidence:.2f})"
            label_pos = (top_left[0], top_left[1] - 10)
            cv2.putText(result, label, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, color, thickness)
        
        return result
