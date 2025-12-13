# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Environment variable loader with support for .env files.
Provides environment-specific .env file loading.
"""

import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find project root by looking for axi.yml or metadata_store.
    
    Args:
        start_path: Starting path for search. Defaults to current working directory.
    
    Returns:
        Project root path or None if not found
    """
    if start_path is None:
        start_path = Path.cwd()
    
    current = Path(start_path).resolve()
    
    # Traverse up to find project root markers
    for _ in range(10):  # Limit search depth
        if (current / "axi.yml").exists() or (current / "metadata_store").exists():
            return current
        if current.parent == current:  # Reached filesystem root
            break
        current = current.parent
    
    return None


def load_env_file(env_name: Optional[str] = None, project_root: Optional[Path] = None, override: bool = False) -> bool:
    """
    Load .env file based on environment.
    
    Priority order:
    1. .env.local (always loaded if exists, highest priority)
    2. .env.{env_name} (if env_name is set)
    3. .env (default)
    
    Environment variables already set take precedence over .env file values.
    
    Args:
        env_name: Environment name (dev, staging, prod, local). If None, uses AXI_ENV env var.
        project_root: Project root directory. If None, auto-detected.
    
    Returns:
        True if any .env file was loaded, False otherwise
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.warning("python-dotenv not installed. .env file support disabled.")
        return False
    
    if project_root is None:
        project_root = find_project_root()
        if project_root is None:
            logger.debug("Project root not found, skipping .env file loading")
            return False
    
    if env_name is None:
        env_name = os.getenv("AXI_ENV", "local")
    
    loaded = False
    
    # Priority 1: .env.local (highest priority, for local overrides)
    env_local = project_root / ".env.local"
    if env_local.exists():
        load_dotenv(env_local, override=override)
        logger.debug(f"Loaded .env.local from {env_local}")
        loaded = True
    
    # Priority 2: .env.{env_name}
    if env_name and env_name != "local":
        env_specific = project_root / f".env.{env_name}"
        if env_specific.exists():
            load_dotenv(env_specific, override=override)
            logger.debug(f"Loaded .env.{env_name} from {env_specific}")
            loaded = True
    
    # Priority 3: .env (default)
    env_default = project_root / ".env"
    if env_default.exists():
        load_dotenv(env_default, override=override)
        logger.debug(f"Loaded .env from {env_default}")
        loaded = True
    
    return loaded
