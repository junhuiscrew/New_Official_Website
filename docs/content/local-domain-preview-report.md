# 骏辉本机真实域名直连预览实施报告

## 1. 结论

- 执行结果：`IMPLEMENTED_AND_RUNNING`。
- 唯一运行目标：原 `phase37-local-https` 隔离实例；Compose project 为 `junhui-phase37-pilot`。
- VPN/TUN 保持开启，四个精确域名均解析到 `127.0.0.1`；TLS 实际远端为 `[::ffff:127.0.0.1]:443`。
- 本机域名模式只发布 `127.0.0.1:443`。WLAN 地址的 443 连接失败，Windows portproxy 条目为 0。
- 本机虚拟主机的 Nginx HTTP Basic 已取消，未配置 Basic 凭据的新 Edge 会话可直接打开前台；默认 Phase 3.7 Nginx 配置中的 Basic Auth 保持不变。
- Admin 应用登录、RBAC、CSRF、Secure/HttpOnly Cookie 和私有附件权限保持；匿名管理 API 与匿名私有附件请求均返回 `401`。
- 全站 `X-Robots-Tag: noindex, nofollow` 保持，常驻 `/sitemap.xml` 返回 `404`。
- 已实际执行一次 Stop/Start，并从桌面快捷方式再次启动成功；结束时本机预览保持运行。
- 未执行 migration、Seed、内容导入、Review/Publish、RFQ 提交、附件上传、邮件、公共 DNS、云端部署、Analytics、commit、push 或 merge。

本报告不构成生产上线许可，也不表示 Privacy 或 Phase 3.7 全部完成。

## 2. 实际目标和版本

| 项目 | 实际值 |
| --- | --- |
| 仓库 | `junhuiscrew/New_Official_Website` |
| 工作区 | `D:\Python_Project\New_Official_Website\junhui-global-website\.worktrees\phase-3.6` |
| 分支 | `phase-3.7` |
| HEAD | `5b10732f3f9213c5f584d541677e7db423603b5b` |
| 迁移版本 | `20260907_0011` |
| Docker Server | `29.7.2` |
| Docker Compose | `5.3.1` |
| Nginx 镜像 | `sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236` |
| API 镜像 | `sha256:c28f232791c7e0f39dc156b4f2762bfb9ac19055fe09e305e81dfcbcd37a21b8` |
| Website 镜像 | `sha256:fba682f220ac2f2a7a5142152623d49f375718de199950bf64584580b1bde5bb` |
| Admin 镜像 | `sha256:d35c3a6639b06f120575e977e72d558ecad6c32ecac63843d65e5b61d570f89c` |
| 本轮 run id | `20260908T135110+0800` |
| 输入 ZIP SHA-256 | `0c6211091ed79a54de3339c354f7f0e4a6941609dd1802836280d46aa3b86ee0` |

已完整阅读 `01-Local-Domain-Handoff.md` 和 `02-Codex-Instruction.txt`，并校验包内 8 项 SHA-256 清单全部匹配。附件中的说明作为实施约束参考，实际授权范围以用户本轮请求为准。

开始前 tracked tree 无修改；仓库已有多份后续未跟踪交付文档，本轮全部保留。本轮新增文件同样保持未跟踪，没有改变 index 或历史提交。

## 3. 实施内容

### 3.1 安全 Compose 启动链

新增 `docker-compose.phase37.runtime.yml`，把 API 最终命令固定为：

