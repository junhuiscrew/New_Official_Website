<!-- 组件职责：首页高端工业 Hero 轮播，仅消费后端已经通过公开门禁的当前语言 DTO。 -->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { ui } from '~/i18n/ui'
import type { HomepageHeroSlideDto, LocaleSlug } from '~/types/public'

import PublicImage from './PublicImage.vue'

const props = defineProps<{
  locale: LocaleSlug
  slides: HomepageHeroSlideDto[]
  demoMode: boolean
}>()

const labels = computed(() => ui[props.locale])
const activeIndex = ref(0)
const userPaused = ref(false)
const pointerInside = ref(false)
const focusInside = ref(false)
const pageHidden = ref(false)
const reducedMotion = ref(false)
const mounted = ref(false)
const activeSlide = computed(() => props.slides[activeIndex.value] ?? props.slides[0])
const hasMultipleSlides = computed(() => props.slides.length > 1)
const shouldAutoplay = computed(
  () =>
    hasMultipleSlides.value &&
    !userPaused.value &&
    !pointerInside.value &&
    !focusInside.value &&
    !pageHidden.value &&
    !reducedMotion.value,
)

let autoplayTimer: ReturnType<typeof setInterval> | undefined
let motionQuery: MediaQueryList | undefined

/** 输入目标索引；输出无，循环切换到有效轮播项并重置自动播放计时。 */
function goToSlide(index: number): void {
  if (!props.slides.length) return
  activeIndex.value = (index + props.slides.length) % props.slides.length
  restartAutoplay()
}

/** 输入无；输出无，切换到下一张轮播图。 */
function showNext(): void {
  goToSlide(activeIndex.value + 1)
}

/** 输入无；输出无，切换到上一张轮播图。 */
function showPrevious(): void {
  goToSlide(activeIndex.value - 1)
}

/** 输入无；输出无，切换用户主动暂停状态。 */
function togglePlayback(): void {
  userPaused.value = !userPaused.value
}

/** 输入无；输出无，根据当前交互和系统偏好安全重建六秒自动播放计时器。 */
function restartAutoplay(): void {
  if (autoplayTimer !== undefined) {
    clearInterval(autoplayTimer)
    autoplayTimer = undefined
  }
  if (!mounted.value || !shouldAutoplay.value) return
  autoplayTimer = setInterval(() => {
    activeIndex.value = (activeIndex.value + 1) % props.slides.length
  }, 6_000)
}

/** 输入系统减弱动态媒体查询事件；输出无，同步访问者偏好。 */
function updateMotionPreference(event: MediaQueryListEvent | MediaQueryList): void {
  reducedMotion.value = event.matches
}

/** 输入页面可见性事件；输出无，页面位于后台时暂停自动播放。 */
function updatePageVisibility(): void {
  pageHidden.value = document.hidden
}

/** 输入焦点移出事件；输出无，仅当焦点真正离开组件时恢复自动播放。 */
function handleFocusOut(event: FocusEvent): void {
  const root = event.currentTarget as HTMLElement
  focusInside.value = root.contains(event.relatedTarget as Node | null)
}

watch(shouldAutoplay, restartAutoplay)
watch(
  () => props.slides.map((slide) => `${slide.media.src}:${slide.title}`).join('|'),
  () => {
    if (activeIndex.value >= props.slides.length) activeIndex.value = 0
    restartAutoplay()
  },
)

onMounted(() => {
  mounted.value = true
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  updateMotionPreference(motionQuery)
  motionQuery.addEventListener('change', updateMotionPreference)
  document.addEventListener('visibilitychange', updatePageVisibility)
  restartAutoplay()
})

onBeforeUnmount(() => {
  mounted.value = false
  if (autoplayTimer !== undefined) clearInterval(autoplayTimer)
  motionQuery?.removeEventListener('change', updateMotionPreference)
  document.removeEventListener('visibilitychange', updatePageVisibility)
})
</script>

