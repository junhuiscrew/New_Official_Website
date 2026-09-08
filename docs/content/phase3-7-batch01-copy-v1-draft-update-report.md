# Phase 3.7 Batch01 COPY-V1 草稿更新报告

## 1. 结论

本次有限草稿更新已在此前批准的 `phase37-local-https` 隔离实例完成。

- 实际更新：16 个文本字段
- 初始 no-op：0 个字段
- 冲突：0 个
- 新建 Company/Product：0 条
- CMS Review：未执行
- Publish / 上线：未执行
- push / merge / deploy：未执行
- 最终回读：16/16 与已确认 COPY-V1 逐字一致

保存后的 TranslationStatus 与 Publication 均保持 `draft`，产品 Route 均保持 `active=false`、`indexable=false`。当前工作停在草稿阶段，等待受保护预览的单独授权。

## 2. 实际目标与代码版本

| 项目 | 实际值 |
| --- | --- |
| 隔离实例标签 | `phase37-local-https` |
| Website | `https://junhui.test/` |
| Admin | `https://admin.junhui.test/` |
| API | `https://api.junhui.test/api/v1/` |
| 工作区 | `.worktrees/phase-3.6` |
| Git 分支 | `phase-3.7` |
| 执行时 HEAD | `afe99c3` |
| 批次 | `JH-P37-B01-20260906` |
| 文案版本 | `COPY-V1` |
| 保存时间 | 2026-09-06 23:51:16（Asia/Shanghai，审计时间 15:51:16 UTC） |

本次保留了工作区中原有的后续提交与未提交工作，没有 reset、checkout、stash 或覆盖无关文件。执行前已有的 `README.md` 修改和 `交接文档-新对话.md` 未跟踪文件均未被本次操作改写。

## 3. 确认包与内容哈希

