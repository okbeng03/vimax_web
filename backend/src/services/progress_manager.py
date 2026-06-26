"""Progress step manager — loads PROGRESS_STEPS from each template's progress.py.

Each template's ``progress.py`` exports a ``PROGRESS_STEPS`` list of
``(name, label)`` tuples defining the pipeline step sequence.

This module provides:
- Ordered step list with auto-assigned order
- "next step" lookup after a given step name
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ProgressStep:
    """A single step in the pipeline."""
    name: str    # internal key, e.g. "story"
    label: str   # human-readable, e.g. "生成故事"
    order: int   # zero-based position


# ---------------------------------------------------------------------------
# Dynamic import helper
# ---------------------------------------------------------------------------


def _import_template_module(template_dir_name: str) -> Any | None:
    """Import a template's progress.py module dynamically by file path."""
    base = Path(__file__).resolve().parent.parent / "templates"
    module_path = base / template_dir_name / "progress.py"
    if not module_path.exists():
        return None

    spec = importlib.util.spec_from_file_location(
        f"templates.{template_dir_name}.progress",
        str(module_path),
    )
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_progress_cache: dict[str, list[ProgressStep]] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_template_progress(template_dir_name: str) -> list[ProgressStep]:
    """Return the progress enum for a template (cached)."""
    if template_dir_name in _progress_cache:
        return _progress_cache[template_dir_name]

    module = _import_template_module(template_dir_name)
    if module is None or not hasattr(module, "PROGRESS_STEPS"):
        _progress_cache[template_dir_name] = []
        return []

    raw = getattr(module, "PROGRESS_STEPS")
    steps = [
        ProgressStep(name=str(pair[0]), label=str(pair[1]), order=i)
        for i, pair in enumerate(raw)
    ]
    _progress_cache[template_dir_name] = steps
    return steps


def get_active_steps(steps: list[ProgressStep]) -> list[ProgressStep]:
    """Return all real steps (there are no sentinels now)."""
    return steps


def get_next_step_name(steps: list[ProgressStep], current_step_name: str) -> str | None:
    """Given a step name, return the next step name, or None if at the end."""
    for i, s in enumerate(steps):
        if s.name == current_step_name:
            if i + 1 < len(steps):
                return steps[i + 1].name
            return None
    return None


def is_last_step(steps: list[ProgressStep], step_name: str) -> bool:
    """Check whether step_name is the final step."""
    if not steps:
        return False
    return steps[-1].name == step_name
