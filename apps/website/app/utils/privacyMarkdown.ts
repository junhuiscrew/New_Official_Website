// 模块用途：把不可信隐私政策 Markdown 解析为受限、安全的纯结构节点。

import { SITE_URL } from '../site-config'

export type PrivacyInlineNode =
  | { type: 'text'; value: string }
  | { type: 'code'; value: string }
  | { type: 'strong'; children: PrivacyInlineNode[] }
  | { type: 'emphasis'; children: PrivacyInlineNode[] }
  | { type: 'link'; href: string; children: PrivacyInlineNode[] }

export type PrivacyMarkdownBlock =
  | { type: 'heading'; level: 2 | 3 | 4 | 5 | 6; children: PrivacyInlineNode[] }
  | { type: 'paragraph'; children: PrivacyInlineNode[] }
  | { type: 'list'; ordered: boolean; items: PrivacyInlineNode[][] }
  | { type: 'blockquote'; children: PrivacyInlineNode[] }
  | { type: 'code'; value: string }

const BLOCK_START = /^(?: {0,3}(?:#{1,6}\s+|>\s?|[-+*]\s+|\d+[.)]\s+|```))/
const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/

/** 合并相邻文本节点，避免渲染器产生大量无意义 span。 */
function appendText(nodes: PrivacyInlineNode[], value: string): void {
  if (!value) return
  const previous = nodes.at(-1)
  if (previous?.type === 'text') previous.value += value
  else nodes.push({ type: 'text', value })
}

/** 仅解码合法 Unicode scalar；超范围值和 UTF-16 代理区都视为非法实体。 */
function decodeNumericEntity(code: string, radix: 10 | 16): string | null {
  const codePoint = Number.parseInt(code, radix)
  if (
    !Number.isInteger(codePoint) ||
    codePoint < 0 ||
    codePoint > 0x10ffff ||
    (codePoint >= 0xd800 && codePoint <= 0xdfff)
  ) {
    return null
  }
  return String.fromCodePoint(codePoint)
}

/** 解码 URI 中常见混淆字符，仅用于识别危险协议；非法实体使整条链接失效。 */
function decodedHrefForInspection(value: string): string | null {
  let hasInvalidNumericEntity = false
  let decoded = value
    .replace(/&#(\d+);?/g, (_match, code: string) => {
      const entity = decodeNumericEntity(code, 10)
      if (entity === null) hasInvalidNumericEntity = true
      return entity ?? ''
    })
    .replace(/&#x([\da-f]+);?/gi, (_match, code: string) => {
      const entity = decodeNumericEntity(code, 16)
      if (entity === null) hasInvalidNumericEntity = true
      return entity ?? ''
    })
    .replace(/&colon;/gi, ':')
    .replace(/&(?:tab|newline);/gi, '')
  if (hasInvalidNumericEntity) return null
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      decoded = decodeURIComponent(decoded)
    } catch {
      break
    }
  }
  return decoded.replace(/[\u0000-\u0020\u007f]+/g, '').toLowerCase()
}

/**
 * 验证 Markdown 链接是否属于允许范围。
 *
 * 输入：candidate，Markdown 圆括号内的原始链接。
 * 输出：string | null，可安全写入 href 的地址；危险或格式异常时返回 null。
 */
