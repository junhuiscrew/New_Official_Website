<!-- 页面用途：以字段化双语表单维护唯一Company Profile，不向编辑人员暴露JSON或媒体UUID。 -->
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

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
interface CompanyTranslationDraft {
  locale_id: string
  code: string
  native_name: string
  company_name: string
  short_intro: string
  full_intro: string
  mission: string
  advantages: string
}

useHead({
  title: '公司资料 · Junhui Admin',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
const api = useAuthorityApi()
const message = ref('')
const errorMessage = ref('')
const saving = ref(false)
const profileId = ref<string | null>(null)
const locales = ref<LocaleItem[]>([])
const media = ref<MediaItem[]>([])
const translations = ref<CompanyTranslationDraft[]>([])
const translationStatuses = ref<Array<{ locale_id: string; status: string }>>([])
const publications = ref<Array<{ locale_id: string; status: string }>>([])
const form = reactive({
  status: 'enabled',
  founded_year: '',
  years_experience: '',
  employee_count_range: '',
  factory_area_sqm: '',
  annual_capacity_text: '',
  export_markets: '',
  public_phone: '',
  public_email: '',
  public_address: '',
  latitude: '',
  longitude: '',
  logo_media_id: '',
  primary_factory_media_id: '',
})

/** 读取公司、语言和媒体选项，并把数组转换为“一行一项”的可读表单。 */
async function load(): Promise<void> {
  try {
    const [value, localeResult, mediaResult] = await Promise.all([
      api.detail<{
        profile: Record<string, unknown> | null
        translations: Array<Record<string, unknown>>
        translation_statuses: Array<{ locale_id: string; status: string }>
        publications: Array<{ locale_id: string; status: string }>
      }>('/trust/company-profile'),
      api.detail<LocaleItem[]>('/locales'),
      api.detail<MediaItem[]>('/media'),
    ])
    locales.value = localeResult
    media.value = mediaResult
    profileId.value = value.profile?.id ? String(value.profile.id) : null
    translationStatuses.value = value.translation_statuses || []
    publications.value = value.publications || []
    const profile = value.profile || {}
    Object.assign(form, {
      status: String(profile.status || 'enabled'),
      founded_year: profile.founded_year == null ? '' : String(profile.founded_year),
      years_experience: profile.years_experience == null ? '' : String(profile.years_experience),
      employee_count_range: String(profile.employee_count_range || ''),
      factory_area_sqm: profile.factory_area_sqm == null ? '' : String(profile.factory_area_sqm),
      annual_capacity_text: String(profile.annual_capacity_text || ''),
      export_markets: Array.isArray(profile.export_markets_json)
        ? profile.export_markets_json.join('\n')
        : '',
      public_phone: String(profile.public_phone || ''),
      public_email: String(profile.public_email || ''),
      public_address: String(profile.public_address || ''),
      latitude: profile.latitude == null ? '' : String(profile.latitude),
      longitude: profile.longitude == null ? '' : String(profile.longitude),
      logo_media_id: String(profile.logo_media_id || ''),
      primary_factory_media_id: String(profile.primary_factory_media_id || ''),
    })
    translations.value = localeResult.map((locale) => {
      const source = value.translations.find((item) => item.locale_id === locale.id) || {}
      return {
        locale_id: locale.id,
        code: locale.code,
        native_name: locale.native_name,
        company_name: String(source.company_name || ''),
        short_intro: String(source.short_intro || ''),
        full_intro: String(source.full_intro || ''),
        mission: String(source.mission || ''),
        advantages: Array.isArray(source.advantages_json) ? source.advantages_json.join('\n') : '',
      }
    })
  } catch {
    errorMessage.value = '无法读取公司资料，请检查公司与媒体读取权限。'
  }
}

function optionalNumber(value: string): number | null {
  return value.trim() ? Number(value) : null
}

/** 保存字段化公司资料；正文、媒体与经营事实继续写入现有Company服务及Revision/Audit。 */
async function save(): Promise<void> {
  saving.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    await api.replace('/trust/company-profile', {
      status: form.status,
      founded_year: optionalNumber(form.founded_year),
      years_experience: optionalNumber(form.years_experience),
      employee_count_range: form.employee_count_range || null,
      factory_area_sqm: optionalNumber(form.factory_area_sqm),
      annual_capacity_text: form.annual_capacity_text || null,
      export_markets_json: form.export_markets
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean),
      public_phone: form.public_phone || null,
      public_email: form.public_email || null,
      public_address: form.public_address || null,
      latitude: optionalNumber(form.latitude),
      longitude: optionalNumber(form.longitude),
      logo_media_id: form.logo_media_id || null,
      primary_factory_media_id: form.primary_factory_media_id || null,
      translations: translations.value.map((translation) => ({
        locale_id: translation.locale_id,
        fields: {
          company_name: translation.company_name,
          short_intro: translation.short_intro,
          full_intro: translation.full_intro,
          mission: translation.mission || null,
          advantages_json: translation.advantages
            .split(/\r?\n/)
            .map((item) => item.trim())
            .filter(Boolean),
        },
      })),
    })
    message.value = '公司资料已保存并重新读取。'
    await load()
  } catch {
    errorMessage.value = '保存失败，请检查必填项或刷新后重试。'
  } finally {
    saving.value = false
  }
}

