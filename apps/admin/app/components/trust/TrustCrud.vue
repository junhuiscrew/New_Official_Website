<!-- 组件职责：以字段化表单维护能力、设备、证书、专利、荣誉和展会，隐藏内部UUID与JSON表示。 -->
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

interface TrustItem {
  id: string
  slug: string
  status: string
  sort_order: number
  translations?: Array<Record<string, unknown>>
  translation_statuses?: Array<{ locale_id: string; status: string }>
  publications?: Array<{ locale_id: string; status: string }>
  [key: string]: unknown
}

interface LocaleItem {
  id: string
  code: string
  native_name: string
}
interface MediaItem {
  id: string
  filename: string
  type: string
}
type FieldKind = 'text' | 'number' | 'date' | 'url' | 'media' | 'lines' | 'key-value' | 'checkbox'
interface FieldDefinition {
  key: string
  label: string
  kind?: FieldKind
  required?: boolean
}
interface TranslationDraft {
  locale_id: string
  code: string
  native_name: string
  fields: Record<string, string>
}

const props = defineProps<{ title: string; resource: string }>()
const api = useAuthorityApi()
const hasIndependentRoute = computed(() => ['capabilities', 'exhibitions'].includes(props.resource))
const items = ref<TrustItem[]>([])
const locales = ref<LocaleItem[]>([])
const media = ref<MediaItem[]>([])
const editingId = ref<string | null>(null)
const slug = ref('')
const status = ref('enabled')
const sortOrder = ref(0)
const masterFields = reactive<Record<string, string | boolean>>({})
const translations = ref<TranslationDraft[]>([])
const errorMessage = ref('')
const saving = ref(false)

const fieldMap: Record<string, FieldDefinition[]> = {
  capabilities: [
    { key: 'capability_type', label: '能力类型', required: true },
    { key: 'primary_media_id', label: '主图', kind: 'media' },
  ],
  equipment: [
    { key: 'equipment_type', label: '设备类型', required: true },
    { key: 'manufacturer', label: '制造商' },
    { key: 'model', label: '型号' },
    { key: 'quantity', label: '数量', kind: 'number' },
    { key: 'commissioning_year', label: '投产年份', kind: 'number' },
    { key: 'precision_text', label: '精度说明' },
    { key: 'capacity_text', label: '能力说明' },
    { key: 'featured', label: '首页推荐', kind: 'checkbox' },
    { key: 'primary_media_id', label: '设备图片', kind: 'media' },
  ],
  certificates: [
    { key: 'certificate_type', label: '证书类型', required: true },
    { key: 'certificate_number', label: '证书编号' },
    { key: 'issuer', label: '颁发机构', required: true },
    { key: 'issue_date', label: '颁发日期', kind: 'date' },
    { key: 'expiry_date', label: '到期日期', kind: 'date' },
    { key: 'verification_url', label: '验证地址', kind: 'url' },
    { key: 'primary_media_id', label: '展示图片', kind: 'media' },
    { key: 'public_file_media_id', label: '公开文件', kind: 'media' },
  ],
  patents: [
    { key: 'patent_number', label: '专利号', required: true },
    { key: 'patent_type', label: '专利类型', required: true },
    { key: 'application_number', label: '申请号' },
    { key: 'filing_date', label: '申请日期', kind: 'date' },
    { key: 'grant_date', label: '授权日期', kind: 'date' },
    { key: 'jurisdiction', label: '司法辖区' },
    { key: 'inventor_text', label: '发明人说明' },
    { key: 'verification_url', label: '验证地址', kind: 'url' },
    { key: 'primary_media_id', label: '展示图片', kind: 'media' },
  ],
  honors: [
    { key: 'issuing_organization', label: '颁发组织', required: true },
    { key: 'award_date', label: '获奖日期', kind: 'date' },
    { key: 'primary_media_id', label: '展示图片', kind: 'media' },
  ],
  exhibitions: [
    { key: 'event_name', label: '展会名称', required: true },
    { key: 'country_code', label: '国家代码' },
    { key: 'city', label: '城市' },
    { key: 'start_date', label: '开始日期', kind: 'date' },
    { key: 'end_date', label: '结束日期', kind: 'date' },
    { key: 'booth_no', label: '展位号' },
    { key: 'primary_media_id', label: '展示图片', kind: 'media' },
  ],
}

