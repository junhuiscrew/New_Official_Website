# Demo R2 后台日常维护说明

## 1. 日常打开

双击桌面快捷方式：`C:\Users\pc\Desktop\打开骏辉完整演示站.lnk`。

快捷方式会调用项目工具，检查 Docker、回环端口、域名解析、证书和服务健康后打开中文 Demo 首页。不会迁移、Seed、覆盖内容或删除数据卷。

也可在项目根目录执行：

```powershell
.\scripts\Junhui-Demo-R2.ps1 -Action Status
.\scripts\Junhui-Demo-R2.ps1 -Action Start
.\scripts\Junhui-Demo-R2.ps1 -Action Stop
```

`Stop` 只停止 Demo 服务并保留 PostgreSQL、MinIO 和 Redis 数据卷；`Restore` 会撤回本轮 Demo 的 hosts/代理/证书与快捷方式设置，日常不应使用。

## 2. 地址

- 中文官网：<https://demo.junhuiscrewbarrel.com/zh-cn/>
- 英文官网：<https://demo.junhuiscrewbarrel.com/en/>
- 后台：<https://admin-demo.junhuiscrewbarrel.com/>
- 作者完整布局预览：<https://admin-demo.junhuiscrewbarrel.com/preview/zh-cn/>

后台使用应用自身登录；没有 Nginx Basic 弹窗，也没有免登录管理员。凭据只保存在本机私有目录，不写入本文件或证据包。

## 3. 后台入口与维护职责

| 入口 | 用途 |
|---|---|
| `/` | 工作台、数据统计、快捷入口 |
| `/homepage` | 首页 14 模块排序、显示、样式、引用、草稿、应用和恢复 |
| `/demo-media` | 首页图片/视频槽位替换与前台播放检查 |
| `/catalog`、`/catalog/products` | 产品、分类、型号、规格、图片和关系 |
| `/media` | 媒体资源库、上传状态、缩略图和元数据 |
| `/cases` | 案例正文、关系和生命周期 |
| `/knowledge` | 知识文章、SEO/GEO、关系和生命周期 |
| `/faqs` | 双语 FAQ |
| `/trust`、`/trust/company` | 公司、能力、设备、证书/专利等内容 |
| `/downloads` | 下载资料与文件关联 |
| `/rfqs` | 仅 Demo 询盘列表与状态演示；不发邮件 |

列表和关系选择器支持可读名称、slug 与搜索，不要求日常用户填写 UUID 或 JSON。

## 4. 推荐维护顺序

1. 在媒体库上传或选择替换素材，确认 Demo 标识、alt、尺寸和状态。
2. 在对应业务编辑器修改双语正文、规格或关系并保存。
3. 刷新页面并重新打开记录，确认数据库回读，而不是只看成功提示。
4. 按权限执行 Review/Publish；演示环境的发布只影响独立 Demo 数据库。
5. 打开对应前台 URL，确认首次 SSR、图片、视频、关系链接与中英文切换。
6. 首页引用变化时，在 `/homepage` 保存草稿、打开完整布局预览，再应用布局。

## 5. 媒体替换

- Logo 和三张既有产品图来自已批准素材，只读复用。
- 其余图片、视频和 PDF 均为 Demo，可通过 Admin 替换。
- 不要把 poster、外部假 URL 或改扩展名文件当作视频；替换后应实际点击播放并观察时间推进。
- 工厂、设备、证书、客户和案例素材在获得真实授权前必须继续标识为示意。

## 6. 安全边界

- 仅本机 `127.0.0.1:443` 对宿主开放；Demo 容器没有单独宿主端口。
- VPN 可保持开启，三个 Demo 域名使用精确 DIRECT/hosts 规则进入本机。
- 全站 `X-Robots-Tag: noindex, nofollow`，Sitemap 返回 404。
- 后台保留登录、RBAC、CSRF、Secure Cookie；匿名作者预览和媒体 API 返回 401。
- 不连接生产、腾讯云、Gmail、Analytics 或公共 DNS。
- RFQ 正式提交保持禁用；不要在此环境录入真实客户资料或附件。

## 7. 恢复和凭据

- 本轮前私有数据库快照保存在 `data/demo-r2/private/backups/`，不进入 Git 或分享 ZIP。
- 管理员凭据保存在 `data/demo-r2/private/`；需要轮换时使用 `scripts/Rotate-Demo-R2-Admin.ps1`，不要把新密码写进文档、截图或提交历史。
- 发生问题时先运行 `Status` 并保留日志，不要删除卷、重跑 Seed 或把 Demo 配置指向原 phase37 数据库。
