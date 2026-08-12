import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'

import App from './App.vue'
import { router } from './router/index.ts'
import { i18n } from './i18n/index.ts'
import { initMesBridge } from './services/mes-bridge.ts'

import 'primeicons/primeicons.css'
import 'primeflex/primeflex.css'
import './style.css'
import './assets/aps.css'

// Đọc query gốc (embed/lang/parentOrigin) + bắt tay MES TRƯỚC khi router chạy —
// route '/' → '/aps' rewrite URL qua History API, initMesBridge() gọi sau đó sẽ
// đọc `location.search` đã bị đổi/mất query nếu MES nhúng ở path '/' thay vì '/aps'.
initMesBridge()

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)
app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: {
      darkModeSelector: '.aps-dark',
    },
  },
})
app.use(ToastService)
app.use(ConfirmationService)

app.mount('#app')
