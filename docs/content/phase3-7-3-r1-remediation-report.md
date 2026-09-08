# Phase 3.7.3 R1 首发准备整改报告

- Run ID：`20260907T140215+0800`
- 唯一目标：`phase37-local-https`
- 本地入口：`https://junhui.test/`
- 分支：`phase-3.7`
- HEAD：`0fd6edabfc6d4efa8666cf49c54765b099b24300`
- 执行结论：`COMPLETED_WITH_OPEN_APPROVAL_ITEMS`
- 生产状态：`NOT_LAUNCH_APPROVED`

## 1. 执行摘要

本轮完成了 F-R1-002 中文搜索、F-R1-003 空栏目导航后置、F-R1-007 面包屑和 F-R1-005 Sitemap 候选规则的限定工程整改，并将新 API/Website 镜像更新到原有受保护隔离实例。F-R1-004 已核对 API→SSR 数据路径，没有发现接线遗漏；8 组新 SEO 元数据只形成待确认候选，没有写入 CMS。F-R1-001 只形成隐私事实表和最小待决策问题，Privacy 双语页面仍为 404，因此该 P0 阻塞仍未关闭。

本轮没有执行生产部署、DNS 变更、commit、push、merge、CMS Review/Publish、内容导入、迁移、Seed、RFQ 提交、附件上传、邮件发送、Analytics 启用或 Sitemap 端点开放。

## 2. 基线、工作区与运行版本

### 2.1 Git 基线

| 项目 | 实际值 |
|---|---|
| Branch | `phase-3.7` |
| HEAD | `0fd6edabfc6d4efa8666cf49c54765b099b24300` |
| HEAD subject | `docs(phase37): record Batch01 COPY-V1 draft update` |
| 整改开始时未提交路径 | 21 |
| 处置 | 全部保留；未回退、覆盖或自动提交 |

原 R1 审计证据的 `environment-baseline.json` 记录了当时 20 个未提交路径及哈希；审计报告生成后，整改开始时另有该报告本身，共 21 个未提交路径。本轮在其上追加整改，旧审计 HEAD 不被当作当前运行代码。

### 2.2 运行镜像

| 服务 | 整改前 Image ID | 整改后 Image ID | 最终状态 |
|---|---|---|---|
| nginx | `a8b39bd9cf0f...` | 未变 | healthy |
| website | `ebd260240e61...` | `fba682f220ac...` | healthy |
| api | `9fc31f522914...` | `8b1fa490b06c...` | healthy |
| admin | `52997f75e8cc...` | 未变 | healthy |
| worker | `6b1f2ef04a30...` | 未变 | healthy |

API 容器使用本轮私有 Compose 覆盖直接运行 `uvicorn app.main:app --host 0.0.0.0 --port 8000`，明确跳过默认的 `alembic upgrade head && python -m app.cli seed`。因此本轮服务更新没有执行迁移或 Seed。仅 API 和 Website 容器被替换，数据库、对象存储、Redis、Admin、Worker、Nginx 和数据卷均保留。

## 3. 工程整改

### 3.1 F-R1-002：中文搜索

根因经真实 PostgreSQL 复现：

- `to_tsvector('simple', '骏辉氮化螺杆')` 把整段中文作为一个词位；
- `websearch_to_tsquery('simple', '氮化')` 无法命中该词位；
- 标题 trigram 相似度在短中文查询中为 0；
- SQLite 测试分支已有 contains 后备，而 PostgreSQL 分支缺少等价的字面子串匹配。

修复在现有 PostgreSQL 查询中加入参数化、区分标题/正文的字面子串条件和稳定排序：完整标题优先，其次标题子串，再次正文子串，原 FTS/trigram 继续保留。查询仍通过原有 `_public_collection_statement` 执行语言、翻译发布、Publication、canonical、Route active/indexable、SEO noindex 和实体 enabled 门禁；没有硬编码产品或放宽隐私过滤。特殊字符 `%` 被按字面处理，不成为 SQL 通配符。

真实浏览器输入→点击结果：

| 语言/查询 | 预期与实际 |
|---|---|
| 中文“氮化” | P01、P02 均显示且可点击 |
| 中文“电镀” | P03 显示且可点击 |
| 中文“螺杆” | P01、P03 均显示且可点击 |
| 中文“机筒” | P02 显示且可点击 |
| English `nitrided` | P01、P02 均显示且可点击 |
| English `electroplated` | P03 显示且可点击 |

另在 375px 移动端完成“氮化”输入、提交和结果点击。全部最终地址保持 `https://junhui.test`，外站请求为 0。

### 3.2 F-R1-003：后置空栏目入口

