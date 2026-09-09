<!-- 页面用途：Demo R2 内容运营工作台，汇总真实业务计数、模块状态和常用编辑入口。 -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { adminMeta } from '../admin-config'

interface ListResult {
  items?: unknown[]
  total?: number
}

interface OverviewResult {
  items: Array<{ key: string; public_count: number; navigation_status: string }>
}

const api = useAuthorityApi()
const runtimeConfig = useRuntimeConfig()
const loading = ref(true)
const loadedAt = ref<Date | null>(null)
const metrics = ref({ products: 0, media: 0, rfqs: 0, visibleModules: 0 })
const recentRfqs = ref<Array<Record<string, string>>>([])
const loadWarnings = ref<string[]>([])

const siteUrl = computed(() => String(runtimeConfig.public.websiteUrl))

useHead({
  htmlAttrs: { lang: 'zh-CN' },
  title: `工作台 · ${adminMeta.title}`,
  meta: [
    { name: 'description', content: 'Junhui Demo R2 内容运营工作台。' },
    { name: 'robots', content: adminMeta.robots },
  ],
})

/** 读取可独立失败的运营摘要；权限不足时保留其他卡片并明确提示。 */
async function loadDashboard(): Promise<void> {
  loading.value = true
  loadWarnings.value = []
  const requests = await Promise.allSettled([
    api.detail<ListResult>('/catalog/products?page=1&page_size=1'),
    api.detail<Array<Record<string, unknown>>>('/media'),
    api.detail<ListResult>('/rfqs'),
    api.detail<OverviewResult>('/presentation/site-overview/zh-CN'),
  ])

  const [products, media, rfqs, overview] = requests
  if (products.status === 'fulfilled') metrics.value.products = products.value.total ?? 0
  else loadWarnings.value.push('产品计数暂不可用')
  if (media.status === 'fulfilled') metrics.value.media = media.value.length
  else loadWarnings.value.push('媒体计数暂不可用')
  if (rfqs.status === 'fulfilled') {
    metrics.value.rfqs = rfqs.value.total ?? rfqs.value.items?.length ?? 0
    recentRfqs.value = (rfqs.value.items ?? []).slice(0, 5) as Array<Record<string, string>>
  } else loadWarnings.value.push('询盘摘要暂不可用')
  if (overview.status === 'fulfilled') {
    metrics.value.visibleModules = overview.value.items.filter(
      (item) => item.public_count > 0 || item.navigation_status === 'visible',
    ).length
  } else loadWarnings.value.push('模块状态暂不可用')
  loadedAt.value = new Date()
  loading.value = false
}

onMounted(loadDashboard)
</script>