function publicationStatus(localeId: string): string {
  return publications.value.find((item) => item.locale_id === localeId)?.status || 'draft'
}

function localeName(localeId: string): string {
  return locales.value.find((item) => item.id === localeId)?.native_name || '未知语言'
}

async function review(localeId: string): Promise<void> {
  if (!profileId.value) return
  await api.archive(`/trust/company-profile/${profileId.value}/translations/${localeId}/review`)
  await load()
}

async function transition(localeId: string, target: 'published' | 'archived'): Promise<void> {
  if (!profileId.value) return
  await api.archive(`/trust/company-profile/${profileId.value}/publications/${localeId}/${target}`)
  await load()
}

onMounted(load)
</script>

<template>
  <main class="admin-shell company-editor-page">
    <header class="page-heading">
      <div>
        <p class="company-kicker">企业资料</p>
        <h1>公司资料</h1>
        <span>公司正文、公开联系信息和首页视觉的单一维护入口。</span>
      </div>
      <button type="button" :disabled="saving" @click="save">
        {{ saving ? '正在保存…' : '保存公司资料' }}
      </button>
    </header>
    <p v-if="message" class="company-message" role="status">{{ message }}</p>
    <p v-if="errorMessage" class="error-message" role="alert">
      {{ errorMessage }}
    </p>

    <section class="company-panel">
      <header>
        <span>01</span>
        <div>
          <h2>公开基本信息</h2>
          <p>留空字段不会在前台制造事实。</p>
        </div>
      </header>
      <div class="company-grid">
        <label
          >状态<select v-model="form.status">
            <option value="enabled">启用</option>
            <option value="disabled">停用</option>
            <option value="retired">退役</option>
          </select></label
        >
        <label
          >成立年份<input v-model="form.founded_year" type="number" min="1800" max="2200"
        /></label>
        <label>行业经验年数<input v-model="form.years_experience" type="number" min="0" /></label>
        <label>员工规模<input v-model="form.employee_count_range" /></label>
        <label
          >厂房面积（平方米）<input v-model="form.factory_area_sqm" type="number" min="0"
        /></label>
        <label>公开邮箱<input v-model="form.public_email" type="email" /></label>
        <label>公开电话<input v-model="form.public_phone" /></label>
        <label class="company-grid__wide">公开地址<textarea v-model="form.public_address" /></label>
        <label class="company-grid__wide"
          >产能说明<textarea v-model="form.annual_capacity_text" />
        </label>
        <label class="company-grid__wide"
          >出口/演示市场（每行一项）<textarea v-model="form.export_markets" />
        </label>
      </div>
    </section>

    <section class="company-panel">
      <header>
        <span>02</span>
        <div>
          <h2>品牌与首页媒体</h2>
          <p>通过文件名选择媒体，不输入内部ID。</p>
        </div>
      </header>
      <div class="company-grid">
        <label
          >企业 Logo<select v-model="form.logo_media_id">
            <option value="">使用前端品牌资源</option>
            <option
              v-for="asset in media.filter((item) => item.type === 'image')"
              :key="asset.id"
              :value="asset.id"
            >
              {{ asset.filename }}
            </option>
          </select></label
        >
        <label
          >首页主视觉<select v-model="form.primary_factory_media_id">
            <option value="">不使用主视觉</option>
            <option
              v-for="asset in media.filter((item) => item.type === 'image')"
              :key="asset.id"
              :value="asset.id"
            >
              {{ asset.filename }}
            </option>
          </select></label
        >
      </div>
    </section>

    <section class="company-panel">
      <header>
        <span>03</span>
        <div>
          <h2>中英文公司正文</h2>
          <p>每种语言独立保存，优势使用一行一项。</p>
        </div>
      </header>
      <fieldset
        v-for="translation in translations"
        :key="translation.locale_id"
        class="translation-fields"
      >
        <legend>{{ translation.native_name }}</legend>
        <label>公司名称<input v-model="translation.company_name" required /></label>
        <label>首页主标题 / Mission<input v-model="translation.mission" /></label>
        <label>简短介绍<textarea v-model="translation.short_intro" required /></label>
        <label>完整介绍<textarea v-model="translation.full_intro" required /></label>
        <label>公司优势（每行一项）<textarea v-model="translation.advantages" /></label>
      </fieldset>
    </section>

    <section v-if="translationStatuses.length" class="company-panel company-lifecycle">
      <header>
        <span>04</span>
        <div>
          <h2>审核与发布</h2>
          <p>状态变化仍由统一生命周期服务校验权限并写入Audit。</p>
        </div>
      </header>
      <article v-for="item in translationStatuses" :key="item.locale_id">
        <strong>{{ localeName(item.locale_id) }}</strong
        ><span>翻译 {{ item.status }} · 发布 {{ publicationStatus(item.locale_id) }}</span>
        <div>
          <button
            v-if="publicationStatus(item.locale_id) !== 'published'"
            type="button"
            @click="review(item.locale_id)"
          >
            审核翻译</button
          ><button
            v-if="publicationStatus(item.locale_id) === 'review'"
            type="button"
            @click="transition(item.locale_id, 'published')"
          >
            发布</button
          ><button
            v-if="publicationStatus(item.locale_id) === 'published'"
            type="button"
            class="danger"
            @click="transition(item.locale_id, 'archived')"
          >
            撤回
          </button>
        </div>
      </article>
    </section>
  </main>