export function safePrivacyHref(candidate: string): string | null {
  const href = candidate.trim().replace(/^<|>$/g, '')
  if (!href || href.startsWith('//') || href.includes('\\') || CONTROL_CHARACTERS.test(href)) {
    return null
  }
  const inspected = decodedHrefForInspection(href)
  if (inspected === null) return null
  if (/^(?:javascript|vbscript|data):/.test(inspected)) return null

  try {
    if (/^mailto:/i.test(href)) {
      const address = href.slice('mailto:'.length)
      // Privacy 正文只允许单一邮箱地址，不接受可注入 subject/body/Bcc 的 mailto header。
      return /^[^\s@<>?,;#&]+@[^\s@<>?,;#&]+$/.test(address) ? href : null
    }
    if (/^https?:\/\//i.test(href)) {
      const parsed = new URL(href)
      return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? href : null
    }
    // 不带 scheme 的地址必须能在正式站 origin 内解析，拒绝协议相对与解析异常值。
    if (!/^[a-z][a-z\d+.-]*:/i.test(href)) {
      const siteOrigin = new URL(SITE_URL).origin
      const parsed = new URL(href, `${siteOrigin}/`)
      return parsed.origin === siteOrigin ? href : null
    }
  } catch {
    return null
  }
  return null
}

const MAX_INLINE_DEPTH = 8

/** 把单行 Markdown 以游标线性解析为安全节点，避免反复切片扫描未闭合标记。 */
function parseInline(value: string, depth = 0): PrivacyInlineNode[] {
  const nodes: PrivacyInlineNode[] = []
  let cursor = 0
  let textStart = 0

  /** 提交当前普通文本片段，并把新的文本起点移动到 end。 */
  const flushText = (end: number): void => {
    appendText(nodes, value.slice(textStart, end))
    textStart = end
  }

  while (cursor < value.length) {
    const marker = value[cursor] ?? ''
    if (!'![`*_'.includes(marker)) {
      cursor += 1
      continue
    }

    // 图片语法永远保持普通文本；找不到闭合符时余下内容整体结束，避免二次扫描。
    if (marker === '!' && value[cursor + 1] === '[') {
      const labelEnd = value.indexOf('](', cursor + 2)
      const destinationEnd = labelEnd >= 0 ? value.indexOf(')', labelEnd + 2) : -1
      if (labelEnd < 0 || destinationEnd < 0) break
      flushText(cursor)
      appendText(nodes, value.slice(cursor, destinationEnd + 1))
      cursor = destinationEnd + 1
      textStart = cursor
      continue
    }

    if (marker === '[') {
      const labelEnd = value.indexOf('](', cursor + 1)
      const destinationEnd = labelEnd >= 0 ? value.indexOf(')', labelEnd + 2) : -1
      if (labelEnd < 0 || destinationEnd < 0) break
      const label = value.slice(cursor + 1, labelEnd)
      const rawHref = value.slice(labelEnd + 2, destinationEnd)
      if (!label) {
        cursor += 1
        continue
      }
      flushText(cursor)
      const href = safePrivacyHref(rawHref)
      const original = value.slice(cursor, destinationEnd + 1)
      if (href) {
        const children =
          depth < MAX_INLINE_DEPTH
            ? parseInline(label, depth + 1)
            : [{ type: 'text' as const, value: label }]
        nodes.push({ type: 'link', href, children })
      } else {
        appendText(nodes, original)
      }
      cursor = destinationEnd + 1
      textStart = cursor
      continue
    }

    if (marker === '`') {
      const end = value.indexOf('`', cursor + 1)
      if (end < 0) break
      if (end === cursor + 1) {
        cursor += 1
        continue
      }
      flushText(cursor)
      nodes.push({ type: 'code', value: value.slice(cursor + 1, end) })
      cursor = end + 1
      textStart = cursor
      continue
    }

    const strongMarker = value.startsWith('**', cursor)
      ? '**'
      : value.startsWith('__', cursor)
        ? '__'
        : null
    if (strongMarker) {
      const contentStart = cursor + strongMarker.length
      const end = value.indexOf(strongMarker, contentStart)
      if (end < 0) break
      if (end === contentStart) {
        cursor = contentStart
        continue
      }
      flushText(cursor)
      const inner = value.slice(contentStart, end)
      const children =
        depth < MAX_INLINE_DEPTH
          ? parseInline(inner, depth + 1)
          : [{ type: 'text' as const, value: inner }]
      nodes.push({ type: 'strong', children })
      cursor = end + strongMarker.length
      textStart = cursor
      continue
    }

    if (marker === '*' || marker === '_') {
      const end = value.indexOf(marker, cursor + 1)
      if (end < 0) break
      if (end === cursor + 1) {
        cursor += 1
        continue
      }
      flushText(cursor)
      const inner = value.slice(cursor + 1, end)
      const children =
        depth < MAX_INLINE_DEPTH
          ? parseInline(inner, depth + 1)
          : [{ type: 'text' as const, value: inner }]
      nodes.push({ type: 'emphasis', children })
      cursor = end + 1
      textStart = cursor
      continue
    }

    cursor += 1
  }
  flushText(value.length)
  return nodes
}

/**
 * 将隐私政策 Markdown 转换为安全结构节点。
 *
 * 输入：markdown，后端交付但仍按不可信内容处理的 Markdown 字符串。
 * 输出：PrivacyMarkdownBlock[]，仅包含渲染白名单允许的结构节点。
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

    const fence = line.match(/^ {0,3}```[^`]*$/)
    if (fence) {
      const codeLines: string[] = []
      let cursor = index + 1
      while (cursor < lines.length && !/^ {0,3}```\s*$/.test(lines[cursor] ?? '')) {
        codeLines.push(lines[cursor] ?? '')
        cursor += 1
      }
      if (cursor < lines.length) {
        blocks.push({ type: 'code', value: codeLines.join('\n') })
        index = cursor + 1
        continue
      }
    }

    const heading = line.match(/^ {0,3}(#{1,6})\s+(.+?)\s*$/)
    if (heading) {
      const level = Math.min(6, (heading[1]?.length ?? 1) + 1) as 2 | 3 | 4 | 5 | 6
      blocks.push({ type: 'heading', level, children: parseInline(heading[2] ?? '') })
      index += 1
      continue
    }

    const quote = line.match(/^ {0,3}>\s?(.*)$/)
    if (quote) {
      const quotedLines: string[] = [quote[1] ?? '']
      index += 1
      while (index < lines.length) {
        const continuation = (lines[index] ?? '').match(/^ {0,3}>\s?(.*)$/)
        if (!continuation) break
        quotedLines.push(continuation[1] ?? '')
        index += 1
      }
      blocks.push({ type: 'blockquote', children: parseInline(quotedLines.join(' ')) })
      continue
    }

    const listItem = line.match(/^ {0,3}([-+*]|\d+[.)])\s+(.+)$/)
    if (listItem) {
      const ordered = /^\d/.test(listItem[1] ?? '')
      const items: PrivacyInlineNode[][] = []
      while (index < lines.length) {
        const candidate = (lines[index] ?? '').match(/^ {0,3}([-+*]|\d+[.)])\s+(.+)$/)
        if (!candidate || /^\d/.test(candidate[1] ?? '') !== ordered) break
        items.push(parseInline(candidate[2] ?? ''))
        index += 1
      }
      blocks.push({ type: 'list', ordered, items })
      continue
    }

    // 未识别的块语法按普通段落文本处理；Vue 插值会继续转义原始 HTML。
    const paragraphLines = [line]
    index += 1
    while (
      index < lines.length &&
      (lines[index] ?? '').trim() &&
      !BLOCK_START.test(lines[index] ?? '')
    ) {
      paragraphLines.push(lines[index] ?? '')
      index += 1
    }
    blocks.push({ type: 'paragraph', children: parseInline(paragraphLines.join(' ')) })
  }
  return blocks
}
