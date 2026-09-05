<!-- 页面用途：匿名 RFQ 多项目公开表单；客户端状态仅改善体验，后端仍负责全部安全校验。 -->
<script setup lang="ts">
import { computed, nextTick, reactive, ref } from 'vue'

import { normalizeLocale, type RfqSourceType } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import {
  buildRfqSubmissionPayload,
  pendingAttachmentSnapshot,
  type RfqFormState,
  type RfqInquiryItem,
  type RfqPendingAttachment,
} from '~/utils/rfqSubmission'
import { publicRequestStatus } from '~/utils/publicRequest'

const ACCEPTED_EXTENSIONS = '.jpg,.jpeg,.png,.webp,.pdf,.dwg,.dxf,.step,.stp,.iges,.igs'
const MAX_FILE_BYTES = 25 * 1024 * 1024
const MAX_TOTAL_BYTES = 100 * 1024 * 1024
const MAX_FILES = 10

const api = useApi()
const route = useRoute()
const locale = normalizeLocale(route.params.lang)
const labels = computed(() => ui[locale])
const RFQ_SOURCE_TYPES = new Set<RfqSourceType>([
  'product',
  'material',
  'technology',
  'application',
  'solution',
  'case_study',
  'knowledge_article',
  'manufacturing_capability',
  'author_expert',
  'exhibition',
])
const rawSourceType = computed(() => String(route.query.source_type ?? '').trim())
const rawSourceSlug = computed(() => String(route.query.source_slug ?? '').trim())
const sourceQueryPresent = computed(() => Boolean(rawSourceType.value || rawSourceSlug.value))
const sourceType = computed<RfqSourceType | null>(() => {
  const candidate = rawSourceType.value as RfqSourceType
  return RFQ_SOURCE_TYPES.has(candidate) ? candidate : null
})
const sourceSlug = computed(() => {
  const candidate = rawSourceSlug.value.toLowerCase()
  return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(candidate) ? candidate.slice(0, 180) : ''
})
const sourceDismissed = ref(false)
const sourceInvalid = computed(
  () => sourceQueryPresent.value && (!sourceType.value || !sourceSlug.value),
)
const activeSource = computed(() =>
  !sourceDismissed.value && sourceType.value && sourceSlug.value
    ? { type: sourceType.value, slug: sourceSlug.value }
    : null,
)
const invalidSourceMessage = computed(() =>
  locale === 'zh-cn'
    ? '来源页面无效、未发布或已撤回。请移除来源后继续提交。'
    : 'The source page is invalid, unpublished, or withdrawn. Remove it before continuing.',
)
const sourceContext = computed(() => {
  if (sourceDismissed.value) return ''
  if (activeSource.value) return `${activeSource.value.type}: ${activeSource.value.slug}`
  return sourceQueryPresent.value ? invalidSourceMessage.value : ''
})

/** 创建结构一致的询价项目，仅 Product 来源预填产品提示，其他来源只做服务端归因。 */
function createItem(fromProduct = false): RfqInquiryItem {
  return {
    item_type: fromProduct ? 'product' : 'custom',
    product_name_text: fromProduct && sourceType.value === 'product' ? sourceSlug.value : '',
    quantity: '',
    material_text: '',
    screw_diameter: '',
    length: '',
    machine_brand: '',
    machine_model: '',
    requirements: '',
  }
}

const form = reactive<RfqFormState>({
  company_name: '',
  contact_name: '',
  email: '',
  phone: '',
  whatsapp: '',
  country_code: '',
  website: '',
  message: '',
  items: [createItem(Boolean(activeSource.value))],
  consent_privacy: false,
  consent_marketing: false,
  honeypot: '',
  preferred_language: locale,
})
const result = ref('')
const attachments = ref<RfqPendingAttachment[]>([])
const errors = ref<Record<string, string>>({})
const errorMessage = ref('')
const isSubmitting = ref(false)
const errorSummary = ref<HTMLElement | null>(null)
// 提交令牌只留在当前页面内存中，用于失败附件重试；绝不渲染或持久化。
const submissionReference = ref('')
const submissionToken = ref('')
const hasFailedAttachments = computed(() =>
  attachments.value.some((attachment) => attachment.status === 'failed'),
)

/** 新增一个空白项目，最多数量仍由服务端 schema 最终裁决。 */
function addItem(): void {
  form.items.push(createItem())
}

