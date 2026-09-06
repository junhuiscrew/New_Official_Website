# Phase 3.7.2 首批产品 Draft Import 技术设计

## 1. 目标与批准边界

本设计只实现 Phase 3.7.2 的首批产品草稿闭环，不包含受保护预览发布、生产部署或 Phase 3.7.3。

批准的首批业务对象为：

- 分类：注塑机料筒；
- 产品：注塑机氮化料筒；
- 媒体：同一产品的四张已确认图片；“日精注塑机氮化料筒”图片留到下一批；
- 来源：用户指定的旧官网产品页，仅采用页面中明确且没有内部冲突的事实；
- 审核责任：中文与英文均由用户本人审核；模型生成或整理的译文只能保持 Draft；
- 媒体处理：允许裁切、缩放、压缩、转 WebP、删除 EXIF 和生成缩略图；
- 目标：仅本机可访问的隔离 HTTPS 环境；
- 状态：TranslationStatus 与 ContentPublication 保持 `draft`，ContentRoute 保持 inactive + noindex。

本轮不创建 Material、Technology、Application、Solution、ProductModel、Case、Expert、Certificate 或其他缺少明确来源的实体，也不导入任何冲突参数。

## 2. 采用方案

采用 API 优先的幂等试点导入，而不是直接写数据库或对象存储：

1. 使用一个私有 batch manifest 保存源文件哈希、审批范围、目标环境、API 返回的实体/媒体 ID 和导入状态。
2. 通过既有 Authentication、Media、Catalog API 执行上传与写入。
3. 通过既有服务创建 TranslationStatus、ContentPublication、ContentRoute、Revision 与 Audit。
4. 同一 manifest 再次运行时先比对源哈希和远端实体状态，只产生 `no-op`，不重复上传或创建。
5. 私有 manifest、原图、派生图、凭据、备份和恢复文件保留在 Git ignore 覆盖的本地目录，不进入公共仓库。

该方案保持现有 **Master Entity + Translation + Publication + Route + Revision + Audit** 架构，不增加新表、不修改 `0001–0010` migration，也不建立第二套 CMS。

## 3. 隔离 HTTPS 环境

新增一个 Phase 3.7 专用 Compose overlay 和 Nginx TLS 配置，使用独立 Compose project、PostgreSQL volume、Redis volume 与 MinIO volume。三个本地域名为：

- Website：`https://junhui.test`；
- Admin：`https://admin.junhui.test`；
- API：`https://api.junhui.test`。

本地 hosts 映射、TLS 私钥、Basic Auth 文件和随机凭据不提交 Git。证书由本地脚本生成，证书信任和 hosts 安装是显式本机操作。Nginx 对三个入口均增加 Basic Auth 和 `X-Robots-Tag: noindex, nofollow`；健康检查端点可以免认证，但不返回业务内容。

Website 与 Admin 的浏览器请求仍走各自同源 `/api/v1` 代理。API 独立域名只用于调试和导入，并同样受 Basic Auth 保护。正式 canonical、hreflang 和 Schema origin 继续是 `https://junhuiscrewbarrel.com`，不得改为 `.test` 域名。

## 4. CMS 最小维护接线

现有 `products.primary_media_id` 已在数据库中存在，但 Product API schema、service 和 Admin 表单没有完整暴露。本轮只补已有字段的接线：

- Product create/update schema 接受可空 `primary_media_id`；
- service 验证目标 MediaAsset 属于 `public-media`、状态为 ready、对象可用，再写入产品；
- Product detail/list DTO 返回 `primary_media_id`；
- Admin Product 页面可从公开 Media Library 选择主图；
- Admin Product 页面完整读写 `short_description`、`description` 与 `highlights_jsonb`；
- 修改上述字段继续走既有 Revision/Audit 和翻译编辑失效逻辑。

本轮不增加产品 Gallery 数据表。四张图片均作为已登记公开媒体上传，其中一张设置为 Product 主图；其余媒体通过双语 metadata 和私有 batch manifest 保持归属。若未来需要公开多图 Gallery，应在独立、经确认的数据模型变更中处理，不能在本轮用非结构化字段伪造关联。

## 5. 内容与参数映射

### 5.1 草稿对象

