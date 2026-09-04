// 模块用途：把 Admin 规格值表单转换为后端要求的互斥结构化字段。

export type SpecificationValueType = 'text' | 'number' | 'range' | 'boolean' | 'enum'

export interface SpecificationValueDraft {
  product_id: string
  product_model_id: string
  definition_id: string
  value_text: string
  value_number: number | null
  value_min: number | null
  value_max: number | null
  value_boolean: boolean
  enum_value: string
}

export type SpecificationValuePayload = {
  product_id: string | null
  product_model_id: string | null
  definition_id: string
  value_text?: string
  value_number?: number | null
  value_min?: number | null
  value_max?: number | null
  value_boolean?: boolean
  enum_value?: string
}

/**
 * 根据规格类型生成只包含当前类型字段的 API payload。
 *
 * 输入：valueType，规格定义类型；draft，Admin 当前表单值。
 * 输出：SpecificationValuePayload，满足后端互斥值校验的请求体。
 */
export function buildSpecificationValuePayload(
  valueType: SpecificationValueType,
  draft: SpecificationValueDraft,
): SpecificationValuePayload {
  const payload: SpecificationValuePayload = {
    product_id: draft.product_id || null,
    product_model_id: draft.product_model_id || null,
    definition_id: draft.definition_id,
  }

  switch (valueType) {
    case 'text':
      payload.value_text = draft.value_text
      break
    case 'number':
      payload.value_number = draft.value_number
      break
    case 'range':
      payload.value_min = draft.value_min
      payload.value_max = draft.value_max
      break
    case 'boolean':
      payload.value_boolean = draft.value_boolean
      break
    case 'enum':
      payload.enum_value = draft.enum_value
      break
  }

  return payload
}
