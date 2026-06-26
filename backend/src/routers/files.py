"""Files API router — browse, read, edit working_dir files."""

import difflib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.models.project import Project
from src.models.operation_log import OperationLog
from src.services.file_manager import FileManager

router = APIRouter(prefix="/api/projects", tags=["files"])


@router.get("/{project_id}/files")
async def list_files(project_id: int, path: str = "", db: AsyncSession = Depends(get_db)):
    """Get file tree for a project's working_dir."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        files = FileManager.list_files(project.working_dir, path)
        return {"current_path": path, "files": files}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/files/content")
async def read_file(project_id: int, path: str, db: AsyncSession = Depends(get_db)):
    """Read a file's content."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return FileManager.read_file(project.working_dir, path)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))


@router.put("/{project_id}/files/content")
async def write_file(
    project_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Save edited file content — diffs against original and stores in operation log."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Read original content before overwriting
    original: str | None = None
    try:
        original_info = FileManager.read_file(project.working_dir, body["path"])
        original = original_info.get("content", "")
    except Exception:
        original = None  # File may not exist yet

    new_content = body["content"]

    try:
        FileManager.write_file(project.working_dir, body["path"], new_content)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Build diff details for operation log
    diff_details: str | None = None
    if original is not None and original != new_content:
        unified = "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{body['path']}",
            tofile=f"b/{body['path']}",
        ))
        diff_details = json.dumps({
            "diff": unified,
            "original": original,
        }, ensure_ascii=False)

    # Record operation
    db.add(OperationLog(
        project_id=project.id,
        user_id=1,
        operation_type="edit_file",
        target_type="file",
        target_name=body["path"],
        summary=f"Edited {body['path']}",
        details=diff_details,
    ))
    await db.commit()
    return {"path": body["path"], "status": "saved"}


@router.get("/{project_id}/files/media")
async def serve_media(project_id: int, path: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Serve image / audio / video files as raw binary for browser playback."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        info = FileManager.get_media_info(project.working_dir, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    file_path = info["target"]
    file_size = info["size"]
    content_type = info["content_type"]

    def file_iterator():
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    range_header = request.headers.get("range")
    headers = {
        "Content-Type": content_type,
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{file_path.name}"',
    }

    if range_header:
        start, end = 0, file_size - 1
        range_match = range_header.strip().lower().replace("bytes=", "")
        if "-" in range_match:
            parts = range_match.split("-", 1)
            if parts[0]:
                start = int(parts[0])
            if parts[1]:
                end = int(parts[1])
        if end >= file_size:
            end = file_size - 1
        chunk_size = end - start + 1

        async def range_iterator():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        headers["Content-Length"] = str(chunk_size)
        return StreamingResponse(range_iterator(), status_code=206, headers=headers)
    else:
        headers["Content-Length"] = str(file_size)
        return StreamingResponse(file_iterator(), headers=headers)


@router.delete("/{project_id}/files")
async def delete_file(
    project_id: int,
    path: str,
    db: AsyncSession = Depends(get_db),
):
    """Move a file to caches/ — soft-delete preserving relative path from working_dir."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        cache_path = FileManager.move_to_cache(project.working_dir, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Record operation
    db.add(OperationLog(
        project_id=project.id,
        user_id=1,
        operation_type="delete_file",
        target_type="file",
        target_name=path,
        summary=f"Moved {path} -> {cache_path}",
        details=json.dumps({"original": path, "cache_path": cache_path}, ensure_ascii=False),
    ))
    await db.commit()

    return {"path": path, "cache_path": cache_path, "status": "deleted"}
