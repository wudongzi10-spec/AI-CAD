import sys
import os
import json
import urllib.request

# ================= 1. 环境配置区 =================
# 替换为你的 Kimi API Key
API_KEY = (os.getenv("LLM_API_KEY") or os.getenv("MOONSHOT_API_KEY") or "").strip()
# 你的 FreeCAD 安装路径
FREECAD_BIN_PATH = r'E:\FreeCAD 1.0\bin'

# ================= 2. 初始化 CAD 引擎 =================
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


# ================= 3. 大脑：自然语言解析模块 =================
def parse_natural_language(user_input):
    print(f"\n🧠 [大脑思考中] 正在分析指令：【{user_input}】...")
    if not API_KEY:
        raise RuntimeError("请先设置环境变量 LLM_API_KEY 或 MOONSHOT_API_KEY。")

    url = "https://api.moonshot.cn/v1/chat/completions"
    system_prompt = """
    你是一个CAD三维建模参数解析器。
    请从用户的自然语言指令中提取几何形状和尺寸参数，并严格以JSON格式输出。
    目前支持的形状(shape_type)只有：cube (立方体), cylinder (圆柱体), sphere (球体)。
    尺寸参数(parameters)包括：length, width, height, radius。
    要求：只输出JSON字符串，不要任何多余文字或markdown标记。
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


# ================= 4. 双手：CAD 自动建模模块 =================
def build_cad_model(json_str, output_filename="final_model.step"):
    print(f"⚙️ [提取参数] 获取到大模型返回数据：{json_str}")

    # 将 JSON 字符串转换成 Python 字典
    try:
        model_data = json.loads(json_str)
    except json.JSONDecodeError:
        print("❌ 解析 JSON 失败，大模型返回格式不正确。")
        return

    shape_type = model_data.get("shape_type")
    params = model_data.get("parameters", {})

    doc = FreeCAD.newDocument("AutoCAD_Final")
    print(f"🛠️ [开始建模] 正在生成 {shape_type} ...")

    # 根据大模型的指令，自动选择生成哪种几何体
    if shape_type == "cube":
        obj = doc.addObject("Part::Box", "Cube")
        obj.Length = params.get("length", 10)
        obj.Width = params.get("width", 10)
        obj.Height = params.get("height", 10)

    elif shape_type == "cylinder":
        obj = doc.addObject("Part::Cylinder", "Cylinder")
        obj.Radius = params.get("radius", 5)
        obj.Height = params.get("height", 10)

    elif shape_type == "sphere":
        obj = doc.addObject("Part::Sphere", "Sphere")
        obj.Radius = params.get("radius", 5)

    else:
        print(f"❌ 不支持的形状类型: {shape_type}")
        return

    doc.recompute()

    # 导出模型
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(current_dir, output_filename)
    Part.export([obj], output_path)
    print(f"🎉 [大功告成] 模型生成完毕！已保存至：{output_path}")


# ================= 5. 系统主控制流 =================
if __name__ == "__main__":
    print("=" * 40)
    print("欢迎使用 基于大模型的 CAD 自动建模系统")
    print("=" * 40)

    # 你可以在这里随便修改指令测试！！！
    instruction = "帮我画一个高为120，底面半径是25的圆柱体。"

    # 步骤 A：调动大脑
    parsed_json = parse_natural_language(instruction)

    # 步骤 B：调动双手
    build_cad_model(parsed_json, "my_smart_model.step")
