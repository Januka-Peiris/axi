# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
API error handling: AXI exceptions → structured JSON.
All validation and AXI errors return a consistent {"error": {code, message, hint?, context?}} shape.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from axi.exceptions import AXIBaseException


def _error_body(detail: Any) -> Dict[str, Any]:
    """Normalize FastAPI HTTPException detail to our error shape."""
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return {"code": detail["code"], "message": detail["message"], **{k: v for k, v in detail.items() if k not in ("code", "message")}}
    if isinstance(detail, dict):
        return {"code": "HTTP_ERROR", "message": str(detail), "context": detail}
    return {"code": "HTTP_ERROR", "message": str(detail)}


async def axi_exception_handler(request: Request, exc: AXIBaseException) -> JSONResponse:
    """Convert AXI exceptions to structured JSON. Human-readable message + machine-readable code and context."""
    status = getattr(exc, "http_status", 500)
    body = {"error": exc.to_dict()}
    return JSONResponse(status_code=status, content=body)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Normalize HTTPException to same JSON shape as AXI errors."""
    body = {"error": _error_body(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=body)


def register_axi_exception_handlers(app: FastAPI) -> None:
    """Register AXI and HTTP exception handlers for consistent API error JSON."""
    app.add_exception_handler(AXIBaseException, axi_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
