"""Template matching utilities for UI detection."""

import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass
import numpy as np
import cv2

from config import TemplateConfig, TEMPLATE_CONFIGS, MIN_MATCH_THRESHOLD

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
    """Handles template matching operations."""
    
    def __init__(self):
        self._template_cache = {}
    
    def _load_template(self, config: TemplateConfig) -> Optional[np.ndarray]:
        """Load and cache a template image."""
        if config.name in self._template_cache:
            return self._template_cache[config.name]
        
        if not config.path.exists():
            logger.warning(f"Template not found: {config.path}")
            return None
        
        try:
            template = cv2.imread(str(config.path))
            if template is None:
                logger.error(f"Failed to load template: {config.path}")
                return None
            
            self._template_cache[config.name] = template
            logger.debug(f"Loaded template: {config.name} ({template.shape[1]}x{template.shape[0]})")
            return template
            
        except Exception as e:
            logger.error(f"Error loading template {config.name}: {e}")
            return None
    
    def match_template(self, 
                      screenshot: np.ndarray, 
                      config: TemplateConfig) -> Optional[MatchResult]:
        """Match a single template against the screenshot."""
        template = self._load_template(config)
        if template is None:
            return None
        
        if screenshot.shape[0] < template.shape[0] or screenshot.shape[1] < template.shape[1]:
            logger.warning(f"Screenshot smaller than template {config.name}")
            return None
        
        try:
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= config.threshold:
                return MatchResult(
                    name=config.name,
                    confidence=float(max_val),
                    location=max_loc,
                    size=(template.shape[1], template.shape[0])
                )
            
            logger.debug(f"Template {config.name} matched with {max_val:.3f} (threshold: {config.threshold})")
            return None
            
        except Exception as e:
            logger.error(f"Error matching template {config.name}: {e}")
            return None
    
    def match_all_templates(self, screenshot: np.ndarray) -> List[MatchResult]:
        """Match all registered templates against the screenshot."""
        matches = []
        
        for config in TEMPLATE_CONFIGS.values():
            match = self.match_template(screenshot, config)
            if match:
                matches.append(match)
        
        return matches
    
    def find_best_match(self, 
                       screenshot: np.ndarray, 
                       template_names: List[str]) -> Optional[MatchResult]:
        """Find the best match among specified templates."""
        best_match = None
        
        for name in template_names:
            if name not in TEMPLATE_CONFIGS:
                logger.warning(f"Unknown template: {name}")
                continue
            
            match = self.match_template(screenshot, TEMPLATE_CONFIGS[name])
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