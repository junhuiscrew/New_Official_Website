# 官网定向复核记录（Admin Chinese UX R1）

- 运行编号：`20260910T121600+0800`
- 环境：本机持久 Demo，`https://demo.junhuiscrewbarrel.com/`
- 范围：只检查与中文后台运营化相关的前台呈现及原验收计划指定交互；未重新设计整套官网。

## 1. 结论

核心前台可在桌面和 375px 移动视口使用，双语导航、产品筛选、中文搜索、产品关系、Gallery、视频、下载和 RFQ 入口均做了真实操作。所有请求保留在本机 Demo 域名，前台没有 Nginx Basic Auth 弹窗，响应继续带外层 `noindex, nofollow`。

本轮发现并修正了一个与 RFQ 禁用状态不一致的 Demo 措辞：产品正文已改成“查看演示询价表单（暂不提交）”，随后定位到旧句还存在于 SEO description 和 GEO direct answer；通过现有后台 API 同步替换后，首页和产品详情的首次 SSR 与浏览器渲染均不再包含旧句。

## 2. 页面矩阵

实际检查 33 个页面：26 个双语核心地址，加 7 个代表性详情页。全部返回 200，HTML `lang`、页面标题和 H1 与对应语言及页面类型一致。

核心双语页面包括：

- 首页、About、Contact、Products、RFQ；
- Materials、Technologies、Applications、Solutions、Capabilities、Case Studies、Knowledge 各总列表；
- 上述 13 类页面的中英文版本，共 26 个地址。

代表性详情页包括：

- 中文产品和英语产品详情；
- 中文材料、工艺、应用、方案、案例详情。

元数据统计：

| 项目 | 实际结果 |
| --- | --- |
| HTTP 200 | 33/33 |
| meta description | 29/33 |
| canonical | 29/33 |
| reciprocal hreflang | 29/33 |
| 网关 `X-Robots-Tag` | 33/33 为 `noindex, nofollow` |

现有缺口：

- About 中文、英语缺 meta description。
- Contact 中文、英语缺 canonical 与 hreflang。
- RFQ 中文、英语缺 description、canonical 与 hreflang。

这些是后续 SEO 接线/内容任务，不是本轮中文后台控件任务；本轮没有写入未经批准的新 SEO 文案。

## 3. 图片与媒体

在真实页面滚动后检查图片解码：

| 页面 | 成功解码 | 缺失 alt |
| --- | ---: | ---: |
| 中文首页 | 18/18 | 0 |
| 中文产品列表 | 9/9 | 0 |
| 中文产品详情 | 1/1 | 0 |
| 中文案例详情 | 1/1 | 0 |
| 中文材料详情 | 页面无图片 | 0 |
| 合计 | 29/29 | 0 |

产品 Gallery 实际打开和关闭成功；关闭后焦点返回触发按钮。两段 Demo 视频真实播放并产生时间进度：约 12.2 秒与 12.36 秒，均为 1280×720；不是 poster、假 URL 或改扩展名文件。

下载入口实际点击后得到 200 `application/pdf`。下载文件：

- 大小：68,291 bytes
- 文件头：`%PDF-1.4`
- SHA-256：`8CCEFAF50E4297884E22D48AA154025FBA7E19A88B2BE162AFE8B8B3EE4B2F44`

本地 CA 的在线吊销列表不可达，因此命令行下载使用 Windows 的 `--ssl-revoke-best-effort`，没有使用 `-k`，证书链校验仍保留。

## 4. 交互核验

- 桌面：中文→英语→中文语言切换，始终留在 Demo 本地域名。
- 移动：完成一次中文→英语语言菜单点击，仍留在本地域名。
- 产品详情：同一 `demo-s01` 内容完成 zh→en→zh；英语 H1 为 `General-purpose injection screw — demo`，返回中文后 H1 正确。
- 产品分类：选择 `demo-cat-screws` 后实际显示 6 个产品。
- 中文搜索：输入“螺杆”并点击，实际返回 6 个产品；未硬编码结果。
- 关系链接：从产品详情点击到 `/zh-cn/materials/demo-pa66/`，保持同源。
- Gallery：打开、关闭和焦点返回均成功。
- RFQ：入口可查看，但提交按钮禁用并显示暂不可提交说明；未提交询盘、附件或邮件。

“氮化”在 Demo 公共搜索中没有结果：当前公开搜索类型白名单不包含 technology，且产品可见文字不含该词。本轮没有为截图硬编码搜索结果，也没有放宽公开语言、发布或隐私过滤。

## 5. 移动端与长页面

375×812 视口检查结果：

- `clientWidth = 375`、`scrollWidth = 375`，无横向溢出。
- 首页 `scrollHeight = 22157`；相较此前 22914 减少 757 px，仍是完整 14 模块的长页面。
- 使用顶部、中段、下段普通视口截图区分真实页面与 full-page 拼接重复问题。
- 产品详情参数首行未被固定页头遮挡；滚动到参数区时页头已离开对应内容位置。
- 移动菜单正常打开并可点击。

## 6. 内容与系统文案

- 首页 6 个应用场景使用不同的中英文 Demo 摘要，不再重复同一占位句。
- 4 个案例使用不同的中英文 Demo 摘要；未虚构真实客户、改善结果或公开同意。
- 首页和 About 未出现旧的 `JUNHUI SYSTEM` 工程文案。
- RFQ CTA、About、Contact 统一说明 Demo 表单可查看但当前不提交。
- 9 个产品、18 条正文翻译、18 条 SEO description、18 条 GEO direct answer 均已清除旧的“创建演示询盘”动作句；新提示存在。再次运行 SEO/GEO 替换为 18 条 no-op。

## 7. 保护与预期错误

- Sitemap：404，符合当前 Demo 关闭要求。
- 公开 Privacy：404，符合政策仍未发布的状态。
- 匿名管理 API：401，符合后台应用认证要求。
- 浏览器控制台观察到的 404/401 仅来自上述预期保护检查；未发现阻断核心页面使用的脚本错误。

## 8. 未执行

- 未提交真实 RFQ、未上传附件、未发邮件。
- 未发布 Privacy、未开放 Sitemap、未启用 Analytics。
- 未访问生产、未改 DNS、未关闭 VPN 或本地 HTTPS 保护。
- 未做 Lighthouse 或真实用户 CWV 测量；因此不声明性能分数或全球访问达标。
