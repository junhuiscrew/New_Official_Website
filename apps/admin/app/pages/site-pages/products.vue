<!-- 页面用途：维护固定 Products 总列表页的双语 SEO 标题和描述。 -->
<script setup lang="ts">
import { adminMeta } from '../../admin-config'

interface LocaleSummary {
  code: string
  slug: string
  name: string
  native_name: string
}

interface ProductsSeoSummary {
  seo_title: string | null
  meta_description: string | null
}

interface ProductsLanguageSummary {
  locale: LocaleSummary
  seo: ProductsSeoSummary | null
  translation_status: { status: string }
  publication: { status: string }
  route: { path: string; active: boolean; indexable: boolean }
}

interface ProductsSitePageDetail {
  page: { system_key: string; status: string }
  languages: ProductsLanguageSummary[]
}

const { currentUser } = useAuth()
const api = useAuthorityApi()
const detail = ref<ProductsSitePageDetail | null>(null)
const activeLocaleCode = ref('zh-CN')
const seoTitle = ref('')
const metaDescription = ref('')
const loading = ref(true)
const saving = ref(false)
const message = ref('')
const errorMessage = ref('')

const activeLanguage = computed(
  () => detail.value?.languages.find((item) => item.locale.code === activeLocaleCode.value) ?? null,
)
const canInitialize = computed(() => currentUser.value?.permissions.includes('content.update'))
const canUpdate = computed(() => currentUser.value?.permissions.includes('seo.update'))

useHead({
  title: `产品总列表 SEO · ${adminMeta.title}`,
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

// 将当前语言已保存的两个可编辑字段复制到表单，不暴露其他 SEO 控制项。
function resetDraft(): void {
  seoTitle.value = activeLanguage.value?.seo?.seo_title ?? ''
  metaDescription.value = activeLanguage.value?.seo?.meta_description ?? ''
  message.value = ''
  errorMessage.value = ''
}

/**
 * 读取固定 Products 页面详情。
 *
 * 输入：无，固定请求 system_key=products。
 * 输出：Promise<boolean>，成功刷新双语 SEO 与生命周期状态时返回 true。
 */
async function loadPage(): Promise<boolean> {
  loading.value = true
  errorMessage.value = ''
  try {
    detail.value = await api.detail<ProductsSitePageDetail>('/discovery/site-pages/products')
    if (!detail.value.languages.some((item) => item.locale.code === activeLocaleCode.value)) {
      activeLocaleCode.value = detail.value.languages[0]?.locale.code ?? 'zh-CN'
    }
    resetDraft()
    return true
  } catch {
    detail.value = null
    errorMessage.value = 'Products 固定页面尚未建立，或当前账号无读取权限。'
    return false
  } finally {
    loading.value = false
  }
}

/**
 * 通过受保护接口建立固定页面，仅向具备 content.update 的账号显示。
 *
 * 输入：无。
 * 输出：Promise<void>，建立成功后重新读取真实页面状态。
 */
async function initializePage(): Promise<void> {
  errorMessage.value = ''
  try {
    await api.create<ProductsSitePageDetail>('/discovery/site-pages/products/initialize', {})
    const reloaded = await loadPage()
    if (reloaded) message.value = 'Products 固定页面已建立。'
  } catch {
    errorMessage.value = '建立失败；请检查目标、权限或路径冲突。'
  }
}

/**
 * 仅保存当前语言的 title 与 description，省略字段由 API 原样保留。
 *
 * 输入：无，使用当前表单值。
 * 输出：Promise<void>，保存后重新读取数据库实际值。
 */
async function saveSeo(): Promise<void> {
  if (!activeLanguage.value || !canUpdate.value) return
  const submittedTitle = seoTitle.value
  const submittedDescription = metaDescription.value
  saving.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    await api.update<ProductsSeoSummary>(
      `/discovery/site-pages/products/seo/${activeLanguage.value.locale.code}`,
      {
        seo_title: seoTitle.value,
        meta_description: metaDescription.value,
      },
    )
    const reloaded = await loadPage()
    const savedSeoMatches =
      reloaded &&
      activeLanguage.value?.seo?.seo_title === submittedTitle &&
      activeLanguage.value?.seo?.meta_description === submittedDescription
    if (!savedSeoMatches) {
      errorMessage.value = '保存请求已返回，但重新读取未确认实际值；请勿继续覆盖。'
      return
    }
    message.value = '已保存并重新读取实际值。'
  } catch {
    errorMessage.value = '保存失败；原有内容未由本页面覆盖。'
  } finally {
    saving.value = false
  }
}

watch(activeLocaleCode, resetDraft)
onMounted(loadPage)
</script>

<template>
  <main class="admin-shell">
    <header>
      <p>固定页面 · products</p>
      <h1>产品总列表 SEO</h1>
      <p>只维护双语 SEO title 与 description；发布权限由既有 CMS 生命周期单独控制。</p>
    </header>

    <p v-if="loading" role="status">正在读取实际数据…</p>
    <section v-else-if="!detail" aria-labelledby="products-site-page-missing">
      <h2 id="products-site-page-missing">页面身份不可用</h2>
      <p role="alert">{{ errorMessage }}</p>
      <button v-if="canInitialize" type="button" @click="initializePage">建立 Products 页面</button>
    </section>

    <template v-else>
      <section aria-label="Products page status">
        <strong>页面状态：{{ detail.page.status }}</strong>
        <label>
          语言
          <select v-model="activeLocaleCode" data-testid="products-seo-locale">
            <option
              v-for="language in detail.languages"
              :key="language.locale.code"
              :value="language.locale.code"
            >
              {{ language.locale.native_name }} ({{ language.locale.code }})
            </option>
          </select>
        </label>
      </section>

      <section v-if="activeLanguage" aria-label="Current lifecycle">
        <p>Translation：{{ activeLanguage.translation_status.status }}</p>
        <p>Publication：{{ activeLanguage.publication.status }}</p>
        <p>
          Route：{{ activeLanguage.route.path }} ·
          {{ activeLanguage.route.active ? 'active' : 'inactive' }} ·
          {{ activeLanguage.route.indexable ? 'indexable' : 'noindex' }}
        </p>
      </section>

      <form v-if="activeLanguage" @submit.prevent="saveSeo">
        <p v-if="!canUpdate">当前账号只有 SEO 读取权限。</p>
        <label>
          SEO title
          <input v-model="seoTitle" name="seo_title" maxlength="320" :readonly="!canUpdate" />
        </label>
        <label>
          Meta description
          <textarea v-model="metaDescription" name="meta_description" :readonly="!canUpdate" />
        </label>
        <button type="submit" :disabled="saving || !canUpdate">
          {{ saving ? '保存中…' : '保存 SEO' }}
        </button>
      </form>

      <p v-if="message" role="status">{{ message }}</p>
      <p v-if="errorMessage" role="alert">{{ errorMessage }}</p>
    </template>
  </main>
</template>
