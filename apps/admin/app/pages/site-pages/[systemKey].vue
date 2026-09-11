<!-- 页面用途：维护 Contact 与 RFQ 固定页面的双语 SEO 和受权限保护的生命周期。 -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { adminMeta } from '../../admin-config'

interface LocaleSummary {
  code: string
  slug: string
  native_name: string
}

interface FixedPageSeoSummary {
  seo_title: string | null
  meta_description: string | null
  robots_index: boolean
  robots_follow: boolean
}

interface FixedPageLanguageSummary {
  locale: LocaleSummary
  seo: FixedPageSeoSummary | null
  translation_status: { status: string }
  publication: { status: string }
  route: { path: string; active: boolean; indexable: boolean }
}

interface FixedPageDetail {
  page: { system_key: string; status: string }
  languages: FixedPageLanguageSummary[]
  seo_defaults: { robots_index: boolean; robots_follow: boolean }
}

interface PageConfig {
  systemKey: 'contact' | 'request-a-quote'
  title: string
  description: string
}

const PAGE_CONFIGS: Record<string, PageConfig> = {
  contact: {
    systemKey: 'contact',
    title: '联系页面 SEO',
    description: '维护联系页面的中英文标题与摘要；页面保持不可索引。',
  },
  'request-a-quote': {
    systemKey: 'request-a-quote',
    title: '询价页面 SEO',
    description: '维护询价页面的中英文标题与摘要；不会开启正式询盘提交。',
  },
}

const route = useRoute()
const resolvedPageConfig = PAGE_CONFIGS[String(route.params.systemKey ?? '')]
if (!resolvedPageConfig) {
  throw createError({ statusCode: 404, statusMessage: '固定页面不存在' })
}
const pageConfig: PageConfig = resolvedPageConfig

const { currentUser } = useAuth()
const api = useAuthorityApi()
const detail = ref<FixedPageDetail | null>(null)
const activeLocaleCode = ref('zh-CN')
const seoTitle = ref('')
const metaDescription = ref('')
const loading = ref(true)
const saving = ref(false)
const lifecycleBusy = ref(false)
const message = ref('')
const errorMessage = ref('')

const activeLanguage = computed(
  () => detail.value?.languages.find((item) => item.locale.code === activeLocaleCode.value) ?? null,
)
const canInitialize = computed(() => currentUser.value?.permissions.includes('content.update'))
const canUpdate = computed(() => currentUser.value?.permissions.includes('seo.update'))
const canReview = computed(
  () =>
    currentUser.value?.permissions.includes('translation.review') &&
    currentUser.value?.permissions.includes('content.review'),
)
const canPublish = computed(
  () =>
    currentUser.value?.permissions.includes('translation.publish') &&
    currentUser.value?.permissions.includes('content.publish'),
)

useHead(() => ({
  title: `${pageConfig.title} · ${adminMeta.title}`,
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
}))

/** 将当前语言的已保存字段复制到表单，切换语言时不互相覆盖。 */
function resetDraft(): void {
  seoTitle.value = activeLanguage.value?.seo?.seo_title ?? ''
  metaDescription.value = activeLanguage.value?.seo?.meta_description ?? ''
  message.value = ''
  errorMessage.value = ''
}

/**
 * 读取固定页面完整管理状态。
 *
 * 输入：无，从路由解析服务端白名单固定键。
 * 输出：Promise<boolean>，成功取得数据库实际值时返回 true。
 */
async function loadPage(): Promise<boolean> {
  loading.value = true
  errorMessage.value = ''
  try {
    detail.value = await api.detail<FixedPageDetail>(
      `/discovery/site-pages/${pageConfig.systemKey}`,
    )
    if (!detail.value.languages.some((item) => item.locale.code === activeLocaleCode.value)) {
      activeLocaleCode.value = detail.value.languages[0]?.locale.code ?? 'zh-CN'
    }
    resetDraft()
    return true
  } catch {
    detail.value = null
    errorMessage.value = '固定页面尚未建立，或当前账号无读取权限。'
    return false
  } finally {
    loading.value = false
  }
}

