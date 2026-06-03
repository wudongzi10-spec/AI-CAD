# 公开演示与固定域名部署

本文档说明如何把 AI-CAD 部署成长期可访问的公开演示服务。当前推荐方案是：

```text
GitHub 仓库 main 分支
        |
        v
GitHub Actions self-hosted runner（安装了 FreeCAD 的 Windows 机器）
        |
        v
本地 Flask 服务：http://127.0.0.1:5001
        |
        v
Cloudflare Named Tunnel
        |
        v
https://cad.wudz.cloud
```

不要使用 `cloudflared tunnel --url http://127.0.0.1:5001` 作为长期入口。Quick Tunnel 每次启动都会生成新的 `trycloudflare.com` 地址，重启后链接会变化。

## 关键结论

- GitHub 用于保存代码和触发自动部署，不适合直接运行 FreeCAD 后端。
- FreeCAD Python API 必须在实际建模的机器上执行。
- 固定公网访问推荐使用 Cloudflare Named Tunnel 绑定自有子域名。
- 公开入口访问管理接口时不会自动拥有本机管理员权限，仍需要 `ADMIN_ACCESS_CODE`。

## 1. 准备本地运行环境

确认部署机器已经安装：

- FreeCAD 1.0
- FreeCAD 自带 Python，例如 `E:\FreeCAD 1.0\bin\python.exe`
- 项目依赖：`pip install -r requirements.txt`
- `tools\cloudflared.exe`

复制并编辑环境变量：

```powershell
Copy-Item .env.example .env
```

至少设置：

```dotenv
LLM_API_KEY=your_api_key
FREECAD_BIN_PATH=E:\FreeCAD 1.0\bin
FREECAD_PYTHON_PATH=E:\FreeCAD 1.0\bin\python.exe
APP_HOST=127.0.0.1
APP_PORT=5001
APP_PUBLIC_URL=https://cad.wudz.cloud
APP_CORS_ORIGINS=https://cad.wudz.cloud
DEMO_MODE=true
DEMO_ACCESS_CODE=your_demo_access_code
ADMIN_ACCESS_CODE=your_admin_access_code
```

建议公开演示配置：

```dotenv
DEMO_SHOW_HISTORY=true
DEMO_ALLOW_GENERATE=true
DEMO_ALLOW_DELETE=false
DEMO_ALLOW_DOWNLOAD=true
DEMO_MAX_INSTRUCTION_LENGTH=240
DEMO_RATE_LIMIT_WINDOW_SECONDS=300
DEMO_RATE_LIMIT_MAX_REQUESTS=6
DEMO_HISTORY_LIMIT=20
```

`.env` 已被 `.gitignore` 忽略，请不要提交真实密钥、访问码或管理员口令。

## 2. 启动后端

前台启动，方便观察日志：

```powershell
.\scripts\Start-AiCadBackend.ps1 -NoRedirect
```

后台日志启动：

```powershell
.\scripts\Start-AiCadBackend.ps1
```

兼容旧入口：

```powershell
.\start_demo_backend.ps1
```

健康检查：

```text
http://127.0.0.1:5001/api/health
```

如果 `cad_engine.available` 为 `false`，通常是没有使用 FreeCAD 自带 Python。请检查 `.env` 中的 `FREECAD_PYTHON_PATH` 是否指向 FreeCAD 的 `python.exe`。

## 3. 创建 Cloudflare Named Tunnel

以下命令通常只需要首次配置时执行。

登录 Cloudflare：

```powershell
.\tools\cloudflared.exe tunnel login
```

创建命名 Tunnel：

```powershell
.\tools\cloudflared.exe tunnel create AI-CAD
```

记录命令输出的 Tunnel UUID。

绑定固定子域名：

```powershell
.\tools\cloudflared.exe tunnel route dns AI-CAD cad.wudz.cloud
```

复制配置模板：

```powershell
Copy-Item .\cloudflared\config.example.yml .\cloudflared\config.yml
```

编辑 `cloudflared\config.yml`：

```yaml
tunnel: your-tunnel-uuid
credentials-file: C:\Users\your-user\.cloudflared\your-tunnel-uuid.json

ingress:
  - hostname: cad.wudz.cloud
    service: http://127.0.0.1:5001
  - service: http_status:404
```

也可以让脚本首次生成配置：

```powershell
.\scripts\Start-AiCadTunnel.ps1 -TunnelId "your-tunnel-uuid" -NoRedirect
```

之后启动 Tunnel：

```powershell
.\scripts\Start-AiCadTunnel.ps1 -NoRedirect
```

公开访问：

```text
https://cad.wudz.cloud
```

带访问码分享：

```text
https://cad.wudz.cloud/?demo_access_code=your_demo_access_code
```

## 4. GitHub 自动部署

仓库包含部署工作流：

```text
.github/workflows/deploy-self-hosted.yml
```

它会在 `main` 分支 push 或手动触发时，在 Windows self-hosted runner 上执行：

1. 拉取最新代码。
2. 写入运行时 `.env`。
3. 安装 Python 依赖。
4. 编译检查 Python 源码。
5. 重启本地 AI-CAD 后端。

在 GitHub 仓库设置里添加 self-hosted runner：

```text
Settings -> Actions -> Runners -> New self-hosted runner -> Windows
```

建议把 runner 安装为 Windows 服务，这样机器重启后也能继续接收部署任务。

需要配置的 GitHub Secrets：

- `LLM_API_KEY`
- `DEMO_ACCESS_CODE`
- `ADMIN_ACCESS_CODE`

可选 GitHub Variables：

- `FREECAD_BIN_PATH`
- `FREECAD_PYTHON_PATH`
- `LLM_PROVIDER`
- `LLM_API_BASE_URL`
- `LLM_MODEL`
- `LLM_TIMEOUT`

代码推送到仓库后：

```text
https://github.com/wudongzi10-spec/AI-CAD
```

GitHub Actions 会在 self-hosted runner 上自动完成后端重启。

## 5. 长期在线建议

至少需要保持两个进程常驻：

- AI-CAD Flask 后端。
- Cloudflare Named Tunnel。

后端可以由 GitHub Actions 重启。Tunnel 建议安装为系统服务，或使用 Windows 任务计划程序开机启动。

手动重启后端：

```powershell
.\scripts\Restart-AiCadDeployment.ps1
```

同时重启后端和 Tunnel：

```powershell
.\scripts\Restart-AiCadDeployment.ps1 -RestartTunnel
```

## 常见问题

### 为什么不能直接部署到 GitHub Pages？

GitHub Pages 只能托管静态网页，不能运行 Flask、SQLite 或 FreeCAD Python API。本项目必须有后端进程执行 CAD 生成。

### 可以把 FreeCAD 放进 GitHub 仓库吗？

不推荐。FreeCAD 是大型二进制软件，会显著拖慢 clone、pull 和 Actions 流程，也容易触发大文件限制。即使把 FreeCAD 文件提交进仓库，生成 STL 时仍然需要一台机器实际执行 FreeCAD Python。

### 固定域名应该使用哪个？

本文默认使用：

```text
cad.wudz.cloud
```

如需更换子域名，需要同步修改：

- Cloudflare DNS route。
- `cloudflared/config.yml`。
- `.env` 中的 `APP_PUBLIC_URL`。
- `.env` 中的 `APP_CORS_ORIGINS`。
- GitHub Actions 工作流或仓库 Variables 中的公开 URL 配置。
