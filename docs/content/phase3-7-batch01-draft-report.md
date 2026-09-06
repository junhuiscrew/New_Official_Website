# Phase 3.7 Batch01 隔离 Draft 导入报告

## 1. 范围与结论

- Batch ID：`JH-P37-B01-20260906`
- 工作分支：`phase-3.7`
- 实际起始/远端 SHA：`60aba2dba797cc6bb24758e12d731d6be4e57415`
- 目标：`phase37-local-https`，独立 PostgreSQL、Redis、MinIO，HTTPS + Basic Auth + 全站 noindex
- 结果：`DRAFT_IMPORT_COMPLETE`
- 发布状态：未 Review、未 Publish、未加入 Sitemap、未连接生产
- 远端操作：未 push、未 merge、未部署

本批经只读 dry-run、写入前 PostgreSQL 备份、单产品小批验证、三产品扩展和重复执行幂等验证完成。所有真实内容通过现有 Admin/API、Publication、Route、Revision、Audit 和 Media 服务写入，没有直接 SQL 改写业务状态。

## 2. 来源与完整性

指定目录 `D:/下载/Junhui-Phase3.7-Batch01/` 中 `SHA256SUMS.txt` 所列 18/18 文件均匹配。四个获批公开来源素材为：

| ID | 用途 | 原文件 SHA-256 | 原始大小 |
|---|---|---|---:|
| IMG-01 | 企业 Logo | `7c44c27b5f22565434a8d98f14ddfa54afc5b49b65169d03fb997513d063fc45` | 49,593 B |
| IMG-02 | 骏辉氮化螺杆 | `bca39ea6b85e358548da45a989f485973009a15e81c42edbf9a85501c18531da` | 157,445 B |
| IMG-03 | 骏辉氮化机筒 | `a1ff66552df181556898a115ca78a49a5e0c862df95785e6193a167d0544ef` | 126,409 B |
| IMG-04 | 骏辉电镀螺杆 | `14b8f9f9f2ce239723490b825e49433121fd86dd30c0ec69d52a4f0d50d083` | 190,515 B |

`IMG-05` 仅为字段参考，源 SHA-256 为 `d741c9bf36df7bb6a4587cb11fdb3b19266ad13a8ef9008875b946965d65e3e`，一直保留在 `references/do-not-publish/`，没有上传媒体库、关联产品、进入 SEO/GEO/Schema 或 Sitemap。

工作簿共 5 个 Sheet、5 个表，产品规格值单元格全部为空；规划 JSON 同样为 3 个产品、7 个定义、0 个规格值。未执行 OCR 数值提取。

## 3. Dry-run 与冲突处理

| 对象 | Dry-run | 实际处理 |
|---|---|---|
| Company Profile | create | 已创建双语 draft；中文全文来自用户原文，英文为未审核工作稿 |
| 分类 `screws` / `barrels` | create | 已创建双语 draft |
| P01 / P02 / P03 | create | 已创建 3 款双语 draft |
| 2 个规格组 | create | 已创建 |
| 7 个规格定义 | create | 已创建；F05 英文保持空缺 |
| ProductSpecValue | `VALUES_INTENTIONALLY_EMPTY` | 0 条 |
| Product relations | blocked | 0 条；没有权威适用关系来源 |
| IMG-01 / IMG-02 / IMG-04 | create | 已写入隔离 `public-media` |
| IMG-03 | no-op | 派生 SHA 与已有试点媒体完全一致，复用原媒体记录 |
| IMG-05 | `blocked_publication` | 未上传 |

P02 原建议 slug `nitrided-barrel` 与先前已验收试点冲突。未覆盖、未重命名旧产品，本批暂用可在后台修改的 `junhui-nitrided-barrel`。该决定只影响 draft，不构成正式 URL 批准。

## 4. 实际 Draft 数据

