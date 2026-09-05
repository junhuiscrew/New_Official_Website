// 模块用途：构建最小化 RFQ 提交载荷，并为附件上传生成稳定重试快照。
import type { LocaleSlug } from '../types/public'
import type { RfqSourceType } from '../composables/useLocalePath'

export type RfqItemType = 'product' | 'screw' | 'barrel' | 'component' | 'custom' | 'other'
export type RfqUploadState = 'pending' | 'uploading' | 'uploaded' | 'failed'

export interface RfqInquiryItem {
  item_type: RfqItemType
  product_name_text: string
  quantity: string
  material_text: string
  screw_diameter: string
  length: string
  machine_brand: string
  machine_model: string
  requirements: string
}

export interface RfqFormState {
  company_name: string
  contact_name: string
  email: string
  phone: string
  whatsapp: string
  country_code: string
  website: string
  message: string
  preferred_language: LocaleSlug
  consent_privacy: boolean
  consent_marketing: boolean
  honeypot: string
  items: RfqInquiryItem[]
}

export interface RfqSourceContext {
  type: RfqSourceType
  slug: string
}

export interface RfqPendingAttachment {
  id: string
  file: File
  status: RfqUploadState
}

/** 把空白可选字段转换为 null，避免空字符串触发后端长度校验。 */
function optionalText(value: string): string | null {
  return value.trim() || null
}

/**
 * 构建匿名 RFQ 载荷，只提交可由服务端重新解析的白名单类型与 slug，不接收内部 ID。
 *
 * 输入：form，客户端表单状态；source，可选的公开页面来源。
 * 输出：可直接发送给匿名 RFQ POST 的最小化对象。
 */
export function buildRfqSubmissionPayload(form: RfqFormState, source: RfqSourceContext | null) {
  return {
    company_name: form.company_name.trim(),
    contact_name: form.contact_name.trim(),
    email: form.email.trim(),
    phone: optionalText(form.phone),
    whatsapp: optionalText(form.whatsapp),
    country_code: optionalText(form.country_code)?.toUpperCase() ?? null,
    website: optionalText(form.website),
    message: optionalText(form.message),
    preferred_language: form.preferred_language,
    consent_privacy: form.consent_privacy,
    consent_marketing: form.consent_marketing,
    // 蜜罐值必须原样提交，不能因客户端清洗而削弱后端反垃圾判断。
    honeypot: form.honeypot,
    items: form.items.map((item) => ({
      item_type: item.item_type,
      product_name_text: optionalText(item.product_name_text),
      quantity: optionalText(item.quantity),
      material_text: optionalText(item.material_text),
      screw_diameter: optionalText(item.screw_diameter),
      length: optionalText(item.length),
      machine_brand: optionalText(item.machine_brand),
      machine_model: optionalText(item.machine_model),
      requirements: optionalText(item.requirements),
    })),
    ...(source ? { source_type: source.type, source_slug: source.slug } : {}),
  }
}

/**
 * 冻结本轮待上传文件，仅选择 Pending/Failed，确保重试不重复上传已完成文件。
 *
 * 输入：attachments，当前客户端附件状态。
 * 输出：独立数组快照；上传期间替换文件选择不会改变本轮队列。
 */
export function pendingAttachmentSnapshot(
  attachments: readonly RfqPendingAttachment[],
): RfqPendingAttachment[] {
  return attachments.filter(
    (attachment) => attachment.status === 'pending' || attachment.status === 'failed',
  )
}
