# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from typing import Dict, Type, Callable, List
from fastapi import APIRouter
from typer import Typer
from axi.plugins.spec import CustomMetric, OptimizationRule

# Registries
METRIC_TYPES_REGISTRY: Dict[str, Type[CustomMetric]] = {}
OPTIMIZER_RULES_REGISTRY: List[Type[OptimizationRule]] = []
CLI_EXTENSIONS_REGISTRY: Dict[str, Typer] = {}
API_ROUTERS_REGISTRY: List[APIRouter] = []
HOOKS_REGISTRY: Dict[str, List[Callable]] = {
    "before_extract": [],
    "after_extract": [],
    "before_optimize": [],
    "after_optimize": [],
    "before_execute": [],
    "after_execute": []
}

def register_metric(metric_cls: Type[CustomMetric]):
    METRIC_TYPES_REGISTRY[metric_cls.type_name] = metric_cls

def register_optimizer_rule(rule_cls: Type[OptimizationRule]):
    OPTIMIZER_RULES_REGISTRY.append(rule_cls)

def register_cli_command(name: str, app: Typer):
    CLI_EXTENSIONS_REGISTRY[name] = app

def register_api_router(router: APIRouter):
    API_ROUTERS_REGISTRY.append(router)

def register_hook(event: str, func: Callable):
    if event in HOOKS_REGISTRY:
        HOOKS_REGISTRY[event].append(func)
