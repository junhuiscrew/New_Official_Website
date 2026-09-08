// 模块用途：把不可信 Privacy Markdown 解析为受限结构，供 Vue 以文本绑定安全渲染。
export type PrivacyInlineKind = 'text' | 'strong' | 'emphasis' | 'code' | 'link'

export interface PrivacyInlineToken {
  kind: PrivacyInlineKind
  text: string
  href?: string
}

export type PrivacyMarkdownBlock =
  | { kind: 'heading'; level: 2 | 3; tokens: PrivacyInlineToken[] }
  | { kind: 'paragraph'; tokens: PrivacyInlineToken[] }
  | { kind: 'blockquote'; tokens: PrivacyInlineToken[] }
  | { kind: 'unordered-list' | 'ordered-list'; items: PrivacyInlineToken[][] }
  | { kind: 'code'; text: string }

const PRIVACY_LINK_SAFE_ORIGIN = 'https://privacy-preview.invalid'
const CONTROL_CHARACTER_PATTERN = /[\u0000-\u001f\u007f]/
const EXPLICIT_SCHEME_PATTERN = /^([a-z][a-z\d+.-]*):/i

/**
 * 过滤 Markdown 链接，仅允许站内路径、锚点和明确的安全协议。
 *
 * 输入：href，Markdown 中的原始链接。
 * 输出：string | null，安全链接原值或 null。
 */
export function sanitizePrivacyLink(href: string): string | null {
  // URL 解析器会把反斜杠解释成路径分隔符，因此在解析前一律拒绝。
  if (href.includes('\\') || CONTROL_CHARACTER_PATTERN.test(href)) return null
  const trimmed = href.trim()
  if (!trimmed || trimmed.startsWith('//')) return null
  const explicitScheme = EXPLICIT_SCHEME_PATTERN.exec(trimmed)?.[1]?.toLowerCase()

  try {
    if (explicitScheme) {
      const parsed = new URL(trimmed)
      if (parsed.protocol === 'mailto:') {
        const address = trimmed.slice('mailto:'.length)
        // 与后端保持一致：只允许单一邮箱，不接受 subject/body/Bcc 等 header。
        return /^[^\s@<>?,;#&]+@[^\s@<>?,;#&]+$/.test(address) ? trimmed : null
      }
      return ['http:', 'https:'].includes(parsed.protocol) ? trimmed : null
    }

    // 相对 URL 只在固定虚拟 origin 下解析，并要求解析结果仍严格同源。
    const parsed = new URL(trimmed, PRIVACY_LINK_SAFE_ORIGIN)
    return parsed.origin === PRIVACY_LINK_SAFE_ORIGIN ? trimmed : null
  } catch {
    return null
  }
}

/**
 * 将一行 Markdown 转换为可枚举的安全行内 token。
 *
 * 输入：text，标题、段落或列表项原文。
 * 输出：PrivacyInlineToken[]，仅含文本、强调、代码和安全链接。
 */
export function parsePrivacyInline(text: string): PrivacyInlineToken[] {
  const tokens: PrivacyInlineToken[] = []
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|\[[^\]]+\]\([^)]+\))/g
  let cursor = 0
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0
    if (index > cursor) tokens.push({ kind: 'text', text: text.slice(cursor, index) })
    const value = match[0]
    if (value.startsWith('`')) {
      tokens.push({ kind: 'code', text: value.slice(1, -1) })
    } else if (value.startsWith('**') || value.startsWith('__')) {
      tokens.push({ kind: 'strong', text: value.slice(2, -2) })
    } else if (value.startsWith('*') || value.startsWith('_')) {
      tokens.push({ kind: 'emphasis', text: value.slice(1, -1) })
    } else {
      const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(value)
      const href = link ? sanitizePrivacyLink(link[2] ?? '') : null
      const linkText = link?.[1] ?? value
      tokens.push(href ? { kind: 'link', text: linkText, href } : { kind: 'text', text: value })
    }
    cursor = index + value.length
  }
  if (cursor < text.length) tokens.push({ kind: 'text', text: text.slice(cursor) })
  return tokens.length ? tokens : [{ kind: 'text', text }]
}

