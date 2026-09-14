// 测试用途：锁定首页 Hero 轮播的单一 H1、自动播放、手动控制及减弱动态偏好。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { enableAutoUnmount, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import HeroBannerSlider from '../app/components/HeroBannerSlider.vue'
import type { HomepageHeroSlideDto } from '../app/types/public'

enableAutoUnmount(afterEach)

const slides: HomepageHeroSlideDto[] = [
  {
    title: '螺杆与机筒精密制造',
    subtitle: '从材料、工艺到制造能力的 Demo 视觉路径。',
    cta_label: '探索产品',
    cta_href: '/zh-cn/products/',
    media: {
      src: '/api/v1/public/media/hero-1',
      type: 'image',
      mime_type: 'image/webp',
      width: 1600,
      height: 900,
      alt: '螺杆与机筒精密制造演示图',
      caption: null,
      loading: 'eager',
    },
  },
  {
    title: '表面工程与工艺技术',
    subtitle: '围绕实际工艺术语组织公开内容。',
    cta_label: '查看工艺技术',
    cta_href: '/zh-cn/technologies/',
    media: {
      src: '/api/v1/public/media/hero-2',
      type: 'image',
      mime_type: 'image/webp',
      width: 1600,
      height: 900,
      alt: '表面工程与工艺技术演示图',
      caption: null,
      loading: 'lazy',
    },
  },
  {
    title: '制造能力与质量控制',
    subtitle: '查看现有 Demo 制造能力页面。',
    cta_label: null,
    cta_href: null,
    media: {
      src: '/api/v1/public/media/hero-3',
      type: 'image',
      mime_type: 'image/webp',
      width: 1600,
      height: 900,
      alt: '制造能力与质量控制演示图',
      caption: null,
      loading: 'lazy',
    },
  },
]

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  )
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('HeroBannerSlider', () => {
  it('keeps the copy inside responsive gutters and allows safe phrase wrapping', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/components/HeroBannerSlider.vue'),
      'utf8',
    )

    expect(source).toMatch(
      /\.hero-slider__content\s*\{[^}]*width:\s*min\(\s*calc\(100%\s*-\s*var\(--container-gutter\)/s,
    )
    expect(source).toMatch(/\.hero-slider h1\s*\{[^}]*word-break:\s*auto-phrase/s)
    expect(source).toMatch(/\.hero-slider h1\s*\{[^}]*overflow-wrap:\s*anywhere/s)
  })

  it('renders one active H1 and supports manual next, previous and dot navigation', async () => {
    const wrapper = mount(HeroBannerSlider, {
      props: { locale: 'zh-cn', slides, demoMode: true },
    })

    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.get('h1').text()).toBe('螺杆与机筒精密制造')
    expect(wrapper.get('[data-testid="hero-slide-cta"]').attributes('href')).toBe(
      '/zh-cn/products/',
    )

    await wrapper.get('[data-testid="hero-slider-next"]').trigger('click')
    expect(wrapper.get('h1').text()).toBe('表面工程与工艺技术')

    await wrapper.get('[data-testid="hero-slider-previous"]').trigger('click')
    expect(wrapper.get('h1').text()).toBe('螺杆与机筒精密制造')

    await wrapper.get('[data-testid="hero-slider-dot-2"]').trigger('click')
    expect(wrapper.get('h1').text()).toBe('制造能力与质量控制')
    expect(wrapper.find('[data-testid="hero-slide-cta"]').exists()).toBe(false)
  })

  it('autoplays every six seconds and the explicit control pauses and resumes it', async () => {
    const wrapper = mount(HeroBannerSlider, {
      props: { locale: 'zh-cn', slides, demoMode: true },
    })

    await vi.advanceTimersByTimeAsync(6_000)
    expect(wrapper.get('h1').text()).toBe('表面工程与工艺技术')

    await wrapper.get('[data-testid="hero-slider-playback"]').trigger('click')
    await vi.advanceTimersByTimeAsync(12_000)
    expect(wrapper.get('h1').text()).toBe('表面工程与工艺技术')

    await wrapper.get('[data-testid="hero-slider-playback"]').trigger('click')
    await vi.advanceTimersByTimeAsync(6_000)
    expect(wrapper.get('h1').text()).toBe('制造能力与质量控制')
  })

  it('does not autoplay when the visitor prefers reduced motion', async () => {
    vi.mocked(matchMedia).mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as unknown as MediaQueryList)
    const wrapper = mount(HeroBannerSlider, {
      props: { locale: 'zh-cn', slides, demoMode: true },
    })

    await vi.advanceTimersByTimeAsync(18_000)
    expect(wrapper.get('h1').text()).toBe('螺杆与机筒精密制造')
  })
})
