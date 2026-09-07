# Phase 3.7.3 SEO 元数据候选（待确认）

- 候选版本：`SEO-CANDIDATE-R1-V1`
- 状态：`PENDING_APPROVAL / NOT_APPLIED`
- 范围：About、Products、screws、barrels 的中英文 title/description，共 8 组
- 内容依据：当前已批准且可见的 Company COPY-V1、P01/P02/P03 COPY-V1、产品名称及 RFQ 入口
- 冻结声明：本轮没有写入 `SeoDocument`、页面默认文案或 COPY-V1 的 16 个正文字段

## 数据路径核查

- About：API 已读取 `SeoDocument` 并返回 `seo.title/description`，Nuxt SSR 也已把该值接入 `useHead`；当前 description 缺失是数据为空，不是 API→SSR 接线遗漏。
- Products：API 当前明确返回 `description: null`，Nuxt SSR 已按有值才输出的规则消费；当前缺失也是未批准元数据，而不是前端丢值。
- screws/barrels：现有分类 description 能正常进入 SSR，但内容只是通用分类短句。本文件提供替换候选，不直接赋值。

因此本轮没有为了“修接线”新增隐式 fallback，也没有让候选文案绕过 CMS 审核链。

## 8 组候选

### About / zh-CN

- Title：`关于骏辉｜舟山骏辉塑料机械有限公司`
- Description：`舟山骏辉塑料机械有限公司位于中国浙江舟山，专注于塑料机械用机筒、螺杆、哥林柱及拉杆等核心部件，将设计、研发、上门测绘、生产、热处理、销售与售后服务相结合，为客户提供定制解决方案。`
- 依据：已确认 Company zh-CN `short_intro`（description 逐字复用）。

### About / en

- Title：`About Junhui | Zhoushan Junhui Plastic Machinery Co., Ltd.`
- Description：`Based in Zhoushan, Zhejiang, China, Junhui specializes in barrels, screws, tie bars and tie rods for plastics machinery. We bring together design, R&D, on-site measurement, production, heat treatment, sales and after-sales service to provide tailored solutions.`
- 依据：已确认 Company en `short_intro`（description 逐字复用）。

### Products / zh-CN

- Title：`骏辉螺杆与机筒产品`
- Description：`查看骏辉氮化螺杆、骏辉氮化机筒和骏辉电镀螺杆，并通过询价入口提交设备信息、图纸或需求说明。`
- 依据：当前三款已批准产品名称及其可见 RFQ 说明。

### Products / en

- Title：`Junhui Screw and Barrel Products`
- Description：`Explore Junhui Nitrided Screw, Junhui Nitrided Barrel and Junhui Electroplated Screw, then use the RFQ entry point to share machine information, drawings or requirements.`
- 依据：当前三款已批准产品名称及其可见 RFQ 说明。

### screws / zh-CN

- Title：`骏辉螺杆｜氮化螺杆与电镀螺杆`
- Description：`查看骏辉氮化螺杆和骏辉电镀螺杆的产品图片与介绍；尺寸、镀层、技术要求和设备适配事项可在询价沟通中分别确认。`
- 依据：P01/P03 已批准可见正文；未把“电镀”改写为“镀铬”。

### screws / en

- Title：`Junhui Screws | Nitrided and Electroplated Screws`
- Description：`View the images and descriptions for Junhui Nitrided Screw and Junhui Electroplated Screw. Dimensions, plating, technical requirements and machine compatibility can be confirmed through an RFQ.`
- 依据：P01/P03 已批准可见正文。

### barrels / zh-CN

- Title：`骏辉机筒｜氮化机筒`
- Description：`查看骏辉氮化机筒的产品图片与介绍；欢迎提供设备名称或型号、机筒需求、采购数量和已有图纸，具体尺寸及配套要求需分别确认。`
- 依据：P02 已批准可见正文。

### barrels / en

- Title：`Junhui Barrels | Nitrided Barrel`
- Description：`View the image and description for Junhui Nitrided Barrel. Share the machine name or model, barrel requirements, quantity and available drawing to confirm dimensions and matching requirements.`
- 依据：P02 已批准可见正文。

## 确认与应用门禁

如负责人确认，应另行给出候选版本或逐项文字，并明确是否授权写入、Review 和 Publish。在获得该授权前：

- `F-R1-004 = WAITING_METADATA_APPROVAL`；
- 不把本文件当作完整 API 请求体；
- 不直接写数据库，不在页面代码加入默认文案；
- 不改变 canonical、hreflang、Schema URL 或 COPY-V1 正文。
