"""汉字模板 — 进度步骤枚举

Pipeline: 爬取字形 → 创意生成 → 动画制作 → 视频合成
"""

PROGRESS_STEPS = [
    # (name, label)
    # ── 汉字数据准备阶段 ──
    ("crawl",              "爬取数据"),
    ("download",           "下载并转换字形图片"),
    # ── 创意与动画生成阶段 ──
    ("idea",               "生成创意"),
    ("transition",         "生成过渡描述"),
    ("video",              "生成演变动画"),
    ("hanzi",              "汉字结果整合"),
    # ── 故事与角色生成阶段 ──
    ("story",              "生成故事"),
    ("character",          "提取角色特征"),
    ("portrait",           "生成角色肖像"),
    ("script",             "生成剧本"),
    # ── 环境与分镜阶段 ──
    ("environment",        "生成环境描述"),
    ("environment_images", "生成环境图片"),
    ("storyboard",         "生成故事板"),
    ("shot_description",   "生成镜头描述"),
    # ── 相机与视频阶段 ──
    ("camera_frame",       "生成相机帧"),
    ("shot_video",         "生成镜头视频"),
    ("shot_transition",    "生成镜头过渡"),
    ("scene_video",        "生成场景视频"),
    ("scene_transition",   "生成场景过渡"),
    ("final",   "生成最终视频"),
]
