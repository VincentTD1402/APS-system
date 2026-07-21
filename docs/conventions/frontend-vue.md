# Frontend Convention — Vue 3

## 1. Cấu trúc thư mục

```text
aps-frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json, tsconfig.node.json
├── package.json, pnpm-lock.yaml
├── src/
│   ├── main.ts               # PrimeVue Aura + Pinia + i18n + ToastService setup
│   ├── App.vue, layouts/     # Shell
│   ├── router/               # vue-router
│   ├── views/                # Page-level components (1 route = 1 view)
│   ├── components/           # Reusable UI, chia sub-folder theo domain nếu cần
│   ├── stores/               # Pinia stores
│   ├── composables/          # `use*.ts` reusable logic (chỉ tạo khi tái sử dụng)
│   ├── api/                  # Axios client + mỗi domain 1 file (`kpi-summary.api.ts`)
│   ├── mocks/                # mock-server, mock-scheduler, master-data, mps-data
│   ├── types/                # enums.ts, master.ts, planning.ts, aps.ts
│   ├── i18n/                 # ko.json, vi.json (bilingual)
│   └── assets/               # icons, images
└── Dockerfile
```

## 2. Naming

| Loại | Style | Ví dụ |
|---|---|---|
| File `.vue` / `.ts` | `kebab-case` | `aps-work-plan-view.vue`, `filter-bar.vue`, `mock-scheduler.ts` |
| Component tag trong `<template>` | `PascalCase` | `<FilterBar />`, `<LoadMatrix />`, `<RiskChip :type="…" />` |
| Composable | `use` prefix + `kebab-case` file | `use-aps-store.ts` export `useApsStore()` |
| Pinia store | file `<domain>-store.ts`, id = domain kebab | `aps-store.ts` → `defineStore('aps', ...)` |
| Type/interface | `PascalCase` | `interface WorkPlan { id: string; dailyPlans: WorkPlanDaily[] }` |
| Enum | `PascalCase` + values `SCREAMING_SNAKE` | `enum RiskType { MATERIAL_SHORTAGE, OVERLOAD }` (hoặc string union nếu đơn giản) |
| API module | `<domain>.api.ts` | `kpi-summary.api.ts` export `kpiSummaryApi` |
| Const module-level | `UPPER_SNAKE` | `const DEFAULT_LOCALE = 'ko'` |
| Ref / reactive var | `camelCase` | `const cellSelection = ref<CellRef | null>(null)` |

**Không suffix `.type.ts`** — file trong `types/` đã tự nói là type. Import: `import type { WorkPlan } from '@/types/planning'`.

## 3. Composition API

- Luôn dùng `<script setup lang="ts">` — không viết Options API.
- Reactive: `ref` cho primitive/object thay thế nguyên; `reactive` chỉ khi object mutate in-place và không thay thế reference.
- Computed: `const filtered = computed(() => plans.value.filter(...))`.
- Watch: prefer `watchEffect` cho side effect đơn giản; `watch` khi cần old/new value hoặc source cụ thể.
- Không truy cập `.value` trong template — chỉ trong `<script>`.

## 4. Component pattern

**Smart (view / container)** — sống trong `views/`:

- Đọc/ghi store, gọi API.
- Điều phối state, xử lý event từ dumb child.
- Không chứa UI phức tạp — delegate xuống components.

**Dumb (presentational)** — sống trong `components/`:

- Nhận props, emit event.
- Không import store, không gọi API trực tiếp.
- Có thể có local state cho UI (mở dialog, hover…).

```vue
<!-- views/aps/aps-work-plan-view.vue -->
<script setup lang="ts">
import { useApsStore } from '@/stores/aps-store'
import LoadMatrix from '@/components/load-matrix.vue'

const store = useApsStore()
</script>

<template>
  <LoadMatrix
    :cells="store.matrixCells"
    @cell-select="store.selectCell"
  />
</template>
```

## 5. Pinia store

- 1 domain = 1 store, file `<domain>-store.ts`.
- Dùng setup syntax (`defineStore('aps', () => { ... })`) — trả state/getters/actions.
- Không đặt logic UI (dialog visibility, hover) trong store — đưa xuống component local.
- Async action: try/catch → toast lỗi qua composable `useToast()`.

```ts
export const useApsStore = defineStore('aps', () => {
  const cellSelection = ref<CellRef | null>(null)
  const pendingDrafts = ref<PendingDraft[]>([])

  const contextualRisk = computed(() => { /* ... */ })

  async function applyAdjustments() { /* ... */ }

  return { cellSelection, pendingDrafts, contextualRisk, applyAdjustments }
})
```