```text
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

最终命令不含 `alembic` 或 `seed`。这样复用现有 `postgres_data`、`minio_data`、`redis_data` 时，不会机械执行基础 Compose 中的默认 migration/Seed 链。

新增 `docker-compose.local-domain.yml`：

- 仅 Nginx 发布 `127.0.0.1:443:443`；
- API、Worker、Website、Admin、PostgreSQL、Redis、MinIO 不发布宿主端口；
- 所有服务均未使用 host network；
- CORS 仅允许裸域、www、admin、api 四个精确 HTTPS origin；
- `APP_ENV=staging`、`PUBLIC_SITEMAP_ENABLED=false` 保持。

实际容器检查显示 8 个常驻容器均为 `running/healthy`；三个原数据卷名称未变化。

### 3.2 本机 Nginx

新增 `infra/nginx/nginx.local-domain.conf`：

- 未知 Host 由 default server 拒绝；
- `www.junhuiscrewbarrel.com` 仅 308 到裸域同路径；
- 裸域代理 Website 和同源 `/api/`；
- admin 域代理 Admin 和同源 `/api/`；
- api 域只代理 API；
- 本机配置中 `auth_basic` 指令数为 0；
- 所有响应保留 noindex、安全头和 `X-Junhui-Local-Preview: loopback-only`。

原 `nginx.phase37.conf` 未改，仍有 4 处 Basic Auth 指令，因此 staging/production 默认保护没有被全局取消。

### 3.3 hosts、TLS 与代理精确规则

- hosts 创建私有备份，以 `BEGIN/END JUNHUI LOCAL PREVIEW` 标记段合并四个域名；标记段外内容与备份逐字一致。
- 四个域名各只有一条 `127.0.0.1` 映射，重复 Setup 后管理段仍只有一份。
- 复用现有 `Junhui Phase 3.7 Local CA`，为四个域名签发同一叶子证书；证书 SAN 包含裸域、www、admin、api。
- 当前用户根证书信任已存在；Edge 和 .NET 均在未跳过 TLS 校验的情况下成功访问。
- 叶子证书 SHA-1：`5D822660346FFE7DA2D5035ABD04AF6459F5986E`，到期时间 `2027-10-10T14:06:30+08:00`。
- CA SHA-256：`a6b626f723ba10ee1566a4c4de0eac1348f10566df58efe0e5a8dbaebf3ca079`。
- Clash Verge 当前活动档案只以脱敏别名记录；没有修改订阅节点、模式或其他 DNS 规则。
- 持久 Script、当前生成配置、hosts、fake-IP filter、DIRECT 规则都只加入四个精确域名；每个生成 DIRECT/host 条目各 1 个。
- `allow-lan=false`、TUN 为 Up，代理 GUI/服务/核心进程均保持运行；Mihomo `-t` 配置检查退出码为 0。
- 系统代理 bypass 保留原值并合并本站域名，没有关闭 VPN、切换全局直连或使用 `--no-proxy-server`。

正常 TLS 连接的远端地址和本地 Nginx 专用响应头共同证明请求进入本机，而不是公网站点或海外代理。

### 3.4 一键工具

新增：

- `scripts/Junhui-LocalPreview.ps1`
- `scripts/Junhui-LocalPreview-Launcher.ps1`
- `scripts/Junhui-LocalPreview-README.md`

支持 `Setup`、`Start`、`Status`、`Stop`、`Restore`，另有内部故障修复动作 `RepairProxy`。

- `Setup`：一次 UAC，安全门检查后合并 hosts、信任 CA、写入代理精确规则、创建快捷方式；不索要系统密码。
- `Start`：验证 Docker/Compose/hosts/代理/证书，按固定覆盖启动原数据栈，访问真实中文首页确认健康后打开网站。
- `Status`：只读显示脱敏代理状态、证书、域名解析、容器和 443 监听。
- `Stop`：只停止本项目容器，保留卷、hosts、证书、代理规则和快捷方式。
- `Restore`：设计为仅撤回本轮 hosts/代理/快捷方式并回到原 Phase 3.7 Basic 保护模式；本轮没有实际执行 Restore，因为验收要求结束时保留新模式运行。

Windows PowerShell 5.1 对无 BOM 中文脚本的解析不稳定，因此快捷方式通过纯 ASCII 启动桥接器按 UTF-8 显式读取主脚本。证书信任检查使用 .NET X509Store，不依赖隐藏会话中可能未加载的 `Cert:` PSDrive。

桌面快捷方式：`C:\Users\pc\Desktop\打开骏辉本地官网.lnk`。实际目标为系统 Windows PowerShell，参数调用 `Junhui-LocalPreview-Launcher.ps1 -Action Start`，启动器窗口隐藏。快捷方式实测写入 `system-powershell-utf8-launcher / healthy` 启动回执。

## 4. 真实 HTTP 与权限核验

| 检查 | 实际结果 |
| --- | --- |
| 中文/英文首页 | `200`，`loopback-only`，`noindex, nofollow`，无 `WWW-Authenticate` |
| 中文 Products | `200`，三款 Batch01 产品 |
| P01 中文 / P02 中文 / P03 英文 | 均 `200`，图片正常 |
| Admin 壳 | `200`，无 Nginx Basic；随后由应用登录控制 |
| API health | `200` |
| 匿名管理 API | `401` |
| 匿名私有附件下载 URL | `401` |
| Sitemap | `404`，仍带本机 noindex/loopback 标记 |
| www 别名 | `308` 到裸域同路径 |
| 允许的 Admin CORS 预检 | `200`，仅返回 `https://admin.junhuiscrewbarrel.com` |
| 未批准外部 Origin | `400`，无 Allow-Origin，未使用通配 CORS |

