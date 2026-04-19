# 公开演示说明

本文档用于把当前项目启动为公开演示版本，并通过 Cloudflare Quick Tunnel 分享给其他人访问。

## 关键结论

这台机器上的默认 `python` 是 `Python 3.10.11`，但当前 FreeCAD 1.0 绑定的是 `python311.dll`。  
因此后端如果直接用：

```powershell
python app.py
```

会在调用建模接口时出现类似错误：

```text
FreeCAD 引擎不可用: Module use of python311.dll conflicts with this version of Python.
```

正确做法是使用 FreeCAD 自带的 Python 启动后端：

```powershell
& "E:\FreeCAD 1.0\bin\python.exe" app.py
```

或者直接执行项目根目录提供的脚本：

```powershell
.\start_demo_backend.ps1
```

## 目录约定

以下路径均以项目根目录为基准：

```text
AutoCAD_Project/
├─ app.py
├─ README_PUBLIC_DEMO.md
├─ start_demo_backend.ps1
├─ demo_v2_stdout.log
├─ demo_v2_stderr.log
├─ cloudflared_v2_stdout.log
├─ cloudflared_v2_stderr.log
└─ tools/
   └─ cloudflared.exe
```

## 1. 进入项目目录

```powershell
Set-Location "D:\PycharmProjects\AutoCAD_Project"
```

## 2. 设置公开演示环境变量

```powershell
$env:DEMO_MODE="true"
$env:DEMO_NAME="AI-CAD 在线演示"
$env:DEMO_ACCESS_CODE="share-demo-code"
$env:ADMIN_ACCESS_CODE="manage-demo-code"

$env:DEMO_SHOW_HISTORY="true"
$env:DEMO_ALLOW_GENERATE="true"
$env:DEMO_ALLOW_DELETE="true"
$env:DEMO_ALLOW_DOWNLOAD="true"

$env:DEMO_RATE_LIMIT_MAX_REQUESTS="6"
$env:DEMO_RATE_LIMIT_WINDOW_SECONDS="300"
$env:DEMO_MAX_INSTRUCTION_LENGTH="240"
```

## 3. 启动后端

### 推荐方式：使用项目脚本

```powershell
.\start_demo_backend.ps1
```

该脚本默认会使用：

```text
E:\FreeCAD 1.0\bin\python.exe
```

并把日志写入：

- `demo_v2_stdout.log`
- `demo_v2_stderr.log`

### 等价手动命令

```powershell
& "E:\FreeCAD 1.0\bin\python.exe" app.py 1> .\demo_v2_stdout.log 2> .\demo_v2_stderr.log
```

### 只想在当前窗口直接看输出

```powershell
.\start_demo_backend.ps1 -NoRedirect
```

## 4. 检查后端是否启动成功

先访问：

```text
http://127.0.0.1:5001/api/health
```

如果健康检查返回的 `cad_engine.available` 是 `false`，请重点看：

- `cad_engine.error`
- `cad_engine.fix_hint`

当前代码已经把版本冲突时的修复建议直接写进接口返回里。

## 5. 启动 Cloudflare Tunnel

在新的 PowerShell 窗口中执行：

```powershell
Set-Location "D:\PycharmProjects\AutoCAD_Project"
& ".\tools\cloudflared.exe" tunnel --url http://127.0.0.1:5001 1> .\cloudflared_v2_stdout.log 2> .\cloudflared_v2_stderr.log
```

## 6. 获取公开访问地址

```powershell
Get-Content .\cloudflared_v2_stderr.log
```

或实时查看：

```powershell
Get-Content .\cloudflared_v2_stderr.log -Wait
```

你会看到类似：

```text
https://xxxxx.trycloudflare.com
```

最终分享链接为：

```text
https://xxxxx.trycloudflare.com/?demo_access_code=share-demo-code
```

例如：

```text
https://your-demo.trycloudflare.com/?demo_access_code=share-demo-code
```

## 7. 最短可执行流程

窗口 1：

```powershell
Set-Location "D:\PycharmProjects\AutoCAD_Project"
$env:DEMO_MODE="true"
$env:DEMO_ACCESS_CODE="share-demo-code"
$env:ADMIN_ACCESS_CODE="manage-demo-code"
.\start_demo_backend.ps1
```

窗口 2：

```powershell
Set-Location "D:\PycharmProjects\AutoCAD_Project"
& ".\tools\cloudflared.exe" tunnel --url http://127.0.0.1:5001 1> .\cloudflared_v2_stdout.log 2> .\cloudflared_v2_stderr.log
```

窗口 3（可选）：

```powershell
Set-Location "D:\PycharmProjects\AutoCAD_Project"
Get-Content .\cloudflared_v2_stderr.log -Wait
```

## 8. 常见问题

### 为什么前端提示通信失败？

如果提示：

```text
通信失败：FreeCAD 引擎不可用: Module use of python311.dll conflicts with this version of Python.
```

说明后端是用错误的 Python 启动的。不要再用：

```powershell
python app.py
```

改用：

```powershell
.\start_demo_backend.ps1
```

或：

```powershell
& "E:\FreeCAD 1.0\bin\python.exe" app.py
```

### 为什么 `cloudflared_v2_stdout.log` 可能是空的？

这是正常的，很多关键信息会写到 `cloudflared_v2_stderr.log`。

### 为什么每次 tunnel 地址都变？

因为这里使用的是 Cloudflare Quick Tunnel，域名不是固定的。

### 关闭窗口后为什么外链失效？

因为公开演示依赖两个本地进程同时在线：

- 后端服务
- `cloudflared.exe`
