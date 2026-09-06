# Phase 3.7.1 资料盘点与只读预检执行计划

> **执行范围：** 仅完成 Phase 3.7.1；不写真实内容数据库、不上传真实素材、不发布、不部署。

**目标：** 以 `phase-3.6-fix` 已验收基线为依据，核对现有 CMS 能力，登记用户明确提供的真实资料，形成可审计的只读 dry-run、最小待确认清单和下一批试点计划。

**架构约束：** 继续复用 Master Entity + Translation + Publication + ContentRoute + Revision + Audit + RBAC，以及后端统一 SEO/GEO、public-media/private-rfq 隔离。所有真实业务事实在来源、技术审核、英文审核和公开许可确认前保持缺失或阻塞。

---

## 任务 1：固定基线与输入边界

**检查对象：** Git 工作区、Phase 3.6 报告、Phase 3.7 交接包、用户明确指定的产品图片目录、已附 Logo/工厂图片、旧官网只读页面。

1. 核对 HEAD、分支、远端基线和未提交修改。
2. 只读取用户明确提供或指定位置，不扫描无关目录。
3. 将 QA fixture 与真实经营资料明确隔离。

## 任务 2：源码级 CMS 能力盘点

**检查对象：** `apps/api/app/modules/`、`apps/api/app/api/v1/`、`apps/admin/app/`。

1. 从模型、Schema、服务和 Router 核对 Company、Catalog、Authority、Trust、Media 的实际字段与生命周期入口。
2. 从 Admin 页面和 composable 核对现有编辑、媒体、Review、Publish、Archive 操作。
3. 核对真实权限、Revision/Audit、SEO/GEO 和媒体安全边界，不凭旧报告推断。

## 任务 3：资料与 dry-run 登记

1. 汇总已收到文件的数量、格式、尺寸、哈希重复、元数据风险与公开许可状态。
2. 建立产品/参数来源、媒体授权与脱敏、中英文术语和首批内容地图。
3. 规划一个真实产品的完整内容链，但不代替用户选择产品或确认技术事实。
4. 按 `create / update / no-op / conflict / blocked` 输出只读预检结果，并检查 slug、关系、单位、重复和许可。

## 任务 4：环境与后续执行准备

1. 核对本地 Docker/PostgreSQL/Redis/MinIO/API/Website/Admin 的只读可用状态。
2. 准备媒体 QA、性能、受保护非生产环境、SEO/GEO、备份恢复和发布清单。
3. 明确 3.7.2 的输入门槛：具体批次、真实来源、公开许可、审核责任人与非生产目标确认。

## 任务 5：报告与验证

**新增文件：** `docs/architecture/phase3-7-1-readiness-report.md`

1. 写入实际基线、资料清单、CMS 映射、dry-run、环境、最小待确认清单和下一批试点计划。
2. 明确状态为 `PREPARATION_COMPLETE / WAITING_FOR_INPUT`，不宣称 Phase 3.7 完成。
3. 运行文档格式、敏感信息扫描、Git diff/status 检查；记录真实命令和结果。
