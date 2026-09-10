<!-- 页面用途：只读展示全站栏目真实前后台地址、内容数量、导航状态和隐藏原因。 -->
<script setup lang="ts">
import { adminMeta } from '../admin-config'
import {
  HIDDEN_REASON_LABELS,
  IMPLEMENTATION_STATUS_LABELS,
  NAVIGATION_STATUS_LABELS,
  labelFrom,
} from '../utils/adminZhCn'

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
const runtimeConfig = useRuntimeConfig()
const localeCode = ref('zh-CN')
const overview = ref<SiteOverview | null>(null)
const loading = ref(true)
const errorMessage = ref('')

// Technologies 与 Contact 保留独立核对项，但主界面统一显示中文名称。
const names: Record<string, string> = {
  hero: '首页主视觉',
  core_product_families: '核心产品系列',
  materials: '材料',
  special_applications: '特殊应用',
  technologies: '技术工艺',
  manufacturing_capability: '制造能力',
  why_junhui: '为什么选择骏辉',
  factory_equipment: '工厂与设备',
  solutions: '解决方案',
  case_studies: '客户案例',
  technical_knowledge: '技术知识',
  certificates_patents: '证书与专利',
  global_markets: '全球市场',
  rfq_cta: '询价入口',
  products: '产品总列表',
  about: '关于骏辉',
  search: '站内搜索',
  privacy: '隐私说明',
  contact: '联系我们',
}

/** 输入服务端隐藏原因代码；输出员工可读中文，不把未知代码直接放进主界面。 */
function hiddenReasonLabel(value: string | null): string {
  if (!value) return '—'
  const mapped = labelFrom(HIDDEN_REASON_LABELS, value, '')
  return HIDDEN_REASON_LABELS[value] ? mapped : '暂未配置中文说明'
}

useHead({
  title: `网站总览 · ${adminMeta.title}`,
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
        <p>官网内容与入口状态</p>
        <h1>网站总览</h1>
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
    <p v-else-if="errorMessage" class="overview-message" role="alert">
      {{ errorMessage }}
    </p>

    <section v-else-if="overview" class="overview-table-wrap">
      <table>
        <thead>
          <tr>
            <th>栏目 / 模块</th>
            <th>实际记录数</th>
            <th>公开可见数</th>
            <th>导航状态</th>
            <th>实现状态</th>
            <th>地址与原因</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in overview.items" :key="item.key">
            <th scope="row">{{ names[item.key] || '暂未配置栏目名称' }}</th>
            <td>{{ item.actual_count }} 项</td>
            <td>
              <span :class="item.public_count ? 'status status--ready' : 'status status--empty'">
                {{ item.public_count }} 项
              </span>
            </td>
            <td>
              {{ labelFrom(NAVIGATION_STATUS_LABELS, item.navigation_status) }}
            </td>
            <td>
              {{ labelFrom(IMPLEMENTATION_STATUS_LABELS, item.implementation) }}
            </td>
            <td>
              <div class="overview-links">
                <a :href="`${runtimeConfig.public.websiteUrl}${item.frontend_url}`">前台</a>
                <a v-if="item.admin_url" :href="item.admin_url">后台</a>
              </div>
              <small v-if="item.hidden_reason">{{ hiddenReasonLabel(item.hidden_reason) }}</small>
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
