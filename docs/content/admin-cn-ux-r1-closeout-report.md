# 中文后台运营化 R1：有限收尾报告

## 结论

本轮已在 `junhui-demo-r2 / phase37-local-https` 完成限定收尾，保留了已完成的 Trust 入口、询盘分页、记录回填、防串线和登录刷新。案例、知识文章、FAQ 的中文标题已在 1440px 实际页面中恢复为正常横向排版；网站总览、通用内容表单、下载、媒体和角色权限页的主要业务界面已改为简体中文。Demo 继续运行，未清库、未重导、未进入 Privacy 或生产环境。

实际工作树基线为 `a9cdca5b909d03edccf866f10106a1611f4d5936`；本轮修改仍未提交、未 push、未 merge。Docker Server 为 `29.7.2`，本地 Demo Compose 的 API、Admin、Website、PostgreSQL、Redis、MinIO 和 Worker 均为 healthy。

## 本轮修改

- `apps/admin/app/components/authority/AuthorityCrud.vue`
  - 将列表标题拆分为中文主标题、英文副标题和状态徽标，并修正网格最小宽度，避免 1440px 下中文标题被压成一字一行。
  - 技术字段改放入“技术字段”折叠区；主操作区不再直接显示原始字段代码。
  - 生命周期操作按钮补充中文显示。
- `apps/admin/app/utils/adminZhCn.ts`
  - 补齐导航状态、实现状态、下载资料类型、媒体使用角色和隐私原因的中文词表。
  - 英文业务正文、Locale、slug、权限代码和技术字段值仍保留原值；角色页以中文资源/动作矩阵作为主界面。
- `apps/admin/app/pages/downloads.vue`
  - 增加明确的“新建资料”“正在编辑”“正在加载”状态和资料类型中文下拉。
  - 保留现有保存后重新 GET 的流程，并加强深色行的文字对比。
- `apps/admin/app/pages/media.vue`、`apps/api/app/api/v1/media.py`
  - 增加媒体名称搜索、类型筛选和 48 项总数/筛选数显示。
  - 增加受保护的公开使用位置读取；只显示可公开引用，私有询盘附件不进入结果。
  - 服务端按位置和角色去重，避免同一产品主图重复显示。
- `apps/admin/app/pages/roles.vue`
  - 增加角色/权限中文搜索和当前账号实际能力提示；不修改系统角色或权限。
- `apps/admin/app/pages/site-overview.vue`
  - 网站总览的导航状态、实现状态和已知隐私原因均通过中文映射显示，未知值不直接泄漏为主界面代码。
- `apps/admin/tests/admin-cn-ux-r1-closeout.test.ts`
  - 增加本轮布局、词表、下载状态、媒体使用位置、角色搜索和总览映射的源代码契约测试。

## 实际验收结果

| 项目 | 实际结果 | 状态 |
| --- | --- | --- |
| 案例 / 知识 / FAQ 1440px | 中文标题和英文副标题均保持正常横向换行；未通过缩小浏览器或修改标题数据规避 | FIXED |
| 网站总览 | “工具入口（不进入主导航）”“站内搜索服务”“当前私有草稿（未设置公开版本）”“正式政策尚未批准发布”等显示为中文 | FIXED |
| 下载页状态 | 新建状态、编辑状态、加载状态、资料类型和深色行对比可见 | FIXED |
| 下载保存回读 | 真实 Demo 记录临时追加回读标记，保存后通过接口重新读取、刷新并重新打开；最后已通过同一后台流程恢复原中文摘要，英文摘要、文件引用和启用状态保持 | FIXED；业务数据已恢复 |
| 媒体页 | 真实读取 48/48；名称 `approved-product-01` + 图片筛选为 1/48；使用位置实际显示“产品 · 主图”，无重复位置 | FIXED |
| 角色权限 | 真实读取 112 项权限；搜索“媒体”可过滤中文权限分组；当前账号实际具有 `role.manage`，页面仅说明既有接口能力，本轮未改权限 | FIXED / 未改权限 |
| Trust、询盘分页、回填、防串线、登录刷新 | 本轮未重做，保持现有实现 | 保持 |

## 真实证据

证据根目录：

`C:\Users\pc\.codex\visualizations\2026\09\06\01a07751-0048-7712-8122-6a86b43f844b\admin-cn-ux-r1-closeout-20260910T1625+0800`

重点文件：

- `cases-1440-final.png`、`knowledge-1440-final.png`、`faqs-1440-final.png`
- `site-overview-final.png`、`site-overview-final.yml`
- `downloads-edit-final.png`、`downloads-edit-final.yml`
- `downloads-saved-reread.yml`、`downloads-postsave-reopen.yml`、`downloads-after-refresh.yml`、`downloads-final-original.yml`
- `media-final.png`、`media-search-filtered-final.png`、`media-search-filtered-final.yml`
- `roles-final.yml`、`roles-search-final.png`、`roles-search-final.yml`

下载保存流程的中间快照没有被伪造为“只读”：它记录了真实保存后的回读和随后恢复原值；最终截图对应恢复后的 Demo 数据。

## 测试与检查

- `pnpm --dir apps/admin test -- admin-cn-ux-r1-closeout.test.ts`：PASS，12 个测试文件、82 个测试通过（Vitest 配置会同时运行现有 Admin 契约集合）。
- Docker `build api admin`：PASS；API 和 Admin 镜像均重新构建。
- Admin Nuxt production build：PASS，构建中的 checker 完成，服务已重启并 healthy。
- `python -c "ast.parse(...)"`（`apps/api/app/api/v1/media.py`）：PASS。
- `git diff --check`：PASS；仅有 Git 的 LF/CRLF 提示，无空白错误。
- 真实浏览器：1440px 的案例/知识/FAQ、网站总览、下载编辑、媒体筛选/使用位置、角色搜索均完成；保存后 fresh GET、刷新和重开均完成。
- `ruff`：BLOCKED_TOOLING；当前宿主没有可调用的 Ruff，不安装全局工具。
- `pytest`：BLOCKED_TOOLING；当前宿主没有可调用的 pytest，本轮未复制旧数量为 PASS。
- `pnpm --dir apps/admin typecheck`：BLOCKED_TOOLING；Nuxt schema 写入受到本地 EPERM 阻断，未将其写成通过。
- Prettier：BLOCKED_TOOLING；当前环境没有可调用的 Prettier，未将其写成通过。

## 范围冻结与未执行项

本轮没有迁移、Seed、清库、重导、Privacy 发布、真实询盘、附件上传、发信、云/NAS连接、生产部署、DNS/Analytics 修改，也没有改变原 phase37 的 COPY-V1、8 组 SEO、三款产品参数 0/0/0、F05 英文空缺、产品媒体、旧试点或前台安全入口。Demo 继续保持 HTTPS、应用自身登录、noindex 和 Sitemap 关闭。

媒体“使用位置”本轮只核对公开业务引用；私有附件按权限继续排除。角色页验证了当前权限管理能力和搜索，不以截图宣称本轮新增了权限管理 API。原批准数据及本轮以外的未提交文件均未纳入本轮处理。

