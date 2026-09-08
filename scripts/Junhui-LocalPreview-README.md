# 骏辉本机真实域名预览工具

脚本：`scripts/Junhui-LocalPreview.ps1`

第一次配置只需运行一次 `Setup`。它会申请一次 UAC，用项目标记段合并 hosts、复用现有 Phase 3.7 CA 签发真实域名叶子证书、设置四个域名的 Clash DIRECT/本地解析，并创建桌面快捷方式。

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\Junhui-LocalPreview.ps1 -Action Setup
```

日常使用桌面“打开骏辉本地官网”，或运行：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\Junhui-LocalPreview.ps1 -Action Start
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\Junhui-LocalPreview.ps1 -Action Status
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\Junhui-LocalPreview.ps1 -Action Stop
```

`Stop` 只停止本项目容器，不删除容器或数据卷。`Restore` 需要管理员 PowerShell，只撤回本轮 hosts/代理例外和本机免 Basic 网关，并恢复原 Phase 3.7 Basic Auth 保护模式；它不会删除共享 CA、数据库或 MinIO 数据。

本工具只管理以下域名：

- `junhuiscrewbarrel.com`
- `www.junhuiscrewbarrel.com`
- `admin.junhuiscrewbarrel.com`
- `api.junhuiscrewbarrel.com`

它不修改公共 DNS、路由器、腾讯云、VPN 节点/订阅、生产服务或业务数据。