/** 使用 content.update 和 CSRF 初始化固定页面，再回读真实状态。 */
async function initializePage(): Promise<void> {
  errorMessage.value = ''
  try {
    await api.create(`/discovery/site-pages/${pageConfig.systemKey}/initialize`, {})
    const reloaded = await loadPage()
    if (reloaded) message.value = '固定页面已建立并重新读取。'
  } catch {
    errorMessage.value = '建立失败；请检查目标、权限或固定路径冲突。'
  }
}

/**
 * 保存当前语言 SEO，并通过 fresh GET 核对完整值。
 *
 * 输入：无，使用当前语言、标题与摘要表单。
 * 输出：Promise<void>，回读不一致时显示错误且不继续生命周期操作。
 */
async function saveSeo(): Promise<void> {
  if (!activeLanguage.value || !canUpdate.value) return
  const submitted = {
    seo_title: seoTitle.value,
    meta_description: metaDescription.value,
    robots_index: detail.value?.seo_defaults.robots_index ?? false,
    robots_follow: detail.value?.seo_defaults.robots_follow ?? false,
  }
  saving.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    await api.update(
      `/discovery/site-pages/${pageConfig.systemKey}/seo/${activeLanguage.value.locale.code}`,
      submitted,
    )
    const reloaded = await loadPage()
    const savedSeo = activeLanguage.value?.seo
    if (
      !reloaded ||
      savedSeo?.seo_title !== submitted.seo_title ||
      savedSeo.meta_description !== submitted.meta_description ||
      savedSeo.robots_index !== submitted.robots_index ||
      savedSeo.robots_follow !== submitted.robots_follow
    ) {
      errorMessage.value = '保存请求已返回，但重新读取未确认实际值；请勿继续操作。'
      return
    }
    message.value = 'SEO 已保存并重新读取实际值。'
  } catch {
    errorMessage.value = '保存失败；已有内容未被本页面覆盖。'
  } finally {
    saving.value = false
  }
}

/** 通过既有双权限服务审核当前语言，并重新读取状态。 */
async function reviewCurrent(): Promise<void> {
  if (!activeLanguage.value || !canReview.value) return
  lifecycleBusy.value = true
  try {
    await api.archive(
      `/discovery/site-pages/${pageConfig.systemKey}/translations/${activeLanguage.value.locale.code}/review`,
    )
    await loadPage()
    message.value = '当前语言已审核。'
  } catch {
    errorMessage.value = '审核失败；请检查权限和当前状态。'
  } finally {
    lifecycleBusy.value = false
  }
}

/** 通过既有双权限服务发布当前语言，并重新读取 Route 状态。 */
async function publishCurrent(): Promise<void> {
  if (!activeLanguage.value || !canPublish.value) return
  lifecycleBusy.value = true
  try {
    await api.archive(
      `/discovery/site-pages/${pageConfig.systemKey}/publications/${activeLanguage.value.locale.code}/publish`,
    )
    await loadPage()
    message.value = '当前语言已发布到受保护 Demo 预览。'
  } catch {
    errorMessage.value = '发布失败；页面须先审核且元数据必须完整。'
  } finally {
    lifecycleBusy.value = false
  }
}

watch(activeLocaleCode, resetDraft)
onMounted(loadPage)
</script>

