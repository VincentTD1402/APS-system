# Testing Convention

MVP hiện chưa có test — convention này để **áp dụng khi bắt đầu viết**. Không backfill hàng loạt; viết test khi:

- Fix bug → viết test tái tạo bug trước, rồi fix (regression guard).
- Business logic quan trọng (scheduling, KPI calc, material shortage).
- Public contract (API endpoint response shape).

Không viết test cho:

- Getter/setter thuần, framework code, boilerplate.
- Route handler mỏng (chỉ orchestration) — test service bên dưới thay vì.

## 1. Backend — pytest

**Framework**: `pytest` + `pytest-asyncio` (mode=auto, đã set trong `pyproject.toml`).

**Vị trí**: `aps-backend/tests/` mirror cấu trúc `app/`:

```text
aps-backend/
└── tests/
    ├── conftest.py                         # fixtures dùng chung (db session, client)
    ├── unit/
    │   ├── services/
    │   │   ├── kpi_summary/
    │   │   │   └── test_kpi_calculator.py
    │   │   └── scheduling/
    │   │       └── test_daily_plan_builder.py
    │   └── schemas/
    │       └── test_kpi_summary_schemas.py
    └── integration/
        ├── api/
        │   └── test_kpi_summary_routes.py
        └── db/
            └── test_migrations.py
```

### 1.1 Naming

| Loại | Style | Ví dụ |
|---|---|---|
| Test file | `test_<module>.py` snake_case | `test_kpi_calculator.py` |
| Test function | `test_<action>_<expected>` | `test_calculate_kpi1_returns_zero_when_no_orders` |
| Fixture | `snake_case` | `db_session`, `mock_gsystem_client` |
| Test class (nếu cần group) | `Test<Feature>` | `class TestBackwardFill:` |

**Không** đặt tên test theo plan ID, phase, ticket. Đặt tên theo behavior/invariant.

### 1.2 Cấu trúc test

Arrange → Act → Assert, comment nếu step phức tạp:

```python
def test_backward_fill_dumps_overflow_at_start_date(db_session):
    # Arrange
    wc = create_workcenter(db_session, capacity_minutes=480)
    mps = create_mps(db_session, plan_qty=1000, start_date=date(2026, 8, 1), end_date=date(2026, 8, 5))

    # Act
    rebuild_daily_plan(db_session)

    # Assert
    rows = db_session.execute(select(DailyPlan).order_by(DailyPlan.work_date)).scalars().all()
    assert rows[0].work_date == date(2026, 8, 1)
    assert rows[0].planned_qty > wc.daily_capacity_ea    # overflow dumped
    assert rows[0].status == "overload"
```

### 1.3 Fixtures

- `conftest.py` ở tests/ root cho fixture dùng chung.
- Fixture DB session: **transaction rollback** sau mỗi test — không seed rồi truncate.

```python
@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
```

- Fixture API client:

