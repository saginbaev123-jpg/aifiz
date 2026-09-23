from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
required = [
    "ai/openai_client.py",
    "ai/question_generator.py",
    "ai/pisa_agent.py",
    "ai_core/__init__.py",
    "ai_core/config.py",
    "ai_core/context.py",
    "ai_core/engine.py",
    "ai_core/files.py",
    "ai_core/generators.py",
    "ai_core/jobs.py",
    "ai_core/math_text.py",
    "ai_core/permissions.py",
    "ai_core/physics_diagrams.py",
    "ai_core/prompts.py",
    "ai_core/router.py",
    "ai_core/tool_planner.py",
    "ai_core/visual_engine.py",
    "app.py",
]
missing = [p for p in required if not (ROOT / p).exists()]
if missing:
    print("ERROR: Missing required files:")
    for p in missing:
        print(" -", p)
    sys.exit(2)

try:
    from ai.openai_client import AIClient  # noqa: F401
    from ai.pisa_agent import choose_pisa_visual  # noqa: F401
    from ai_core.permissions import PermissionManager  # noqa: F401
    from ai_core.tool_planner import ModelToolPlanner  # noqa: F401
    from ai_core.visual_engine import infer_diagram_type, validate_diagram_spec  # noqa: F401
    from ai_core.physics_diagrams import render_physics_diagram_svg  # noqa: F401
except Exception as exc:
    print(f"ERROR: Import check failed: {type(exc).__name__}: {exc}")
    sys.exit(3)

print("OK: AI Physics KZ 8.1.0 agentic assistant + PISA files are present.")
