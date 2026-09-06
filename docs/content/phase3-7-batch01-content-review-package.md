# Batch01 内容审核包（实际 Admin/API 导出）

> 导出范围：`phase37-local-https` 隔离环境；数据来自已保存的 Admin/API 草稿，不是规划 JSON，也不是生产环境快照。导出时未执行 Review、Publish、Route 激活或 Sitemap 写入。
>
> 审核人：中文与英文均由用户审核。英文、字段术语和摘要均保持工作草稿状态。

## 1. 公司介绍（原样草稿）

### 中文（已保存原文）

公司名称：舟山骏辉塑料机械有限公司

完整介绍：

舟山骏辉塑料机械有限公司座落在中国东海之滨，中国 浙江 舟山。 我公司凭着自身近20年的行业经验从设计、研发、上门测绘、热处理、生产、工艺、销售、售后为一体经营模式，专业生产注塑机，挤出机，吹膜机、吹塑机、制鞋机、橡胶机、化纤机、造粒机、发泡机等塑机核心部件：机筒、螺杆、哥林柱、拉杆等，自公司成立以来，积累了丰富的生产制造经验，以强大的研发、设计及精湛的工艺领先行业水平，为客户提供可靠性的高效：氮化式机筒、双合金机筒、锥双机筒螺杆、平双机筒螺杆、氮化式螺杆、电镀螺杆、PTA牙顶喷焊螺杆、双合金全熔射螺杆、光学螺杆、无卤螺杆、全硬式螺杆、涂层螺杆，帮助我们的客户在激烈的市场竞争中立于不败之地。 专业人做专业事，骏辉螺杆在光纤通讯、电子、医疗、汽车配件、光学镜片、IT、航空业插件、家用电器、玩具、快餐盒、管材、工业精密齿轮等多个行业领域，成功的为塑机行业核心之配件提供量身定制个性化解决方案。 坚持“优良品质、服务迅速”一直是骏辉螺杆对客户信守的诺言，我们致力于开发创新型螺杆设计解决方案，着力打造成为塑机行业螺杆优质品牌，圆你所想，期待与您的合作！

### English（已保存工作草稿，待审核）

Company name: `Zhoushan Junhui Plastic Machinery Co., Ltd.`

Short intro：`Junhui is based in Zhoushan, Zhejiang, China. Its company profile describes design, R&D, on-site measurement, production, heat treatment, sales and after-sales services for core components of plastics machinery, including screws, barrels and tie bars.`

Full intro：`Junhui is based in Zhoushan, Zhejiang, China. Its company profile describes design, R&D, on-site measurement, production, heat treatment, sales and after-sales services for core components of plastics machinery, including screws, barrels and tie bars.`

公司记录仍为 `TranslationStatus=draft`、`Publication=draft`；`/zh-cn/about/` 与 `/en/about/` 均 inactive/noindex。未从“近20年”倒推 founded year 或 years experience。

## 2. 三款 Batch01 产品草稿

以下名称、摘要、分类、slug 和主图均从已保存 Product detail API 读取。三款产品的中文和英文 TranslationStatus、Publication 均为 `draft`；每条 canonical Route 均 `active=false`、`indexable=false`。

| 外部键 | 中文名称 | 中文摘要 | English name（待审核） | English summary（待审核） | 分类 / slug | 主图 |
|---|---|---|---|---|---|---|
| P01 | 骏辉氮化螺杆 | 骏辉氮化螺杆产品。请通过询价沟通具体需求。 | Junhui Nitrided Screw | Junhui Nitrided Screw. Submit an RFQ to discuss your requirements. | 螺杆 / `screws` / `nitrided-screw` | IMG-02，已保存媒体 `f72e03cf-63e4-4f15-a820-edf7d182f015` |
| P02 | 骏辉氮化机筒 | 骏辉氮化机筒产品。请通过询价沟通具体需求。 | Junhui Nitrided Barrel | Junhui Nitrided Barrel. Submit an RFQ to discuss your requirements. | 机筒 / `barrels` / `junhui-nitrided-barrel` | IMG-03，复用媒体 `eb856c52-1007-485e-a92e-f4fcff6296c8` |
| P03 | 骏辉电镀螺杆 | 骏辉电镀螺杆产品。请通过询价沟通具体需求。 | Junhui Electroplated Screw | Junhui Electroplated Screw. Submit an RFQ to discuss your requirements. | 螺杆 / `screws` / `electroplated-screw` | IMG-04，已保存媒体 `323912a2-60ec-4580-b3de-108973f2e4d1` |

