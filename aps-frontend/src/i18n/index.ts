import { createI18n } from 'vue-i18n'
import ko from './ko.json'
import vi from './vi.json'

// Khoá locale = mã ngôn ngữ GSystem (không dùng ISO 'ko'/'vi') — theo giao thức
// postMessage với MES (docs/# [Bàn giao] MES → APS Đồng bộ đa ngôn ngữ qua iframe
// postMessage.txt). ko.json/vi.json vẫn là bộ nhãn RIÊNG của APS (nav, common...),
// đăng ký sẵn dưới đúng mã GSystem tương ứng để 2 hệ dùng chung 1 khoá.
export const GSYSTEM_LOCALE = {
  KO: '10121001',
  EN: '10121002',
  VI: '10121003',
  ZH: '10121004',
  JA: '10121005',
} as const

export type Locale = string

const DEFAULT_LOCALE: Locale = GSYSTEM_LOCALE.VI
const FALLBACK_LOCALE: Locale = GSYSTEM_LOCALE.KO

// `lang` attribute của <html> là chuyện hiển thị/accessibility (SEO, screen reader),
// không phải "khoá locale" mà tài liệu MES cấm dùng ISO — nên map riêng ở đây là ổn.
const HTML_LANG_BY_GSYSTEM: Record<string, string> = {
  [GSYSTEM_LOCALE.KO]: 'ko',
  [GSYSTEM_LOCALE.EN]: 'en',
  [GSYSTEM_LOCALE.VI]: 'vi',
  [GSYSTEM_LOCALE.ZH]: 'zh',
  [GSYSTEM_LOCALE.JA]: 'ja',
}

const stored = localStorage.getItem('aps.locale') || DEFAULT_LOCALE

export const i18n = createI18n({
  legacy: false,
  locale: stored,
  fallbackLocale: FALLBACK_LOCALE,
  messages: {
    [GSYSTEM_LOCALE.KO]: ko,
    [GSYSTEM_LOCALE.VI]: vi,
  },
})

/**
 * `i18n.global`'s TS type locks `locale`/messages to the 2 literal codes known at
 * build time (ko/vi) — but MES gửi mã ngôn ngữ RUNTIME (bất kỳ mã GSystem nào MES
 * công bố), không biết trước lúc build. Cast 1 lần ở đây, không rải `as any` khắp file.
 */
const globalI18n = i18n.global as unknown as {
  locale: { value: string }
  availableLocales: string[]
  mergeLocaleMessage: (locale: string, message: Record<string, unknown>) => void
  setLocaleMessage: (locale: string, message: Record<string, unknown>) => void
}

function setHtmlLang(locale: Locale): void {
  document.documentElement.setAttribute('lang', HTML_LANG_BY_GSYSTEM[locale] || locale)
}

/** Đổi ngôn ngữ chủ động từ UI riêng của APS (standalone, không nhúng MES). */
export function setLocale(locale: Locale): void {
  globalI18n.locale.value = locale
  localStorage.setItem('aps.locale', locale)
  setHtmlLang(locale)
}

/**
 * Áp dụng ngôn ngữ theo lệnh từ MES (`GSYSTEM_I18N_INIT`/`GSYSTEM_I18N_CHANGE`).
 * Không throw, không crash nếu MES gửi mã lạ — giữ nguyên ngôn ngữ hiện tại.
 * Không persist vào localStorage: ngôn ngữ khi nhúng do MES làm chủ, không phải lựa
 * chọn riêng của APS — thoát embed thì APS trở lại locale đã lưu trước đó.
 */
export function applyLanguage(code: string | null | undefined): void {
  if (!code) return
  const key = String(code)
  if (!globalI18n.availableLocales.includes(key)) return
  globalI18n.locale.value = key
  setHtmlLang(key)
}

/**
 * Nạp từ điển dịch MES gửi trong `GSYSTEM_I18N_INIT.messages`.
 * `mergeLocaleMessage` giữ nhãn riêng của APS (ko.json/vi.json) đã có, chỉ bổ
 * sung/ghi đè theo msgCode GSystem — 2 hệ khoá cùng sống trong 1 message pack
 * vì namespace không đụng nhau (nested vs flat `_`).
 */
export function registerGsystemMessages(messages: Record<string, Record<string, string>> | null | undefined): void {
  if (!messages) return
  for (const [code, dict] of Object.entries(messages)) {
    if (!dict) continue
    globalI18n.mergeLocaleMessage(code, dict)
  }
}

/**
 * Đăng ký danh sách ngôn ngữ MES công bố (`GSYSTEM_I18N_INIT.languages`) làm
 * "available locale" ngay cả khi `messages` không có mã đó — để `applyLanguage`
 * không từ chối 1 ngôn ngữ hợp lệ MES vừa báo chỉ vì chưa có dict riêng của APS.
 */
export function registerAvailableLocales(codes: string[] | null | undefined): void {
  if (!codes) return
  for (const code of codes) {
    if (!globalI18n.availableLocales.includes(code)) {
      globalI18n.setLocaleMessage(code, {})
    }
  }
}

setHtmlLang(stored)
