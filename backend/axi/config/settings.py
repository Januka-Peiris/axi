# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
from typing import Optional

class Settings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        # Default to ./metadata_store in current directory if not set
        # But prefer avoiding CWD dependence if possible
        default_metadata = os.path.join(os.getcwd(), "metadata_store")
        
        self.AXI_METADATA_DIR = os.getenv("AXI_METADATA_DIR", default_metadata)
        self.AXI_DEMO_MODE = os.getenv("AXI_DEMO_MODE", "false").lower() == "true"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    def reload(self):
        self._load()

def get_settings():
    return Settings()
