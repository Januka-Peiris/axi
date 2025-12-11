# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import re
import glob
from typing import List, Generator, Optional
from axi.extractor.promotion import PromotionEngine, PromotionResult
from axi.utils.jinja import strip_jinja


class ScannedModel:
    def __init__(self, path: str, content: str, tags: List[str], promotion_result=None):
        self.path = path
        self.content = content
        self.tags = tags
        self.promotion_result = promotion_result  # PromotionResult object


class SqlScanner:
    """
    Scans SQL files from a given root directory.
    All paths are computed relative to sql_root for promotion matching.
    """
    def __init__(self, sql_root: str, promotion_engine: PromotionEngine):
        self.sql_root = os.path.abspath(sql_root)
        self.promotion_engine = promotion_engine
        self.project_name = self._get_project_name()

    def _debug(self, msg: str):
        if os.environ.get("AXI_DEBUG") == "true":
            print(f"[AXI-DEBUG] {msg}")

    def scan(self) -> Generator[ScannedModel, None, None]:
        """
        Scan SQL files from sql_root.
        Returns ScannedModel with relative path (from sql_root) for promotion matching.
        """
        self._debug(f"SQL root: {self.sql_root}")
        
        if not os.path.exists(self.sql_root):
            self._debug(f"SQL root does not exist: {self.sql_root}")
            return
        
        # Exclude common non-SQL directories
        excludes = {"target", "dbt_packages", "logs", "macros", "tests", "snapshots", "analysis", "__pycache__", ".git"}
        
        try:
            self._debug(f"Contents of SQL root: {os.listdir(self.sql_root)}")
        except Exception:
            pass

        for root, dirs, files in os.walk(self.sql_root):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in excludes and not d.startswith(".")]
            
            self._debug(f"Scanning directory: {root}")

            for file in files:
                if not file.endswith(".sql"):
                    continue
                    
                full_path = os.path.join(root, file)
                # Calculate relative path from sql_root (for promotion matching)
                rel_path = os.path.relpath(full_path, self.sql_root)
                # Normalize path separators
                rel_path = rel_path.replace("\\", "/")

                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        raw_content = f.read()
                except Exception as e:
                    self._debug(f"[WARN] Failed to read {rel_path}: {e}")
                    continue

                # Prefer compiled dbt SQL if available
                compiled_candidates = []
                if self.project_name:
                    compiled_candidates.append(os.path.join(self.sql_root, "target", "compiled", self.project_name, rel_path))
                compiled_candidates.append(os.path.join(self.sql_root, "target", "compiled", rel_path))
                compiled_candidates.extend(glob.glob(os.path.join(self.sql_root, "target", "compiled", "**", rel_path), recursive=True))
                self._debug(f"[CHECK] compiled candidates: {compiled_candidates}")

                for compiled_path in compiled_candidates:
                    self._debug(f"[CHECK] compiled candidate: {compiled_path} exists={os.path.exists(compiled_path)}")
                    if os.path.exists(compiled_path):
                        try:
                            with open(compiled_path, "r", encoding="utf-8") as f:
                                raw_content = f.read()
                            self._debug(f"[INFO] Using compiled SQL for {rel_path}")
                            break
                        except Exception as e:
                            self._debug(f"[WARN] Failed to read compiled SQL {compiled_path}: {e}")

                self._debug(f"SQL length={len(raw_content)} for file {rel_path}")

                # Filter: Only treat .sql files containing select as models
                if "select" not in raw_content.lower():
                    self._debug(f"[SKIP] No SELECT found → {rel_path}")
                    continue
                        
                # Filter: Ephemeral (only check if not already compiled)
                if "config(materialized='ephemeral'" in raw_content.lower() or 'config(materialized="ephemeral"' in raw_content.lower():
                    self._debug(f"[SKIP] Ephemeral model: {rel_path}")
                    continue

                # Filter: skip schema files if they happen to be .sql (unlikely but safe)
                if file == "schema.yml": 
                    continue

                # Extract tags from SQL content
                tags = self._extract_tags(raw_content)
                
                # Promotion check with detailed result - uses rel_path (relative to sql_root)
                promotion_result = self.promotion_engine.check_promotion(rel_path, tags)
                
                if promotion_result.promoted:
                    # Content is already compiled if from compiled_path, otherwise strip jinja
                    final_content = raw_content
                    
                    # Check if content still has jinja (means it's not compiled)
                    if "{{" in final_content or "{%" in final_content:
                        # Strip jinja from raw SQL
                        final_content = strip_jinja(final_content)
                    else:
                        # Already compiled - just clean up any remaining artifacts
                        cleaned_lines = []
                        for line in final_content.splitlines():
                            # Remove any remaining jinja-like artifacts
                            if "{{" in line or "{%" in line:
                                continue
                            cleaned_lines.append(line)
                        final_content = "\n".join(cleaned_lines)

                    # Final cleanup
                    final_content = final_content.replace(";;", ";").strip()
                    
                    self._debug(f"SQL after cleanup (first 200 chars):\n{final_content[:200]}")
                        
                    yield ScannedModel(rel_path, final_content, tags, promotion_result)
                else:
                    self._debug(f"[SKIP] Not promoted: {rel_path} - {promotion_result.reason}")
                    # Still yield for tracking, but with empty content
                    yield ScannedModel(rel_path, "", tags, promotion_result)

    def _extract_tags(self, content: str) -> List[str]:
        """Extract tags from SQL content."""
        tags = []
        # Check for -- axi: true comment
        if re.search(r'--\s*axi:\s*true', content, re.IGNORECASE):
            tags.append("axi")
        return tags

    def _get_project_name(self) -> Optional[str]:
        """Load dbt project name if dbt_project.yml exists."""
        project_file = os.path.join(self.sql_root, "dbt_project.yml")
        if not os.path.exists(project_file):
            return None
        try:
            with open(project_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("name:"):
                        _, _, value = line.partition(":")
                        name = value.strip()
                        if name:
                            return name
            # Fallback to yaml if present
            try:
                import yaml  # type: ignore
                with open(project_file, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                name = cfg.get("name")
                if name:
                    return name
            except Exception:
                pass
        except Exception as e:
            self._debug(f"[WARN] Failed to read dbt_project.yml: {e}")
        return None
