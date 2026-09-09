/**
 * 将可信格式的电话号码转换为 tel 链接。
 *
 * 输入：phone，来自公开公司资料的电话号码或空值。
 * 输出：string | null；可拨号时返回规范化 tel URL，演示标签等非号码文本返回 null。
 */
export function telephoneHref(phone: string | null | undefined): string | null {
  const value = phone?.trim()
  if (!value || !/^\+?[\d\s().-]+$/.test(value)) return null
  const digits = value.replace(/\D/g, '')
  if (digits.length < 6) return null
  return `tel:${value.replace(/[\s().-]/g, '')}`
}
