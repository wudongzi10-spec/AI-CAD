# 公开演示与固定域名部署

本文档用于把 AI-CAD 部署成长期可访问的公开演示服务。现在推荐使用 Cloudflare Named Tunnel 绑定固定子域名，例如：

```text
https://cad.wudz.cloud
```

不要再使用 `cloudflared tunnel --url http://127.0.0.1:5001` 这种 Quick Tunnel。Quick Tunnel 每次启动都会生成新的 `trycloudflare.com` 地址，重启后链接自然会变化。

## 部署结论

由于项目依赖本机 FreeCAD Python API，后端必须运行在已安装 FreeCAD 的机器上。GitHub 适合做代码仓库和自动部署触发器，不适合作为直接运行 CAD 后端的服务器。

推荐架构如下：

```text
GitHub 仓库 main 分支
        |
        v
GitHub Actions self-hosted runner（这台 Windows/FreeCAD 机器）
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

## 1. 准备本地环境

确认这台机器已经安装：

- FreeCAD 1.0
- FreeCAD 自带 Python，例如 `E:\FreeCAD 1.0\bin\python.exe`
- 项目依赖：`pip install -r requirements.txt`
- `tools\cloudflared.exe`

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，至少改掉：

- `LLM_API_KEY`
- `DEMO_ACCESS_CODE`
- `ADMIN_ACCESS_CODE`
- `APP_PUBLIC_URL=https://cad.wudz.cloud`
- `APP_CORS_ORIGINS=https://cad.wudz.cloud`

`.env` 已被 `.gitignore` 忽略，不要提交真实密钥。

公开域名入口访问管理接口时不会享受本机免管理员码，仍需要 `ADMIN_ACCESS_CODE`。

## 2. 启动后端

推荐使用统一启动脚本：

```powershell
.\scripts\Start-AiCadBackend.ps1 -NoRedirect
```

后台写日志启动：

```powershell
.\scripts\Start-AiCadBackend.ps1
```

兼容旧命令：

```powershell
.\start_demo_backend.ps1
```

健康检查：

```text
http://127.0.0.1:5001/api/health
```

如果 `cad_engine.available` 是 `false`，通常是没有使用 FreeCAD 自带 Python。请确认 `.env` 中：

```text
FREECAD_PYTHON_PATH=E:\FreeCAD 1.0\bin\python.exe
```

## 3. 创建 Cloudflare Named Tunnel

以下命令只需要首次配置时执行。先登录 Cloudflare：

```powershell
.\tools\cloudflared.exe tunnel login
```

创建命名 tunnel：

```powershell
.\tools\cloudflared.exe tunnel create AI-CAD
```

命令会输出一个 Tunnel UUID，后面配置文件需要使用这个 UUID。

绑定固定子域名：

```powershell
.\tools\cloudflared.exe tunnel route dns AI-CAD cad.wudz.cloud
```

复制配置模板：

```powershell
Copy-Item .\cloudflared\config.example.yml .\cloudflared\config.yml
```

打开 `cloudflared\config.yml`，把 `credentials-file` 改成真实凭据文件路径。通常类似：

```yaml
tunnel: 你的 Tunnel UUID
credentials-file: C:\Users\你的用户名\.cloudflared\你的 Tunnel UUID.json

ingress:
  - hostname: cad.wudz.cloud
    service: http://127.0.0.1:5001
  - service: http_status:404
```

也可以让脚本首次生成配置，把 `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` 换成创建 tunnel 时输出的 UUID：

```powershell
.\scripts\Start-AiCadTunnel.ps1 -TunnelId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" -NoRedirect
```

启动固定域名 tunnel：

```powershell
.\scripts\Start-AiCadTunnel.ps1 -NoRedirect
```

正常后访问：

```text
https://cad.wudz.cloud
```

如果设置了访问码，分享链接可以是：

```text
https://cad.wudz.cloud/?demo_access_code=你的访问码
```

## 4. 通过 GitHub 自动部署

仓库已包含：

```text
.github/workflows/deploy-self-hosted.yml
```

它会在 `main` 分支 push 后，在 Windows self-hosted runner 上执行：

1. 拉取 GitHub 最新代码
2. 写入运行时 `.env`
3. 安装依赖
4. 编译检查 Python 源码
5. 重启本地 Flask 后端

你需要在 GitHub 仓库设置里添加 self-hosted runner：

```text
Settings -> Actions -> Runners -> New self-hosted runner -> Windows
```

按 GitHub 页面给出的命令安装并启动 runner。建议把 runner 安装成 Windows 服务，这样机器重启后也会自动接收部署任务。

还需要在 GitHub 仓库中设置：

Secrets:

- `LLM_API_KEY`
- `DEMO_ACCESS_CODE`
- `ADMIN_ACCESS_CODE`

Variables（可选）:

- `FREECAD_BIN_PATH`
- `FREECAD_PYTHON_PATH`
- `LLM_PROVIDER`
- `LLM_API_BASE_URL`
- `LLM_MODEL`
- `LLM_TIMEOUT`

之后你只要把代码 push 到：

```text
https://github.com/wudongzi10-spec/AI-CAD
```

GitHub Actions 就会在本机自动重启服务。

## 5. 让服务长期在线

最少需要两个常驻进程：

- AI-CAD Flask 后端
- Cloudflare Named Tunnel

后端可以由 GitHub Actions 自动重启。Tunnel 推荐安装成系统服务，或用任务计划程序开机启动。

如果你想手动重启后端：

```powershell
.\scripts\Restart-AiCadDeployment.ps1
```

如果也想同时重启 tunnel：

```powershell
.\scripts\Restart-AiCadDeployment.ps1 -RestartTunnel
```

## 6. 常见问题

### 为什么不直接部署到 GitHub Pages？

GitHub Pages 只能托管静态网页，不能运行 Flask、SQLite 和 FreeCAD Python API。本项目的 CAD 生成必须有后端进程。

### 能不能把 FreeCAD 也 push 到 GitHub？

不推荐，也不能因此省掉运行服务器。原因是：

- GitHub 仓库主要用于保存代码，不是长期运行 Flask/FreeCAD 的服务器。
- FreeCAD 是大型二进制软件，把它直接放进 Git 仓库会让 clone、pull、Actions 部署都变慢，也容易触发大文件限制。
- 即使 FreeCAD 文件在仓库里，生成 STL 时仍然需要某台 Windows/Linux 机器实际执行 FreeCAD Python。

如果目标是“不依赖当前这台本地电脑”，推荐改成云服务器部署：

- Windows 云服务器：安装 FreeCAD，运行 Flask 后端，再用 Cloudflare Tunnel 或公网反代绑定 `cad.wudz.cloud`。
- Linux 云服务器：使用 FreeCAD headless 或 Docker 镜像运行后端，适合长期在线。
- GitHub Actions self-hosted runner：保留当前机器或一台云主机作为运行节点，GitHub 负责自动拉代码和重启服务。

### 为什么以前的外链每次都变？

因为以前使用的是 Cloudflare Quick Tunnel。它适合临时演示，不适合固定公开地址。

### 固定域名应该用哪个？

本文档默认使用：

```text
cad.wudz.cloud
```

你也可以换成其他子域名，例如 `aicad.wudz.cloud`，但需要同时修改：

- Cloudflare DNS route
- `cloudflared/config.yml`
- `.env` 里的 `APP_PUBLIC_URL`
- `.env` 里的 `APP_CORS_ORIGINS`
- GitHub Actions 工作流中的域名环境变量