const translationFieldMap: Record<string, FieldDefinition[]> = {
  capabilities: [
    { key: 'name', label: '名称', required: true },
    { key: 'summary', label: '摘要' },
    { key: 'description', label: '正文' },
    { key: 'key_facts_json', label: '关键事实（每行一项）', kind: 'lines' },
  ],
  equipment: [
    { key: 'name', label: '名称', required: true },
    { key: 'summary', label: '摘要' },
    { key: 'description', label: '说明' },
    { key: 'public_specs_json', label: '公开规格（每行“名称=值”）', kind: 'key-value' },
  ],
  certificates: [
    { key: 'name', label: '证书名称', required: true },
    { key: 'summary', label: '摘要' },
    { key: 'scope', label: '适用范围' },
  ],
  patents: [
    { key: 'title', label: '专利标题', required: true },
    { key: 'summary', label: '摘要' },
    { key: 'technical_scope', label: '技术范围' },
  ],
  honors: [
    { key: 'title', label: '荣誉标题', required: true },
    { key: 'summary', label: '摘要' },
  ],
  exhibitions: [
    { key: 'title', label: '展会标题', required: true },
    { key: 'summary', label: '摘要' },
    { key: 'description', label: '正文' },
  ],
}

const masterDefinitions = computed(() => fieldMap[props.resource] ?? [])
const translationDefinitions = computed(() => translationFieldMap[props.resource] ?? [])

/** 输入结构化字段值和显示类型；输出无需JSON语法的可读编辑文本。 */
function toDisplayValue(value: unknown, kind: FieldKind = 'text'): string | boolean {
  if (kind === 'checkbox') return Boolean(value)
  if (kind === 'lines' && Array.isArray(value)) return value.join('\n')
  if (kind === 'key-value' && value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `${key}=${String(item ?? '')}`)
      .join('\n')
  }
  return value === null || value === undefined ? '' : String(value)
}

/** 输入表单文本和字段类型；输出后端结构化字段值。 */
function toPayloadValue(value: string | boolean, kind: FieldKind = 'text'): unknown {
  if (kind === 'checkbox') return Boolean(value)
  const text = String(value).trim()
  if (!text) return null
  if (kind === 'number') return Number(text)
  if (kind === 'lines')
    return text
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean)
  if (kind === 'key-value') {
    return Object.fromEntries(
      text
        .split(/\r?\n/)
        .map((line) => line.split('=').map((part) => part.trim()))
        .filter((parts) => parts.length >= 2 && parts[0])
        .map(([key, ...rest]) => [key, rest.join('=')]),
    )
  }
  return text
}

function resetForm(): void {
  editingId.value = null
  slug.value = ''
  status.value = 'enabled'
  sortOrder.value = 0
  for (const key of Object.keys(masterFields)) delete masterFields[key]
  for (const definition of masterDefinitions.value) {
    masterFields[definition.key] = definition.kind === 'checkbox' ? false : ''
  }
  translations.value = locales.value.map((locale) => ({
    locale_id: locale.id,
    code: locale.code,
    native_name: locale.native_name,
    fields: Object.fromEntries(translationDefinitions.value.map((field) => [field.key, ''])),
  }))
}

