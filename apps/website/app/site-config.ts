// 模块用途：集中维护 Phase 3.1 两个语言 placeholder 的规范化元数据。
export const SITE_URL = 'https://junhuiscrewbarrel.com' as const

export interface LocalePageConfig {
  localeCode: 'zh-CN' | 'en'
  title: string
  description: string
  heading: string
  directAnswer: string
  phaseLabel: string
  canonical: string
  alternates: Record<'zh-CN' | 'en', string>
}

const alternates = {
  'zh-CN': `${SITE_URL}/zh-cn/`,
  en: `${SITE_URL}/en/`,
} as const

export const localePages: Record<'zh-cn' | 'en', LocalePageConfig> = {
  'zh-cn': {
    localeCode: 'zh-CN',
    title: 'Junhui Global Website｜螺杆与机筒制造商官网建设中',
    description:
      'Junhui Global Website 正在建设面向全球塑料机械行业的螺杆、机筒与塑化部件技术网站。',
    heading: 'Junhui Global Website',
    directAnswer: '面向全球塑料机械行业的螺杆、机筒及相关塑化部件 B2B 官网正在建设中。',
    phaseLabel: 'Phase 3.1 基础工程',
    canonical: alternates['zh-CN'],
    alternates,
  },
  en: {
    localeCode: 'en',
    title: 'Junhui Global Website | Screw and Barrel Manufacturer Site in Progress',
    description:
      'Junhui Global Website is building a technical B2B site for screws, barrels, and plasticizing components.',
    heading: 'Junhui Global Website',
    directAnswer:
      'A global B2B website for plastic machinery screws, barrels, and related plasticizing components is in progress.',
    phaseLabel: 'Phase 3.1 foundation',
    canonical: alternates.en,
    alternates,
  },
}
