<!-- 页面用途：维护固定 Privacy 页面、双语政策草稿及人工审核发布生命周期。 -->
<script setup lang="ts">
import { adminMeta } from '../admin-config'
import {
  canEditPrivacy,
  canPublishDraft,
  canReviewPrivacy,
  getPrivacyErrorStatus,
  hasPrivacyPublishPermissions,
  isDraftEditable,
  resolvePrivacyLoadFailure,
  resolvePrivacyEffectiveAt,
  savedDraftMatches,
  toPrivacyDateTimeLocal,
  type PrivacyLocale,
  type PrivacyState,
  type PrivacyTranslationInput,
  type PrivacyVersion,
} from '../utils/privacyAdmin'

interface PrivacyHistory {
  items: PrivacyVersion[]
  total: number
}

const PRIVACY_LOCALES: Array<{ code: PrivacyLocale; label: string }> = [
  { code: 'zh-CN', label: '简体中文' },
  { code: 'en', label: 'English' },
]

const { currentUser } = useAuth()
const api = useAuthorityApi()
const privacyState = ref<PrivacyState | null>(null)
const history = ref<PrivacyVersion[]>([])
const historyError = ref('')
const initialized = ref(true)
const loading = ref(true)
const saving = ref(false)
const lifecycleBusy = ref(false)
const activeLocale = ref<PrivacyLocale>('zh-CN')
const effectiveAt = ref('')
const originalEffectiveAt = ref<string | null>(null)
const effectiveAtEdited = ref(false)
const translationDrafts = reactive<Record<PrivacyLocale, { title: string; body_markdown: string }>>(
  {
    'zh-CN': { title: '', body_markdown: '' },
    en: { title: '', body_markdown: '' },
  },
)
const message = ref('')
const errorMessage = ref('')

const permissions = computed(() => currentUser.value?.permissions ?? [])
const canEdit = computed(() => canEditPrivacy(permissions.value))
const canReview = computed(() => canReviewPrivacy(permissions.value))
const canPublishByPermission = computed(() => hasPrivacyPublishPermissions(permissions.value))
const canReadHistory = computed(() => permissions.value.includes('privacy.history'))
const draft = computed(() => privacyState.value?.draft ?? null)
const current = computed(() => privacyState.value?.current ?? null)
const canEditDraft = computed(() => canEdit.value && isDraftEditable(draft.value))
const canPublish = computed(
  () => canPublishByPermission.value && canPublishDraft(draft.value) && !lifecycleBusy.value,
)
const activeTranslation = computed(() => translationDrafts[activeLocale.value])