Navigation API 现在按当前语言的严格公开内容决定 `primary` 键，不再无条件返回固定栏目。Desktop Header、Mobile Menu 和 Footer 只渲染 API 允许的栏目。

当前实际 API 返回：

```json
["products", "about"]
```

因此 Solutions、Materials、Applications、Capabilities、Case Studies、Knowledge 在桌面主导航、移动菜单和页脚中的入口均不再显示；Products、About、Search、RFQ 和语言切换继续保留。对应 CMS、数据模型和路由未删除，未来有符合门禁的内容时 API 会自动恢复入口。空栏目 URL 本身仍可直接访问并返回既有页面，这是“导航后置”而不是模块删除。

### 3.3 F-R1-007：中文面包屑和本地同源点击

- 中文 P01/P02/P03 现显示“首页 / 产品 / 产品名”；
- 英文仍为 “Home / Products / Product name”；
- 可见面包屑复用语言导航已有的同站 URL 解析器，把正式本站来源转换成相对路径；
- 解析器只接受精确正式 origin、HTTPS、无 userinfo、无反斜线/控制字符/异常百分号编码的地址；协议相对 URL、外站和非法输入回退到安全首页，没有任意截域名；
- 六个双语产品页分别实际点击 Products 和 Home，共 12 次，全部留在 `https://junhui.test`；
- canonical、三组 hreflang 及 Schema 的正式 URL 保持 `https://junhuiscrewbarrel.com`，未改为预览域名。

### 3.4 F-R1-005：Sitemap 候选规则

既有 `list_indexable_routes` 严格门禁保持不变。在其结果上新增统一候选层：

- 当前语言存在符合资格的公开内容时加入该语言首页；
- 当前语言存在符合资格的 Product 路由时加入产品总列表；
- owner 路由继续原样进入；
- 聚合页 `lastmod` 使用可证实的合格路由最大更新时间，不伪造当前时间；
- 去重并稳定排序。

独立测试配置验证了 XML 包含 Home、Products、分类和公开产品，并排除 draft 旧试点。对现有 phase37 数据只读计算得到 16 条候选：原 12 条 Company/分类/产品路由，加双语首页和双语 Products；旧试点不在其中。常驻预览 `/sitemap.xml` 仍为 404，开关仍关闭。

## 4. 只准备、不发布的事项

### 4.1 F-R1-004：SEO 元数据

核查结论：

- About API 已读取 `SeoDocument` 并返回 `seo.title/description`，Nuxt SSR 已消费；
- Products API 当前明确返回 `description: null`，Nuxt SSR 也已按有值才输出；
- 当前缺失来自未赋值数据，没有发现 API→SSR 接线遗漏。

因此未新增页面默认文案或隐式 fallback。已生成 `SEO-CANDIDATE-R1-V1` 的 8 组中英文候选，来源仅为已批准可见内容；状态为 `PENDING_APPROVAL / NOT_APPLIED`。

### 4.2 F-R1-001：隐私事实

已根据代码和实际配置整理 RFQ 字段、用途、RBAC、私有附件、PostgreSQL/MinIO、IP/User-Agent、访问日志、审计、候选保留阈值、Cookie、Analytics/邮件开关和未来生产差异。

仍缺法定主体与联系渠道、适用法域/法律依据、生产供应商与地区、正式保留删除政策、数据主体请求流程、生产 Cookie/第三方清单等负责人决定。当前 730 天只是代码中的 closed RFQ 候选统计阈值，任务不删除数据，不能写成已批准政策。

双语 Privacy 仍为 404，RFQ 必选同意链接仍指向这些地址。本轮未发布隐私内容，F-R1-001 继续阻塞生产 RFQ 首发。

## 5. 冻结与保护回读

### 5.1 内容冻结

更新前后通过实际受保护 Admin/API 回读：

| 检查 | 结果 |
|---|---|
| COPY-V1 16 字段 | 16/16 匹配 |
| 冻结 SHA-256 | `eb3604a43247931034745a6d3494f31c954ab9ba1b304a9d7cc7de075ec2d93b`，前后相同 |
| Company/分类/P01/P02/P03 双语生命周期 | 12/12 published、Route active/indexable |
| P01/P02/P03 参数值 | 0 / 0 / 0 |
| 七个字段定义、F05 英文 | 保持；F05 英文继续空缺 |
| 型号与关系 | 继续为空 |
| 名称、slug、分类、Logo、主图及媒体内容 | 未修改 |
| 旧试点 | closed draft；双语前台均 404 |

正常认证读取会产生会话和访问日志附带行为；本轮未把它表述成“全库绝对零写入”。没有调用内容写接口、Review 或 Publish。

### 5.2 隔离保护