| 外部键 | 中文草稿名 | 英文工作名（未审核） | 分类 | Draft slug | 主图 |
|---|---|---|---|---|---|
| P01 | 骏辉氮化螺杆 | Junhui Nitrided Screw | screws | `nitrided-screw` | IMG-02 |
| P02 | 骏辉氮化机筒 | Junhui Nitrided Barrel | barrels | `junhui-nitrided-barrel` | IMG-03（复用） |
| P03 | 骏辉电镀螺杆 | Junhui Electroplated Screw | screws | `electroplated-screw` | IMG-04 |

导入后隔离库计数：Product 4（含旧试点 1）、CompanyProfile 1、ProductCategory 3（含旧试点分类 1）、SpecificationGroup 2、SpecificationDefinition 7、ProductSpecValue 0、MediaAsset 7。三款本批产品均没有 ProductModel、Material、Technology、Application 或 Solution 关系。

公司名称按用户原文保存为“舟山骏辉塑料机械有限公司”；没有自动添加“浙江”，没有倒推出成立年份或写入 `years_experience=20`，未提供的电话、邮箱、地址、面积、人数和产能保持空缺。

## 5. 规格字段字典

已建立 F01–F07 定义，值数量为 0：

1. 螺杆直径，range，mm（建议、待确认）；
2. 螺杆有效长度，range，mm；
3. 表面粗糙度，number，μm；
4. 螺杆直线度，number，mm；
5. 氮化后表面镀硬铬硬度，text，HV；英文保持空缺；
6. 镀铬层厚度，range，mm；
7. 双合金硬度，range，HRC。

Admin/API 已补齐字段分组与定义的编辑、启停、排序和安全删除，以及产品选择、规格值编辑/清空。已有值时禁止静默修改 `value_type` 或单位；被引用定义和非空分组返回 409。本轮的赋值/清空测试只使用明确的 TEST ONLY 隔离测试记录，没有向三款真实产品写假参数。

## 6. 生命周期、索引与媒体边界

- 三款产品各有 zh-CN/en TranslationStatus=`draft`、ContentPublication=`draft`；
- 六条本批 canonical Route 均 `active=false`、`indexable=false`；
- Company zh-CN/en 同样为 Translation/Publication draft，`/zh-cn/about/` 和 `/en/about/` 均关闭；
- Public Product API 返回 `total=0`；`/sitemap.xml` 因该隔离环境关闭 Sitemap 返回 404，本批 slug 未出现；
- MinIO `public-media` 实际有 7 个对象（4 个旧试点 + 本批新建 3 个，IMG-03 复用）；`private-rfq` 为 0；
- 原图只读保留在用户资料包；隔离媒体库仅保存去 EXIF、等比例 WebP 派生件，水印保留；
- 备份位于忽略目录 `data/phase3-7/batch01/batch01-preapply.dump`，459,221 B，SHA-256 `8186E3B0639C7ADBD744635E939B03F6DD64F73BDECF251AE2F51E56A8364C93`，不提交公共 Git。

## 7. 幂等与测试

| 检查 | 实际结果 |
|---|---|
| 包 SHA-256 | PASS，18/18 |
| Dry-run | PASS，状态 `ready` |
| 首个产品 apply + verify | PASS，P01 与 Company 全部 draft/closed，值和关系为空 |
| 三产品 apply + verify | PASS，P01–P03 全部 draft/closed |
| 同批重复 apply | PASS，新增 media/group/definition/value 均为 0 |
| Ruff（完整 `/app`） | PASS，`All checks passed!` |
| Backend 相关回归 | PASS，47 passed / 25.21s |
| PostgreSQL integration | PASS，8 passed / 3.43s；空测试库迁移至 `20260905_0010` |
| Admin Vitest | PASS，26 passed |
| Admin Typecheck | PASS |
| Prettier（3 个改动文件） | PASS |
| Admin production build | PASS，Nuxt 4.5.2 |
| Compose/HTTP | PASS；核心及测试服务 healthy，API live/ready=200，HTTPS health=`healthy` |