useHead({
  title: `Privacy · ${adminMeta.title}`,
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

/**
 * 将当前表单完整同步为保存请求的双语正文。
 *
 * 输入：无，读取双语表单状态。
 * 输出：PrivacyTranslationInput[]，固定 zh-CN/en 顺序的完整正文。
 */
function buildTranslationPayload(): PrivacyTranslationInput[] {
  return PRIVACY_LOCALES.map(({ code }) => ({
    locale: code,
    title: translationDrafts[code].title,
    body_markdown: translationDrafts[code].body_markdown,
  }))
}

/**
 * 构造发布操作绑定的双语服务端哈希。
 *
 * 输入：version，管理员当前实际看到的草稿。
 * 输出：Record<PrivacyLocale, string>，固定 zh-CN/en 的服务端哈希。
 */
function buildExpectedContentHashes(version: PrivacyVersion): Record<PrivacyLocale, string> {
  const hashes = Object.fromEntries(
    PRIVACY_LOCALES.map(({ code }) => [code, version.translations[code].content_hash ?? '']),
  ) as Record<PrivacyLocale, string>
  if (!hashes['zh-CN'] || !hashes.en) throw new Error('Privacy 双语正文哈希缺失')
  return hashes
}

/**
 * 把 fresh GET 草稿写回表单，防止继续编辑陈旧 revision。
 *
 * 输入：version，服务端返回的当前草稿或 null。
 * 输出：void，更新双语标题、正文和生效时间。
 */
function hydrateDraftForm(version: PrivacyVersion | null): void {
  originalEffectiveAt.value = version?.effective_at ?? null
  effectiveAt.value = toPrivacyDateTimeLocal(originalEffectiveAt.value)
  effectiveAtEdited.value = false
  for (const { code } of PRIVACY_LOCALES) {
    translationDrafts[code].title = version?.translations[code]?.title ?? ''
    translationDrafts[code].body_markdown = version?.translations[code]?.body_markdown ?? ''
  }
}

/**
 * 仅在具备 privacy.history 时请求版本历史。
 *
 * 输入：无。
 * 输出：Promise<void>，成功时更新历史列表。
 */
async function loadHistory(): Promise<void> {
  historyError.value = ''
  if (!canReadHistory.value) {
    history.value = []
    return
  }
  try {
    const response = await api.detail<PrivacyHistory>('/privacy/history')
    history.value = response.items
  } catch {
    // 历史读取失败只影响历史区域，不能清空已经成功加载的编辑状态。
    historyError.value = 'Privacy 历史读取失败，请稍后重试。'
  }
}

/**
 * 从固定 GET /privacy 读取真实 current/draft 状态。
 *
 * 输入：无。
 * 输出：Promise<PrivacyState | null>，未初始化或读取失败时返回 null。
 */
async function loadPrivacy(): Promise<PrivacyState | null> {
  loading.value = true
  try {
    const response = await api.detail<PrivacyState>('/privacy')
    errorMessage.value = ''
    initialized.value = true
    privacyState.value = response
    hydrateDraftForm(response.draft)
    if (canReadHistory.value) await loadHistory()
    return response
  } catch (error) {
    privacyState.value = null
    history.value = []
    const failure = resolvePrivacyLoadFailure(error)
    initialized.value = failure.initialized
    errorMessage.value = failure.errorMessage
    return null
  } finally {
    loading.value = false
  }
}

/**
 * 初始化固定 Privacy 页面身份，不写入任何政策正文。
 *
 * 输入：无。
 * 输出：Promise<void>，成功后通过 GET /privacy 回读真实状态。
 */
async function initializePrivacy(): Promise<void> {
  if (!canEdit.value) return
  lifecycleBusy.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    await api.create<PrivacyState>('/privacy/initialize', {})
    await loadPrivacy()
    message.value = 'Privacy 页面已初始化，可手动创建草稿。'
  } catch {
    errorMessage.value = '初始化失败，请检查权限后重试。'
  } finally {
    lifecycleBusy.value = false
  }
}

/**
 * 请求服务端创建草稿；有 current 时由服务端克隆，无 current 时创建空草稿。
 *
 * 输入：无。
 * 输出：Promise<void>，成功后回读新 revision 与双语状态。
 */
async function createDraft(): Promise<void> {
  if (!canEdit.value) return
  lifecycleBusy.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    const created = await api.create<PrivacyState>('/privacy/drafts', { clone_current: true })
    await loadPrivacy()
    message.value = created.draft?.cloned_from_version_label
      ? `已从 ${created.draft.cloned_from_version_label} 克隆新草稿。`
      : '已创建空白双语草稿。'
  } catch (error) {
    const statusCode = getPrivacyErrorStatus(error)
    errorMessage.value =
      statusCode === 409 ? '当前已有可编辑草稿，请刷新后再编辑。' : '创建草稿失败。'
  } finally {
    lifecycleBusy.value = false
  }
}

/**
 * 使用乐观 revision 完整保存双语正文，并以 fresh GET 校验数据库实际值。
 *
 * 输入：无，读取当前表单与服务端 draft revision。
 * 输出：Promise<void>，仅回读值逐项一致时显示保存成功。
 */
