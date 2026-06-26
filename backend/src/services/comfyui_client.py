"""ComfyUI API client — health check, submit, query, and workflow file reading."""

import json
from pathlib import Path
import httpx


class ComfyUIClient:
    """HTTP client for ComfyUI REST API."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def health_check(self) -> bool:
        """Check if ComfyUI is accessible."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/system_stats", timeout=5)
                return resp.status_code == 200
        except Exception:
            return False

    async def submit_workflow(self, workflow: dict) -> str:
        """Submit workflow, return prompt_id."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["prompt_id"]

    async def get_result(self, prompt_id: str) -> dict:
        """Get generation result by prompt_id."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/history/{prompt_id}",
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def read_workflow_from_dir(working_dir: str, prompt_id: str) -> dict | None:
        """Read workflow JSON from {working_dir}/workflows/ (ui + api versions)."""
        wf_dir = Path(working_dir) / "workflows"
        if not wf_dir.exists():
            return None
        for fname in wf_dir.iterdir():
            if fname.suffix in (".json",) and (prompt_id in fname.stem or fname.stem.startswith("workflow")):
                try:
                    return json.loads(fname.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
        return None