/** 移除指定项目，但始终保留至少一个可填写项目。 */
function removeItem(index: number): void {
  if (form.items.length > 1) form.items.splice(index, 1)
}

/** 执行本地化的基础格式校验；后端仍会完整重验所有字段。 */
function validateForm(): boolean {
  const nextErrors: Record<string, string> = {}
  if (!form.company_name.trim()) nextErrors.company_name = labels.value.error.required
  if (!form.contact_name.trim()) nextErrors.contact_name = labels.value.error.required
  if (!form.email.trim()) nextErrors.email = labels.value.error.required
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    nextErrors.email = labels.value.error.invalidEmail
  }
  if (form.website) {
    try {
      const parsed = new URL(form.website)
      if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('invalid protocol')
    } catch {
      nextErrors.website = labels.value.error.invalidUrl
    }
  }
  if (!form.consent_privacy) nextErrors.consent_privacy = labels.value.error.required
  errors.value = nextErrors
  return Object.keys(nextErrors).length === 0
}

/** 接收本地文件并建立 Pending 状态，不读取或暴露任何私有下载地址。 */
function selectFiles(event: Event): void {
  if (isSubmitting.value || result.value) return
  const input = event.target as HTMLInputElement
  const selected = Array.from(input.files ?? [])
  errorMessage.value = ''
  if (selected.length > MAX_FILES) {
    errorMessage.value = labels.value.error.tooManyFiles
    attachments.value = []
    return
  }
  if (selected.some((file) => file.size > MAX_FILE_BYTES)) {
    errorMessage.value = labels.value.error.fileTooLarge
    attachments.value = []
    return
  }
  if (selected.reduce((total, file) => total + file.size, 0) > MAX_TOTAL_BYTES) {
    errorMessage.value = labels.value.error.totalFilesTooLarge
    attachments.value = []
    return
  }
  attachments.value = selected.map((file, index) => ({
    id: `${index}-${file.size}-${file.lastModified}`,
    file,
    status: 'pending',
  }))
}

/** 通过短期 submission token 顺序上传附件，并独立记录每个文件的最终状态。 */
async function uploadAttachments(reference: string, token: string): Promise<void> {
  let hasFailure = false
  // 先冻结待处理对象；上传期间文件选择已禁用，重试也不会重复发送 Uploaded 文件。
  const uploadQueue = pendingAttachmentSnapshot(attachments.value)
  for (const attachment of uploadQueue) {
    attachment.status = 'uploading'
    const body = new FormData()
    body.append('file', attachment.file)
    body.append('file_category', 'other')
    try {
      await api(`/public/rfqs/${reference}/files`, {
        method: 'POST',
        body,
        headers: { 'X-RFQ-Submission-Token': token },
      })
      attachment.status = 'uploaded'
    } catch {
      attachment.status = 'failed'
      hasFailure = true
    }
  }
  if (hasFailure) errorMessage.value = labels.value.error.uploadFailed
  else submissionToken.value = ''
}

/** 只重试失败附件，复用既有 reference/token，绝不创建第二张询盘。 */
async function retryFailedAttachments(): Promise<void> {
  if (!submissionReference.value || !submissionToken.value || isSubmitting.value) return
  errorMessage.value = ''
  isSubmitting.value = true
  try {
    await uploadAttachments(submissionReference.value, submissionToken.value)
  } finally {
    isSubmitting.value = false
  }
}

/** 提交匿名 RFQ；不发送 query 中的伪造 owner ID，服务端始终保持权威。 */
async function submit(): Promise<void> {
  // 已创建询盘时只能走附件级重试，避免用户重复点击产生重复询盘。
  if (submissionReference.value) return
  errorMessage.value = ''
  result.value = ''
  // 来源参数成对且由白名单约束；非法来源必须由用户明确移除，不能静默丢弃后提交。
  if (!sourceDismissed.value && sourceInvalid.value) {
    errorMessage.value = invalidSourceMessage.value
    await nextTick()
    errorSummary.value?.focus()
    return
  }
  if (!validateForm()) {
    errorMessage.value = labels.value.error.validation
    await nextTick()
    errorSummary.value?.focus()
    return
  }

  isSubmitting.value = true
  try {
    const response = await api<{
      data: { reference: string; status: string; submission_token: string }
    }>('/public/rfqs', {
      method: 'POST',
      body: buildRfqSubmissionPayload(form, activeSource.value),
    })
    result.value = response.data.reference
    submissionReference.value = response.data.reference
    submissionToken.value = response.data.submission_token
    // 短期提交令牌只允许为刚创建的 RFQ 写入 private-rfq。
    await uploadAttachments(response.data.reference, response.data.submission_token)
  } catch (failure: unknown) {
    // 已撤回或未发布的来源由后端返回 422；保留上下文并引导客户移除后重试。
    errorMessage.value =
      publicRequestStatus(failure) === 422 && activeSource.value
        ? invalidSourceMessage.value
        : labels.value.error.loadingFailed
  } finally {
    isSubmitting.value = false
  }
}