async function saveDraft(): Promise<void> {
  const activeDraft = draft.value
  if (!activeDraft || !canEditDraft.value) return
  const effectiveAtSubmission = resolvePrivacyEffectiveAt(
    originalEffectiveAt.value,
    effectiveAt.value,
    effectiveAtEdited.value,
  )
  saving.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    const saved = await api.replace<PrivacyState>('/privacy/draft', {
      expected_revision: activeDraft.revision,
      effective_at: effectiveAtSubmission,
      translations: buildTranslationPayload(),
    })
    const reloaded = await loadPrivacy()
    if (!reloaded || !savedDraftMatches(reloaded.draft, saved.draft)) {
      errorMessage.value = '保存请求已返回，但 fresh GET 未确认实际值；请刷新后再编辑。'
      return
    }
    message.value = '双语正文已保存，并已通过 fresh GET 确认实际值。'
  } catch (error) {
    const statusCode = getPrivacyErrorStatus(error)
    errorMessage.value =
      statusCode === 409
        ? '草稿 revision 已冲突，不能自动覆盖；请刷新后再编辑。'
        : '保存失败，现有内容未被本页面继续覆盖。'
  } finally {
    saving.value = false
  }
}

/**
 * 判断一种语言是否可由当前用户手动审核。
 *
 * 输入：locale，zh-CN 或 en。
 * 输出：boolean，权限完整、正文完整且尚未审核时返回 true。
 */
function canReviewLocale(locale: PrivacyLocale): boolean {
  const translation = draft.value?.translations[locale]
  return Boolean(
    canReview.value &&
      translation?.title &&
      translation.body_markdown &&
      translation.content_hash &&
      translation.translation_status === 'draft' &&
      !lifecycleBusy.value,
  )
}

/**
 * 经明确确认后人工审核指定语言，不会连带发布。
 *
 * 输入：locale，待审核语言。
 * 输出：Promise<void>，确认并成功后重新读取服务端状态。
 */
async function reviewTranslation(locale: PrivacyLocale): Promise<void> {
  const activeDraft = draft.value
  const translation = activeDraft?.translations[locale]
  if (!activeDraft || !translation?.content_hash || !canReviewLocale(locale)) return
  if (!window.confirm(`确认将 ${locale} 标记为人工审核？审核后不能直接编辑，且不会自动发布。`)) {
    return
  }
  lifecycleBusy.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    await api.create<PrivacyState>(`/privacy/draft/review/${locale}`, {
      expected_version_label: activeDraft.version_label,
      expected_revision: activeDraft.revision,
      expected_content_hash: translation.content_hash,
    })
    await loadPrivacy()
    message.value = `${locale} 已人工审核；发布仍需单独确认。`
  } catch (error) {
    if (getPrivacyErrorStatus(error) === 409) await loadPrivacy()
    errorMessage.value =
      getPrivacyErrorStatus(error) === 409
        ? '草稿已变化，已刷新实际状态；请重新查看并确认。'
        : '审核失败，请检查正文、权限或最新状态。'
  } finally {
    lifecycleBusy.value = false
  }
}

/**
 * 经明确确认后原子发布双语草稿并切换 current。
 *
 * 输入：无。
 * 输出：Promise<void>，仅用户确认后调用固定 publish API。
 */
async function publishDraft(): Promise<void> {
  const activeDraft = draft.value
  if (!activeDraft || !canPublish.value) return
  if (!window.confirm('确认发布此双语版本？发布会切换 current，且已发布版本不能直接编辑。')) {
    return
  }
  lifecycleBusy.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    await api.create<PrivacyState>('/privacy/draft/publish', {
      expected_version_label: activeDraft.version_label,
      expected_revision: activeDraft.revision,
      expected_content_hashes: buildExpectedContentHashes(activeDraft),
    })
    await loadPrivacy()
    message.value = '发布完成，current 已切换为服务器返回版本。'
  } catch (error) {
    if (getPrivacyErrorStatus(error) === 409) await loadPrivacy()
    errorMessage.value =
      getPrivacyErrorStatus(error) === 409
        ? '草稿已变化，已刷新实际状态；请重新查看并确认。'
        : '发布失败；current 未由本页面自动切换。'
  } finally {
    lifecycleBusy.value = false
  }
}

onMounted(loadPrivacy)
</script>

