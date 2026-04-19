import sys
import os

# 1. 你的 FreeCAD 安装路径
FREECAD_BIN_PATH = r'E:\FreeCAD 1.0\bin'

# 2. 告诉 Python 去哪里找 FreeCAD 的 Python 模块
sys.path.append(FREECAD_BIN_PATH)

# 3. 核心修复：告诉 Windows 去哪里加载底层的 DLL 依赖！(Python 3.8+ 必备)
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(FREECAD_BIN_PATH)

# 4. 导入 FreeCAD 核心库
try:
    import FreeCAD
    import Part
    print("🎉 成功连接到 FreeCAD 引擎！")
except ImportError as e:
    print(f"❌ 连接失败，具体的底层错误是: {e}")
    sys.exit()

# 5. 创建一个新的 CAD 文档
doc = FreeCAD.newDocument("MyAutoCAD")

# 6. 核心建模：生成一个长 50，宽 50，高 80 的立方体
print("正在生成三维模型...")
box = doc.addObject("Part::Box", "MyCube")
box.Length = 50
box.Width = 50
box.Height = 80

# 7. 刷新文档以应用更改
doc.recompute()

# 8. 将生成的模型导出为 STEP 格式
output_filename = "test_model.step"
current_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(current_dir, output_filename)

Part.export([box], output_path)
print(f"🚀 太棒了！模型已成功生成并保存至：{output_path}")