| 检查 | 实际结果 |
|---|---|
| HTTPS | Edge 严格证书校验下可访问 |
| Basic Auth | Website/Admin/API 匿名均 401 |
| noindex | 匿名与认证响应均有 `X-Robots-Tag: noindex, nofollow` |
| Sitemap | 404；关闭 |
| 宿主端口 | 仅 Nginx 443；其余 phase37 服务无宿主端口 |
| 直连 origin 绕过 | 未发现 |
| 环境 | staging |
| Analytics / 营销邮件 | false / false |
| 公网隧道、生产访问 | 未创建 / 未访问 |

## 6. 验证结果

| 检查 | 本轮真实结果 |
|---|---|
| Ruff 0.12.11：`app tests` | PASS，All checks passed |
| 后端受影响回归文件 | PASS，41 passed |
| 真实独立 PostgreSQL 搜索 | PASS，2 passed |
| Website Vitest | PASS，11 files / 120 tests |
| Website typecheck | PASS |
| Website production build | PASS |
| 全项目前端 Prettier check | PASS |
| `git diff --check` | PASS；仅显示既有 Windows LF→CRLF 提示 |
| Edge 16 个核心页 | PASS，16/16 HTTP 200 且有外层 noindex |
| Edge 搜索 | PASS，6 个桌面场景 + 1 个 375px 移动场景 |
| Edge 面包屑 | PASS，6 页标签/正式 Head URL + 12 次同源点击 |
| Desktop/Mobile/Footer 后置入口 | PASS，目标空栏目链接 0 |
| 受保护边界 | PASS |
| 冻结回读 | PASS |
| Admin 测试/构建 | NOT_RUN，本轮未修改 Admin |
| Lighthouse | NOT_RUN，不属于本轮整改验证；L-R1-001 未改变 |
| 全仓无关测试、历史迁移测试 | NOT_RUN，按授权不扩大 |

测试数据库仅使用独立 `postgres-test`；没有让测试连接 phase37 业务库。Ruff 在一次性测试容器中安装项目已锁定版本，没有全局安装或修改项目依赖。

### 6.1 过程中的非产品失败

为避免把工具问题伪装成产品通过，记录如下：

- 首次通过 `pnpm exec prettier` 调用时 Windows shim 未找到命令；改用项目内 `.CMD` 后专项和全量格式检查通过；
- 首次 typecheck 因 linked worktree 写 `.nuxt` 遭沙箱 EPERM；在批准权限下重跑通过；
- 浏览器采集脚本前三次分别遇到 SPA load 等待竞态、移动端选中隐藏桌面入口、Node 请求客户端不读取 Windows 用户 CA；修正采集脚本后从头完整重跑并通过，只有最终成功 JSON 作为验收结果；
- 边界脚本首次漏传必填 RunId，未执行检查；补参数后实际通过；
- 一次内联 Sitemap 采集命令发生 shell 引号语法错误，未查询数据库；随后改用只读脚本成功得到 16 条候选。

## 7. Findings 状态

| ID | 状态 | 说明 |
|---|---|---|
| F-R1-001 | `WAITING_APPROVED_PRIVACY_FACTS_AND_COPY` | 事实已整理；Privacy 404 和 RFQ 法务阻塞未关闭 |
| F-R1-002 | `REMEDIATED_VERIFIED` | CJK 子串、英文回归、真实 PostgreSQL 和浏览器点击均通过 |
| F-R1-003 | `REMEDIATED_VERIFIED` | 三处导航后置；CMS/路由可恢复 |
| F-R1-004 | `WAITING_METADATA_APPROVAL` | 无接线缺陷；8 组候选未应用 |
| F-R1-005 | `REMEDIATED_CODE_VERIFIED_PREVIEW_DISABLED` | 候选/XML 测试通过；预览端点仍 404 |
| F-R1-006 | `ACCEPTED_LIMITATION` | 无真实 offers/review/评分，不伪造富结果字段 |
| F-R1-007 | `REMEDIATED_VERIFIED` | 中文标签、同源点击、正式规范 URL 均验证 |
| L-R1-001 | `NOT_RUN_UNCHANGED` | 本轮未引入 Lighthouse |

## 8. 交付与下一步

仓库内交付：

- `docs/content/phase3-7-3-r1-remediation-report.md`
- `docs/content/privacy-facts-and-questions.md`
- `docs/content/seo-metadata-candidates.md`
- `docs/content/seo-metadata-candidates.json`

私有证据包括脱敏检查 JSON、Sitemap 候选、冻结/边界结果、环境记录、真实截图、manifest 和 SHA256SUMS。受保护预览继续运行，等待 Privacy/SEO 文案决策和前台复验。本报告不宣布 Phase 3.7 完成，也不构成生产上线许可。