<template>
  <main class="admin-shell dashboard-page">
    <!-- 欢迎区：明确当前是持久、隔离且不索引的演示内容环境。 -->
    <section class="dashboard-hero">
      <div>
        <p class="dashboard-eyebrow">DEMO R2 · CONTENT OPERATIONS</p>
        <h1>内容与视觉，保持在同一条发布链路</h1>
        <p>
          这里展示独立演示库的真实状态。内容、媒体、关系与首页排序均通过现有 API
          保存，刷新后仍会保留。
        </p>
        <div class="dashboard-actions">
          <NuxtLink to="/catalog/products">编辑产品目录</NuxtLink>
          <NuxtLink to="/homepage" class="dashboard-actions__secondary">编排首页</NuxtLink>
        </div>
      </div>
      <div class="dashboard-environment">
        <span>LOCAL / HTTPS</span>
        <strong>DEMO R2</strong>
        <dl>
          <div>
            <dt>索引</dt>
            <dd>NOINDEX</dd>
          </div>
          <div>
            <dt>数据</dt>
            <dd>ISOLATED</dd>
          </div>
          <div>
            <dt>邮件</dt>
            <dd>DISABLED</dd>
          </div>
        </dl>
      </div>
    </section>

    <p v-if="loadWarnings.length" class="dashboard-warning" role="status">
      {{ loadWarnings.join('；') }}。其余模块已继续读取。
    </p>

    <!-- 指标区：数字来自当前Demo API，不使用前端常量伪造业务数量。 -->
    <section class="dashboard-metrics" aria-label="内容摘要">
      <article>
        <span>01</span>
        <p>可维护产品</p>
        <strong>{{ loading ? '—' : metrics.products }}</strong>
        <NuxtLink to="/catalog/products">查看目录 →</NuxtLink>
      </article>
      <article>
        <span>02</span>
        <p>媒体资产</p>
        <strong>{{ loading ? '—' : metrics.media }}</strong>
        <NuxtLink to="/media">打开媒体库 →</NuxtLink>
      </article>
      <article>
        <span>03</span>
        <p>演示询盘</p>
        <strong>{{ loading ? '—' : metrics.rfqs }}</strong>
        <NuxtLink to="/rfqs">进入询盘中心 →</NuxtLink>
      </article>
      <article>
        <span>04</span>
        <p>有内容模块</p>
        <strong>{{ loading ? '—' : metrics.visibleModules }}</strong>
        <NuxtLink to="/site-overview">检查全站 →</NuxtLink>
      </article>
    </section>

    <section class="dashboard-columns">
      <article class="dashboard-panel dashboard-panel--wide">
        <header>
          <div>
            <p class="dashboard-eyebrow">PUBLISHING FLOW</p>
            <h2>今日内容工作流</h2>
          </div>
          <span>{{ loadedAt ? '已连接实时 API' : '正在连接' }}</span>
        </header>
        <div class="dashboard-flow">
          <NuxtLink to="/catalog"
            ><span>01</span><strong>结构化内容</strong
            ><small>产品、材料、工艺、应用与关系</small></NuxtLink
          >
          <NuxtLink to="/media"
            ><span>02</span><strong>媒体与视频</strong
            ><small>上传、Alt、封面与首页槽位</small></NuxtLink
          >
          <NuxtLink to="/site-pages/products"
            ><span>03</span><strong>SEO / GEO</strong
            ><small>页面级标题、描述和问答信号</small></NuxtLink
          >
          <a :href="siteUrl" target="_blank" rel="noopener"
            ><span>04</span><strong>前台验收</strong><small>SSR、移动端、视频与关联导航</small></a
          >
        </div>
      </article>

      <article class="dashboard-panel">
        <header>
          <div>
            <p class="dashboard-eyebrow">QUICK ACCESS</p>
            <h2>常用入口</h2>
          </div>
        </header>
        <nav class="dashboard-quick" aria-label="常用管理入口">
          <NuxtLink to="/demo-media"><span>AV</span>替换首页视频与封面</NuxtLink>
          <NuxtLink to="/knowledge"><span>KN</span>编辑并发布技术文章</NuxtLink>
          <NuxtLink to="/catalog/specifications"><span>SP</span>维护产品参数</NuxtLink>
          <NuxtLink to="/rfqs"><span>RF</span>处理演示询盘</NuxtLink>
        </nav>
      </article>
    </section>

    <section class="dashboard-panel dashboard-rfqs">
      <header>
        <div>
          <p class="dashboard-eyebrow">DEMO INQUIRIES</p>
          <h2>最近演示询盘</h2>
        </div>
        <NuxtLink to="/rfqs">查看全部</NuxtLink>
      </header>
      <div v-if="recentRfqs.length" class="dashboard-rfq-list">
        <NuxtLink v-for="item in recentRfqs" :key="item.id" :to="`/rfqs/${item.id}`">
          <strong>{{ item.company_name }}</strong>
          <span>{{ item.public_reference }}</span>
          <small>{{ item.status }}</small>
        </NuxtLink>
      </div>
      <p v-else class="dashboard-empty">{{ loading ? '正在读取…' : '当前没有可显示的询盘。' }}</p>
    </section>
  </main>
</template>