后台已使用现有真实应用账号完成表单登录，没有创建免登录管理员或扩大权限。登录后：

- `auth/me` 为 `200`；
- 不带 CSRF Header 的 logout 为 `403`，之后 `auth/me` 仍为 `200`；
- access/refresh Cookie 均为 `Secure + HttpOnly + SameSite=Lax`；
- CSRF Cookie 为 `Secure + 非 HttpOnly + SameSite=Lax`，符合双提交读取需求；
- Stop/Start 后现有应用登录会话可恢复。

Admin 首次客户端恢复时仍可观察到一次预期的匿名 `auth/me 401`，随后 refresh 后 `auth/me 200`；既有 Nuxt hydration mismatch 控制台信息仍存在。本轮没有把该既有观察项写为 PASS，也没有扩大范围修改 Admin 业务代码。

## 5. Edge 实际操作

使用全新、未配置 HTTP Basic 凭据的 Microsoft Edge/Playwright 会话；VPN/TUN 全程开启，没有网络拦截、代理禁用、TLS 跳过或 mock 正文。

| 操作 | 实际结果 |
| --- | --- |
| 桌面语言菜单 zh→en→zh | 实际点击成功，始终为 `junhuiscrewbarrel.com` |
| 375px 移动菜单 | 实际打开；Product、About、Search、RFQ、语言入口可见，后置空栏目未重新出现 |
| 375px 中文→英文 | 实际点击成功，进入 `/en/` 本地域名 |
| 中文搜索“氮化” | 命中 P01 骏辉氮化螺杆、P02 骏辉氮化机筒 |
| 中文搜索“电镀” | 命中并实际点击进入 P03 骏辉电镀螺杆 |
| P02 Gallery | 实际打开、关闭；关闭后焦点返回 `gallery-open` 按钮 |
| 后台登录 | 实际表单登录成功；无 Nginx Basic 弹窗 |

P01/P02/P03 在 Products 列表和详情的真实图片均成功解码，natural/declared 尺寸均为 `700×700`；P02 Gallery 图片也正常显示。未访问 Privacy 正文，未提交 RFQ、未上传附件。

## 6. 冻结项与数据卷复用

通过公开 API/首次 SSR 与批准基线比较：

- COPY-V1：`16/16` 文本字段逐字及 SHA-256 匹配；
- SEO-CANDIDATE-R1-V1：`8/8` title/description 逐字匹配；
- 正式 canonical 仍为 `https://junhuiscrewbarrel.com/...`，外层本机 noindex 单独保留；
- P01/P02/P03 参数值：`0/0/0`；
- 规格定义：7 个；F05 英文翻译行数：0；
- 三款产品型号和关系计数仍为 0；
- 公开产品恰为三款 Batch01；旧试点可见 Route 数为 0；
- Revision/Audit：Stop/Start 前后均为 `34/204`；
- RFQ/RFQ 附件：前后均为 `0/0`。

Stop 后 8 个常驻容器均退出、443 监听为 0；三个原数据卷、hosts 和快捷方式均保留。随后重新 Start，并比较 24 张冻结业务表：行数与内容指纹全部一致，无 mismatch。API 实际启动命令不含 migration/Seed。

## 7. 安全边界补充

- Windows 实际 443 监听只有 `127.0.0.1:443`；WLAN `192.168.31.x:443` 实测不可达。
- 宿主另有 8000/5432 监听，进程和 Docker project 归属检查确认不属于 `junhui-phase37-pilot`，本轮没有创建、修改或移除这些其他本机服务。
- 当前项目 API、Admin、Website、PostgreSQL、Redis、MinIO 均没有宿主直出端口。
- 没有公共 DNSPod 修改、上海服务器连接、公网隧道、腾讯云/NAS 操作或私钥分享。

## 8. 实施中发现并修正的问题

以下为本轮真实发生、随后修正并重新验证的工具问题：