## 6. API layer

- File `api/http.ts` khởi tạo axios instance với `baseURL = import.meta.env.VITE_API_BASE_URL`.
- Mỗi domain BE → 1 file `<domain>.api.ts`, export object với named methods (không class).
- Component/store **không import axios trực tiếp** — chỉ qua `api/*.api.ts`.
- Type response = Pydantic schema BE → sinh manual trong `types/` (hoặc dùng `openapi-typescript` sau).

```ts
// api/kpi-summary.api.ts
import { http } from './http'
import type { KPI1DeliveryResponse } from '@/types/aps'

export const kpiSummaryApi = {
  getDelivery: () => http.get<KPI1DeliveryResponse>('/kpi-summary/delivery'),
  rebuildDailyPlan: () => http.post<DailyPlanRebuildResponse>('/kpi-summary/daily-plan/rebuild'),
}
```

## 7. Mock → Real transition

- `mocks/mock-server.ts` giữ nguyên để dev offline / test scheduler logic client-side.
- Khi endpoint BE ready → **xóa mock đối ứng** và trỏ store sang `<domain>.api.ts`. Không giữ song song lâu.
- Store phải là **single caller** — không component nào gọi thẳng mock/api.

## 8. i18n (bilingual KO/VI)

- Tất cả label hiển thị trong template dùng `{{ t('key.name') }}` — không hardcode chuỗi.
- File `i18n/ko.json` là **canonical** (tên gốc theo spec). `vi.json` mirror cấu trúc.
- Key theo dot notation, kebab bên trong: `filter.cell-select-hint`, `work-plan.qty-column`.
- Không tự dịch spec Korean — hỏi để đảm bảo thuật ngữ MFG chuẩn.

## 9. PrimeVue 4 (Aura)

- Import component từ `primevue/<name>` theo docs v4.
- Icon: PrimeIcons class `pi pi-<name>`.
- Toast: dùng `useToast()` — cấu hình `ToastService` đã có ở `main.ts`.
- Không mix component thư viện khác (Vuetify/Element) — giữ 1 hệ.

## 10. TypeScript

- **Không dùng `any`.** Nếu bắt buộc → `unknown` + narrow, hoặc comment lý do.
- Type từ BE (Pydantic response) copy sang `types/` manual — mỗi field khớp `Field(..., description=...)` bên BE.
- Prefer `interface` cho shape có thể extend; `type` cho union/intersection.
- Import type: `import type { X } from '...'` để tree-shake khỏi bundle.

## 11. Style & CSS

- **Scoped style** mặc định: `<style scoped>` trong component.
- Global style ở `src/assets/styles/*.css`.
- Sử dụng PrimeFlex utility (`flex`, `gap-2`, `p-3`) trước khi viết custom CSS.
- Không inline style nếu có > 2 property — tách class.

## 12. Import order

```ts
// 1. Vue core
import { ref, computed, onMounted } from 'vue'

// 2. Third-party
import dayjs from 'dayjs'
import { useToast } from 'primevue/usetoast'

// 3. Aliases (@ = src/)
import { useApsStore } from '@/stores/aps-store'
import { kpiSummaryApi } from '@/api/kpi-summary.api'

// 4. Components
import LoadMatrix from '@/components/load-matrix.vue'

// 5. Types (type-only import cuối)
import type { WorkPlan } from '@/types/planning'
```

## 13. Router

- 1 file `router/index.ts`, lazy import view: `component: () => import('@/views/aps/aps-work-plan-view.vue')`.
- Route name kebab-case: `name: 'aps-work-plan'`.
- Không auth guard trong MVP (single-user demo).

## 14. Dependency management

```bash
just fe-add axios              # runtime
just fe-add -D vitest          # dev
just fe-remove primeicons      # xóa
```

Không sửa `package.json` bằng tay — pnpm tự lock.

## 15. Cấm liệt kê nhanh

- `axios.get(...)` trong `<script setup>` component (phải qua `api/*.api.ts` + store).
- Chuỗi hiển thị hardcode tiếng Hàn/Việt trong template — luôn qua `t(...)`.
- Component trong `components/` gọi API hoặc import store.
- `console.log` khi commit — dùng breakpoint debugger.
- Tag `.vue` viết `<work_plan_list/>` — luôn PascalCase `<WorkPlanList/>`.
- Truy cập `.value` của ref trong template.
- Sử dụng Options API (`export default { data() {...} }`).