/**
 * 判断一行是否开始新的受支持块。
 *
 * 输入：line，当前 Markdown 行。
 * 输出：boolean，标题、引用、列表或代码围栏开头时返回 true。
 */
function startsPrivacyBlock(line: string): boolean {
  return (
    /^#{1,3}\s+/.test(line) ||
    /^>\s?/.test(line) ||
    /^\s*[-+*]\s+/.test(line) ||
    /^\s*\d+[.)]\s+/.test(line) ||
    /^```/.test(line)
  )
}

/**
 * 将完整 Markdown 解析为受限块列表，不生成或接受 HTML。
 *
 * 输入：markdown，不可信的完整 Privacy 正文。
 * 输出：PrivacyMarkdownBlock[]，仅包含 h2/h3、段落、列表、引用和代码块数据。
 */
export function parsePrivacyMarkdown(markdown: string): PrivacyMarkdownBlock[] {
  const lines = markdown.replace(/\r\n?/g, '\n').split('\n')
  const blocks: PrivacyMarkdownBlock[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index] ?? ''
    if (!line.trim()) {
      index += 1
      continue
    }

    if (/^```/.test(line)) {
      const codeLines: string[] = []
      index += 1
      while (index < lines.length) {
        const codeLine = lines[index] ?? ''
        if (/^```/.test(codeLine)) break
        codeLines.push(codeLine)
        index += 1
      }
      if (index < lines.length) index += 1
      blocks.push({ kind: 'code', text: codeLines.join('\n') })
      continue
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line)
    if (heading) {
      blocks.push({
        kind: 'heading',
        level: (heading[1] ?? '').length <= 2 ? 2 : 3,
        tokens: parsePrivacyInline(heading[2] ?? ''),
      })
      index += 1
      continue
    }

    const unordered = /^\s*[-+*]\s+(.+)$/.exec(line)
    if (unordered) {
      const items: PrivacyInlineToken[][] = []
      while (index < lines.length) {
        const item = /^\s*[-+*]\s+(.+)$/.exec(lines[index] ?? '')
        if (!item) break
        items.push(parsePrivacyInline(item[1] ?? ''))
        index += 1
      }
      blocks.push({ kind: 'unordered-list', items })
      continue
    }

    const ordered = /^\s*\d+[.)]\s+(.+)$/.exec(line)
    if (ordered) {
      const items: PrivacyInlineToken[][] = []
      while (index < lines.length) {
        const item = /^\s*\d+[.)]\s+(.+)$/.exec(lines[index] ?? '')
        if (!item) break
        items.push(parsePrivacyInline(item[1] ?? ''))
        index += 1
      }
      blocks.push({ kind: 'ordered-list', items })
      continue
    }

    if (/^>\s?/.test(line)) {
      const quoteLines: string[] = []
      while (index < lines.length) {
        const quoteLine = lines[index] ?? ''
        if (!/^>\s?/.test(quoteLine)) break
        quoteLines.push(quoteLine.replace(/^>\s?/, ''))
        index += 1
      }
      blocks.push({ kind: 'blockquote', tokens: parsePrivacyInline(quoteLines.join(' ')) })
      continue
    }

    const paragraphLines = [line.trim()]
    index += 1
    while (index < lines.length) {
      const paragraphLine = lines[index] ?? ''
      if (!paragraphLine.trim() || startsPrivacyBlock(paragraphLine)) break
      paragraphLines.push(paragraphLine.trim())
      index += 1
    }
    blocks.push({ kind: 'paragraph', tokens: parsePrivacyInline(paragraphLines.join(' ')) })
  }

  return blocks
}
