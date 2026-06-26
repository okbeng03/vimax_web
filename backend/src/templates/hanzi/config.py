"""Standard Template — Balanced quality and speed."""

# Video output settings
VIDEO_WIDTH = 1680
VIDEO_HEIGHT = 960
FPS = 30

working_dir = "/Users/wangchangbin/ai/vimax_ru"
evaluate_agent_baseurl = "http://192.168.3.4:8000"
evealute_project_id = "fdf55d15-388f-48e4-a75f-55608ca138a3"

register_voices = {
    "字博士": "字博士",
    "小豆丁": "小豆丁",
    "旁白": "旁白",
    "default": "男生",
    "Male": "男生",
    "Female": "女生",
}

idea = """
小豆丁逛超市回来，心里有个大大的疑惑。他看到入口的“入”字更像古代的“人”字，于是并问字博士“爷爷，人字也是多音字吗？为什么入口的入跟它古时候很像？一个是左撇子写的，另一个是右撇子写的吗？”
"""
user_requirement = """
观众是儿童(3到8岁)。哪吒电影类中国动画，漫画式夸张，热血与幽默并存。故事节奏、推进要合理。
"""
style = "中国动画，国潮美学，东方奇幻，传统纹样，漫画式夸张，硬朗线条，光影戏剧，热血与幽默并存"