确认包位于本地 `D:\下载\Junhui-Phase3.7-Batch01-Copy-V1-Confirmed\`。执行前完整读取了：

- `Copy-V1-Confirmation.md`
- `copy-v1-confirmation.json`
- `approved-source/` 下全部原文案与说明文件

确认包中 7 个文件均通过 `SHA256SUMS.txt` 校验。关键哈希如下：

| 内容 | SHA-256 |
| --- | --- |
| `Batch01-Bilingual-Copy-Candidate-V1.md` | `133ba6b95751ab03e6b2a4475779240be055e78af0886dd19ae7a142b460be0d` |
| `copy-v1-confirmation.json` | `8ec8df022fa0a346480d13c186cad80384f78deca9bfb70a0a8157382f86f7b9` |
| `company-original-zh.txt` | `14e0cf1874069aed605ba776db924326220bc8c953dbc11a327d3aec05a5b82e` |

`copy-v1-confirmation.json` 仅被用作内容记录和逐字段比对来源，没有被直接当作完整 API 请求体提交。请求体由当前 CMS 实体回读结果构造，只替换获准的 16 个字段。

### 16 个字段的保存后哈希

| 对象 | 语言 | 字段 | SHA-256 |
| --- | --- | --- | --- |
| Company | zh-CN | `short_intro` | `16b22465ec9d7decfb5fcb8f449eda39cdfd20d5bf1517a4b34067189176c274` |
| Company | zh-CN | `full_intro` | `e46b45ef1530e0a666bde71de7daa3355130de1d0fb447794114324213df2300` |
| Company | en | `short_intro` | `e3a02439326f09083ff303d3c8d78a901b3b3cea463d07e4487c5e4ea163a757` |
| Company | en | `full_intro` | `7ce24e5515f53a11a6f50a2492f6622e3ab065f54c1e96f0f12161302dc09159` |
| P01 | zh-CN | `short_description` | `e8fd58a8f5b734401501fb5db80e93fc21cfa05777b005a580e4e8f13f6f1123` |
| P01 | zh-CN | `description` | `2519f679cc1b2d018c428eb3ac3c816a9d23cc1d64ae3fe62d7ab34df597d229` |
| P01 | en | `short_description` | `f6392f8fcacf5ca5cffc56820f03a76f328d74fb0375fe2484f496c75c405fdf` |
| P01 | en | `description` | `783ae3747e37ecda8f6aefd5e0562bfde7d9e84e081f8a22529148703a8d6901` |
| P02 | zh-CN | `short_description` | `ac2aa6b6153aa9a7e50b555df1b848b030735aab76a6cb32f14657b0c8a25b7b` |
| P02 | zh-CN | `description` | `ca982a85fcb37b740bfa87dff1717e84bd60ee1bae73fccff6a09d091060ae69` |
| P02 | en | `short_description` | `c343126b5d0941344b2e8ef75a1ceb28119131a6222b8933070d00fcc3f425a3` |
| P02 | en | `description` | `d9487326eca602b020b059cf677c14c09195e98aa006fb737fef1175ef2d60b4` |
| P03 | zh-CN | `short_description` | `5d244d56f0e3b1251c3586b0a7ded8809d7fdff67996537be03622b3a1a8349a` |
| P03 | zh-CN | `description` | `b44b8a2ac1a87f264f86632f5c5a8237222a15b0d29b21aa9272f4e8c934f03b` |
| P03 | en | `short_description` | `312e7b3c3def02fe3a22bc8fab99ae1e23c6593b398a4b4f8112cc3a21c3af0e` |
| P03 | en | `description` | `6fa5714949ea47d75b31fdf2dab35672a9c6dface2b90e2227b1ebf2852be85b` |

## 4. 写入前冲突保护

写入前先通过实际 API 读取 Company、P01、P02、P03 的当前草稿，并读取对应最新 Revision/Audit。随后执行三组校验：

1. 当前 16 个字段必须与 Batch01 原始草稿基线一致，或已经与 COPY-V1 一致；
2. 当前 Revision 必须与准备请求时读取的 Revision 一致；
3. 名称、分类、slug、Logo、主图、字段定义、型号、关系、参数值、旧试点和生命周期状态必须符合冻结基线。

结果为 16 个待更新、0 个 no-op、0 个冲突。Company 中文原始介绍的文件结尾换行按源文件原样参与哈希比对，没有被误判为人工修改。未发现需要停止的人工修改，因此才进入保存阶段。

保存前完整快照保存在本地忽略目录：

- `data/phase3-7/batch01/copy-v1/copy-v1-pre-update-snapshot.json`
- `data/phase3-7/batch01/copy-v1/copy-v1-revision-audit-before.json`

这些文件包含草稿内容和内部实体标识，不纳入公共 GitHub 提交。

## 5. 实际保存操作

保存使用现有 CMS/API、现有权限模型、Basic Auth、Admin 会话、CSRF、Revision 与 Audit 链路：

- Company：1 次现有 Company Profile 更新请求，更新 zh-CN/en 的 `short_intro`、`full_intro`；
- P01/P02/P03：各 1 次现有 Product 更新请求，更新 zh-CN/en 的 `short_description`、`description`；
- 总计：1 次 Company 请求、3 次 Product 请求、16 个字段更新；
- 未重新导入数据，未创建重复产品，未修改产品名称或其他字段。

保存返回摘要：

```json
{
  "status": "applied",
  "updated_fields": 16,
  "no_op_fields": 0,
  "company_request_count": 1,
  "product_request_count": 3
}
```

## 6. Revision 与 Audit 摘要

### Revision 变化

| 对象 | zh-CN | en |
| --- | --- | --- |
| Company | 1 → 2 | 1 → 2 |
| P01 | 1 → 2 | 0 → 1 |
| P02 | 1 → 2 | 0 → 1 |
| P03 | 1 → 2 | 0 → 1 |

共新增 8 条按语言记录的 Revision。三个产品的英文 Revision 从 0 到 1，是因为初始产品创建历史只在默认中文语言下保存了一条聚合创建快照；本次编辑按当前 CMS 规则为每种语言分别写入 Revision。

### Audit 增量

| Audit action | 新增数量 | 说明 |
| --- | ---: | --- |
| `company_profile.update` | 1 | Company Profile 保存 |
| `product.update` | 3 | P01/P02/P03 各一次保存 |
| `translation.edited` | 6 | 三款产品的中英文翻译编辑 |
| `publication.invalidated_by_translation` | 8 | 现有生命周期服务对 4 个对象、2 种语言执行发布失效保护 |

`publication.invalidated_by_translation` 是既有保存链路自动产生的保护审计，不代表发布。保存前后 Publication 均为 `draft`。Audit 中没有新增 translation review、publication review、publish 或伪造审核人记录。

## 7. 保存后实际回读

保存后重新通过已认证的实际 Admin API 读取 Company 与三个产品，并重新计算字段哈希：

- 16/16 字段与 COPY-V1 一致；
- 0 个字段不一致；
- 第二次校验中的 16 个字段全部表现为 no-op，说明已保存值与确认值相同；这不改变本次初始保存的“更新 16、初始 no-op 0”统计。

完整可读文本见 [phase3-7-batch01-copy-v1-readback.md](./phase3-7-batch01-copy-v1-readback.md)。机器可核验的本地回读文件位于：

- `data/phase3-7/batch01/copy-v1/copy-v1-readback.json`
- `data/phase3-7/batch01/copy-v1/copy-v1-verification.json`
- `data/phase3-7/batch01/copy-v1/copy-v1-revision-audit-after.json`

## 8. 冻结字段与状态检查

| 检查项 | 实际结果 |
| --- | --- |
| Company/Product 名称 | 未变 |
| 分类与 slug | 未变 |
| Company Logo、产品主图 | 未变 |
| 7 个参数字段定义 | 未变 |
| P01/P02/P03 参数值 | 均为 0 条 |
| F05 英文 | 继续缺失/空缺 |
| 产品型号 | 均为 0 条 |
| 产品关系 | 均为空 |
| 旧试点 `nitrided-barrel` | 保留且未变 |
| Company `years_experience` 数值字段 | 继续为 `null`；“近20年”仅存在于已确认正文 |
| P03 术语 | 保持“电镀 / electroplated”，未改成“镀铬 / chrome-plated” |
| 图5 | 未设为主图、未新增公开关系；本次没有任何媒体写操作 |
| TranslationStatus | Company/P01/P02/P03 的 zh-CN/en 均为 `draft` |
| Publication | Company/P01/P02/P03 的 zh-CN/en 均为 `draft` |
| Product Route | zh-CN/en 均为 `active=false`、`indexable=false` |

## 9. HTTPS、认证与 noindex 复核

| 入口 | 未认证 | 已认证 | `X-Robots-Tag` |
| --- | ---: | ---: | --- |
| Website | 401 | 200 | `noindex, nofollow` |
| Admin | 401 | 200 | `noindex, nofollow` |
| API readiness | 401 | 200 | `noindex, nofollow` |

三个入口仍为 HTTPS，Basic Auth 边界保持有效，未为截图开放公开前台页面。

## 10. 后台与 API 截图证据

截图通过已认证的本地后台会话生成，未点击 Save、Review、Publish、Archive 或任何生命周期按钮。截图保存在本地忽略目录，不提交公共 GitHub：

- `data/phase3-7/batch01/copy-v1/admin-api-copy-v1-readback.png`：实际 API 的 16 个文案字段、草稿状态、关闭路由及空模型/关系/参数值回读；
- `data/phase3-7/batch01/copy-v1/admin-p01-copy-v1.png`：P01 Admin 实体与生命周期；
- `data/phase3-7/batch01/copy-v1/admin-p02-copy-v1.png`：P02 Admin 实体与生命周期；
- `data/phase3-7/batch01/copy-v1/admin-p03-copy-v1.png`：P03 Admin 实体与生命周期。

截图用临时凭据副本已在浏览器会话建立后删除，浏览器会话也已关闭；原 `.env.phase37` 未改动。

## 11. 本次执行的检查

实际执行：

- 确认包 7 个文件 SHA-256 校验；
- 更新脚本语法编译检查；
- 写入前 API/Revision/Audit/冻结基线冲突检查；
- 1 次有限草稿保存；
- 保存后实际 Admin API 回读与 16 字段 SHA-256 比对；
- 保存前后 Revision/Audit 差异核对；
- HTTPS、Basic Auth、noindex、生命周期、Route、参数值、F05、型号、关系和旧试点检查；
- 后台截图及截图目视检查。

按本次“纯内容修改不重跑无关全量测试”的授权边界，没有运行无关单元测试、端到端全量测试、构建或性能测试；这些未执行项不记为 PASS。

## 12. 停止点

本次工作已停在现有隔离实例的草稿状态。没有执行 CMS Review、受保护预览发布、生产发布、部署、push 或 merge。下一步仅在收到受保护预览的单独授权后继续。
