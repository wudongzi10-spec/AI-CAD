import sys
import os
import json
import urllib.request
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

# ================= 1. 环境配置 =================
API_KEY = (os.getenv("LLM_API_KEY") or os.getenv("MOONSHOT_API_KEY") or "").strip()
FREECAD_BIN_PATH = r'E:\FreeCAD 1.0\bin'

sys.path.append(FREECAD_BIN_PATH)
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(FREECAD_BIN_PATH)

try:
    import FreeCAD
    import Part

    print("✅ CAD 引擎初始化成功！")
except ImportError as e:
    print(f"❌ CAD 引擎连接失败: {e}")
    sys.exit()

app = Flask(__name__)
CORS(app)


# ================= 3. 大脑：全面接管 FreeCAD API 映射 =================
def parse_natural_language(user_input):
    if not API_KEY:
        raise RuntimeError("请先设置环境变量 LLM_API_KEY 或 MOONSHOT_API_KEY。")

    url = "https://api.moonshot.cn/v1/chat/completions"

    # 🧠 【神级 Prompt】：直接教 Kimi 学会 FreeCAD 的底层 API
    system_prompt = """
    你是一个精通 FreeCAD Python API 的高级智能内核。
    请将用户的自然语言三维建模指令，严格转化为符合 FreeCAD 原生 API 属性的 JSON 格式。
    不要包含任何 markdown 或多余文字。

    要求 1："objects" 数组定义几何体。
    - "id": 唯一标识符（如 "obj1"）。
    - "freecad_type": 必须是 FreeCAD 原生类名！如 "Part::Box" (长方体), "Part::Cylinder" (圆柱), "Part::Sphere" (球体), "Part::Cone" (圆锥), "Part::Torus" (圆环)。
    - "properties": 键名必须严格对应 FreeCAD 属性（首字母大写）！
        - Box属性: Length, Width, Height
        - Cylinder属性: Radius, Height
        - Sphere属性: Radius
        - Cone属性: Radius1 (底面), Radius2 (顶面), Height
        - Torus属性: Radius1 (主半径), Radius2 (管半径)
    - "position": {"x": 0, "y": 0, "z": 0}。(注意：球体的定位点是中心，圆柱和长方体的定位点是底面中心或角点，请精确计算防止物体相互穿透或包裹！)

    要求 2："operations" 数组定义布尔运算。
    - "type": "cut" (切除/打孔), "fuse" (融合拼接), "common" (交集)。
    - "base": 基础物体 id。
    - "tool": 工具物体 id。
    """

    data = {
        "model": "moonshot-v1-8k",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        "temperature": 0.1
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {API_KEY}')

    response = urllib.request.urlopen(req)
    result = json.loads(response.read().decode('utf-8'))
    return result['choices'][0]['message']['content']


# ================= 4. 双手：彻底动态化的万能建模执行器 =================
def build_cad_model(json_str, output_filename="model.stl"):
    static_dir = os.path.join(os.path.dirname(__file__), '../static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
    output_path = os.path.join(static_dir, output_filename)

    # 用正则表达式强行把 { } 包裹的 JSON 抠出来，无视 Kimi 的废话
    match = re.search(r'\{.*\}', json_str.replace('\n', ''), re.DOTALL)
    clean_json = match.group(0) if match else json_str
    model_data = json.loads(clean_json)
    objects_data = model_data.get("objects", [])
    operations_data = model_data.get("operations", [])

    doc = FreeCAD.newDocument("AutoCAD_Dynamic")
    created_parts = {}

    # ⚙️ 第一阶段：动态生成任意几何体（彻底告别 if-else！）
    for obj_data in objects_data:
        obj_id = obj_data.get("id")
        freecad_type = obj_data.get("freecad_type")  # 直接获取原生的类名
        properties = obj_data.get("properties", {})
        pos = obj_data.get("position", {"x": 0, "y": 0, "z": 0})

        try:
            # 动态创建 FreeCAD 对象
            obj = doc.addObject(freecad_type, obj_id)

            # 动态赋予属性（管它是长宽高还是半径，直接映射过去）
            for prop_name, prop_value in properties.items():
                if hasattr(obj, prop_name):
                    setattr(obj, prop_name, float(prop_value))

            # 定位
            obj.Placement.Base = FreeCAD.Vector(pos.get("x", 0), pos.get("y", 0), pos.get("z", 0))
            created_parts[obj_id] = obj

        except Exception as e:
            print(f"⚠️ 创建 {freecad_type} 时出错: {e}")

    final_exports = list(created_parts.values())

    # ⚙️ 第二阶段：动态布尔运算
    for op in operations_data:
        op_type = op.get("type")
        base_id = op.get("base")
        tool_id = op.get("tool")

        base_obj = created_parts.get(base_id)
        tool_obj = created_parts.get(tool_id)

        if base_obj and tool_obj:
            if op_type == "cut":
                result_obj = doc.addObject("Part::Cut", f"Cut_{base_id}_{tool_id}")
                result_obj.Base = base_obj
                result_obj.Tool = tool_obj
            elif op_type == "fuse":
                result_obj = doc.addObject("Part::MultiFuse", f"Fuse_{base_id}_{tool_id}")
                result_obj.Shapes = [base_obj, tool_obj]
            elif op_type == "common":
                result_obj = doc.addObject("Part::Common", f"Common_{base_id}_{tool_id}")
                result_obj.Base = base_obj
                result_obj.Tool = tool_obj
            else:
                continue

            if base_obj in final_exports: final_exports.remove(base_obj)
            if tool_obj in final_exports: final_exports.remove(tool_obj)
            final_exports.append(result_obj)

    doc.recompute()

    if final_exports:
        Part.export(final_exports, output_path)
    return output_filename, model_data


# ================= 5. API 接口定义 =================
@app.route('/api/generate', methods=['POST'])
def generate_model():
    data = request.json
    instruction = data.get('instruction', '')
    if not instruction:
        return jsonify({"status": "error", "message": "指令不能为空"}), 400

    try:
        json_str = parse_natural_language(instruction)
        print(f"\n[大模型解析结果]：\n{json_str}")
        filename, parsed_params = build_cad_model(json_str, output_filename="dynamic_model.stl")

        return jsonify({
            "status": "success",
            "message": "动态建模生成成功！",
            "parsed_params": parsed_params,
            "model_url": f"/static/{filename}"
        })
    except Exception as e:
        print(f"生成出错: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    print("🚀 动态内核后端服务已启动！无视固化代码，接受任意挑战...")
    app.run(host='0.0.0.0', port=5000, debug=False)
