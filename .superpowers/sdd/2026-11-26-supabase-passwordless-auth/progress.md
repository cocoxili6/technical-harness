# SDD ledger — plan: docs/superpowers/plans/2026-11-26-supabase-passwordless-auth.md

## Preflight conflict scan

| Scope | Shared files/interfaces checked | Finding |
|---|---|---|
| Task 1 | backend/requirements.txt, config/test setup | Task 1 installs backend/frontend test foundations; Task 2/3 may add backend dependencies and settings. Keep Task 1 limited to test-runner setup, and later tasks own feature dependencies/settings to avoid concurrent edits. |
| Task 1 ↔ Task 2 | backend/config.py, main.py only by task 2; test foundation by task 1 | Task 1 introduces tests, Task 2 consumes them; no conflicting implementation ownership. |
| Task 1 ↔ Task 3 | requirements.txt/config.py | Sequential dependency overlap; Task 3 must preserve Task 1 test dependencies and only add runtime DB dependencies. |
| Task 2 ↔ Task 4 | main.py, CurrentUser dependency | Task 2 supplies `CurrentUser` and route auth; Task 4 consumes it to scope database operations. Interface must be stable before Task 4. |
| Task 2 ↔ Task 6 | main.py gateway credential | Task 6 introduces `x-harness-gateway-token`; Task 2 must define the shared-token verifier as a separate dependency so the two bearer/header credentials remain distinct. |
| Task 3 ↔ Task 4 | db.py, repositories, conversations/memories | Task 3 produces request/session and repository interfaces; Task 4 consumes them. Implement repositories before route migration. |
| Task 3 ↔ Task 5 | agent_context repository and checkpoint schema | Task 3 defines durable summary/catalog storage; Task 5 consumes it and configures the library Postgres checkpointer. Do not hand-author LangGraph's private schema; use its supported setup/migrations. |
| Task 4 ↔ Task 5 | main.py, request-scoped user/thread and graph invocation | Task 4 must pass verified user ID and owned thread to streaming; Task 5 uses them to namespace checkpointer and context persistence. |
| Task 6 ↔ Task 2 | gateway-token dependency/header | Task 6 changes the gateway credential header and Task 2 validates it. Keep both serial; contract is `x-harness-gateway-token` plus Supabase bearer token. |
| Task 7 | frontend/src/App.vue, api.ts, supabase.ts | Auth UI/session work shares files within one task and is deliberately not parallelized internally. |
| Task 8 | README.md, backend/.env.example, Dockerfile | Documentation follows implemented settings and dependencies; no earlier task owns these files except settings templates. |
| Task 1 self-check | tests vs. files | Tests cover settings and Vue runner; no behavior change is specified in Task 1. |
| Task 2 self-check | auth tests vs. route dependency | Plan needs two credentials: gateway credential and Supabase JWT; verifier dependencies must be separate. |
| Task 3 self-check | migration vs. checkpoint package | Plan's phrase “LangGraph checkpoint tables” could imply manually creating library-owned tables; resolve via supported checkpointer setup and user-scoped namespace. |
| Task 4 self-check | route tests vs. route list | Chat/thread/memory/analyze endpoints must be authenticated; thread ownership must be checked before SSE response starts. |
| Task 5 self-check | namespace vs. persistence | `checkpoint_ns=user:<uuid>` plus user-scoped `thread_id` is required; summaries/catalog remain in app-owned tables with `user_id`. |
| Task 6 self-check | Edge forwarding vs. gateway validation | Browser bearer must be forwarded untouched; Edge shared credential is a separate header. |
| Task 7 self-check | OTP UI vs. API | Session restoration and sign-out cleanup are in scope; no custom auth tokens may be minted. |
| Task 8 self-check | docs vs. spec | Local JSON migration is explicitly excluded; deployment docs must say no unowned local data is imported. |

## Rulings

- Ruling: PostgreSQL claim setup must include `SET LOCAL ROLE authenticated` (or an equivalently non-BYPASSRLS role) in addition to transaction-local JWT claims and explicit `user_id` predicates — setting claims alone does not make RLS effective when FastAPI connects as a table owner/service role — if wrong, additional role permissions/configuration may be needed, but omitting it risks bypassing database RLS.
- Ruling: LangGraph's checkpoint tables will be initialized with the package's supported migrations and isolated by a server-generated thread identifier containing the verified user UUID plus a `checkpoint_ns` user namespace — the package owns its checkpoint schema and custom mutations are brittle — if wrong, a custom saver/table migration may be needed to add direct `user_id` RLS.

## Task progress

Task 1: complete (commits 8375da4..e32228d, review approved after one fix round)
Task 2: complete (commits e32228d..8aa0bf2, review clean after one fix round)
Task 3: complete (RLS claims set in transaction as role authenticated plus explicit user predicates; repository append locking and pooled engine lifecycle reviewed)
Task 4: complete (thread/message and manual-memory routes use user-scoped database sessions; SSE writes persist user and assistant messages; response shape preserved)
Task 5: pending
Task 6: pending
Task 7: pending
Task 8: pending