<template>
  <main class="admin-shell privacy-page">
    <!-- 页面标题区：主标题保持全页唯一 H1。 -->
    <header class="privacy-heading">
      <div>
        <p class="eyebrow">Compliance content</p>
        <h1>Privacy 管理</h1>
        <p>维护固定双语政策版本；所有审核与发布操作都必须由用户明确触发。</p>
      </div>
      <button type="button" :disabled="loading" @click="loadPrivacy">刷新实际状态</button>
    </header>

    <p v-if="message" class="success-message" role="status">{{ message }}</p>
    <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
    <p v-if="loading" role="status">正在读取 Privacy 实际状态…</p>

    <!-- 未初始化状态：只有满足后端当前编辑组合权限的用户能执行初始化。 -->
    <section v-else-if="!initialized" class="privacy-empty" aria-labelledby="privacy-empty-title">
      <h2 id="privacy-empty-title">Privacy 页面尚未初始化</h2>
      <p>初始化只建立固定页面身份与生命周期骨架，不会写入或发布正文。</p>
      <button v-if="canEdit" type="button" :disabled="lifecycleBusy" @click="initializePrivacy">
        初始化 Privacy 页面
      </button>
    </section>

    <template v-else-if="privacyState">
      <!-- 页面与 current 摘要：只展示 API 返回值，不硬编码版本或经营期限。 -->
      <section class="privacy-summary" aria-label="Privacy page summary">
        <div>
          <span>页面状态</span>
          <strong>{{ privacyState.page.status }}</strong>
        </div>
        <div>
          <span>Current</span>
          <strong>{{ current?.version_label ?? '暂无 current' }}</strong>
        </div>
        <div>
          <span>Draft</span>
          <strong>{{ draft?.version_label ?? '暂无 draft' }}</strong>
        </div>
      </section>

      <section v-if="current" class="version-panel" aria-labelledby="current-version-title">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Current</p>
            <h2 id="current-version-title">{{ current.version_label }}</h2>
          </div>
          <dl class="version-meta">
            <div>
              <dt>Revision</dt>
              <dd>{{ current.revision }}</dd>
            </div>
            <div>
              <dt>生效时间</dt>
              <dd>{{ current.effective_at ?? '未设置' }}</dd>
            </div>
          </dl>
        </div>
        <div class="language-status-grid">
          <article v-for="locale in PRIVACY_LOCALES" :key="locale.code">
            <h3>{{ locale.label }}</h3>
            <p>Translation：{{ current.translations[locale.code].translation_status }}</p>
            <p>Publication：{{ current.translations[locale.code].publication_status }}</p>
            <p>
              Route：{{ current.translations[locale.code].canonical_path }} ·
              {{ current.translations[locale.code].route_active ? 'active' : 'inactive' }} ·
              {{ current.translations[locale.code].route_indexable ? 'indexable' : 'noindex' }}
            </p>
          </article>
        </div>
        <p class="immutable-note">已发布版本不能直接编辑，请创建新草稿。</p>
      </section>

      <!-- 无草稿或不可变草稿时，满足编辑组合权限的用户可显式创建下一版。 -->
      <section v-if="!draft" class="privacy-empty" aria-labelledby="privacy-no-draft-title">
        <h2 id="privacy-no-draft-title">当前没有工作草稿</h2>
        <p>{{ current ? '可从 current 克隆一个新版本。' : '可创建一个空白双语版本。' }}</p>
        <button v-if="canEdit" type="button" :disabled="lifecycleBusy" @click="createDraft">
          创建/克隆草稿
        </button>
      </section>

      <section v-else class="version-panel draft-panel" aria-labelledby="draft-version-title">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Working draft <span class="not-approved">NOT APPROVED</span></p>
            <h2 id="draft-version-title">{{ draft.version_label }}</h2>
            <p v-if="draft.cloned_from_version_label">
              克隆自 {{ draft.cloned_from_version_label }}
            </p>
          </div>
          <dl class="version-meta">
            <div>
              <dt>Revision</dt>
              <dd>{{ draft.revision }}</dd>
            </div>
            <div>
              <dt>生效时间</dt>
              <dd>{{ draft.effective_at ?? '未设置' }}</dd>
            </div>
          </dl>
        </div>

        <p v-if="!isDraftEditable(draft)" class="immutable-note">
          已审核或已发布版本不能直接编辑，请创建新草稿。
          <button v-if="canEdit" type="button" :disabled="lifecycleBusy" @click="createDraft">
            创建/克隆草稿
          </button>
        </p>

        <div class="language-status-grid">
          <article v-for="locale in PRIVACY_LOCALES" :key="locale.code">
            <h3>{{ locale.label }}</h3>
            <p>Translation：{{ draft.translations[locale.code].translation_status }}</p>
            <p>Publication：{{ draft.translations[locale.code].publication_status }}</p>
            <p>
              Route：{{ draft.translations[locale.code].canonical_path }} ·
              {{ draft.translations[locale.code].route_active ? 'active' : 'inactive' }} ·
              {{ draft.translations[locale.code].route_indexable ? 'indexable' : 'noindex' }}
            </p>
            <button
              v-if="canReview && canReviewLocale(locale.code)"
              type="button"
              :disabled="lifecycleBusy"
              @click="reviewTranslation(locale.code)"
            >
              人工审核 {{ locale.code }}
            </button>
          </article>
        </div>

        <!-- 编辑区：始终同时提交 zh-CN/en 的完整标题和 Markdown 正文。 -->
        <form class="privacy-editor" @submit.prevent="saveDraft">
          <label>
            生效时间
            <input
              v-model="effectiveAt"
              name="effective_at"
              type="datetime-local"
              step="1"
              :readonly="!canEditDraft"
              @input="effectiveAtEdited = true"
            />
            <small>未修改则保留服务端原始 ISO；修改后按本地时区精确到秒保存，毫秒归零。</small>
          </label>

          <div class="tab-list" role="group" aria-label="Privacy languages">
            <button
              v-for="locale in PRIVACY_LOCALES"
              :key="locale.code"
              type="button"
              :aria-pressed="activeLocale === locale.code"
              :class="{ active: activeLocale === locale.code }"
              @click="activeLocale = locale.code"
            >
              {{ locale.label }} · {{ locale.code }}
            </button>
          </div>

          <div class="editor-preview-grid">
            <div class="editor-fields">
              <label>
                标题
                <input
                  v-model="activeTranslation.title"
                  :name="`${activeLocale}_title`"
                  maxlength="300"
                  :readonly="!canEditDraft"
                  required
                />
              </label>
              <label>
                完整 Markdown 正文
                <textarea
                  v-model="activeTranslation.body_markdown"
                  :name="`${activeLocale}_body_markdown`"
                  rows="24"
                  maxlength="200000"
                  :readonly="!canEditDraft"
                  required
                />
              </label>
            </div>
            <section class="preview-card" :aria-label="`${activeLocale} 安全预览`">
              <p class="preview-label">后台安全预览 · NOT APPROVED</p>
              <p class="preview-title">{{ activeTranslation.title || '未填写标题' }}</p>
              <SafeMarkdownPreview :markdown="activeTranslation.body_markdown" />
            </section>
          </div>

          <div class="form-actions">
            <button type="submit" :disabled="saving || !canEditDraft">
              {{ saving ? '保存并回读中…' : '保存双语草稿' }}
            </button>
            <span v-if="!canEdit">当前账号不具备 Privacy 编辑组合权限。</span>
          </div>
        </form>

        <!-- 发布按钮只在三项权限、双语 human_reviewed 和 effective_at 齐全时出现。 -->
        <div class="publish-panel">
          <p>发布是独立手动操作；页面不会自动审核或自动发布。</p>
          <button
            v-if="
              canPublishByPermission &&
              draft.effective_at &&
              PRIVACY_LOCALES.every(
                ({ code }) => draft!.translations[code].translation_status === 'human_reviewed',
              )
            "
            type="button"
            class="danger"
            :disabled="!canPublish"
            @click="publishDraft"
          >
            发布并切换 current
          </button>
        </div>
      </section>

      <!-- 历史区：无 privacy.history 时既不请求也不渲染。 -->
      <section v-if="canReadHistory" class="version-panel" aria-labelledby="privacy-history-title">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Authorized history</p>
            <h2 id="privacy-history-title">版本历史</h2>
          </div>
          <span>{{ history.length }} 个版本</span>
        </div>
        <p v-if="historyError" class="error-message" role="alert">{{ historyError }}</p>
        <ol v-else-if="history.length" class="history-list">
          <li v-for="version in history" :key="version.version_label">
            <strong>{{ version.version_label }}</strong>
            <span>revision {{ version.revision }}</span>
            <span>{{ version.effective_at ?? '未设置生效时间' }}</span>
            <span>
              zh-CN {{ version.translations['zh-CN'].translation_status }} / en
              {{ version.translations.en.translation_status }}
            </span>
          </li>
        </ol>
        <p v-else>暂无版本历史。</p>
      </section>
    </template>
  </main>
