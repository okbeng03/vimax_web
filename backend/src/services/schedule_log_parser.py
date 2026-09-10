"""调度日志解析 — 从 vimax_output.tmp 中提取 `[COMFYUI SCHEDULE]` 事件。

日志格式（由 Vimax 调度分支输出，顺序固定）:
  [COMFYUI SCHEDULE]:: prompt_id: p_xxx, type: first_frame, workflow_name: wf.json, workflow_path: /abs/wf.json, output_ids: [a1, b2]
  [COMFYUI SCHEDULE DETAIL]:: file_path: /abs/output/xxx.png

SCHEDULE 行（基础信息）先出现，DETAIL 行（file_path）紧接着补全；
SCHEDULE 行必须存在，DETAIL 行可选。事件仅在拿到 file_path（或确认缺失）后才返回。
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_SCHEDULE_RE = re.compile(
    r"\[COMFYUI SCHEDULE\]::\s*prompt_id:\s*(\S+),\s*type:\s*(\S+),\s*"
    r"workflow_name:\s*(\S+),\s*workflow_path:\s*(\S+),\s*output_ids:\s*(\[.*?\]|\S+)"
)
_DETAIL_RE = re.compile(
    r"\[COMFYUI SCHEDULE DETAIL\]::\s*file_path:\s*(\S+)"
)

MAX_RETENTION = 4096  # 防止无界内存（调度解析器实例级缓存）


@dataclass
class ScheduleEvent:
    prompt_id: str
    generation_type: str
    workflow_name: str
    workflow_path: str
    output_ids: list[str] = field(default_factory=list)
    file_path: str | None = None

    @property
    def complete(self) -> bool:
        """SCHEDULE 行即视为完整事件（file_path 可选）。"""
        return bool(self.prompt_id and self.workflow_name)


class ScheduleLogParser:
    """增量解析调度日志。调用方负责按位置切分新增行后逐行 feed。

    真实顺序：SCHEDULE 行先到（基础信息），DETAIL 行紧接着补全 file_path。
    SCHEDULE 事件先暂存为 pending，DETAIL 行到来时补全并返回；
    DETAIL 缺失时由下一个 SCHEDULE 行或 parse_file 收尾时 flush。
    """

    def __init__(self) -> None:
        # 边界情况：DETAIL 行先于 SCHEDULE 到达时暂存，等待后续 SCHEDULE 拼接
        self._detail_buffer: str | None = None
        # 等待 DETAIL 补全 file_path 的 SCHEDULE 事件（真实顺序下的主路径）
        self._pending_event: ScheduleEvent | None = None

    def parse_line(self, line: str) -> ScheduleEvent | None:
        """解析单行。返回完整事件（file_path 已补全或确认缺失），否则返回 None。"""
        line = line.strip()
        if not line:
            return None

        detail = _DETAIL_RE.search(line)
        if detail:
            pending = self._pending_event
            if pending is not None:
                # 真实顺序：SCHEDULE 先、DETAIL 后 → 补全并返回
                pending.file_path = detail.group(1)
                self._pending_event = None
                return pending
            # 边界：DETAIL 先到 → 暂存，等 SCHEDULE 行拼接
            self._detail_buffer = detail.group(1)
            return None

        m = _SCHEDULE_RE.search(line)
        if not m:
            return None

        event = ScheduleEvent(
            prompt_id=m.group(1),
            generation_type=m.group(2),
            workflow_name=m.group(3),
            workflow_path=m.group(4),
            output_ids=_parse_output_ids(m.group(5)),
            file_path=self._detail_buffer,
        )
        self._detail_buffer = None
        # 上一个 SCHEDULE 未等到 DETAIL（可选行）→ 先返回它，当前事件留待补全
        prev = self._pending_event
        self._pending_event = event
        if prev is not None:
            return prev
        return None

    def parse_file(self, path: str) -> list[ScheduleEvent]:
        """整文件解析（非增量），用于启动时兜底扫描。"""
        events: list[ScheduleEvent] = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for raw in f:
                    evt = self.parse_line(raw)
                    if evt:
                        events.append(evt)
        except OSError:
            logger.warning("ScheduleLogParser: cannot read %s", path)
        # 收尾：最后一个 SCHEDULE 事件未等到 DETAIL → flush（file_path 缺失）
        if self._pending_event is not None:
            events.append(self._pending_event)
            self._pending_event = None
        return events


def _parse_output_ids(raw: str) -> list[str]:
    """解析 `[a1, b2]` → ["a1", "b2"]；容错空/半角括号。"""
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    parts = [p.strip().strip('"\'') for p in raw.split(",") if p.strip()]
    return parts