Typecheck 首次在受限沙箱中因 Nuxt 无法写忽略的 `.nuxt/schema/nuxt.schema.json` 返回 EPERM；移除该生成文件并在允许写生成目录的环境重跑后真实通过。这不是 TypeScript 诊断失败。

## 8. SEO/GEO 检查与未完成事项

本批遵循 `$seo-rank` / `$geo-rank` 的最小公开门禁：未审核的名称、英文、公司稿和空规格值不进入 Public DTO、SSR、Schema、GEO 或 Sitemap；没有把 IMG-05 的数值变成隐藏 AI facts。未建立第二套索引或发布逻辑，与冻结架构无冲突。

仍需用户在 Admin 中逐项审核：

- 三款中英文名称、摘要和 draft slug；
- Company 法定名、正式英文名与英文介绍；
- F01 的 mm 建议、F05 的技术含义及 6 个英文字段名；
- 后续真实参数值和每个字段适用产品/型号；
- 产品结构化关系。

这些待审核项不阻塞当前 draft 保存，但会阻塞 Review/Publish。任何受保护预览发布、正式发布、生产部署、DNS、旧站下线、Search Console/Bing 或 Analytics 仍需单独授权。

## 9. 本轮规格停用门禁与内容审核包（2026-09-06）

本轮没有重新导入 Batch01，也没有写入任何实际参数、Review 或 Publish 状态。后端新增规格值前会同时读取 Definition 与所属 Group：两者必须均为 `enabled`；Definition disabled/retired 返回 HTTP 409 `specification_definition_inactive`，Group disabled/retired 返回 HTTP 409 `specification_group_inactive`。已有历史值不会因停用而被级联删除，仍可按权限查看和清空；被引用的定义继续拒绝删除。Admin 新增值选择器只展示 enabled Definition 且所属 Group enabled 的选项。

从实际隔离 Admin/API 读取的公司、三款产品、主图、分类/slug 和七个字段已整理为可阅读审核包：

`docs/content/phase3-7-batch01-content-review-package.md`

审核包明确记录：

- 公司中文全文为已保存用户原文；英文名称、摘要和全文为待审核工作稿；
- P01/P02/P03 的中英文名称与摘要、分类、draft slug 和 primary media；
- F01–F07 的中文名称、英文草稿/缺失状态、类型、单位和分组；
- 旧试点 `nitrided-barrel` 与 P02 `junhui-nitrided-barrel` 的并列差异；
- 三款真实产品当前 `ProductSpecValue=0`，状态 `VALUES_INTENTIONALLY_EMPTY`；F05 未使用、无数值和无关系不构成本批审核阻塞。

本轮只读复核再次确认 P01/P02/P03 均为双语 Translation/Publication draft、canonical Route inactive/noindex，Company 也保持 draft/closed；未改变任何审核或发布状态。

### 本轮实际验证

| 检查 | 实际结果 |
|---|---|
| Backend catalog/regression（含 TEST ONLY 规格停用场景） | PASS，48 passed / 29.67s |
| PostgreSQL integration + `alembic upgrade head` | PASS，8 passed / 3.15s |
| Batch01 API verify（P01–P03） | PASS；三款 `values_intentionally_empty=true`、relations empty、routes closed |
| Admin Vitest | PASS，27 passed |
| Admin Typecheck | PASS |
| Prettier（本轮前端与审核包相关文件） | PASS，All matched files use Prettier code style |
| Admin production build | PASS，Nuxt 4.5.2 / Nitro node-server |
| Ruff（隔离一次性容器，`ruff==0.12.11`） | PASS，`All checks passed!` |
| Compose health | PASS；API/Admin/Website/PostgreSQL/Redis/MinIO/Worker/Nginx 及测试服务 healthy |

本轮已重新构建并重启隔离 API/Worker 镜像，运行中的本地后台已包含上述规格停用门禁。没有修改 migration、权限、Publication/Route 架构或真实 Batch01 内容状态。未完成项仍只需用户审核，不代表可公开发布。
