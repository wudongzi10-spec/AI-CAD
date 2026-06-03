# AI-CAD 自然语言三维建模系统

AI-CAD 是一个面向毕业设计、课程项目和原型演示的中文自然语言 CAD 工作台。用户在浏览器中输入建模指令后，后端会调用 OpenAI 兼容的 Chat Completions 接口生成结构化 CAD 蓝图，再通过 FreeCAD Python API 创建几何体、执行空间对齐和布尔运算，最终导出 STL 并在前端用 Three.js 预览。

## 当前能力

- 中文自然语言解析为结构化 CAD JSON 蓝图。
- 基于 FreeCAD 自动生成 STL 模型。
- 支持模型历史、模板库、统计面板、STL 下载和历史复用。
- 支持运行时配置 LLM Provider、Base URL、模型名和 API Key。
- 支持公开演示模式：访问码、管理员口令、功能开关、输入长度限制和生成限流。
- 支持 GitHub Actions self-hosted runner 配合 Cloudflare Named Tunnel 自动部署。

## 支持范围

当前支持的 FreeCAD 基础体：

- `Part::Box`：`Length`、`Width`、`Height`
- `Part::Cylinder`：`Radius`、`Height`
- `Part::Sphere`：`Radius`
- `Part::Cone`：`Radius1`、`Radius2`、`Height`
- `Part::Torus`：`Radius1`、`Radius2`

当前支持的空间对齐：

- `top_center`
- `bottom_center`
- `left`
- `right`
- `front`
- `back`
- `center`

当前支持的布尔运算：

- `cut`
- `fuse`
- `common`

系统会拒绝未声明的复杂自由形体或超出上述范围的几何体，避免 LLM 生成 FreeCAD 无法稳定执行的蓝图。

## 项目结构

```text
AutoCAD_Project/
├─ app.py                         # Flask 应用入口与 HTTP API
├─ config.py                      # 环境变量、路径和运行配置
├─ index.html                     # 单文件 Vue 3 + Three.js 前端工作台
├─ requirements.txt               # Web 后端依赖
├─ start_demo_backend.ps1         # 兼容旧入口的启动脚本
├─ .github/workflows/             # GitHub Actions self-hosted 部署流程
├─ cloudflared/                   # Cloudflare Tunnel 配置模板
├─ scripts/
│  ├─ Start-AiCadBackend.ps1      # 启动本地 Flask 后端
│  ├─ Start-AiCadTunnel.ps1       # 启动 Cloudflare Named Tunnel
│  └─ Restart-AiCadDeployment.ps1 # 重启本地部署
├─ core/
│  ├─ cad_engine.py               # CAD 蓝图校验、FreeCAD 建模和 STL 导出
│  ├─ llm_parser.py               # 自然语言到 CAD 蓝图的 LLM 调用
│  └─ prompt_templates.py         # 内置提示模板
├─ database/
│  └─ db_manager.py               # SQLite 历史、统计和设置管理
├─ static/                        # 运行时导出的 STL 文件，默认不提交
└─ test/
   ├─ test_cad_engine.py          # CAD 引擎单元测试
   └─ test_db_manager.py          # 数据库管理单元测试
```

## 环境要求

- Python 3.10 或更高版本。
- 已安装 FreeCAD 1.0，并可使用 FreeCAD 自带 Python。
- 一个 OpenAI 兼容的 LLM API Key，例如 Moonshot、DeepSeek、OpenRouter、Qwen、SiliconFlow 或 OpenAI。
- 现代浏览器。

安装 Python 依赖：

```bash
pip install -r requirements.txt
```

说明：

- `requirements.txt` 只包含 Flask、CORS、dotenv 等 Web 服务依赖。
- FreeCAD 需要在本机单独安装。
- 前端依赖通过 CDN 加载，不需要前端构建步骤。

## 环境变量

复制模板后编辑：

```powershell
Copy-Item .env.example .env
```

常用配置：

```dotenv
LLM_API_KEY=your_api_key
LLM_PROVIDER=moonshot
LLM_API_BASE_URL=https://api.moonshot.cn/v1
LLM_MODEL=moonshot-v1-8k
LLM_TIMEOUT=60

FREECAD_BIN_PATH=E:\FreeCAD 1.0\bin
FREECAD_PYTHON_PATH=E:\FreeCAD 1.0\bin\python.exe

APP_HOST=0.0.0.0
APP_PORT=5001
APP_PUBLIC_URL=https://cad.wudz.cloud
APP_CORS_ORIGINS=https://cad.wudz.cloud
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

补充：

- 运行时保存到 SQLite 的 LLM 设置优先级高于环境变量。
- 兼容旧变量：`MOONSHOT_API_KEY`、`MOONSHOT_API_BASE_URL`、`MOONSHOT_MODEL`、`MOONSHOT_TIMEOUT`。
- `.env`、数据库、日志和生成的 STL 已被 `.gitignore` 忽略，不要把真实密钥提交到仓库。

## 启动

推荐使用 FreeCAD 自带 Python：

```powershell
& "E:\FreeCAD 1.0\bin\python.exe" app.py
```

或使用项目脚本读取 `.env` 后启动：

```powershell
.\scripts\Start-AiCadBackend.ps1 -NoRedirect
```

默认访问地址：

```text
http://127.0.0.1:5001
```

公开演示和固定域名部署见 [README_PUBLIC_DEMO.md](README_PUBLIC_DEMO.md)。

## API

主要接口：

- `GET /`、`GET /index.html`
- `GET /api/public-config`
- `GET /api/health`
- `GET /api/settings/llm`
- `POST /api/settings/llm`
- `GET /api/stats`
- `GET /api/templates`
- `POST /api/generate`
- `GET /api/history`
- `GET /api/history/<id>`
- `DELETE /api/history/<id>`
- `GET /api/download?path=...`

生成模型请求示例：

```json
{
  "instruction": "创建一个长60宽40高30的长方体，在顶部中心打一个半径5深10的圆孔",
  "template_id": "cylinder_hole",
  "source_record_id": 12
}
```

## 测试与校验

语法编译：

```powershell
& "E:\FreeCAD 1.0\bin\python.exe" -m py_compile app.py config.py core\llm_parser.py core\cad_engine.py core\prompt_templates.py database\db_manager.py
```

单元测试：

```powershell
& "E:\FreeCAD 1.0\bin\python.exe" -m unittest discover -s test -p "test_*.py"
```

## 当前限制

- 仍以基础参数化几何体、基础空间对齐和基础布尔运算为主。
- 建模质量依赖外部 LLM 对自然语言的解析质量。
- FreeCAD 必须在实际运行后端的机器上安装，GitHub Pages 无法直接运行本项目后端。
- 前端目前是单文件工作台，适合演示和原型，不是完整工程化前端项目。
