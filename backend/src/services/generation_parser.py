"""Parse ViMax stdout for ComfyUI generation results.

Matches log patterns from tools.comfyui_workflow_runner:

1. 开始执行工作流workflows/{name}.json         → workflow_name
2. Comfyui Queued prompt: {uuid}. 开始时间: ... → prompt_id, start_time
3. Prompt {uuid} 执行完成。结束时间: ...        → end_time (keyed by prompt_id)
4. Downloading image from ... to {path}           → output_file(s)
"""

import re
import os
from datetime import datetime
from pathlib import Path


class GenerationParser:
    """Extract ComfyUI generation records from ViMax stdout."""

    WORKFLOW_START = re.compile(r"开始执行工作流workflows/(.+?)\.json")
    PROMPT_QUEUED = re.compile(
        r"Comfyui Queued prompt: (\S+)\. 开始时间: (.+)"
    )
    PROMPT_DONE = re.compile(
        r"Prompt (\S+) 执行完成。结束时间: (.+)"
    )
    IMAGE_DOWNLOAD = re.compile(r"Downloading (?:image|audio|video) from .+ to (.+)")

    # Time formats used in ViMax logs
    TIME_FORMATS = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S,%f",
    ]

    @classmethod
    def parse(cls, content: str, working_dir: str) -> list[dict]:
        """Extract generation results from raw stdout content.

        Returns list of dicts:
            workflow_name  : str
            prompt_id      : str (UUID)
            start_time     : datetime | None
            end_time       : datetime | None
            output_path    : str  (absolute)
            generation_type: str  (last_frame / first_frame / video / image)
            duration_seconds: float
        """
        lines = content.split("\n")
        pending: dict[str, dict] = {}  # prompt_id → info
        current_workflow: str | None = None

        for line in lines:
            m = cls.WORKFLOW_START.search(line)
            if m:
                current_workflow = m.group(1)
                continue

            m = cls.PROMPT_QUEUED.search(line)
            if m:
                pid = m.group(1)
                start_time = cls._parse_time(m.group(2))
                pending[pid] = {
                    "workflow_name": current_workflow or "",
                    "start_time": start_time,
                    "end_time": None,
                    "outputs": [],
                }
                continue

            m = cls.PROMPT_DONE.search(line)
            if m:
                pid = m.group(1)
                end_time = cls._parse_time(m.group(2))
                if pid in pending:
                    pending[pid]["end_time"] = end_time
                continue

            m = cls.IMAGE_DOWNLOAD.search(line)
            if m:
                path_str = m.group(1)
                # Assign to the most recently completed prompt
                for pid, info in reversed(list(pending.items())):
                    if info["end_time"] is not None:
                        info["outputs"].append(path_str)
                        break

        # ── Build result records ──
        results: list[dict] = []
        for prompt_id, info in pending.items():
            outputs: list[str] = info.get("outputs", [])
            output_path = outputs[0] if outputs else ""
            gen_type = cls._infer_type(output_path)

            start = info.get("start_time")
            end = info.get("end_time")
            duration = 0.0
            if start and end:
                duration = (end - start).total_seconds()

            results.append({
                "workflow_name": info.get("workflow_name", ""),
                "prompt_id": prompt_id,
                "start_time": start,
                "end_time": end,
                "output_path": output_path,
                "generation_type": gen_type,
                "duration_seconds": max(duration, 0),
            })

        return results

    @classmethod
    def parse_file(cls, output_path: str, working_dir: str) -> list[dict]:
        """Parse from a file path."""
        if not os.path.exists(output_path):
            return []
        try:
            with open(output_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return []
        return cls.parse(content, working_dir)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @classmethod
    def _parse_time(cls, raw: str) -> datetime | None:
        raw = raw.strip()
        for fmt in cls.TIME_FORMATS:
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _infer_type(output_path: str) -> str:
        """Infer generation_type from output filename."""
        fname = Path(output_path).name.lower()
        if "last_frame" in fname:
            return "last_frame"
        if "first_frame" in fname:
            return "first_frame"
        if fname.endswith((".mp4", ".mov", ".avi", ".webm", ".mkv")):
            return "video"
        if fname.endswith((".flac", ".wav", ".mp3", ".ogg", ".aac", ".m4a")):
            return "audio"
        return "image"
