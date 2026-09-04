// 工具用途：安全序列化服务端生成的 JSON-LD，避免正文闭合 script 标签。
export function serializeJsonLd(value: unknown): string {
  return JSON.stringify(value).replaceAll('<', '\\u003c')
}
