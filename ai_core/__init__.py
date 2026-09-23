"""Shared AI Core used by teacher and student assistants.

Heavy provider dependencies are imported lazily so utility modules (math, visual
validation, routing) remain testable and reusable independently.
"""

from .permissions import PermissionManager
from .router import ToolPlan, ToolRouter

__all__ = ["AICore", "AIResult", "PermissionManager", "ToolPlan", "ToolRouter"]


def __getattr__(name: str):
    if name in {"AICore", "AIResult"}:
        from .engine import AICore, AIResult
        return {"AICore": AICore, "AIResult": AIResult}[name]
    raise AttributeError(name)