P01/P02/P03 的 description 与摘要相同，仅作为当前后台工作稿；未从图片或旧站补充型号、材料、性能或适用关系。三款均无 ProductModel、Material、Technology、Application、Solution 关系。

## 3. 七个规格字段（只保存定义，不保存数值）

字段定义、双语名称、类型、单位和状态来自实际 Definition detail API。所有三款产品 `ProductSpecValue` 数量均为 **0**，参数状态为 `VALUES_INTENTIONALLY_EMPTY`。

| 字段 | 中文名称 | English name（待审核） | value_type | 单位 | 所属分组 | 当前状态 |
|---|---|---|---|---|---|---|
| F01 | 螺杆直径 | Screw diameter | range | mm（建议，待确认） | 尺寸与外观 | enabled / draft |
| F02 | 螺杆有效长度 | Effective screw length | range | mm | 尺寸与外观 | enabled / draft |
| F03 | 表面粗糙度 | Surface roughness | number | μm | 尺寸与外观 | enabled / draft |
| F04 | 螺杆直线度 | Screw straightness | number | mm | 尺寸与外观 | enabled / draft |
| F05 | 氮化后表面镀硬铬硬度 | 未提供，保持空缺 | text | HV | 表面处理与硬度 | enabled / 中文 draft；英文 missing |
| F06 | 镀铬层厚度 | Chromium layer thickness | range | mm | 表面处理与硬度 | enabled / draft |
| F07 | 双合金硬度 | Bimetallic hardness | range | HRC | 表面处理与硬度 | enabled / draft |

F05 保留原名并待确认；没有把“氮化”与“镀硬铬”关系拆成新的性能结论。未把 F01–F07 自动套用到任何产品，也未将图5作为公开媒体、隐藏 GEO facts 或 Schema 数据源。

## 4. 旧试点与 P02 并列说明

| 项目 | 旧试点（保留） | Batch01 P02 |
|---|---|---|
| 中文名 | 注塑机氮化料筒 | 骏辉氮化机筒 |
| English name（待审核） | Nitrided Barrel for Injection Molding Machines | Junhui Nitrided Barrel |
| slug | `nitrided-barrel` | `junhui-nitrided-barrel` |
| 分类 | 注塑机料筒 / `injection-molding-machine-barrels` | 机筒 / `barrels` |
| 主图 | 旧试点媒体 `a4881719-e8ac-4504-afed-18e6b47ab457` | IMG-03 / `eb856c52-1007-485e-a92e-f4fcff6296c8` |
| 状态 | 双语 draft，Route inactive/noindex | 双语 draft，Route inactive/noindex |
| 说明 | 旧试点 description 明确标注旧站参数冲突，未录入规格 | 新批次单独保存，不覆盖旧 slug 或旧产品 |

P02 使用新 slug 是为保留旧试点并避免自然键冲突；最终名称、分类和 slug 仍由用户审核决定。两者均未发布。

## 5. 本轮规格停用门禁与审核结论

- 新增 ProductSpecValue 前，后端现在同时要求 Definition=`enabled` 且所属 Group=`enabled`；disabled/retired 分别返回 `specification_definition_inactive` 或 `specification_group_inactive`（HTTP 409）。
- Admin 新增值选择器只列出同时属于 enabled Group 且自身 enabled 的 Definition，与后端门禁一致。
- 已有历史值不因停用而删除；允许有权限者查看、清空，定义删除仍受引用保护。
- 本轮 TEST ONLY 测试记录覆盖启用新增、Definition disabled/retired 拒绝、Group disabled 拒绝、历史值保留；三款真实产品仍为 0 个参数值。
- 本审核包只是可读导出；未改变任何 TranslationStatus、Publication、Route、Review 或 Publish 状态。

## 6. 需用户确认的最小清单

1. 确认三款中文名称、摘要、分类和 draft slug。
2. 审核三款英文名称和摘要；确认 `Electroplated Screw` 术语。
3. 审核七个字段的英文名称、单位和适用产品；确认 F01 的 mm 建议。
4. 确认 F05 技术含义及是否需要英文名称；不确认前保持空缺。
5. 在确认真实技术参数和适用关系后，再由用户单独授权 Review/Publish。