useHead(() => ({
  htmlAttrs: { lang: locale === 'zh-cn' ? 'zh-CN' : 'en' },
  title: labels.value.cta.requestQuote,
  meta: [{ name: 'robots', content: 'noindex,follow' }],
}))
</script>

<template>
  <div class="rfq-page">
    <div class="public-container">
      <header class="rfq-page__header">
        <p class="eyebrow">{{ labels.form.inquiryItems }}</p>
        <h1>{{ labels.cta.requestQuote }}</h1>
        <div v-if="sourceContext" class="source-context">
          <p>
            <strong>{{ labels.form.sourceContext }}:</strong> {{ sourceContext }}
          </p>
          <button type="button" @click="sourceDismissed = true">
            {{ locale === 'zh-cn' ? '移除来源并继续' : 'Remove source and continue' }}
          </button>
        </div>
      </header>

      <form class="rfq-form" novalidate @submit.prevent="submit">
        <p
          v-if="errorMessage"
          ref="errorSummary"
          class="rfq-form__message status-error"
          role="alert"
          tabindex="-1"
        >
          {{ errorMessage }}
        </p>
        <p v-if="result" class="rfq-form__message status-success" role="status">
          <strong>{{ labels.form.success }}</strong
          ><br />
          {{ labels.form.successReference }}: <span class="technical-number">{{ result }}</span>
        </p>

        <fieldset>
          <legend>{{ labels.form.contactInformation }}</legend>
          <div class="rfq-form__grid">
            <label for="rfq-company"
              >{{ labels.form.company
              }}<input
                id="rfq-company"
                v-model="form.company_name"
                autocomplete="organization"
                required
                aria-required="true"
                :aria-invalid="Boolean(errors.company_name)"
                :aria-describedby="errors.company_name ? 'rfq-company-error' : undefined"
              /><span
                v-if="errors.company_name"
                id="rfq-company-error"
                class="rfq-form__field-error"
                >{{ errors.company_name }}</span
              ></label
            >
            <label for="rfq-contact"
              >{{ labels.form.name
              }}<input
                id="rfq-contact"
                v-model="form.contact_name"
                autocomplete="name"
                required
                aria-required="true"
                :aria-invalid="Boolean(errors.contact_name)"
                :aria-describedby="errors.contact_name ? 'rfq-contact-error' : undefined"
              /><span
                v-if="errors.contact_name"
                id="rfq-contact-error"
                class="rfq-form__field-error"
                >{{ errors.contact_name }}</span
              ></label
            >
            <label for="rfq-email"
              >{{ labels.form.email
              }}<input
                id="rfq-email"
                v-model="form.email"
                type="email"
                autocomplete="email"
                required
                aria-required="true"
                :aria-invalid="Boolean(errors.email)"
                :aria-describedby="errors.email ? 'rfq-email-error' : undefined"
              /><span v-if="errors.email" id="rfq-email-error" class="rfq-form__field-error">{{
                errors.email
              }}</span></label
            >
            <label for="rfq-phone"
              >{{ labels.form.phone
              }}<input id="rfq-phone" v-model="form.phone" type="tel" autocomplete="tel"
            /></label>
            <label for="rfq-whatsapp"
              >{{ labels.form.whatsapp
              }}<input id="rfq-whatsapp" v-model="form.whatsapp" type="tel"
            /></label>
            <label for="rfq-country"
              >{{ labels.form.country
              }}<input
                id="rfq-country"
                v-model="form.country_code"
                maxlength="2"
                autocomplete="country"
                placeholder="CN"
            /></label>
            <label for="rfq-website" class="rfq-form__wide"
              >{{ labels.form.website
              }}<input
                id="rfq-website"
                v-model="form.website"
                type="url"
                autocomplete="url"
                placeholder="https://"
                :aria-invalid="Boolean(errors.website)"
                :aria-describedby="errors.website ? 'rfq-website-error' : undefined"
              /><span v-if="errors.website" id="rfq-website-error" class="rfq-form__field-error">{{
                errors.website
              }}</span></label
            >
            <label for="rfq-message" class="rfq-form__wide"
              >{{ labels.form.message }}<textarea id="rfq-message" v-model="form.message" />
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>{{ labels.form.inquiryItems }}</legend>
          <div v-for="(item, index) in form.items" :key="index" class="rfq-form__item">
            <div class="rfq-form__grid">
              <label :for="`rfq-item-type-${index}`"
                >{{ labels.form.itemType
                }}<select v-model="item.item_type" :id="`rfq-item-type-${index}`">
                  <option value="product">{{ labels.form.product }}</option>
                  <option value="screw">{{ labels.form.screw }}</option>
                  <option value="barrel">{{ labels.form.barrel }}</option>
                  <option value="component">{{ labels.form.component }}</option>
                  <option value="custom">{{ labels.form.custom }}</option>
                  <option value="other">{{ labels.form.other }}</option>
                </select></label
              >
              <label :for="`rfq-product-${index}`"
                >{{ labels.form.productName
                }}<input :id="`rfq-product-${index}`" v-model="item.product_name_text"
              /></label>
              <label :for="`rfq-quantity-${index}`"
                >{{ labels.form.quantity
                }}<input :id="`rfq-quantity-${index}`" v-model="item.quantity"
              /></label>
              <label :for="`rfq-material-${index}`"
                >{{ labels.form.material
                }}<input :id="`rfq-material-${index}`" v-model="item.material_text"
              /></label>
              <label :for="`rfq-diameter-${index}`"
                >{{ labels.form.screwDiameter
                }}<input :id="`rfq-diameter-${index}`" v-model="item.screw_diameter"
              /></label>
              <label :for="`rfq-length-${index}`"
                >{{ labels.form.length }}<input :id="`rfq-length-${index}`" v-model="item.length"
              /></label>
              <label :for="`rfq-brand-${index}`"
                >{{ labels.form.machineBrand
                }}<input :id="`rfq-brand-${index}`" v-model="item.machine_brand"
              /></label>
              <label :for="`rfq-model-${index}`"
                >{{ labels.form.machineModel
                }}<input :id="`rfq-model-${index}`" v-model="item.machine_model"
              /></label>
              <label :for="`rfq-requirements-${index}`" class="rfq-form__wide"
                >{{ labels.form.itemRequirements
                }}<textarea :id="`rfq-requirements-${index}`" v-model="item.requirements" />
              </label>
            </div>
            <button
              type="button"
              class="rfq-form__secondary"
              :disabled="form.items.length === 1"
              @click="removeItem(index)"
            >
              {{ labels.form.removeItem }}
            </button>
          </div>
          <button type="button" class="rfq-form__secondary" @click="addItem">
            {{ labels.form.addItem }}
          </button>
        </fieldset>

        <fieldset>
          <legend>{{ labels.form.attachments }}</legend>
          <label for="rfq-files"
            >{{ labels.form.chooseFiles
            }}<input
              id="rfq-files"
              type="file"
              multiple
              :accept="ACCEPTED_EXTENSIONS"
              :disabled="isSubmitting || Boolean(result)"
              aria-describedby="rfq-file-policy"
              @change="selectFiles"
          /></label>
          <p id="rfq-file-policy" class="rfq-form__hint">
            {{ labels.form.filePolicy }}
          </p>
          <ul v-if="attachments.length" class="rfq-form__uploads" aria-live="polite">
            <li v-for="attachment in attachments" :key="attachment.id">
              <span>{{ attachment.file.name }}</span
              ><strong :class="`upload-status upload-status--${attachment.status}`">{{
                labels.upload[attachment.status]
              }}</strong>
            </li>
          </ul>
        </fieldset>

        <fieldset>
          <legend>{{ labels.form.privacy }}</legend>
          <label class="rfq-form__check"
            ><input
              v-model="form.consent_privacy"
              type="checkbox"
              required
              aria-required="true"
              :aria-invalid="Boolean(errors.consent_privacy)"
              :aria-describedby="errors.consent_privacy ? 'rfq-consent-privacy-error' : undefined"
            /><span
              >{{ labels.form.privacyConsent }}
              <a :href="`/${locale}/privacy/`">{{ labels.footer.privacy }}</a></span
            ></label
          >
          <span
            v-if="errors.consent_privacy"
            id="rfq-consent-privacy-error"
            class="rfq-form__field-error"
            >{{ errors.consent_privacy }}</span
          >
          <label class="rfq-form__check"
            ><input v-model="form.consent_marketing" type="checkbox" /><span>{{
              labels.form.marketingConsent
            }}</span></label
          >
        </fieldset>

        <label class="honeypot" hidden aria-hidden="true"
          >Website confirmation<input v-model="form.honeypot" tabindex="-1" autocomplete="off"
        /></label>
        <button class="rfq-form__submit" type="submit" :disabled="isSubmitting || Boolean(result)">
          {{ isSubmitting ? labels.form.submitting : labels.form.submit }}
        </button>
        <button
          v-if="hasFailedAttachments && submissionToken"
          class="rfq-form__secondary"
          type="button"
          :disabled="isSubmitting"
          @click="retryFailedAttachments"
        >
          {{ labels.cta.retry }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.rfq-page {
  padding-block: var(--space-12) var(--space-20);
  background: var(--color-neutral-50);
}
.rfq-page__header {
  max-width: 52rem;
  display: grid;
  gap: var(--space-4);
}
.source-context {
  padding: var(--space-3) var(--space-4);
  background: var(--color-blue-50);
  border-inline-start: 3px solid var(--color-blue-600);
}
.rfq-form {
  max-width: 64rem;
  margin-block-start: var(--space-8);
  display: grid;
  gap: var(--space-6);
}
.rfq-form fieldset {
  margin: 0;
  padding: var(--space-6);
  background: var(--color-white);
  border: var(--border-subtle);
}
.rfq-form legend {
  padding-inline: var(--space-2);
  color: var(--color-navy-900);
  font-size: var(--font-size-h3);
  font-weight: 700;
}
.rfq-form__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
}
.rfq-form label {
  display: grid;
  gap: var(--space-2);
}
.rfq-form__wide {
  grid-column: 1 / -1;
}
.rfq-form__item {
  padding-block: var(--space-5);
  border-block-end: var(--border-subtle);
}
.rfq-form__item:first-of-type {
  padding-block-start: 0;
}
.rfq-form__item > button {
  margin-block-start: var(--space-4);
}
.rfq-form__secondary,
.rfq-form__submit {
  min-height: 2.75rem;
  padding: var(--space-2) var(--space-5);
  font-weight: 700;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.rfq-form__secondary {
  color: var(--color-blue-700);
  background: var(--color-white);
  border: 1px solid var(--color-blue-700);
}
.rfq-form__submit {
  justify-self: start;
  color: var(--color-white);
  background: var(--color-blue-700);
  border: 0;
}
.rfq-form__secondary:disabled,
.rfq-form__submit:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.rfq-form__message {
  padding: var(--space-4);
  border: 1px solid currentcolor;
}
.rfq-form__field-error {
  color: var(--color-error);
  font-size: var(--font-size-small);
}
.rfq-form__hint {
  margin-block-start: var(--space-3);
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}
.rfq-form__uploads {
  margin-block-start: var(--space-4);
  padding: 0;
  display: grid;
  gap: var(--space-2);
  list-style: none;
}
.rfq-form__uploads li {
  padding: var(--space-3);
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  background: var(--color-neutral-50);
  border: var(--border-subtle);
}
.upload-status--uploaded {
  color: var(--color-success);
}
.upload-status--failed {
  color: var(--color-error);
}
.upload-status--pending,
.upload-status--uploading {
  color: var(--color-warning);
}
.rfq-form__check {
  grid-template-columns: auto minmax(0, 1fr);
  align-items: start;
  margin-block: var(--space-3);
}
.rfq-form__check input {
  width: 1.2rem;
  min-height: 1.2rem;
  margin-block-start: 0.2rem;
}
.honeypot[hidden] {
  display: none;
}
@media (max-width: 40rem) {
  .rfq-form__grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .rfq-form__wide {
    grid-column: auto;
  }
  .rfq-form fieldset {
    padding: var(--space-5) var(--space-4);
  }
  .rfq-form__uploads li {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