/** 读取当前Trust类型、语言和媒体选项，三组请求均来自真实Admin API。 */
async function load(): Promise<void> {
  try {
    const [result, localeResult, mediaResult] = await Promise.all([
      api.list<TrustItem>(`/trust/${props.resource}`),
      api.detail<LocaleItem[]>('/locales'),
      api.detail<MediaItem[]>('/media'),
    ])
    items.value = result.items
    locales.value = localeResult
    media.value = mediaResult
    resetForm()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法读取信任内容。'
  }
}

function edit(item: TrustItem): void {
  editingId.value = item.id
  slug.value = item.slug
  status.value = item.status
  sortOrder.value = item.sort_order
  for (const definition of masterDefinitions.value) {
    masterFields[definition.key] = toDisplayValue(item[definition.key], definition.kind)
  }
  translations.value = locales.value.map((locale) => {
    const source = item.translations?.find((row) => row.locale_id === locale.id) ?? {}
    return {
      locale_id: locale.id,
      code: locale.code,
      native_name: locale.native_name,
      fields: Object.fromEntries(
        translationDefinitions.value.map((definition) => [
          definition.key,
          String(toDisplayValue(source[definition.key], definition.kind)),
        ]),
      ),
    }
  })
}

/** 将字段化表单保存回现有Trust服务，保留Revision、Audit和生命周期。 */
async function save(): Promise<void> {
  saving.value = true
  errorMessage.value = ''
  try {
    const body = {
      slug: slug.value,
      status: status.value,
      sort_order: sortOrder.value,
      fields: Object.fromEntries(
        masterDefinitions.value.map((definition) => [
          definition.key,
          toPayloadValue(masterFields[definition.key] ?? '', definition.kind),
        ]),
      ),
      translations: translations.value.map((translation) => ({
        locale_id: translation.locale_id,
        fields: Object.fromEntries(
          translationDefinitions.value.map((definition) => [
            definition.key,
            toPayloadValue(translation.fields[definition.key] ?? '', definition.kind),
          ]),
        ),
      })),
    }
    if (editingId.value) await api.update(`/trust/${props.resource}/${editingId.value}`, body)
    else await api.create(`/trust/${props.resource}`, body)
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法保存信任内容。'
  } finally {
    saving.value = false
  }
}

async function archiveEntity(item: TrustItem): Promise<void> {
  edit(item)
  status.value = 'retired'
  await save()
}

function publicationStatus(item: TrustItem, localeId: string): string {
  return (
    item.publications?.find((publication) => publication.locale_id === localeId)?.status || 'draft'
  )
}

function localeName(localeId: string): string {
  return locales.value.find((locale) => locale.id === localeId)?.native_name || '未知语言'
}

async function reviewTranslation(item: TrustItem, localeId: string): Promise<void> {
  await api.archive(`/trust/${props.resource}/${item.id}/translations/${localeId}/review`)
  await load()
}

async function publishTranslation(item: TrustItem, localeId: string): Promise<void> {
  await api.archive(`/trust/${props.resource}/${item.id}/translations/${localeId}/publish`)
  await load()
}

async function transitionPublication(
  item: TrustItem,
  localeId: string,
  target: 'published' | 'archived',
): Promise<void> {
  await api.archive(`/trust/${props.resource}/${item.id}/publications/${localeId}/${target}`)
  await load()
}

onMounted(load)
</script>