1. 第一版生成代理规则沿用了错误 YAML 缩进，且失败回滚 regex 在大型配置上出现灾难性回溯。已改为匹配当前缩进结构并使用逐行标记删除；随后恢复原配置、重新 Setup，Mihomo 校验为 0。
2. 第一版 Start 检查业务域 `/healthz`，该路径真实返回 404，导致容器已健康但启动器超时。已改为检查真实 `/zh-cn/` 页面；Start 返回 `LOCAL_DOMAIN_LOOPBACK_PREVIEW_HEALTHY`。
3. 第一版快捷方式引用 Codex 缓存 PowerShell，耐久性不足。已改为系统 PowerShell + UTF-8 桥接器。
4. 隐藏的 Windows PowerShell 会话没有 `Cert:` PSDrive。已改为 .NET X509Store；实际快捷方式再次启动成功并产生 healthy 回执。

上述问题均没有执行业务写库、迁移、Seed、Review/Publish 或数据清理。

## 9. 实际检查记录

| 检查 | 结果 |
| --- | --- |
| PowerShell 主脚本/桥接器 AST parse | PASS：0 errors / 0 errors |
| Windows PowerShell 5.1 桥接器 Status | PASS |
| 最终 Compose 安全门 | PASS：仅 Nginx `127.0.0.1:443`，无 host network |
| 容器内 `nginx -t` | PASS：exit 0，syntax successful |
| Mihomo `-t` | PASS：exit 0 |
| hosts 标记段和外部内容比较 | PASS：1 个管理段，非管理内容保持 |
| TLS 正常校验/SAN/远端 | PASS：TLS 1.3、4 个 SAN、远端 127.0.0.1 |
| WLAN 443 / portproxy | PASS：不可达 / 0 条 |
| 本机 Basic / 默认 Basic | PASS：0 / 4 条指令 |
| noindex / Sitemap | PASS：实际响应 noindex / 404 |
| Admin 登录、Cookie、CSRF、匿名权限 | PASS |
| Edge 桌面/375px/语言/Search/Gallery | PASS |
| COPY-V1 / SEO | PASS：16/16、8/8 |
| Stop/Start + 24 表指纹 | PASS |
| 新增文件尾随空白检查 | PASS：0 findings |
| `git diff --check` | PASS：tracked diff 无错误；本轮文件为未跟踪，另做上述独立检查 |
| Ruff / API pytest / Website/Admin Vitest、typecheck、build | `NOT_RUN`：本轮只改本机 Compose/Nginx/PowerShell 工具，没有修改 Python 或前端业务模块；未复制旧测试数量 |
| Restore 实机执行 | `NOT_RUN`：结束状态必须保留新本机模式运行；恢复路径完成静态审查，未伪称实际恢复通过 |

## 10. 文件与校验值

| 文件 | SHA-256 |
| --- | --- |
| `docker-compose.phase37.runtime.yml` | `8bf8a86c5a371f67f52d73376697df0d2bfb6aefe19481d7e99c2ae9afcddf47` |
| `docker-compose.local-domain.yml` | `cb91bb2083515e5df31005030e658f24b6dcdafc22c9d05e9e050235b1ec0293` |
| `infra/nginx/nginx.local-domain.conf` | `4a992ecd6ce3374b50b0ba31dad34d5dcff51277575e7960a5b3b811bdcd67ed` |
| `scripts/Junhui-LocalPreview.ps1` | `9e8cf1f59ee031038a8ee28cd40ba38410cc6b4419aa58aa822b5f3d48ce8372` |
| `scripts/Junhui-LocalPreview-Launcher.ps1` | `1ca0baef49a1ecb0abc39adf2dba6344bec1ba13f824f66e7333d0b5a3231156` |
| `scripts/Junhui-LocalPreview-README.md` | `5804c4266c1751f5c03840adf400c582f09b08d887cd001748bdd44d51f3caf6` |

原始 hosts 备份、CA 私钥、活动代理档案标识、完整数据库指纹和后台原始截图只保留在本机私有目录，不进入共享 ZIP 或 Git。

## 11. 实际入口与交付

- 中文首页：`https://junhuiscrewbarrel.com/zh-cn/`
- 英文首页：`https://junhuiscrewbarrel.com/en/`
- 中文 Products：`https://junhuiscrewbarrel.com/zh-cn/products/`
- 后台：`https://admin.junhuiscrewbarrel.com/`
- 桌面快捷方式：`C:\Users\pc\Desktop\打开骏辉本地官网.lnk`
- 本报告：`docs/content/local-domain-preview-report.md`
- 脱敏证据 ZIP：`Junhui-Local-Domain-Preview-Evidence-20260908T135110+0800.zip`

最终状态为受保护的本机真实域名模式正在运行，等待用户直接用浏览器复验。
