"""导演台模板: 延续性，后面镜头依赖前面镜头 — 进度步骤枚举

Pipeline: 故事 → 角色 → 环境 → 分镜 → 视频合成
"""

PROGRESS_STEPS = [
    # (name, label)
    # ── 故事与角色阶段 ──
    ("story",              "生成故事"),
    ("character",          "提取角色特征"),
    ("portrait",           "生成角色肖像"),
    # ── 环境阶段 ──
    # ── 分镜阶段 ──
    ("storyboard",         "生成故事板"),
    # ── 相机与视频阶段 ──
    ("shot_video",         "生成镜头视频"),
    ("narration_audio",    "生成旁白音频"),
    ("final",   "生成最终视频"),
]
