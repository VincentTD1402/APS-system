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

// TODO(debug): log tạm để verify handshake với MES thật lần đầu — gỡ sau khi đã
// xác nhận chạy đúng trên môi trường nhúng thật (xem docs/specs/mes-i18n-bridge-*).
const DEBUG_TAG = '[mes-bridge]'

function handleMessage(event: MessageEvent): void {
  if (!isTrustedMesOrigin(event.origin)) {
    console.warn(DEBUG_TAG, 'message bỏ qua — origin không tin cậy:', event.origin)
    return
  }
  const data = event.data as GsystemI18nInit | GsystemI18nChange | undefined
  if (!data || typeof data !== 'object') return

  switch (data.type) {
    case 'GSYSTEM_I18N_INIT': {
      // Log RAW event.data trước (JSON round-trip để có snapshot tĩnh, tránh console
      // lười — object reference có thể bị code khác mutate trước khi mình mở ra xem)
      // — không dựng lại object tóm tắt, để thấy đúng type/version MES gửi thật.
      console.log(DEBUG_TAG, 'INIT raw:', JSON.parse(JSON.stringify(data)))
      const firstLangCode = data.languages?.[0]?.code
      if (firstLangCode && data.messages?.[firstLangCode]) {
        const dict = data.messages[firstLangCode]
        console.log(DEBUG_TAG, `số msgCode (${firstLangCode}):`, Object.keys(dict).length)
        console.log(DEBUG_TAG, 'mẫu 5 msgCode đầu:', Object.entries(dict).slice(0, 5))
      } else {
        console.warn(DEBUG_TAG, 'data.messages rỗng hoặc thiếu mã ngôn ngữ đầu tiên:', data.messages)
      }
      registerAvailableLocales(data.languages?.map((l) => l.code))
      registerGsystemMessages(data.messages)
      applyLanguage(data.current)
      console.log(DEBUG_TAG, 'đã applyLanguage sau INIT:', data.current)
      break
    }
    case 'GSYSTEM_I18N_CHANGE':
      console.log(DEBUG_TAG, 'GSYSTEM_I18N_CHANGE nhận được:', data.current)
      applyLanguage(data.current)
      break
    default:
      console.log(DEBUG_TAG, 'message type không xử lý:', data)
  }
}

/**
 * Gọi 1 lần lúc app mount xong. Đọc `embed`/`lang` từ query trước (fallback tránh
 * nháy sai ngôn ngữ lúc mới load), rồi mới bắt tay với MES qua postMessage.
 */
export function initMesBridge(): void {
  const params = new URLSearchParams(location.search)
  isEmbedded.value = params.get('embed') === '1'
  console.log(DEBUG_TAG, 'init — embed:', isEmbedded.value, 'query:', location.search)

  const initialLang = params.get('lang')
  if (initialLang) {
    applyLanguage(initialLang)
    console.log(DEBUG_TAG, 'applyLanguage từ query param lang:', initialLang)
  }

  if (!isEmbedded.value) {
    console.log(DEBUG_TAG, 'không ở embed mode — bỏ qua handshake với MES')
    return
  }
  if (window.parent === window) {
    console.warn(DEBUG_TAG, 'embed=1 nhưng không nằm trong iframe (window.parent === window)')
    return
  }

  const mesOrigin = resolveMesOrigin()
  if (!mesOrigin) {
    console.warn(
      DEBUG_TAG,
      'không xác định được MES origin tin cậy — parentOrigin param:',
      params.get('parentOrigin'),
      'referrer:',
      document.referrer,
      'patterns:',
      MES_ORIGIN_PATTERNS,
    )
    return
  }

  window.addEventListener('message', handleMessage)
  // MES chỉ gửi GSYSTEM_I18N_INIT SAU KHI nhận được APS_READY.
  window.parent.postMessage({ type: 'APS_READY' }, mesOrigin)
  console.log(DEBUG_TAG, 'đã gửi APS_READY tới', mesOrigin)
}
