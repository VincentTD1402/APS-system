# APS System — Coding Conventions

Bộ quy ước dùng chung cho toàn team APS. Viết theo **thực tế code hiện tại**, không aspirational — nếu bạn thấy quy ước lệch code, cập nhật file trong PR liên quan.

## Nguyên tắc cốt lõi (áp dụng cho mọi tầng)

1. **YAGNI → KISS → DRY** theo thứ tự đó. Đừng thêm abstraction cho use case chưa xuất hiện.
2. **Không hardcode config** — mọi biến môi trường qua `.env` + `pydantic-settings` (BE) hoặc `import.meta.env` (FE).
3. **Không dùng `print()` / `console.log()` khi commit code** — dùng logger.
4. **Không có `any` (TS) hoặc `Any` (Python) mà không có lý do ghi trong comment.**
5. **Không tự đoán** — thiếu context thì hỏi, không assume.
6. **Preserve public contracts** — muốn đổi shape API/DB thì bàn với cả 2 phía và cập nhật `docs/api-spec.md` cùng lúc.
7. **Verify trước khi commit** — chạy tối thiểu lint + typecheck; nếu đổi contract, chạy tests.
8. **Không commit** secrets, `.env`, credentials, personal data.
9. **Không skip pre-commit hooks** (`--no-verify`) hoặc `--no-gpg-sign` khi không được yêu cầu.
10. **Không tham chiếu AI/Claude/Copilot/…** trong commit message hoặc code comment.

## File index

| Chủ đề | File | Áp dụng khi |
|---|---|---|
| Backend FastAPI | [backend-fastapi.md](backend-fastapi.md) | Sửa `aps-backend/app/**` |
| Frontend Vue | [frontend-vue.md](frontend-vue.md) | Sửa `aps-frontend/src/**` |
| Database Postgres | [database-postgres.md](database-postgres.md) | Thêm model, migration, đổi schema |
| API Contract | [api-contract.md](api-contract.md) | Thêm/đổi endpoint (BE) hoặc gọi API (FE) |
| Testing | [testing.md](testing.md) | Viết test cho BE (pytest) hoặc FE (vitest) |
| DevOps & Workflow | [devops-and-workflow.md](devops-and-workflow.md) | Sửa compose, justfile, env, migration process, plan/docs, git |

## Quy trình review nhanh

Trước khi mở PR, tự check:

- [ ] Đúng convention của file bạn động chạm (link trên).
- [ ] Không thêm dep không cần (`uv add` / `pnpm add` phải có lý do).
- [ ] Đổi contract API? → update `docs/api-spec.md` cùng PR.
- [ ] Đổi schema DB? → có Alembic revision (không sửa revision cũ đã merge).
- [ ] Commit message theo conventional commit, không AI reference.
- [ ] Test chạy pass (nếu có test cho tầng đó).