<template>
  <div
    class="hero-slider"
    data-testid="hero-banner-slider"
    aria-roledescription="carousel"
    @mouseenter="pointerInside = true"
    @mouseleave="pointerInside = false"
    @focusin="focusInside = true"
    @focusout="handleFocusOut"
  >
    <template v-if="activeSlide">
      <div class="hero-slider__media" aria-hidden="true">
        <PublicImage
          :key="`${activeSlide.media.src}:${activeSlide.title}`"
          :media="activeSlide.media"
          :locale="locale"
          :priority="activeIndex === 0"
          sizes="100vw"
        />
      </div>
      <div class="hero-slider__veil" aria-hidden="true" />
      <div class="hero-slider__grid" aria-hidden="true" />

      <div class="public-container hero-slider__content" aria-live="polite">
        <div class="hero-slider__copy">
          <div class="hero-slider__badges">
            <p>{{ labels.presentation.badge }}</p>
            <span v-if="demoMode">{{ labels.presentation.demoAsset }}</span>
          </div>
          <h1>{{ activeSlide.title }}</h1>
          <p class="hero-slider__subtitle">{{ activeSlide.subtitle }}</p>
          <a
            v-if="activeSlide.cta_label && activeSlide.cta_href"
            class="hero-slider__cta"
            :href="activeSlide.cta_href"
            data-testid="hero-slide-cta"
          >
            {{ activeSlide.cta_label }}
            <span aria-hidden="true">→</span>
          </a>
        </div>
      </div>
    </template>

    <div v-if="hasMultipleSlides" class="public-container hero-slider__controls">
      <div class="hero-slider__arrows">
        <button
          type="button"
          :aria-label="labels.presentation.sliderPrevious"
          data-testid="hero-slider-previous"
          @click="showPrevious"
        >
          <span aria-hidden="true">←</span>
        </button>
        <button
          type="button"
          :aria-label="labels.presentation.sliderNext"
          data-testid="hero-slider-next"
          @click="showNext"
        >
          <span aria-hidden="true">→</span>
        </button>
      </div>

      <div class="hero-slider__progress" role="tablist" aria-label="Banner slides">
        <button
          v-for="(slide, index) in slides"
          :key="`${slide.media.src}:${slide.title}`"
          type="button"
          :class="{ 'is-active': index === activeIndex }"
          :aria-label="`${labels.presentation.sliderGoTo} ${index + 1}: ${slide.title}`"
          :aria-selected="index === activeIndex"
          :data-testid="`hero-slider-dot-${index}`"
          role="tab"
          @click="goToSlide(index)"
        >
          <span>{{ String(index + 1).padStart(2, '0') }}</span>
        </button>
      </div>

      <button
        type="button"
        class="hero-slider__playback"
        :aria-label="userPaused ? labels.presentation.sliderPlay : labels.presentation.sliderPause"
        :aria-pressed="userPaused"
        data-testid="hero-slider-playback"
        @click="togglePlayback"
      >
        <span aria-hidden="true">{{ userPaused ? '▶' : 'Ⅱ' }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.hero-slider {
  position: relative;
  isolation: isolate;
  min-height: min(49rem, calc(100svh - 4.5rem));
  display: grid;
  align-items: center;
  overflow: hidden;
  color: #fff;
  background: #061525;
}

.hero-slider__media,
.hero-slider__veil,
.hero-slider__grid {
  position: absolute;
  z-index: -3;
  inset: 0;
}

.hero-slider__media :deep(.public-image),
.hero-slider__media :deep(img) {
  width: 100%;
  height: 100%;
}

.hero-slider__media :deep(img) {
  object-fit: cover;
  object-position: center;
  animation: hero-reveal 700ms ease-out both;
}

.hero-slider__veil {
  z-index: -2;
  background:
    linear-gradient(90deg, rgb(2 13 26 / 96%) 0%, rgb(3 21 41 / 87%) 42%, rgb(4 29 54 / 42%) 72%),
    linear-gradient(0deg, rgb(2 14 27 / 74%) 0%, transparent 42%);
}

.hero-slider__grid {
  z-index: -1;
  opacity: 0.18;
  background-image:
    linear-gradient(rgb(126 188 240 / 34%) 1px, transparent 1px),
    linear-gradient(90deg, rgb(126 188 240 / 34%) 1px, transparent 1px);
  background-size: 5rem 5rem;
  mask-image: linear-gradient(90deg, #000, transparent 68%);
}

.hero-slider__content {
  width: 100%;
  padding-block: clamp(6rem, 12vw, 10rem) clamp(8rem, 14vw, 11rem);
}

.hero-slider__copy {
  max-width: 50rem;
  display: grid;
  justify-items: start;
  gap: clamp(1rem, 2vw, 1.6rem);
}

.hero-slider__badges {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  color: #82c8ff;
  font-family: var(--font-technical);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.hero-slider__badges p {
  margin: 0;
}

.hero-slider__badges span {
  padding: 0.34rem 0.58rem;
  color: #071d34;
  background: #91d5ff;
  border-radius: 999px;
}

.hero-slider h1 {
  max-width: 12ch;
  margin: 0;
  color: #fff;
  font-size: clamp(2.7rem, 6vw, 5.8rem);
  line-height: 1.02;
  letter-spacing: -0.045em;
  text-wrap: balance;
}

.hero-slider__subtitle {
  max-width: 42rem;
  margin: 0;
  color: #d5e7f5;
  font-size: clamp(1rem, 1.55vw, 1.24rem);
  line-height: 1.75;
}

.hero-slider__cta {
  min-height: 3.35rem;
  padding: 0.84rem 1.35rem;
  display: inline-flex;
  align-items: center;
  gap: 1.35rem;
  color: #fff;
  background: #086fc9;
  border: 1px solid #339ae9;
  font-weight: 800;
  text-decoration: none;
  box-shadow: 0 1rem 2.5rem rgb(0 89 173 / 32%);
  transition:
    transform 180ms ease,
    background 180ms ease;
}

.hero-slider__cta:hover,
.hero-slider__cta:focus-visible {
  background: #1386e0;
  transform: translateY(-2px);
}

.hero-slider__controls {
  position: absolute;
  right: 0;
  bottom: clamp(2rem, 5vw, 4rem);
  left: 0;
  display: grid;
  grid-template-columns: auto minmax(12rem, 34rem) auto;
  align-items: center;
  gap: 1.25rem;
}

.hero-slider__arrows {
  display: flex;
  gap: 0.5rem;
}

.hero-slider__arrows button,
.hero-slider__playback {
  width: 2.75rem;
  height: 2.75rem;
  display: grid;
  place-items: center;
  color: #fff;
  background: rgb(3 22 42 / 65%);
  border: 1px solid rgb(174 218 250 / 48%);
  cursor: pointer;
  backdrop-filter: blur(0.75rem);
}

.hero-slider__progress {
  display: flex;
  align-items: end;
  gap: 0.7rem;
}

.hero-slider__progress button {
  min-width: 3.3rem;
  padding: 0 0 0.55rem;
  color: #91b2cf;
  background: transparent;
  border: 0;
  border-bottom: 2px solid rgb(179 216 244 / 30%);
  font-family: var(--font-technical);
  font-size: 0.72rem;
  text-align: left;
  cursor: pointer;
  transition:
    color 180ms ease,
    border-color 180ms ease;
}

.hero-slider__progress button.is-active {
  color: #fff;
  border-color: #55b9ff;
}

@keyframes hero-reveal {
  from {
    opacity: 0.55;
    transform: scale(1.025);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@media (max-width: 48rem) {
  .hero-slider {
    min-height: 39rem;
  }

  .hero-slider__media :deep(img) {
    object-position: 64% center;
  }

  .hero-slider__veil {
    background:
      linear-gradient(90deg, rgb(2 13 26 / 94%) 0%, rgb(3 22 42 / 70%) 80%),
      linear-gradient(0deg, rgb(2 14 27 / 88%) 0%, transparent 58%);
  }

  .hero-slider__content {
    padding-block: 5.25rem 9.5rem;
  }

  .hero-slider h1 {
    max-width: 11ch;
    font-size: clamp(2.35rem, 11vw, 3.8rem);
  }

  .hero-slider__controls {
    bottom: 1.5rem;
    grid-template-columns: auto 1fr auto;
    gap: 0.75rem;
  }

  .hero-slider__progress {
    justify-content: center;
  }

  .hero-slider__progress button {
    min-width: 1.8rem;
    color: transparent;
    font-size: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-slider__media :deep(img),
  .hero-slider__cta {
    animation: none;
    transition: none;
  }
}
</style>
