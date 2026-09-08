# Phase 3.7 Batch01 COPY-V1 受保护预览执行报告

## 1. 执行结论

- 运行编号：`20260907T092737+0800`
- 实际目标：`phase37-local-https`
- 本地入口：`https://junhui.test/`
- 分支：`phase-3.7`
- 执行时 HEAD：`0fd6edabfc6d4efa8666cf49c54765b099b24300`
- CMS 生命周期结果：**完成**。白名单内 6 个 owner、2 个语言，共 12 个 owner/locale pair 已通过现有 Review/Publish API 到达 published。
- 受保护入口：**保持**。HTTPS、Basic Auth、网关 `X-Robots-Tag: noindex, nofollow`、Sitemap 关闭均已复核。
- 前台视觉验收：**未全部通过**。文字、路由、状态、移动布局、空规格隐藏和 RFQ 来源正常；三款产品图片因现有媒体记录缺少 `width/height` 而显示“图片暂不可用”。
- 当前处置：未修改媒体元数据，未扩大本轮写入范围；受保护预览仍保留，供用户查看本次真实结果。未宣布 Phase 3.7 完成。

## 2. 授权与目标绑定

已完整读取并核对：

- `Junhui-Batch01-Protected-Preview-Handoff.md`
- `preview-authorization.json`

授权记录与实际环境均绑定到 `JH-P37-B01-20260906`、`COPY-V1`、`phase37-local-https` 和 `phase-3.7`。确认包内 4 个文件的 SHA256 清单为 4/4 匹配。预览授权 JSON 的 SHA256 为：

`242b4b53aa248f9bc4fb5d9028913fe65ab5aa9e5e1b18b1046f738159489741`

发布前确认 Git 工作区已有状态被保留：`README.md` 为既有修改，`交接文档-新对话.md` 为既有未跟踪文件；本轮未重置、覆盖或清理这些内容。

## 3. 发布前门禁与备份

发布前实际 Admin/API 回读结果：

- COPY-V1：16/16 字段 SHA256 完全匹配；未重新翻译、润色或写入正文。
- 冻结字段快照 SHA256：`eb3604a43247931034745a6d3494f31c954ab9ba1b304a9d7cc7de075ec2d93b`。
- P01/P02/P03 参数值：各 0。
- 三款产品型号及四类关系：全部为空。
- F05 英文定义：继续缺失。
- 名称、slug、分类、Logo、主图、featured、七个规格定义：与发布前快照一致。
- 旧试点 `injection-molding-machine-barrels/nitrided-barrel`：双语 draft，Route 关闭且不可索引。
- IMG-05：未进入三款产品公开关联。

已在私有、Git 忽略目录保存：

- PostgreSQL 发布前 custom-format 备份，并使用 `pg_restore --list` 成功读取目录（1361 TOC entries）。
- 完整 Admin/API 生命周期快照。
- Revision/Audit 发布前摘要。

私有备份不进入验收 ZIP，也不提交 Git。

## 4. 外层保护检查

发布前、第一阶段发布后及全部发布后均复核：

- 匿名访问 website、admin、public API：HTTP 401，并带 `X-Robots-Tag: noindex, nofollow`。
- 认证访问 website、admin、public API：HTTP 200，并带 noindex。
- `/sitemap.xml`：HTTP 404，Sitemap 保持关闭。
- `/healthz`：唯一无需 Basic Auth 的健康端点，HTTP 200，仍带 noindex。
- Compose 项目仅 Nginx 暴露宿主机 `443:443`。
- website 3000、admin 3001、API/worker 8000、PostgreSQL 5432、Redis 6379、MinIO 9000 均只有容器内部端口，没有 phase37 宿主机映射。
- `APP_ENV=staging`；Analytics、营销邮件与公开隧道均未启用。

本机另一个无关 Docker 项目占用宿主机 8000；经容器标签和端口映射核实，它不属于 `junhui-phase37-pilot`，phase37 API 本身没有暴露 8000。

## 5. CMS Review/Publish 实际执行

执行顺序：

1. CompanyProfile zh-CN/en；
2. `screws` zh-CN/en；
3. `barrels` zh-CN/en；
4. P01 zh-CN/en，并进行小步前台回读；
5. P02 zh-CN/en；
6. P03 zh-CN/en。

所有状态变更均调用现有 CMS/API，使用真实账号权限、会话 Cookie 与 CSRF；没有直接 SQL 改状态，没有伪造审核人、审核时间或扩大权限。

有效结果：

