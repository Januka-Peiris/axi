# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from typing import List, Dict, Any, Optional, Tuple
import os
import re
from axi.config.loader import Config

class PromotionResult:
    """Result of a promotion decision with detailed reason."""
    def __init__(self, promoted: bool, reason: str, matched_rule: Optional[str] = None):
        self.promoted = promoted
        self.reason = reason
        self.matched_rule = matched_rule
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "promoted": self.promoted,
            "reason": self.reason,
            "matched_rule": self.matched_rule
        }

class PromotionEngine:
    def __init__(self, config: Config):
        self.config = config

    def is_promoted(self, file_path: str, tags: List[str]) -> bool:
        """
        Determines if a model is promoted based on file path and tags.
        file_path is relative to SQL root (e.g., "staging/orders/orders.sql").
        """
        result = self.check_promotion(file_path, tags)
        return result.promoted

    def check_promotion(self, file_path: str, tags: List[str]) -> PromotionResult:
        """
        Determines if a model is promoted with detailed reason.
        Returns PromotionResult with promoted status and reason.
        """
        # Check Exclusion first (exclude takes precedence)
        exclude_match = self._matches_rules(file_path, tags, self.config.exclude)
        if exclude_match[0]:
            return PromotionResult(
                promoted=False,
                reason=f"excluded_by_rule: {exclude_match[1]}",
                matched_rule=exclude_match[1]
            )
            
        # Check Inclusion
        # If no include rules specified, default to promoting all (for raw SQL mode)
        if len(self.config.include.folders) == 0 and len(self.config.include.tags) == 0:
            return PromotionResult(
                promoted=True,
                reason="included_by_default: no_include_rules",
                matched_rule=None
            )
            
        include_match = self._matches_rules(file_path, tags, self.config.include)
        if include_match[0]:
            return PromotionResult(
                promoted=True,
                reason=f"included_by_rule: {include_match[1]}",
                matched_rule=include_match[1]
            )
        
        # Check promotion mode
        if self.config.promotion.mode == "strict":
            return PromotionResult(
                promoted=False,
                reason="not_promoted: strict_mode",
                matched_rule=None
            )
        
        # Auto mode - not explicitly included, so not promoted
        return PromotionResult(
            promoted=False,
            reason="not_promoted: not_in_include_rules",
            matched_rule=None
        )

    def _matches_rules(self, file_path: str, tags: List[str], rules) -> Tuple[bool, Optional[str]]:
        """
        Check if file_path or tags match the given rules.
        Returns (matched: bool, matched_rule: str | None)
        file_path is relative to SQL root (e.g., "staging/orders/orders.sql").
        """
        # Normalize path separators
        file_path = file_path.replace("\\", "/")
        
        # Check tags
        for tag in tags:
            if tag in rules.tags:
                return (True, f"tag:{tag}")
                
        # Check folders/patterns
        # Support glob patterns: *, **
        for pattern in rules.folders:
            # Normalize pattern
            pattern = pattern.replace("\\", "/")
            
            # Simple exact match or prefix match
            if file_path == pattern or file_path.startswith(pattern + "/"):
                return (True, f"folder:{pattern}")
            
            # Support ** wildcard (matches any number of directories)
            if "**" in pattern:
                # Convert pattern to regex
                regex_pattern = pattern.replace("**", ".*").replace("*", "[^/]*")
                if re.match(regex_pattern, file_path):
                    return (True, f"pattern:{pattern}")
            
            # Support * wildcard (matches single directory/file)
            if "*" in pattern:
                # Convert to regex
                regex_pattern = pattern.replace("*", "[^/]*")
                if re.match(regex_pattern, file_path):
                    return (True, f"pattern:{pattern}")
        
        return (False, None)
