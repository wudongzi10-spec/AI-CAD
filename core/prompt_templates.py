PROMPT_TEMPLATES = [
    {
        "id": "simple_box",
        "name": "基础长方体",
        "category": "basic",
        "category_label": "基础体",
        "difficulty": "easy",
        "summary": "快速验证基础参数化建模能力。",
        "instruction": "创建一个长80宽50高30的长方体。",
    },
    {
        "id": "cylinder_hole",
        "name": "带孔基座",
        "category": "machining",
        "category_label": "加工特征",
        "difficulty": "medium",
        "summary": "测试圆柱钻孔和 cut 布尔运算。",
        "instruction": "创建一个长60宽40高30的长方体，在顶部中心打一个半径5深10的圆孔。",
    },
    {
        "id": "stacked_tower",
        "name": "塔式堆叠",
        "category": "assembly",
        "category_label": "装配结构",
        "difficulty": "medium",
        "summary": "测试 top_center 空间对齐与 fuse 融合。",
        "instruction": "生成一个长宽高均为50的基座立方体。在它的正上方放一个底面半径为25、高为40的圆柱体。最后在圆柱体的正上方再放一个底面半径为25、顶面半径为0、高为30的圆锥体，并把这三个实体融合在一起。",
    },
    {
        "id": "dumbbell",
        "name": "哑铃结构",
        "category": "assembly",
        "category_label": "装配结构",
        "difficulty": "medium",
        "summary": "测试上下对称组合和球体融合。",
        "instruction": "帮我建一个哑铃。中间的握把是一个半径为10、高为70的圆柱体。握把的正上方放一个半径为25的球体，握把的正下方也放一个半径为25的球体。最后把它们融合在一起。",
    },
    {
        "id": "push_pin",
        "name": "图钉模型",
        "category": "assembly",
        "category_label": "装配结构",
        "difficulty": "hard",
        "summary": "测试圆柱、圆锥和装配逻辑。",
        "instruction": "画一个图钉。图钉的针部是一个底面半径为2、高为30的圆柱体。图钉的帽子是一个底面半径为15、高为8的圆锥体，顶面半径设为0。把帽子放在针部的正上方并融合。",
    },
    {
        "id": "left_right_layout",
        "name": "左右布局",
        "category": "layout",
        "category_label": "空间布局",
        "difficulty": "medium",
        "summary": "测试 left 和 right 对齐策略。",
        "instruction": "先建一个长100宽100高5的方形底板。然后在它的左侧紧贴着放一个边长为20的正方体，在它的右侧紧贴着放一个半径为15的球体。",
    },
    {
        "id": "common_shape",
        "name": "求交实验",
        "category": "boolean",
        "category_label": "布尔运算",
        "difficulty": "hard",
        "summary": "测试球体与立方体求交。",
        "instruction": "在原点生成一个半径为30的球体。然后在原地再生成一个长宽高均为40的立方体。求这两个物体的交集。",
    },
]


def get_prompt_templates(category="", keyword=""):
    category = (category or "").strip().lower()
    keyword = (keyword or "").strip().lower()
    results = []

    for template in PROMPT_TEMPLATES:
        haystack = " ".join(
            [
                template["id"],
                template["name"],
                template["category_label"],
                template["summary"],
                template["instruction"],
            ]
        ).lower()

        if category and category != "all" and template["category"].lower() != category:
            continue

        if keyword and keyword not in haystack:
            continue

        results.append(template.copy())

    return results


def get_template_by_id(template_id):
    template_id = (template_id or "").strip()
    for template in PROMPT_TEMPLATES:
        if template["id"] == template_id:
            return template.copy()
    return None
