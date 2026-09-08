# 官网首页模块后台使用说明

## 入口

- 后台登录：`https://admin.junhuiscrewbarrel.com/login`
- 首页模块编辑器：`https://admin.junhuiscrewbarrel.com/homepage`
- 全站模块总览：`https://admin.junhuiscrewbarrel.com/site-overview`

这些地址只用于当前本机 `phase37-local-https`。后台继续使用应用自己的账号、RBAC、CSRF 与 Secure Cookie。

## 日常编辑流程

1. 登录后打开“Homepage”。
2. 在“简体中文 / English”标签间切换；两种语言分别保存和应用。
3. 使用“上移 / 下移”调整模块顺序。
4. 使用“启用此模块”控制普通首页显隐。完整布局预览仍会保留隐藏位置并说明原因。
5. 在“视觉样式”中选择该模块允许的有限 variant。
6. Hero 与 Core Product Families 可勾选最多三款现有已发布产品；此操作不会修改产品精选状态或关系。
7. 点击“保存草稿”。页面会回读新的 Revision；出现冲突时不会覆盖服务端修改。
8. 点击“打开完整预览”，检查全部十四模块、空态和管理入口。
9. 确认后才点击“应用布局”。应用需要 `content.publish`，保存草稿只需要 `content.update`。

## 恢复

“从应用版恢复草稿”会把当前应用版复制为一个新的草稿 Revision，不会直接改变普通首页。恢复后仍应重新预览；如果需要让普通首页变化，再单独应用。

## 内容从哪里维护

首页编辑器只保存布局和引用，不复制业务正文：

- 公司名、简介、Why Junhui：Company/Trust 后台；
- 产品和分类：Catalog；
- Materials、Applications、Technologies、Solutions：Catalog 对应模块；
- Manufacturing Capability、Factory & Equipment、Certificates/Patents：Trust；
- Case Studies、Knowledge：各自后台模块；
- Privacy：Privacy 后台，但当前只有私有 draft，未获准发布。

“全站模块总览”中的数量来自实际 API。公开数量为 0 时，应补充并走正常内容生命周期，不能用首页布局伪造内容。

## 当前限制

- 普通首页当前真实显示 4 个模块；其余 10 个只有 renderer、配置入口和诚实空态。
- RFQ 页面可打开，但没有当前获准的已发布 Privacy 版本，因此正式提交保持禁用。
- 本机入口保持全站 noindex，Sitemap 关闭；不要把认证预览链接当公开网址。
