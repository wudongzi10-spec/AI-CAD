# AI-CAD 自然语言驱动三维建模系统

一个面向毕业设计、课程项目和原型验证场景的 AI-CAD 工作台。用户输入中文自然语言建模指令后，系统会先调用大语言模型解析出结构化建模蓝图，再通过 FreeCAD Python API 生成几何体、执行对齐与布尔运算，并导出 STL 供浏览器三维预览。

## 项目概览

- 中文自然语言转 CAD 建模蓝图
- FreeCAD 自动生成三维模型并导出 STL
- 支持模板库、历史记录、统计面板和公开演示模式
- 支持多家 OpenAI 兼容接口，运行时可保存 LLM 配置
- 前端为单文件页面，适合快速演示和部署

## 核心能力

### 当前支持的几何体

- `Part::Box`
- `Part::Cylinder`
- `Part::Sphere`
- `Part::Cone`
- `Part::Torus`

### 当前支持的空间语义

- `top_center`
- `bottom_center`
- `left`
- `right`
- `front`
- `back`
- `center`

### 当前支持的布尔运算

- `cut`
- `fuse`
- `common`

## 系统流程

1. 用户在前端输入自然语言建模指令，或从模板库、历史记录中复用指令。
2. 后端调用 LLM，将自然语言解析为结构化 JSON 建模蓝图。
3. `CADBuilder` 根据蓝图创建几何体、执行空间对齐与布尔运算。
4. 生成结果导出为 STL 文件并记录到 SQLite。
5. 前端使用 Three.js 加载模型并完成三维预览。

## 技术栈

- 后端：`Flask`、`Flask-CORS`
- 前端：`Vue 3`、`Axios`、`Three.js`
- 建模引擎：`FreeCAD Python API`
- 大模型接入：OpenAI 兼容 `Chat Completions API`
- 数据存储：`SQLite`

## 项目结构

```text
AutoCAD_Project/
├─ app.py                     # Flask 入口与 API
├─ config.py                  # 环境变量与运行配置
├─ index.html                 # 前端工作台页面
├─ README.md                  # 项目说明
├─ README_PUBLIC_DEMO.md      # 公开演示部署说明
├─ requirements.txt           # Python 依赖
├─ start_demo_backend.ps1     # Windows 下的演示启动脚本
├─ core/
│  ├─ cad_engine.py           # JSON 蓝图 -> FreeCAD -> STL
│  ├─ llm_parser.py           # 自然语言 -> JSON 蓝图
│  └─ prompt_templates.py     # 内置提示模板
├─ database/
│  └─ db_manager.py           # 历史、统计与设置管理
├─ static/                    # 运行期导出的模型文件
├─ test/                      # 原型脚本与测试用例
└─ tools/                     # 辅助工具
```

## 快速开始

### 1. 环境要求

- Python 3.10 及以上
- 已安装 FreeCAD，并且可以通过 Python API 调用
- 可用的 OpenAI 兼容 LLM API Key
- 现代浏览器

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

说明：

- `requirements.txt` 只包含 Web 服务依赖
- FreeCAD 需要本地单独安装
- 前端依赖通过 CDN 加载，不需要额外构建

### 3. 配置环境变量

常用环境变量如下：

```bash
LLM_API_KEY=your_api_key
LLM_PROVIDER=moonshot
LLM_API_BASE_URL=https://api.moonshot.cn/v1
LLM_MODEL=moonshot-v1-8k
LLM_TIMEOUT=60

FREECAD_BIN_PATH=E:\FreeCAD 1.0\bin

APP_HOST=0.0.0.0
APP_PORT=5001
APP_CORS_ORIGINS=
MAX_HISTORY_LIMIT=200

DEMO_MODE=false
DEMO_NAME=AI-CAD Public Demo
DEMO_ACCESS_CODE=
DEMO_SHOW_HISTORY=true
DEMO_ALLOW_GENERATE=true
DEMO_ALLOW_DELETE=false
DEMO_ALLOW_DOWNLOAD=true
DEMO_MAX_INSTRUCTION_LENGTH=240
DEMO_RATE_LIMIT_WINDOW_SECONDS=300
DEMO_RATE_LIMIT_MAX_REQUESTS=6
DEMO_HISTORY_LIMIT=20
ADMIN_ACCESS_CODE=
```

补充说明：

- 如果数据库中已经保存过 LLM 配置，运行时会优先读取数据库配置
- 同时兼容旧变量 `MOONSHOT_API_KEY`、`MOONSHOT_API_BASE_URL`、`MOONSHOT_MODEL`
- 建议通过环境变量或本地数据库保存密钥，不要把真实 Key 写进代码仓库

### 4. 启动项目

```bash
python app.py
```

默认访问地址：

- `http://127.0.0.1:5001`

如果你使用的是 FreeCAD 自带 Python，可以改用：

```powershell
& "E:\FreeCAD 1.0\bin\python.exe" app.py
```

## 主要页面与接口

### 页面能力

- 工作台首页：系统状态、LLM 配置、模板库、建模输入和实时反馈
- 历史记录页：历史查询、详情查看、再次生成、删除联动清理和 STL 下载
- 公开演示模式：支持访问码、管理员口令、功能开关和速率限制

### 主要 API

- `GET /api/public-config`
- `GET /api/health`
- `GET /api/stats`
- `GET /api/templates`
- `GET /api/settings/llm`
- `POST /api/settings/llm`
- `POST /api/generate`
- `GET /api/history`
- `GET /api/history/<id>`
- `DELETE /api/history/<id>`
- `GET /api/download?path=...`

`POST /api/generate` 请求示例：

```json
{
  "instruction": "创建一个长60宽40高30的长方体，在顶部中心打一个半径5深10的圆孔",
  "template_id": "cylinder_hole",
  "source_record_id": 12
}
```

## 测试与校验

语法编译：

```bash
python -m py_compile app.py config.py core\llm_parser.py core\cad_engine.py core\prompt_templates.py database\db_manager.py
```

单元测试：

```bash
python -m unittest discover -s test -p "test_*.py"
```

## 适用场景

- AI + CAD 毕业设计或课程项目展示
- 中文自然语言建模原型验证
- FreeCAD 自动化建模实验
- OpenAI 兼容接口接入示例

## 当前限制

- 当前仍以基础几何体、基础对齐与基础布尔运算为主
- 建模效果依赖外部 LLM 的解析质量
- 前端目前是单文件页面，更偏向原型和演示
- 自动化测试覆盖仍有提升空间

## 后续优化方向

- 扩展更多几何体、参数约束和装配语义
- 完善前后端工程化拆分与自动化测试
- 增强错误提示、输入校验和任务调度能力
- 提升公开演示模式下的安全性与治理能力

## 相关文档

- [README_PUBLIC_DEMO.md](README_PUBLIC_DEMO.md)：公开演示与 Cloudflare Tunnel 使用说明