<template>
  <main class="admin-shell trust-editor-page">
    <header class="page-heading">
      <div>
        <p class="trust-kicker">TRUST &amp; CAPABILITY</p>
        <h1>{{ title }}</h1>
        <span>字段、媒体与双语正文均保存到现有CMS实体。</span>
      </div>
      <button type="button" @click="resetForm">新建记录</button>
    </header>
    <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>

    <div class="trust-editor-layout">
      <aside class="record-list">
        <button
          v-for="item in items"
          :key="item.id"
          type="button"
          :class="{ active: editingId === item.id }"
          @click="edit(item)"
        >
          <strong>{{ item.slug }}</strong
          ><span>{{ item.status }}</span>
        </button>
      </aside>

      <form class="editor-form trust-editor-form" @submit.prevent="save">
        <section class="trust-form-section">
          <header>
            <span>01</span>
            <div>
              <h2>基础信息</h2>
              <p>稳定地址、状态与排序</p>
            </div>
          </header>
          <div class="trust-form-grid">
            <label>Slug<input v-model="slug" required pattern="[a-z0-9-]+" /></label>
            <label
              >状态<select v-model="status">
                <option value="enabled">启用</option>
                <option value="disabled">停用</option>
                <option value="retired">退役</option>
              </select></label
            >
            <label>排序<input v-model.number="sortOrder" type="number" /></label>
          </div>
        </section>

        <section class="trust-form-section">
          <header>
            <span>02</span>
            <div>
              <h2>结构化事实</h2>
              <p>按当前内容类型提供可读字段</p>
            </div>
          </header>
          <div class="trust-form-grid">
            <label
              v-for="field in masterDefinitions"
              :key="field.key"
              :class="{ 'trust-checkbox': field.kind === 'checkbox' }"
            >
              <template v-if="field.kind === 'checkbox'"
                ><input v-model="masterFields[field.key]" type="checkbox" />{{
                  field.label
                }}</template
              >
              <template v-else
                >{{ field.label }}
                <select
                  v-if="field.kind === 'media'"
                  v-model="masterFields[field.key]"
                  :required="field.required"
                >
                  <option value="">不使用媒体</option>
                  <option v-for="asset in media" :key="asset.id" :value="asset.id">
                    {{ asset.filename }}
                  </option>
                </select>
                <input
                  v-else
                  v-model="masterFields[field.key]"
                  :type="
                    field.kind === 'number'
                      ? 'number'
                      : field.kind === 'date'
                        ? 'date'
                        : field.kind === 'url'
                          ? 'url'
                          : 'text'
                  "
                  :required="field.required"
                />
              </template>
            </label>
          </div>
        </section>

        <section class="trust-form-section">
          <header>
            <span>03</span>
            <div>
              <h2>中英文内容</h2>
              <p>数组和规格使用“一行一项”，无需JSON</p>
            </div>
          </header>
          <fieldset
            v-for="translation in translations"
            :key="translation.locale_id"
            class="translation-fields"
          >
            <legend>{{ translation.native_name }}</legend>
            <label v-for="field in translationDefinitions" :key="field.key"
              >{{ field.label }}
              <textarea
                v-if="
                  ['lines', 'key-value'].includes(field.kind || '') ||
                  ['summary', 'description', 'scope', 'technical_scope'].includes(field.key)
                "
                v-model="translation.fields[field.key]"
                :required="field.required"
              />
              <input v-else v-model="translation.fields[field.key]" :required="field.required" />
            </label>
          </fieldset>
        </section>

        <div class="form-actions">
          <button type="submit" :disabled="saving">
            {{ saving ? '正在保存…' : editingId ? '保存更改' : '创建记录' }}</button
          ><button
            v-if="editingId"
            type="button"
            class="danger"
            @click="archiveEntity(items.find((item) => item.id === editingId)!)"
          >
            归档记录
          </button>
        </div>
      </form>
    </div>

    <section class="trust-lifecycle">
      <header>
        <p class="trust-kicker">CONTENT LIFECYCLE</p>
        <h2>翻译与发布状态</h2>
      </header>
      <article v-for="item in items" :key="`lifecycle-${item.id}`">
        <strong>{{ item.slug }}</strong>
        <div
          v-for="translationStatus in item.translation_statuses || []"
          :key="translationStatus.locale_id"
        >
          <span
            >{{ localeName(translationStatus.locale_id) }} · {{ translationStatus.status
            }}<template v-if="hasIndependentRoute">
              · {{ publicationStatus(item, translationStatus.locale_id) }}</template
            ></span
          >
          <button
            v-if="translationStatus.status === 'draft'"
            type="button"
            @click="reviewTranslation(item, translationStatus.locale_id)"
          >
            审核翻译
          </button>
          <button
            v-if="
              hasIndependentRoute &&
              publicationStatus(item, translationStatus.locale_id) === 'review'
            "
            type="button"
            @click="transitionPublication(item, translationStatus.locale_id, 'published')"
          >
            发布
          </button>
          <button
            v-if="!hasIndependentRoute && translationStatus.status === 'human_reviewed'"
            type="button"
            @click="publishTranslation(item, translationStatus.locale_id)"
          >
            发布翻译
          </button>
          <button
            v-if="
              hasIndependentRoute &&
              publicationStatus(item, translationStatus.locale_id) === 'published'
            "
            type="button"
            class="danger"
            @click="transitionPublication(item, translationStatus.locale_id, 'archived')"
          >
            撤回
          </button>
        </div>
      </article>
    </section>
  </main>
