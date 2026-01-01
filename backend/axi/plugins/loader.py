# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import sys
import importlib.util
from typing import List
from axi.plugins.registry import (
    register_metric, register_optimizer_rule, register_cli_command,
    register_api_router, register_hook
)
from axi.plugins.spec import AXIPluginManifest

class PluginLoader:
    def __init__(self, plugin_dirs: List[str]):
        self.plugin_dirs = plugin_dirs

    def load_plugins(self):
        for path in self.plugin_dirs:
            if not os.path.exists(path):
                continue
            
            # Scan for python files or packages
            # Assumption: plugins are dirs with axi_plugin.py or simple .py files
            for entry in sorted(os.listdir(path)):
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path):
                     self._load_from_dir(full_path)
                elif entry.endswith(".py") and not entry.startswith("__"):
                     self._load_module(full_path)

    def _load_from_dir(self, path: str):
        # Look for axi_plugin.py
        manifest_path = os.path.join(path, "axi_plugin.py")
        if os.path.exists(manifest_path):
            self._load_module(manifest_path)

    def _load_module(self, path: str):
        try:
            name = os.path.splitext(os.path.basename(path))[0]
            if name == "axi_plugin":
                # Use parent dir name
                name = os.path.basename(os.path.dirname(path))
                
            spec = importlib.util.spec_from_file_location(f"axi_plugins.{name}", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"axi_plugins.{name}"] = module
            spec.loader.exec_module(module)
            
            # Look for manifest
            manifest = getattr(module, "MANIFEST", None)
            if manifest and isinstance(manifest, AXIPluginManifest):
                self._register_manifest(manifest, module)
            
        except Exception as e:
            print(f"Failed to load plugin {path}: {e}")

    def _register_manifest(self, manifest: AXIPluginManifest, module):
        print(f"Loading plugin: {manifest.name} v{manifest.version}")
        
        # Register Metrics
        if manifest.metrics:
            for m in manifest.metrics:
                register_metric(m)
        
        # Register Rules
        if manifest.optimizer_rules:
            for r in manifest.optimizer_rules:
                register_optimizer_rule(r)
        
        # Register Hooks
        if manifest.hooks:
            for event, func in manifest.hooks.items():
                register_hook(event, func)
        
        # Check for CLI/API entrypoints in module if strictly defined or use conventions
        # For this stage, assume manifest-driven isn't deeply nested or we check module attrs
        
        cli_app = getattr(module, "cli_app", None)
        if cli_app:
             register_cli_command(manifest.name, cli_app)
             
        api_router = getattr(module, "api_router", None)
        if api_router:
             register_api_router(api_router)