<template>
  <main class="admin-shell fixed-page-editor">
    <header class="page-heading">
      <div>
        <p>固定页面 · {{ pageConfig.systemKey }}</p>
        <h1>{{ pageConfig.title }}</h1>
        <span>{{ pageConfig.description }}</span>
      </div>
    </header>

    <p v-if="loading" role="status">正在读取实际数据…</p>
    <section v-else-if="!detail" class="fixed-page-panel">
      <h2>页面身份不可用</h2>
      <p role="alert">{{ errorMessage }}</p>
      <button v-if="canInitialize" type="button" @click="initializePage">建立固定页面</button>
    </section>

    <template v-else>
      <section class="fixed-page-panel fixed-page-toolbar">
        <strong>页面状态：{{ detail.page.status }}</strong>
        <label>
          编辑语言
          <select v-model="activeLocaleCode" data-testid="fixed-page-seo-locale">
            <option
              v-for="language in detail.languages"
              :key="language.locale.code"
              :value="language.locale.code"
            >
              {{ language.locale.native_name }}（{{ language.locale.code }}）
            </option>
          </select>
        </label>
      </section>

      <section v-if="activeLanguage" class="fixed-page-panel">
        <h2>当前状态</h2>
        <dl class="status-grid">
          <div>
            <dt>翻译</dt>
            <dd>{{ activeLanguage.translation_status.status }}</dd>
          </div>
          <div>
            <dt>发布</dt>
            <dd>{{ activeLanguage.publication.status }}</dd>
          </div>
          <div>
            <dt>固定路径</dt>
            <dd>{{ activeLanguage.route.path }}</dd>
          </div>
          <div>
            <dt>Route</dt>
            <dd>
              {{ activeLanguage.route.active ? '已启用' : '未启用' }} ·
              {{ activeLanguage.route.indexable ? '业务可索引' : '业务不可索引' }}
            </dd>
          </div>
        </dl>
      </section>

      <form v-if="activeLanguage" class="fixed-page-panel" @submit.prevent="saveSeo">
        <h2>搜索元数据</h2>
        <p v-if="!canUpdate">当前账号只有 SEO 读取权限。</p>
        <label>
          SEO 标题
          <input v-model="seoTitle" name="seo_title" maxlength="320" :readonly="!canUpdate" />
        </label>
        <label>
          页面摘要
          <textarea v-model="metaDescription" name="meta_description" :readonly="!canUpdate" />
        </label>
        <p>
          固定 robots：{{ detail.seo_defaults.robots_index ? 'index' : 'noindex' }},
          {{ detail.seo_defaults.robots_follow ? 'follow' : 'nofollow' }}
        </p>
        <button type="submit" :disabled="saving || !canUpdate">
          {{ saving ? '保存中…' : '保存 SEO' }}
        </button>
      </form>

      <section v-if="activeLanguage" class="fixed-page-panel lifecycle-actions">
        <h2>受保护预览生命周期</h2>
        <button
          v-if="activeLanguage.publication.status === 'draft'"
          type="button"
          :disabled="lifecycleBusy || !canReview"
          @click="reviewCurrent"
        >
          审核当前语言
        </button>
        <button
          v-if="activeLanguage.publication.status === 'review'"
          type="button"
          :disabled="lifecycleBusy || !canPublish"
          @click="publishCurrent"
        >
          发布到 Demo 预览
        </button>
        <span v-if="activeLanguage.publication.status === 'published'">当前语言已发布。</span>
      </section>
    </template>

    <p v-if="message" class="success-message" role="status">{{ message }}</p>
    <p v-if="errorMessage && detail" class="error-message" role="alert">{{ errorMessage }}</p>
  </main>
</template>

<style scoped>
.fixed-page-editor {
  display: grid;
  align-content: start;
  gap: 1rem;
}
.fixed-page-editor .page-heading p,
.fixed-page-editor .page-heading h1 {
  margin: 0;
}
.fixed-page-editor .page-heading p {
  color: #176dae;
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}
.fixed-page-editor .page-heading span {
  color: #64778a;
}
.fixed-page-panel {
  padding: 1.15rem;
  display: grid;
  gap: 0.85rem;
  background: #fff;
  border: 1px solid #dbe5ed;
  border-radius: 0.8rem;
}
.fixed-page-panel h2,
.fixed-page-panel p,
.status-grid {
  margin: 0;
}
.fixed-page-toolbar {
  grid-template-columns: 1fr minmax(15rem, 22rem);
  align-items: end;
}
.status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}
.status-grid div {
  padding: 0.75rem;
  background: #f4f8fb;
  border-radius: 0.5rem;
}
.status-grid dt {
  color: #738598;
  font-size: 0.7rem;
}
.status-grid dd {
  margin: 0.2rem 0 0;
  overflow-wrap: anywhere;
}
.lifecycle-actions {
  grid-template-columns: 1fr auto;
  align-items: center;
}
.success-message {
  color: #0a6c4b;
}
@media (max-width: 48rem) {
  .fixed-page-toolbar,
  .status-grid,
  .lifecycle-actions {
    grid-template-columns: 1fr;
  }
}
</style>
