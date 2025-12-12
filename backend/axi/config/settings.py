# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import pathlib
from typing import Optional

class Settings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        # Dynamic path resolution: find 'metadata_store' relative to this file
        # File: backend/axi/config/settings.py
        # Root: ../../../  (backend/axi/config -> backend/axi -> backend -> ROOT)
        
        current_file = pathlib.Path(__file__).resolve()
        # Traverse up to find directory containing 'metadata_store' or fall back to known structure
        # Start from parent dir
        project_root = None
        current = current_file.parent
        
        # Traverse up to 5 levels to find 'metadata_store' or 'axi.yml' marker
        for _ in range(5):
            if (current / "metadata_store").exists():
                project_root = current
                break
            if current.parent == current: # Reached file system root
                break
            current = current.parent
            
        if not project_root:
             # Fallback: assume standard structure: backend/axi/config/settings.py -> ROOT is 3 levels up
             # config -> axi -> backend -> ROOT
             project_root = current_file.parents[3]

        self.AXI_METADATA_DIR = os.getenv("AXI_METADATA_DIR", str(project_root / "metadata_store"))
        self.AXI_DEMO_MODE = os.getenv("AXI_DEMO_MODE", "false").lower() == "true"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    def reload(self):
        self._load()

def get_settings():
    return Settings()
