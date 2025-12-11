# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import json
import os
from typing import Dict, Any

class MetadataWriter:
    def __init__(self, output_dir: str):
        self.output_dir = os.path.abspath(output_dir)
        
        # Safety check: Never write to dbt target/compiled folders
        normalized = self.output_dir.replace("\\", "/").lower()
        if "/target/compiled" in normalized or "/target/compiled/" in normalized:
            raise ValueError(
                f"Metadata directory cannot be inside dbt compiled folder: {self.output_dir}\n"
                f"Use a separate directory like 'metadata_store' in your project root."
            )
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

    def write(self, metadata: Dict[str, Any]):
        model_name = metadata.get("model", "unknown")
        # sanitize filename
        filename = f"{model_name}.json"
        # Store one JSON per promoted model: metadata_store/models/<model>.json
        # This is separate from dbt's target/compiled folder
        models_dir = os.path.join(self.output_dir, "models")
        os.makedirs(models_dir, exist_ok=True)
        path = os.path.join(models_dir, filename)
        
        with open(path, "w") as f:
            json.dump(metadata, f, indent=2)