</template>

<style scoped>
.privacy-page {
  display: block;
  max-width: 90rem;
  margin: 0 auto;
  padding-block: 3rem 5rem;
}

.privacy-page > section,
.privacy-page > header,
.privacy-page > p {
  width: 100%;
  box-sizing: border-box;
}

.privacy-heading,
.panel-heading,
.privacy-summary,
.language-status-grid,
.editor-preview-grid {
  display: grid;
  gap: 1rem;
}

.privacy-heading,
.panel-heading {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
}

.privacy-heading {
  margin-bottom: 1.5rem;
}

.privacy-heading h1,
.panel-heading h2,
.language-status-grid h3 {
  margin: 0;
}

.eyebrow,
.preview-label {
  margin: 0 0 0.4rem;
  color: #475569;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.privacy-summary {
  grid-template-columns: repeat(3, 1fr);
  margin-bottom: 1.5rem;
}

.privacy-summary > div,
.version-panel,
.privacy-empty {
  border: 1px solid #cbd5e1;
  border-radius: 0.85rem;
  background: #fff;
}

.privacy-summary > div {
  display: grid;
  gap: 0.35rem;
  padding: 1rem;
}

.privacy-summary span,
.version-meta dt {
  color: #64748b;
  font-size: 0.85rem;
}

