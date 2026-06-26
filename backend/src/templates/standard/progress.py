"""标准模板 — 进度步骤枚举

Pipeline: 故事 → 角色 → 环境 → 分镜 → 视频合成
"""

PROGRESS_STEPS = [
    # (name, label)
    # ── 故事与角色阶段 ──
    ("story",              "生成故事"),
    ("character",          "提取角色特征"),
    ("portrait",           "生成角色肖像"),
    ("script",             "生成剧本"),
    # ── 环境阶段 ──
    ("environment",        "生成环境描述"),
    ("environment_images", "生成环境图片"),
    # ── 分镜阶段 ──
    ("storyboard",         "生成故事板"),
    ("shot_description",   "生成镜头描述"),
    # ── 相机与视频阶段 ──
    ("camera_frame",       "生成相机帧"),
    ("shot_video",         "生成镜头视频"),
    ("shot_transition",    "生成镜头过渡"),
    ("scene_video",        "生成场景视频"),
    ("scene_transition",   "生成场景过渡"),
]
