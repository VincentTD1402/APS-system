// Cầu nối postMessage với MES (parent iframe) — đồng bộ đa ngôn ngữ real-time,
// không reload iframe. Giao thức đầy đủ: `docs/# [Bàn giao] MES → APS Đồng bộ đa
// ngôn ngữ qua iframe postMessage.txt`.
import { ref } from 'vue'
import { applyLanguage, registerAvailableLocales, registerGsystemMessages } from '@/i18n'

// 1 dòng config duy nhất, dùng chung mọi môi trường — '*' thay đúng 1 cấp subdomain.
// Nếu APS chạy dev ở origin ngoài *.gsystem.ai (localhost, IP nội bộ), thêm nguyên
// chuỗi origin đó vào đây (không phải hardcode rải rác — vẫn 1 nơi duy nhất).
const MES_ORIGIN_PATTERNS = ['https://*.gsystem.ai']

interface GsystemI18nInit {
  type: 'GSYSTEM_I18N_INIT'
  version: number
  current: string
  languages: Array<{ code: string; flag: string }>
  messages: Record<string, Record<string, string>>
}

interface GsystemI18nChange {
  type: 'GSYSTEM_I18N_CHANGE'
  version: number
  current: string
}

function matchPattern(origin: string, pattern: string): boolean {
  const source = pattern
    .split('*')
    .map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('[^./]+')
  return new RegExp(`^${source}$`).test(origin)
}

function isTrustedMesOrigin(origin: string | null | undefined): boolean {
  return !!origin && MES_ORIGIN_PATTERNS.some((p) => matchPattern(origin, p))
}

function resolveMesOrigin(): string | null {
  const fromParam = new URLSearchParams(location.search).get('parentOrigin')
  let fromReferrer = ''
  try {
    fromReferrer = document.referrer ? new URL(document.referrer).origin : ''
  } catch {
    // ignore malformed referrer
  }
  return [fromParam, fromReferrer].find(isTrustedMesOrigin) || null
}

/** true khi APS đang chạy nhúng trong MES (`?embed=1`) — layout dùng để ẩn UI riêng. */
export const isEmbedded = ref(false)

function handleMessage(event: MessageEvent): void {
  if (!isTrustedMesOrigin(event.origin)) return
  const data = event.data as GsystemI18nInit | GsystemI18nChange | undefined
  if (!data || typeof data !== 'object') return

  switch (data.type) {
    case 'GSYSTEM_I18N_INIT':
      registerAvailableLocales(data.languages?.map((l) => l.code))
      registerGsystemMessages(data.messages)
      applyLanguage(data.current)
      break
    case 'GSYSTEM_I18N_CHANGE':
      applyLanguage(data.current)
      break
  }
}

/**
 * Gọi 1 lần lúc app mount xong. Đọc `embed`/`lang` từ query trước (fallback tránh
 * nháy sai ngôn ngữ lúc mới load), rồi mới bắt tay với MES qua postMessage.
 */
export function initMesBridge(): void {
  const params = new URLSearchParams(location.search)
  isEmbedded.value = params.get('embed') === '1'

  const initialLang = params.get('lang')
  if (initialLang) applyLanguage(initialLang)

  if (!isEmbedded.value || window.parent === window) return

  const mesOrigin = resolveMesOrigin()
  if (!mesOrigin) return

  window.addEventListener('message', handleMessage)
  // MES chỉ gửi GSYSTEM_I18N_INIT SAU KHI nhận được APS_READY.
  window.parent.postMessage({ type: 'APS_READY' }, mesOrigin)
}