- Review + Publish：12 pair。
- 发布前已达目标状态的 no-op：0 pair。
- 一次本地证据清单脚本在 Company 双语已成功发布后中断；重入时依据发布前快照将这 2 pair 识别为本轮已完成并 no-op，没有重复审核或重复发布。
- 最终 TranslationStatus：12/12 `published`。
- 最终 Publication：12/12 `published`。
- 最终内部 canonical Route：12/12 `active=true`、`indexable=true`。
- 外层 Nginx Basic Auth/noindex 与内部 Route 状态相互独立，外层保护未关闭。

## 6. Revision 与 Audit 摘要

- ContentRevision 总数：发布前 15，发布后 15；纯生命周期操作未伪造正文 Revision。
- Audit 总事件数（仅本轮白名单 owner）：发布前 24，发布后 60，新增 36。
- 新增事件组成：12 个 `translation.review`，以及 24 个 `publication.status_change`（draft→review、review→published）。
- 实际审核账号数：1，报告中记为 `REVIEWER-01`。
- 发布后已发布翻译数：12。

## 7. 发布后内容与状态回读

发布后重新读取实际 Admin/API：

- 16/16 COPY-V1 字段哈希继续匹配。
- 冻结字段哈希仍为 `eb3604a43247931034745a6d3494f31c954ab9ba1b304a9d7cc7de075ec2d93b`。
- P01/P02/P03 参数值仍各为 0；型号和关系仍为空。
- F05 英文继续缺失。
- 旧试点及其分类继续 draft、Route 关闭；真实旧试点前台 URL 返回 404。
- 没有新增产品、分类、型号或关系。

## 8. 真实前台验证

使用真实 Chrome 和本地 HTTPS 入口完成以下检查：

- 中英文首页、About、产品列表；
- `screws`、`barrels` 中英文分类页；
- P01/P02/P03 中英文详情页；
- 旧试点排除页；
- 375px、320px 移动视口；
- Gallery 打开、焦点进入关闭按钮、Escape 关闭及焦点返回；
- RFQ 从 P03 实际点击进入，并保留 `source_type=product`、`source_slug=electroplated-screw`；未提交、未上传、未发邮件。

结果：

- 16 个应公开的页面均为 HTTP 200，文字检查匹配，响应带 noindex。
- 旧试点页面为 HTTP 404，响应带 noindex。
- 产品列表仅出现 P01/P02/P03；没有旧试点链接。
- 三款详情的空规格区均隐藏。
- 375px 与 320px 最终稳定状态均无横向溢出。
- 语言菜单已实际打开。菜单中的 English alternate 使用正式 canonical 地址；为遵守“所有实际导航留在本地”，未点击该外部地址，而是直接使用 `https://junhui.test/en/` 完成英文页面验证。正式 canonical 地址未被作为预览入口，也未访问生产站。

### 媒体视觉检查：未通过

三张产品图的实际媒体接口检查：

- IMG-02：匿名 401；认证 200；`image/webp`；15374 bytes；noindex。
- IMG-03：匿名 401；认证 200；`image/webp`；10492 bytes；noindex。
- IMG-04：匿名 401；认证 200；`image/webp`；16528 bytes；noindex。

文件并未丢失，但现有媒体记录的 `width`、`height` 均为空。前端 `PublicImage` 只渲染具有正整数固有尺寸的图片，因此三款详情和 Gallery 对话框显示“图片暂不可用”。本轮未获授权修改媒体元数据，故没有回填尺寸或改动图片。该项在 `preview-checks.json` 中明确为 FAIL，不写成 PASS。

## 9. 截图与证据

本轮生成 14 张实际截图，覆盖：

- 中英文首页；
- 中英文 About；
- 中文产品列表；
- P01 中英文详情、P02/P03 中文详情；
- 语言菜单打开；
- Gallery 打开；
- RFQ 来源入口；
- 375px 与 320px 移动端详情。

所有截图均已人工查看。截图如实保留媒体占位状态，没有伪造正常图片。

## 10. 未执行与边界

- 未执行生产发布、部署、DNS 修改、公开隧道、搜索引擎提交或 Analytics 启用。
- 未 push、merge 或修改 GitHub 仓库公开/私有设置。
- 未提交 RFQ、未上传附件、未发送邮件。
- 未重新导入正文、产品或媒体。
- 未运行与本次纯内容生命周期无关的全量测试；因此未将全量测试写为 PASS。
- 未撤回已批准内容：当前入口仍受 Basic Auth 和 noindex 保护，且保留预览便于用户确认上述真实视觉问题。

## 11. 当前状态与下一步

受保护预览服务仍运行在本机 443 端口。当前可用于检查 COPY-V1 文案、页面结构与流程，但产品图视觉项尚未达到验收通过标准。等待用户前台视觉验收及后续是否单独授权修复媒体尺寸元数据/本地 alternate 链接；在新授权前不继续修改。
