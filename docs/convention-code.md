# Coding Convention

## 1. Backend Convention (FastAPI)

### 1.1. Project Structure

```text
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── users.py
│   │       └── plans.py
│   │
│   ├── domain/
│   │   ├── entities/
│   │   ├── repositories/
│   │   └── services/
│   │
│   ├── infrastructure/
│   │   ├── database/
│   │   ├── repositories/
│   │   └── external/
│   │
│   ├── schemas/
│   ├── core/
│   └── main.py
│
├── tests/
├── alembic/
└── requirements.txt
```

---

### 1.2. Naming Convention

#### File

```python
user_service.py
plan_repository.py
production_instruction.py
```

- Use `snake_case`

#### Class

```python
UserService
PlanRepository
ProductionInstruction
```

- Use `PascalCase`

#### Function

```python
get_user_by_id()
create_production_plan()
calculate_schedule()
```

- Use `snake_case`

#### Variable

```python
user_id
plan_no
production_date
```

- Use `snake_case`

---

### 1.3. API Convention

#### URL Format

❌ Bad

```text
/api/GetUser
/api/UserList
```

✅ Good

```text
GET    /api/v1/users
GET    /api/v1/users/{id}
POST   /api/v1/users
PUT    /api/v1/users/{id}
DELETE /api/v1/users/{id}
```

---

### 1.4. Response Format

#### Success

```json
{
  "success": true,
  "message": "Success",
  "data": {}
}
```

#### Error

```json
{
  "success": false,
  "message": "User not found"
}
```

---

### 1.5. Layer Architecture

```text
Controller
    ↓
Service
    ↓
Repository
    ↓
Database
```

#### Controller

- Receive request
- Validate request
- Return response

❌ Do not implement business logic

```python
@router.post("/")
async def create_user(payload: UserCreate):
    return user_service.create(payload)
```

#### Service

- Handle business logic
- Handle transaction
- Call repository

```python
class UserService:
    def create(self, payload):
        ...
```

#### Repository

- Database access only

```python
class UserRepository:
    def create(self, user):
        ...
```

---

### 1.6. Database Convention

#### Table

```sql
users
production_plans
production_instructions
```

#### Primary Key

```sql
id
```

#### Foreign Key

```sql
user_id
plan_id
workcenter_id
```

#### Audit Columns

```sql
created_at
updated_at
created_by
updated_by
```

---

### 1.7. Logging

❌ Bad

```python
print("Error")
```

✅ Good

```python
logger.info(...)
logger.warning(...)
logger.error(...)
```

---

### 1.8. Exception Handling

❌ Bad

```python
except:
    pass
```

✅ Good

```python
except Exception as e:
    logger.error(str(e))
    raise
```

---

## 2. Frontend Convention (Vue)

### 2.1. Project Structure

```text
src/
├── api/
├── views/
├── components/
├── stores/
├── composables/
├── router/
├── layouts/
├── types/
├── utils/
└── assets/
```

---

### 2.2. Naming Convention

#### Component

```text
UserTable.vue
PlanHistoryModal.vue
WorkCenterCard.vue
```

- Use PascalCase

#### View

```text
UserManagementView.vue
PlanVersionView.vue
```

#### Store

```text
user.store.ts
auth.store.ts
plan.store.ts
```

#### API

```text
user.api.ts
plan.api.ts
```

#### Type

```text
user.type.ts
plan.type.ts
```

---

### 2.3. API Layer

❌ Bad

```vue
<script setup>
axios.get(...)
</script>
```

✅ Good

```vue
<script setup>
await userApi.getUsers()
</script>
```

---

### API Example

```ts
export const userApi = {
  getUsers() {
    return api.get('/users')
  },

  createUser(payload) {
    return api.post('/users', payload)
  }
}
```

---

### 2.4. State Management

Use Pinia

```ts
export const useUserStore = defineStore(...)
```

---

### 2.5. TypeScript

❌ Bad

```ts
const user: any
```

✅ Good

```ts
interface User {
  id: number
  username: string
}
```

---

### 2.6. Component Rule

#### Smart Component

Responsible for:

- Fetch data
- Call store
- Control page state

#### Dumb Component

Responsible for:

- Display UI only
- Emit events

---

### 2.7. CSS Convention

#### Global Style

```text
assets/styles/
```

#### Component Style

```vue
<style scoped>
</style>
```

---

### 2.8. Import Order

```ts
// Vue
import { ref } from 'vue'

// Third-party
import dayjs from 'dayjs'

// API
import { userApi } from '@/api/user.api'

// Components
import UserTable from '@/components/UserTable.vue'

// Types
import type { User } from '@/types/user.type'
```

---

## 3. Git Convention

### Branch Naming

```text
main
develop

feature/user-management
feature/plan-versioning

bugfix/login-error

hotfix/production-error
```

---

### Commit Convention

```text
feat: add production instruction history

fix: resolve duplicate purchase request

refactor: split user service

docs: update api document

style: format code

test: add user service test
```

---

## 4. General Rules

### Backend

❌ Not Allowed

- Business logic inside Controller
- SQL inside Controller
- SQL inside API Layer
- Hardcoded configuration
- print() for debugging

### Frontend

❌ Not Allowed

- API call directly inside reusable component
- Business logic inside View
- Usage of any without reason
- Duplicate UI component implementation

---

## 5. Architecture Rules

### Backend

```text
Controller
    ↓
Service
    ↓
Repository
    ↓
Database
```

### Frontend

```text
View
    ↓
Store
    ↓
API
    ↓
Backend
```

---

## 6. Code Review Checklist

### Backend

- [ ] API follows RESTful convention
- [ ] No business logic in Controller
- [ ] No SQL outside Repository
- [ ] Proper exception handling
- [ ] Logging implemented
- [ ] DTO/Schema validation implemented

### Frontend

- [ ] No API call inside reusable component
- [ ] TypeScript type defined
- [ ] Pinia used correctly
- [ ] Component reusable
- [ ] Naming convention followed
- [ ] No duplicated code