- ProductCategory external key：`junhui:product-category:injection-molding-machine-barrels`；
- Category slug：`injection-molding-machine-barrels`；
- Product external key：`junhui:product:nitrided-barrel`；
- Product slug：`nitrided-barrel`；
- 中文草稿名称：注塑机氮化料筒；
- 英文草稿名称：Nitrided Barrel for Injection Molding Machines。

英文名称和正文是待用户审核的 Draft，不得自动标记为 human reviewed。

### 5.2 参数规则

允许整理为结构化规格的事实必须在指定旧官网页面内部一致。每个规格在私有 fact register 中保存来源 URL、页面位置、原文、标准化值、单位和适用范围。

以下发生内部冲突的字段不写入 ProductSpecValue：

- 直线度；
- 镀硬铬硬度；
- 镀层厚度；
- 双合金硬度。

旧页中无冲突但语义或适用对象仍不明确的值也保持 `blocked`。不得把螺杆参数自动归到料筒，不得进行 HV/HRC 换算，不得修正文案中的单位或工艺含义后冒充来源事实。

### 5.3 媒体处理

每张批准图片执行：

1. 校验 JPEG 解码、实际 MIME、尺寸和 SHA-256；
2. 生成固定质量的 WebP 网站副本；
3. 删除 EXIF；
4. 保持真实产品像素内容，不做生成式重绘、设备增删或事实性修图；
5. 写入中文和英文 alt/title/caption Draft metadata；
6. 通过公开媒体 API 上传到隔离 MinIO 的 `public-media`；
7. 验证浏览器 URL 不暴露 Docker 内部 `minio:9000`。

## 6. 导入流程与失败处理

导入命令分为 `dry-run` 和 `apply`：

1. 校验当前 Git SHA、目标环境标识、数据库指纹、MinIO endpoint 和 batch ID。
2. 校验本批四个源文件的哈希与授权清单；任何额外文件都拒绝处理。
3. 检查 category/product slug、双语记录和 manifest 映射，输出 `create / update / no-op / conflict / blocked`。
4. `apply` 前完成目标数据库备份和恢复到独立校验库的演练，并保存脱敏结果。
5. 逐张生成派生副本并调用 Media API；成功后写入媒体多语言 metadata。
6. 调用 Catalog API 创建分类和产品 Draft，并将首图设置为 `primary_media_id`。
7. 只创建已通过无冲突检查的规格定义和值；本批不建立推断关系和型号。
8. 读取 Product detail、TranslationStatus、Publication、Route、Revision 与 Audit，证明生命周期仍为 Draft。
9. 任一步失败时只删除本次尚未被实体引用的新增对象；不清空数据库、卷或 bucket，不修改既有 QA/真实内容。

如果目标中已存在同 slug 实体但不在本 manifest 映射内，结果必须是 `conflict`，不自动覆盖。

## 7. 测试策略

所有行为修改遵循测试先行：

- Backend schema/service/API：主媒体合法性、私有/未就绪媒体拒绝、Product DTO、Revision/Audit；
- PostgreSQL integration：创建 Draft 后只有 draft Publication 和 inactive/noindex canonical Route；
- Import tool：dry-run 分类、源哈希限制、幂等 no-op、外部同 slug 冲突、敏感字段不输出；
- Media processing：WebP 可解码、尺寸合理、EXIF 删除、SHA-256 可复算；
- Admin Vitest：主图选择、双语摘要和 highlights 正确提交；
- Typecheck、Prettier、Ruff、相关 backend tests、production build；
- 隔离 Compose：HTTPS、Basic Auth、noindex、Website/Admin/API health、MinIO 对象存在；
- SEO/GEO：Draft 不进入 Public DTO、Sitemap、hreflang、Schema 或 GEO visible source。

未运行写 `NOT RUN`，环境阻塞写 `BLOCKED`，功能失败写 `FAIL`，不能复用旧报告的测试数量。

## 8. 交付物与停止点

本批交付：

- 可复跑的通用导入与图片派生工具；
- 不含真实资料和凭据的 manifest schema/example；
- CMS 最小维护接线及回归测试；
- 隔离 HTTPS 配置和本地启动说明；
- 私有实际 batch manifest、备份/恢复结果和脱敏证据；
- `docs/content/phase3-7-pilot-report.md`。

完成 Draft Import 后停止并等待用户在 Admin 核对中文和英文内容。本批不调用 Translation Review、Publication Publish 或公开 Route 激活操作；用户的 Draft Import 授权不等于受保护预览发布授权。