</template>

<style scoped>
.company-editor-page {
  display: grid;
  align-content: start;
  gap: 1rem;
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
  color: #6c7e90;
}
.company-kicker {
  color: #0f70c9;
  font-size: 0.64rem;
  font-weight: 850;
  letter-spacing: 0.13em;
}
.company-message {
  margin: 0;
  padding: 0.75rem 1rem;
  color: #0d6a4b;
  background: #e8f8f2;
  border: 1px solid #bae6d6;
  border-radius: 0.6rem;
}
.company-panel {
  padding: 1.2rem;
  display: grid;
  gap: 1rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.85rem;
  box-shadow: 0 0.5rem 1.5rem rgb(20 46 73 / 5%);
}
.company-panel > header {
  display: grid;
  grid-template-columns: 2.2rem 1fr;
  gap: 0.7rem;
}
.company-panel > header > span {
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
.company-panel h2,
.company-panel header p {
  margin: 0;
}
.company-panel h2 {
  font-size: 1rem;
}
.company-panel header p {
  margin-top: 0.2rem;
  color: #77889a;
  font-size: 0.7rem;
}
.company-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
}
.company-grid__wide {
  grid-column: 1 / -1;
}
.company-lifecycle article {
  padding: 0.75rem 0;
  display: grid;
  grid-template-columns: minmax(9rem, 0.5fr) minmax(12rem, 1fr) auto;
  align-items: center;
  gap: 0.8rem;
  border-top: 1px solid #e1e8ee;
}
.company-lifecycle article > span {
  color: #687a8e;
  font-size: 0.72rem;
}
.company-lifecycle article > div {
  display: flex;
  gap: 0.45rem;
}
.company-lifecycle button {
  min-height: 2.1rem;
  padding: 0.35rem 0.55rem;
  font-size: 0.68rem;
}
@media (max-width: 42rem) {
  .company-grid {
    grid-template-columns: 1fr;
  }
  .company-grid__wide {
    grid-column: 1;
  }
  .company-lifecycle article {
    grid-template-columns: 1fr;
  }
}
</style>