<style scoped>
.dashboard-page {
  display: grid;
  align-content: start;
  gap: 1.25rem;
}
.dashboard-hero {
  min-height: 0;
  padding: 1.25rem 1.4rem;
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(14rem, 0.3fr);
  align-items: center;
  gap: 2rem;
  overflow: hidden;
  color: #d8eafa;
  background: linear-gradient(110deg, #07182b, #0b3e69);
  border-radius: 1rem;
  box-shadow: 0 1.5rem 3.5rem rgb(7 24 43 / 18%);
}
.dashboard-hero h1 {
  max-width: 28ch;
  margin: 0.35rem 0 0.55rem;
  color: #fff;
  font-size: clamp(1.45rem, 2.3vw, 2.1rem);
  line-height: 1.12;
  letter-spacing: -0.035em;
}
.dashboard-hero p:not(.dashboard-eyebrow) {
  max-width: 49rem;
  margin: 0;
  color: #bdd4e7;
  font-size: 0.78rem;
  line-height: 1.6;
}
.dashboard-eyebrow {
  margin: 0;
  color: #65c8f7;
  font-size: 0.65rem;
  font-weight: 850;
  letter-spacing: 0.14em;
}
.dashboard-actions {
  margin-top: 0.8rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
}
.dashboard-actions a {
  padding: 0.58rem 0.8rem;
  color: #08213a;
  background: #7ad2fb;
  border: 1px solid #7ad2fb;
  border-radius: 0.45rem;
  font-size: 0.78rem;
  font-weight: 800;
  text-decoration: none;
}
.dashboard-actions .dashboard-actions__secondary {
  color: #eaf6ff;
  background: transparent;
  border-color: #5982a3;
}
.dashboard-environment {
  padding: 0.85rem;
  background: rgb(4 20 38 / 52%);
  border: 1px solid rgb(117 193 237 / 27%);
  border-radius: 0.8rem;
}
.dashboard-environment > span {
  color: #66c7f5;
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.13em;
}
.dashboard-environment > strong {
  margin-block: 0.2rem 0.6rem;
  display: block;
  color: #fff;
  font-size: clamp(1.45rem, 2.2vw, 2rem);
  letter-spacing: -0.04em;
}
.dashboard-environment dl {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.35rem;
}
.dashboard-environment dl > div {
  padding-top: 0.45rem;
  display: grid;
  gap: 0.1rem;
  border-top: 1px solid rgb(255 255 255 / 12%);
}
.dashboard-environment dt,
.dashboard-environment dd {
  margin: 0;
  font-size: 0.65rem;
}
.dashboard-environment dd {
  color: #7eddb7;
  font-weight: 800;
}
.dashboard-warning {
  margin: 0;
  padding: 0.75rem 1rem;
  color: #7d4b08;
  background: #fff8e7;
  border: 1px solid #eed19a;
  border-radius: 0.6rem;
}
.dashboard-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}
.dashboard-metrics article {
  padding: 1.1rem;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.3rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.8rem;
  box-shadow: 0 0.6rem 1.6rem rgb(20 46 73 / 5%);
}
.dashboard-metrics article > span {
  color: #7f94a8;
  font-size: 0.62rem;
  font-weight: 800;
}
.dashboard-metrics p {
  margin: 0;
  color: #65778a;
  font-size: 0.72rem;
}
.dashboard-metrics strong {
  grid-row: 1 / 3;
  grid-column: 2;
  color: #10263d;
  font-size: 2rem;
  letter-spacing: -0.06em;
}
.dashboard-metrics a {
  margin-top: 0.6rem;
  color: #0d69b9;
  font-size: 0.7rem;
  font-weight: 750;
  text-decoration: none;
}
.dashboard-columns {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(18rem, 0.65fr);
  gap: 1rem;
}
.dashboard-panel {
  padding: 1.25rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.85rem;
  box-shadow: 0 0.6rem 1.6rem rgb(20 46 73 / 5%);
}
.dashboard-panel > header {
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.dashboard-panel h2 {
  margin: 0.22rem 0 0;
  color: #14273c;
  font-size: 1.08rem;
}
.dashboard-panel > header > span {
  color: #16815e;
  font-size: 0.68rem;
  font-weight: 750;
}
.dashboard-panel > header > a {
  color: #0f70c9;
  font-size: 0.72rem;
  font-weight: 750;
  text-decoration: none;
}
.dashboard-flow {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-top: 1px solid #d9e3eb;
  border-left: 1px solid #d9e3eb;
}
.dashboard-flow a {
  min-height: 9rem;
  padding: 1rem;
  display: grid;
  align-content: start;
  gap: 0.45rem;
  color: #263b50;
  text-decoration: none;
  border-right: 1px solid #d9e3eb;
  border-bottom: 1px solid #d9e3eb;
}
.dashboard-flow a:hover {
  background: #eef8fe;
}
.dashboard-flow span {
  color: #1684d7;
  font-size: 0.62rem;
  font-weight: 850;
}
.dashboard-flow strong {
  font-size: 0.82rem;
}
.dashboard-flow small {
  color: #738396;
  line-height: 1.5;
}
.dashboard-quick {
  display: grid;
}
.dashboard-quick a {
  padding: 0.72rem 0;
  display: grid;
  grid-template-columns: 2rem 1fr;
  align-items: center;
  gap: 0.6rem;
  color: #263b50;
  font-size: 0.76rem;
  font-weight: 700;
  text-decoration: none;
  border-bottom: 1px solid #e4eaf0;
}
.dashboard-quick a:last-child {
  border-bottom: 0;
}
.dashboard-quick span {
  width: 1.8rem;
  height: 1.55rem;
  display: grid;
  place-items: center;
  color: #0c6ab8;
  background: #e9f5fd;
  border-radius: 0.3rem;
  font-size: 0.55rem;
  font-weight: 850;
}
.dashboard-rfq-list {
  display: grid;
}
.dashboard-rfq-list a {
  min-height: 3.5rem;
  padding: 0.65rem 0.4rem;
  display: grid;
  grid-template-columns: minmax(12rem, 1fr) minmax(8rem, 0.7fr) auto;
  align-items: center;
  gap: 1rem;
  color: #263b50;
  text-decoration: none;
  border-top: 1px solid #e3e9ef;
}
.dashboard-rfq-list span {
  color: #687a8c;
  font-size: 0.75rem;
}
.dashboard-rfq-list small {
  padding: 0.28rem 0.5rem;
  color: #0d6e50;
  background: #e7f7f1;
  border-radius: 99rem;
  font-weight: 800;
  text-transform: uppercase;
}
.dashboard-empty {
  color: #718297;
}
@media (max-width: 72rem) {
  .dashboard-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .dashboard-columns {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 48rem) {
  .dashboard-hero {
    grid-template-columns: 1fr;
  }
  .dashboard-metrics {
    grid-template-columns: 1fr;
  }
  .dashboard-flow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .dashboard-rfq-list a {
    grid-template-columns: 1fr auto;
  }
  .dashboard-rfq-list span {
    grid-row: 2;
  }
}
</style>
