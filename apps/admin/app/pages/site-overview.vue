<!-- 页面用途：只读展示全站栏目真实前后台地址、内容数量、导航状态和隐藏原因。 -->
<script setup lang="ts">
import { adminMeta } from '../admin-config'

interface OverviewItem {
  key: string
  frontend_url: string
  admin_url: string | null
  actual_count: number
  public_count: number
  navigation_status: string
  implementation: string
  hidden_reason: string | null
}

interface SiteOverview {
  locale: { code: string; slug: string; native_name: string }
  items: OverviewItem[]
}

const api = useAuthorityApi()
const localeCode = ref('zh-CN')
const overview = ref<SiteOverview | null>(null)
const loading = ref(true)
const errorMessage = ref('')

const names: Record<string, string> = {
  hero: 'Hero',
  core_product_families: 'Core Product Families',
  materials: 'Materials',
  special_applications: 'Special Applications',
  technologies: 'Technologies',
  manufacturing_capability: 'Manufacturing Capability',
  why_junhui: 'Why Junhui',
  factory_equipment: 'Factory & Equipment',
  solutions: 'Solutions',
  case_studies: 'Case Studies',
  technical_knowledge: 'Technical Knowledge',
  certificates_patents: 'Certificates / Patents',
  global_markets: 'Global Markets',
  rfq_cta: 'RFQ CTA',
  products: 'Products',
  about: 'About',
  search: 'Search',
  privacy: 'Privacy',
  contact: 'Contact',
}

useHead({
  title: `Site Overview · ${adminMeta.title}`,
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

/** 读取指定语言的全站真实状态；不根据前端路由猜测内容是否已经发布。 */
async function loadOverview(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    overview.value = await api.detail<SiteOverview>(
      `/presentation/site-overview/${localeCode.value}`,
    )
  } catch {
    overview.value = null
    errorMessage.value = '无法读取全站模块总览，请检查 content.read 权限和本地服务。'
  } finally {
    loading.value = false
  }
}

watch(localeCode, loadOverview)
onMounted(loadOverview)
</script>

<template>
  <main class="overview-page">
    <header class="overview-heading">
      <div>
        <p>Website Presentation V1.0 · R1</p>
        <h1>全站模块总览</h1>
        <p>“已有模型”“后台入口”和“前台已有内容”分别统计，空栏目不再被笼统归为隐藏。</p>
      </div>
      <div>
        <label>
          语言
          <select v-model="localeCode">
            <option value="zh-CN">简体中文</option>
            <option value="en">English</option>
          </select>
        </label>
        <NuxtLink to="/homepage">首页模块编辑器</NuxtLink>
      </div>
    </header>

    <p v-if="loading" class="overview-message" role="status">正在核对实际 API…</p>
    <p v-else-if="errorMessage" class="overview-message" role="alert">{{ errorMessage }}</p>

    <section v-else-if="overview" class="overview-table-wrap">
      <table>
        <thead>
          <tr>
            <th>栏目 / 模块</th>
            <th>实际记录</th>
            <th>公开可见</th>
            <th>导航状态</th>
            <th>实现状态</th>
            <th>地址与原因</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in overview.items" :key="item.key">
            <th scope="row">{{ names[item.key] || item.key }}</th>
            <td>{{ item.actual_count }}</td>
            <td>
              <span :class="item.public_count ? 'status status--ready' : 'status status--empty'">
                {{ item.public_count }}
              </span>
            </td>
            <td>{{ item.navigation_status }}</td>
            <td>{{ item.implementation }}</td>
            <td>
              <div class="overview-links">
                <a :href="`https://junhuiscrewbarrel.com${item.frontend_url}`">前台</a>
                <a v-if="item.admin_url" :href="item.admin_url">后台</a>
              </div>
              <small v-if="item.hidden_reason">{{ item.hidden_reason }}</small>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>

<style scoped>
.overview-page {
  width: min(calc(100% - 2rem), 92rem);
  margin: 0 auto;
  padding-block: 2rem 5rem;
}

.overview-heading {
  padding: clamp(1.5rem, 4vw, 3rem);
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 2rem;
  color: #dbeeff;
  background: linear-gradient(115deg, #07182b, #0a4a88);
  border-radius: 1rem;
}

.overview-heading h1,
.overview-heading > div > p:first-child {
  color: #fff;
}

.overview-heading > div:last-child {
  min-width: 13rem;
  display: grid;
  gap: 0.75rem;
}

.overview-heading label {
  color: #fff;
}

.overview-heading a {
  color: #fff;
}

.overview-table-wrap,
.overview-message {
  margin-top: 1.5rem;
  overflow-x: auto;
  background: #fff;
  border: 1px solid #d8e1ea;
  border-radius: 0.75rem;
}

.overview-message {
  padding: 1.5rem;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}

th,
td {
  padding: 0.9rem 1rem;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid #e4ebf1;
}

thead th {
  color: #486177;
  background: #eff5f9;
  font-size: 0.74rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

tbody th {
  color: #0d2d4c;
}

.status {
  min-width: 2rem;
  padding: 0.2rem 0.5rem;
  display: inline-block;
  text-align: center;
  border-radius: 999px;
}

.status--ready {
  color: #176333;
  background: #e6f5eb;
}

.status--empty {
  color: #6e4f10;
  background: #fff2d2;
}

.overview-links {
  display: flex;
  gap: 0.8rem;
}

td small {
  margin-top: 0.35rem;
  display: block;
  color: #6b7e90;
}

@media (max-width: 48rem) {
  .overview-heading {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