.version-panel,
.privacy-empty {
  margin-top: 1.5rem;
  padding: 1.25rem;
}

.draft-panel {
  border-top: 4px solid #d97706;
}

.not-approved {
  display: inline-block;
  margin-left: 0.4rem;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  color: #7c2d12;
  background: #ffedd5;
}

.version-meta {
  display: flex;
  gap: 1.5rem;
  margin: 0;
}

.version-meta div {
  display: grid;
  gap: 0.2rem;
}

.version-meta dd {
  margin: 0;
  font-weight: 700;
}

.language-status-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 1rem;
}

.language-status-grid article {
  padding: 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.65rem;
  background: #f8fafc;
}

.immutable-note {
  padding: 0.8rem;
  border-radius: 0.6rem;
  color: #7c2d12;
  background: #fff7ed;
}

.privacy-editor {
  display: grid;
  gap: 1rem;
  margin-top: 1.5rem;
}

.privacy-editor label,
.editor-fields {
  display: grid;
  gap: 0.45rem;
}

.editor-preview-grid {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.editor-fields textarea {
  min-height: 32rem;
  resize: vertical;
}

.preview-card {
  overflow: auto;
  max-height: 44rem;
  padding: 1rem 1.25rem;
  border: 1px solid #cbd5e1;
  border-radius: 0.7rem;
  background: #f8fafc;
}

.preview-title {
  margin-top: 0;
  font-size: 1.6rem;
  font-weight: 700;
}

.privacy-markdown-preview :deep(blockquote) {
  margin-inline: 0;
  padding-left: 1rem;
  border-left: 3px solid #94a3b8;
  color: #475569;
}

.privacy-markdown-preview :deep(pre) {
  overflow: auto;
  padding: 0.85rem;
  border-radius: 0.5rem;
  background: #e2e8f0;
}

.publish-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.history-list {
  display: grid;
  gap: 0.65rem;
  padding: 0;
  list-style: none;
}

.history-list li {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  padding: 0.75rem;
  border-bottom: 1px solid #e2e8f0;
}

.success-message {
  padding: 0.75rem;
  border-radius: 0.5rem;
  color: #166534;
  background: #dcfce7;
}

@media (max-width: 900px) {
  .privacy-summary,
  .language-status-grid,
  .editor-preview-grid {
    grid-template-columns: 1fr;
  }

  .privacy-heading,
  .panel-heading,
  .history-list li {
    grid-template-columns: 1fr;
  }

  .version-meta,
  .publish-panel {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