```python
@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

### 1.4 Chạy

```bash
just test-be                      # toàn bộ
just test-be tests/unit           # scope
just test-be -k "backward_fill"   # filter theo tên
just test-be --cov=app            # với coverage
```

Coverage threshold: **không hardcode** ở MVP. Đo trước, đặt threshold sau.

### 1.5 Mock policy

- **Prefer real DB** (Postgres trong docker) — mock DB dễ mask bug schema/query. Setup fixture rollback.
- **Mock external calls**: G-System HTTP client, LLM API, `datetime.now()`. Dùng `pytest-mock` hoặc `monkeypatch`.
- Không mock service của chính mình — test end-to-end tầng service.

### 1.6 Async

- Test `async def` → `@pytest.mark.asyncio` (mode auto đã set trong `pyproject.toml`, không cần decorator).
- Test route sync (`def` handler) → dùng `TestClient` bình thường.

## 2. Frontend — Vitest

**Framework**: `vitest` + `@vue/test-utils` + optional `@testing-library/vue` cho UI-heavy.

**Vị trí**: `aps-frontend/src/**/__tests__/*.spec.ts` (co-located) hoặc `tests/` (root FE).

Cách co-located gọn hơn cho project nhỏ:

```text
aps-frontend/src/
├── stores/
│   ├── aps-store.ts
│   └── __tests__/
│       └── aps-store.spec.ts
├── mocks/
│   ├── mock-scheduler.ts
│   └── __tests__/
│       └── mock-scheduler.spec.ts
└── components/
    ├── load-matrix.vue
    └── __tests__/
        └── load-matrix.spec.ts
```

### 2.1 Naming

| Loại | Style | Ví dụ |
|---|---|---|
| Test file | `<file>.spec.ts` | `mock-scheduler.spec.ts` |
| `describe(...)` | Domain hoặc file dưới test | `describe('mockScheduler', ...)` |
| `it(...)` | Behavior đầy đủ câu | `it('should dump overflow at start date when qty > capacity')` |

### 2.2 Cấu trúc

```ts
import { describe, it, expect } from 'vitest'
import { backwardFill } from '@/mocks/mock-scheduler'

describe('backwardFill', () => {
  it('should distribute qty from end_date backward respecting EA capacity', () => {
    // Arrange
    const wc = { id: 'WC001', daily_capacity_ea: 168 }
    const mps = { start_date: '2026-08-09', end_date: '2026-08-15', qty: 1000 }

    // Act
    const cells = backwardFill(wc, mps)

    // Assert
    expect(cells.at(-1).qty).toBe(168)               // last day full
    expect(cells[0].qty).toBeGreaterThanOrEqual(0)   // first day may overflow
  })
})
```

### 2.3 Component testing

Dùng `@vue/test-utils` cho render + shallowMount, prefer testing behavior không phải markup:

```ts
import { mount } from '@vue/test-utils'
import FilterBar from '../filter-bar.vue'

it('emits apply event with adjusted filter', async () => {
  const wrapper = mount(FilterBar, { props: { initial: {...} } })
  await wrapper.find('[data-test="apply-btn"]').trigger('click')
  expect(wrapper.emitted('apply')).toBeTruthy()
})
```

- Test qua `data-test="..."` attribute, **không** selector CSS class (dễ break khi restyle).
- Không snapshot test cho component có UI thay đổi thường xuyên — verify từng behavior.

### 2.4 Pinia store

Setup Pinia test instance:

```ts
import { setActivePinia, createPinia } from 'pinia'
import { beforeEach } from 'vitest'

beforeEach(() => setActivePinia(createPinia()))
```

Test action → assert state:

```ts
it('selecting a cell filters plans by that cell', () => {
  const store = useApsStore()
  store.selectCell({ workcenterId: 1, workDate: '2026-08-01' })
  expect(store.filteredPlans).toHaveLength(3)
})
```

### 2.5 Chạy

```bash
just test-fe                    # toàn bộ
just test-fe --run              # 1 lần (không watch)
just test-fe filter-bar         # filter tên
```

Chưa dùng coverage tool cho FE ở MVP — thêm khi cần.

## 3. E2E (chưa)

Chưa scope MVP. Khi cần → Playwright (script trong root `justfile`), test path: `login → RUN APS → click cell → apply → verify recompute`.

## 4. CI

```bash
just ci                # lint + typecheck + test (BE+FE) + build-fe
```

Chạy trước mỗi PR. Github Actions/GitLab CI wire vào recipe này khi setup.

## 5. Test data

- **Không dùng production data** trong test.
- Factory function trong `tests/factories/` (BE) hoặc `mocks/` (FE) — không copy fixture json to lớn.
- Seed data có sẵn ở `app/scripts/seed_may2026_single_overload_scenario.py` (BE) — dùng cho manual testing, **không** import trong unit test.

## 6. Cấm

- `time.sleep(...)` trong test — dùng mock time hoặc event/condition.
- Test phụ thuộc thứ tự chạy (`test_a` xong mới đến `test_b`).
- Assert quá rộng: `assert result is not None` — assert cụ thể.
- Test 1 lúc nhiều behavior — 1 test = 1 assertion topic.
- Skip test rồi quên (`@pytest.mark.skip` không có reason).
