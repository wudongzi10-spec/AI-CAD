import urllib.request
import json
import os

# 1. 把这里换成你刚刚在 Kimi 官网申请的 API Key (保留双引号)
API_KEY = (os.getenv("LLM_API_KEY") or os.getenv("MOONSHOT_API_KEY") or "").strip()


def parse_natural_language(user_input):
    print(f"正在请教 Kimi 解析指令：【{user_input}】...")
    if not API_KEY:
        return "请求失败: 请先设置环境变量 LLM_API_KEY 或 MOONSHOT_API_KEY。"

    url = "https://api.moonshot.cn/v1/chat/completions"

    # 2. 精心设计的“提示词 (Prompt)”，强迫 Kimi 变成一个冷酷的 JSON 机器
    system_prompt = """
    你是一个CAD三维建模参数解析器。
    请从用户的自然语言指令中提取几何形状和尺寸参数，并严格以JSON格式输出。
    目前支持的形状(shape_type)只有：cube (立方体), cylinder (圆柱体), sphere (球体)。
    尺寸参数(parameters)包括：length(长), width(宽), height(高), radius(半径)。

    要求：
    1. 必须只输出合法的 JSON 字符串，不要包含任何 markdown 标记（如 ```json），不要包含任何解释性文字！
    2. JSON 格式示例：{"shape_type": "cube", "parameters": {"length": 50, "width": 50, "height": 80}}
    """

    data = {
        "model": "moonshot-v1-8k",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        "temperature": 0.1  # 温度调低，让 Kimi 的回答更严谨稳定
    }

    # 3. 发送网络请求给 Kimi
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {API_KEY}')

    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        # 提取 Kimi 返回的内容
        kimi_reply = result['choices'][0]['message']['content']
        return kimi_reply
    except Exception as e:
        return f"请求失败: {e}"


# 4. 测试一下！
if __name__ == "__main__":
    test_instruction = "帮我建一个长50、宽50、高80的立方体。"
    json_result = parse_natural_language(test_instruction)

    print("\n🎉 Kimi 解析完成！提取到的结构化参数如下：")
    print(json_result)