</template>

<style scoped>
.trust-editor-page {
  display: grid;
  align-content: start;
  gap: 1.1rem;
}
.page-heading > div {
  display: grid;
  gap: 0.2rem;
}
.page-heading p,
.page-heading h1 {
  margin: 0;
}
.page-heading span {
  color: #6f8092;
}
.trust-kicker {
  color: #0f70c9;
  font-size: 0.64rem;
  font-weight: 850;
  letter-spacing: 0.13em;
}
.trust-editor-layout {
  display: grid;
  grid-template-columns: minmax(14rem, 0.65fr) minmax(0, 2fr);
  gap: 1rem;
  align-items: start;
}
.trust-editor-form {
  padding: 0;
  overflow: hidden;
}
.trust-form-section {
  padding: 1.25rem;
  display: grid;
  gap: 1rem;
  border-bottom: 1px solid #dfe7ee;
}
.trust-form-section > header {
  display: grid;
  grid-template-columns: 2.2rem 1fr;
  gap: 0.65rem;
}
.trust-form-section > header > span {
  width: 1.9rem;
  height: 1.55rem;
  display: grid;
  place-items: center;
  color: #0d68b5;
  background: #e9f5fd;
  border-radius: 0.3rem;
  font-size: 0.6rem;
  font-weight: 850;
}
.trust-form-section h2,
.trust-form-section p {
  margin: 0;
}
.trust-form-section h2 {
  font-size: 1rem;
}
.trust-form-section p {
  margin-top: 0.2rem;
  color: #758699;
  font-size: 0.7rem;
}
.trust-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
}
.trust-checkbox {
  align-self: end;
  min-height: 2.7rem;
  display: flex !important;
  grid-template-columns: auto 1fr;
  align-items: center;
}
.trust-checkbox input {
  width: 1rem;
  min-height: 1rem;
}
.translation-fields {
  margin: 0;
}
.form-actions {
  padding: 1.1rem 1.25rem;
}
.trust-lifecycle {
  padding: 1.2rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.85rem;
}
.trust-lifecycle header {
  margin-bottom: 0.8rem;
}
.trust-lifecycle h2 {
  margin: 0.2rem 0 0;
  font-size: 1.1rem;
}
.trust-lifecycle article {
  padding: 0.75rem 0;
  display: grid;
  grid-template-columns: minmax(10rem, 0.6fr) minmax(0, 1.4fr);
  gap: 0.8rem;
  border-top: 1px solid #e1e8ee;
}
.trust-lifecycle article > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}
.trust-lifecycle article span {
  color: #627588;
  font-size: 0.72rem;
}
.trust-lifecycle button {
  min-height: 2rem;
  padding: 0.35rem 0.55rem;
  font-size: 0.68rem;
}
@media (max-width: 58rem) {
  .trust-editor-layout {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 42rem) {
  .trust-form-grid {
    grid-template-columns: 1fr;
  }
  .trust-lifecycle article {
    grid-template-columns: 1fr;
  }
}
</style>
