"""File system operations — read, write, browse working_dir."""

import os
import shutil
from pathlib import Path

ALLOWED_EXTENSIONS = {".txt", ".json", ".py", ".yaml", ".yml"}
MEDIA_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp",
    ".mp4", ".webm", ".mkv", ".mov", ".avi",
    ".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".opus",
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_MEDIA_SIZE = 100 * 1024 * 1024  # 100MB for media

CONTENT_TYPE_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".opus": "audio/opus",
}


class FileManager:
    """Manage project working_dir file operations with security validations."""

    @staticmethod
    def _validate_path(working_dir: str, relative_path: str) -> Path:
        """Validate and resolve a safe file path."""
        base = Path(working_dir).resolve()
        resolved = (base / relative_path).resolve()
        if base not in resolved.parents and resolved != base:
            raise ValueError("Path traversal detected")
        return resolved

    @staticmethod
    def list_files(working_dir: str, relative_path: str = "") -> list[dict]:
        """List files and dirs in working_dir subdirectory."""
        target = FileManager._validate_path(working_dir, relative_path)
        if not target.exists():
            return []

        items = []
        try:
            for entry in os.scandir(target):
                if entry.name.startswith(".") or entry.name in ("vimax_stdout.tmp", "caches"):
                    continue
                stat = entry.stat()
                items.append({
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": stat.st_size if entry.is_file() else None,
                    "modified_at": int(stat.st_mtime),
                    "children_count": sum(1 for _ in Path(entry.path).iterdir()) if entry.is_dir() else None,
                })
        except OSError:
            return []
        return sorted(items, key=lambda x: (x["type"] != "directory", x["name"]))

    @staticmethod
    def read_file(working_dir: str, relative_path: str) -> dict:
        """Read text file content with size limit."""
        target = FileManager._validate_path(working_dir, relative_path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")

        ext = target.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}")

        stat = target.stat()
        if stat.st_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {stat.st_size} bytes (max {MAX_FILE_SIZE})")

        content = target.read_text(encoding="utf-8")
        return {
            "path": relative_path,
            "content": content,
            "size": stat.st_size,
            "modified_at": int(stat.st_mtime),
        }

    @staticmethod
    def get_media_info(working_dir: str, relative_path: str) -> dict:
        """Validate and return media file info (path, content_type, size) for streaming."""
        target = FileManager._validate_path(working_dir, relative_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"File not found: {relative_path}")
        ext = target.suffix.lower()
        if ext not in MEDIA_EXTENSIONS:
            raise ValueError(f"Unsupported media type: {ext}")
        stat = target.stat()
        if stat.st_size > MAX_MEDIA_SIZE:
            raise ValueError(f"File too large: {stat.st_size} bytes (max {MAX_MEDIA_SIZE})")
        content_type = CONTENT_TYPE_MAP.get(ext, "application/octet-stream")
        return {"target": target, "content_type": content_type, "size": stat.st_size, "ext": ext}

    @staticmethod
    def write_file(working_dir: str, relative_path: str, content: str) -> None:
        """Write content to file, creating parent dirs."""
        target = FileManager._validate_path(working_dir, relative_path)
        ext = target.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}")
        if len(content.encode("utf-8")) > MAX_FILE_SIZE:
            raise ValueError("Content too large")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    @staticmethod
    def move_to_cache(working_dir: str, relative_path: str) -> str:
        """Move a file to caches/ preserving relative path from working_dir.

        Returns the cache-relative path (e.g. 'caches/scene_0/images/foo.png').
        """
        target = FileManager._validate_path(working_dir, relative_path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        if not target.is_file():
            raise ValueError(f"Cannot delete directory: {relative_path}")

        cache_dir = Path(working_dir) / "caches"
        cache_target = cache_dir / relative_path
        cache_target.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(target), str(cache_target))
        return str(Path("caches") / relative_path)
