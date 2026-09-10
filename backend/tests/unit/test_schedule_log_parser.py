"""Unit tests for ScheduleLogParser."""

import pytest

from src.services.schedule_log_parser import ScheduleLogParser, _parse_output_ids


def test_parse_schedule_line(tmp_path):
    # 单条 SCHEDULE 行（无 DETAIL）：事件暂存，由 parse_file 收尾 flush
    log = tmp_path / "vimax_output.tmp"
    line = (
        "[COMFYUI SCHEDULE]:: prompt_id: p_0001, type: first_frame, "
        "workflow_name: wf_a.json, workflow_path: /tmp/proj/wf_a.json, "
        "output_ids: [node1, node2]"
    )
    log.write_text(line + "\n", encoding="utf-8")
    events = ScheduleLogParser().parse_file(str(log))
    assert len(events) == 1
    evt = events[0]
    assert evt.prompt_id == "p_0001"
    assert evt.generation_type == "first_frame"
    assert evt.workflow_name == "wf_a.json"
    assert evt.workflow_path == "/tmp/proj/wf_a.json"
    assert evt.output_ids == ["node1", "node2"]
    assert evt.file_path is None


def test_parse_schedule_with_detail():
    parser = ScheduleLogParser()
    line1 = (
        "[COMFYUI SCHEDULE]:: prompt_id: p_0002, type: last_frame, "
        "workflow_name: wf_b.json, workflow_path: /tmp/proj/wf_b.json, "
        "output_ids: [out]"
    )
    # SCHEDULE 行先到：事件暂存，不立即返回
    evt1 = parser.parse_line(line1)
    assert evt1 is None

    # DETAIL 行紧接着补全 file_path 并返回完整事件
    line2 = "[COMFYUI SCHEDULE DETAIL]:: file_path: /tmp/proj/out/abc.png"
    evt2 = parser.parse_line(line2)
    assert evt2 is not None
    assert evt2.prompt_id == "p_0002"
    assert evt2.file_path == "/tmp/proj/out/abc.png"


def test_parse_schedule_without_detail():
    # DETAIL 可选：SCHEDULE 行之间会 flush 上一个事件
    parser = ScheduleLogParser()
    line1 = (
        "[COMFYUI SCHEDULE]:: prompt_id: p_010, type: video, "
        "workflow_name: wf_a.json, workflow_path: /tmp/proj/wf_a.json, "
        "output_ids: [n1]"
    )
    assert parser.parse_line(line1) is None

    line2 = (
        "[COMFYUI SCHEDULE]:: prompt_id: p_011, type: video, "
        "workflow_name: wf_b.json, workflow_path: /tmp/proj/wf_b.json, "
        "output_ids: [n2]"
    )
    evt = parser.parse_line(line2)
    assert evt is not None
    assert evt.prompt_id == "p_010"
    assert evt.file_path is None


def test_parse_ignores_unrelated_lines():
    parser = ScheduleLogParser()
    assert parser.parse_line("Progress: 45%") is None
    assert parser.parse_line("") is None
    assert parser.parse_line("random text") is None


def test_parse_output_ids():
    assert _parse_output_ids("[a1, b2]") == ["a1", "b2"]
    assert _parse_output_ids('["x", "y"]') == ["x", "y"]
    assert _parse_output_ids("[]") == []
    assert _parse_output_ids("[]") == []


def test_parse_file(tmp_path):
    log = tmp_path / "vimax_output.tmp"
    log.write_text(
        "[COMFYUI SCHEDULE]:: prompt_id: p_100, type: first_frame, "
        "workflow_name: wf.json, workflow_path: /tmp/wf.json, output_ids: [n]\n"
        "Progress: 10%\n"
        "[COMFYUI SCHEDULE DETAIL]:: file_path: /tmp/out.png\n",
        encoding="utf-8",
    )
    events = ScheduleLogParser().parse_file(str(log))
    assert len(events) == 1
    assert events[0].prompt_id == "p_100"
    assert events[0].file_path == "/tmp/out.png"


def test_parse_file_flush_pending_without_detail(tmp_path):
    # 只有 SCHEDULE 行、无 DETAIL 行：parse_file 收尾时 flush 未补全事件
    log = tmp_path / "vimax_output.tmp"
    log.write_text(
        "[COMFYUI SCHEDULE]:: prompt_id: p_200, type: video, "
        "workflow_name: wf.json, workflow_path: /tmp/wf.json, output_ids: [n]\n",
        encoding="utf-8",
    )
    events = ScheduleLogParser().parse_file(str(log))
    assert len(events) == 1
    assert events[0].prompt_id == "p_200"
    assert events[0].file_path is None
