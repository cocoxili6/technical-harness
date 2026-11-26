# Supabase Passwordless Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Supabase email OTP sign-in and persist every user's threads, messages, memories, LangGraph context, paper catalog, and rolling summaries in user-isolated Supabase PostgreSQL.

**Architecture:** Vue uses Supabase Auth and attaches its access token to API calls. FastAPI verifies each JWT and uses the verified `sub` as `user_id`; a Postgres repository runs in a transaction with the user's JWT claims installed so RLS and explicit ownership predicates both apply. Qoder Edge Function preserves the browser authorization header while adding its own backend shared-token credential.

**Tech Stack:** Vue 3, TypeScript, `@supabase/supabase-js`; FastAPI, PyJWT/JWKS verification, SQLAlchemy async + asyncpg, LangGraph Postgres checkpointer; Supabase PostgreSQL migrations and RLS; Deno Edge Function.

**Spec:** `docs/superpowers/specs/2026-11-26-supabase-passwordless-auth-design.md`

## Global Constraints

- `user_id` is always taken from a verified JWT `sub`; clients cannot choose it.
- Supabase PostgreSQL is the source of truth for threads, messages, memories, LangGraph context, paper catalog entries, and rolling summaries.
- FastAPI runs on an independent server; Vue deploys to Qoder Sites; Qoder Edge Function remains the API gateway.
- Secrets are never committed, returned by `/api/health`, or exposed to the browser except the public Supabase URL and anon key.
- Preserve existing API fields and SSE event names.
- Do not auto-migrate local JSON data because it has no trustworthy owner.
- Every task follows TDD: add a failing test, observe the expected failure, implement minimally, and rerun tests.

---

## File Map

- `backend/app/auth.py`: bearer parsing and Supabase JWT verification.
- `backend/app/db.py`: async engine/session lifecycle and per-transaction RLS claim setup.
- `backend/app/repositories/`: user-scoped SQL persistence for conversations, memories, and agent context.
- `backend/app/main.py`: protect data endpoints, pass `CurrentUser`, persist stream events and check ownership.
- `backend/app/agent/graph.py`: switch in-memory checkpointer to Postgres checkpointer and namespace by authenticated user/thread.
- `backend/migrations/`: schema, foreign keys, composite user/thread constraints, and RLS policies.
- `backend/tests/`: auth, route, isolation, and persistence tests using isolated Postgres or SQL statement fixtures.
- `frontend/src/lib/supabase.ts`: singleton Supabase browser client and session helpers.
- `frontend/src/lib/api.ts`: attach fresh access token to JSON and SSE requests.
- `frontend/src/components/AuthGate.vue`: email and OTP form states.
- `frontend/src/App.vue`: session gate, sign-out, user-bound UI state cleanup.
- `frontend/src/main.ts`: initialize auth client before mounting.
- `frontend/tests/`: OTP transitions and token attachment.
- `functions/app/index.ts`: forward browser Authorization separately from backend shared token.
- `functions/tests/`: authorization forwarding, whitelist, validation, and SSE forwarding.
- `README.md`, `backend/.env.example`, `frontend/.env.example`: setup and deployment configuration.

## Task 1: Test and Dependency Foundation

**Files:** `backend/requirements.txt`, `backend/app/config.py`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`; create `backend/tests/conftest.py`, `backend/tests/test_settings.py`, `frontend/vitest.config.ts`, `frontend/src/test-setup.ts`.

- [ ] Add tests proving Supabase settings can be configured without exposing secrets and a frontend test runner mounts Vue components.
- [ ] Run each focused test and confirm it fails because the setting/test setup is missing.
- [ ] Add PyJWT, async SQLAlchemy/asyncpg, LangGraph Postgres checkpointer, Supabase JS, Vitest, Vue Test Utils, and jsdom at compatible pinned ranges.
- [ ] Add test scripts without changing existing build/typecheck behavior.
- [ ] Install dependencies in the isolated worktree and run focused baseline tests.

## Task 2: JWT Authentication Boundary

**Files:** create `backend/app/auth.py`, `backend/tests/test_auth.py`, `backend/tests/test_protected_routes.py`; modify `backend/app/config.py`, `backend/app/main.py`.

- [ ] Write tests for valid issuer/audience/signature, missing/malformed/expired token, and user-data endpoints returning 401 without a token.
- [ ] Run tests and observe failures before adding implementation.
- [ ] Implement `CurrentUser(id: UUID, email: str | None)`, JWKS-aware JWT verification with cached keys, and `get_current_user` dependency.
- [ ] Replace `verify_token` router dependency with auth dependency plus independent shared-token validation for Edge-to-backend calls; accept both credentials without confusing them.
- [ ] Run auth and route tests; retain public `/` and `/api/health` behavior while not reporting secrets.

## Task 3: PostgreSQL Schema and User-Scoped Repository Core

**Files:** create `backend/migrations/0001_user_data.sql`; create `backend/app/db.py` and `backend/app/repositories/{__init__,base,conversation,memory,agent_context}.py`; create `backend/tests/test_repository_isolation.py`, `backend/tests/test_migrations.py`; modify `backend/app/config.py`, `backend/requirements.txt`.

- [ ] Write repository tests for user A/B isolation, same URL per-user uniqueness, thread-child ownership, and RLS claim setup.
- [ ] Run focused tests and observe the expected missing-schema/repository failures.
- [ ] Create `threads`, `messages`, `memories`, `paper_catalog`, `tool_runs`, `context_summaries`, and LangGraph checkpoint tables with UUID user ownership, composite keys/FKs, indexes, RLS, and `auth.uid()` policies.
- [ ] Implement an async session factory and `set_config('request.jwt.claims', ..., true)` for each authenticated transaction; repository methods must always accept user_id and add explicit user predicates.
- [ ] Implement conversation create/list/get/append, memory CRUD/review/context, paper catalog upsert/list, tool-run persistence, and rolling-summary persistence.
- [ ] Run SQL/migration and repository tests against a local Supabase/Postgres test database; SQL policy tests must still run and integration tests must clearly skip if that service is unavailable.

## Task 4: FastAPI User-Scoped Routes and Streaming

**Files:** modify `backend/app/main.py`, `backend/app/store.py`, `backend/app/memory.py`; modify `backend/tests/test_protected_routes.py`; create `backend/tests/test_chat_persistence.py`.

- [ ] Add tests proving user A cannot read/append to user B's thread and cannot review/delete user B's memory; assert foreign IDs return 404.
- [ ] Run tests and confirm the process-global store leaks or cannot satisfy persistence.
- [ ] Remove module-global `ConversationStore`/`MemoryStore` runtime usage in favor of request-scoped repository operations; keep pure memory scoring helpers if useful.
- [ ] Protect thread, stream, analyze, and memory endpoints with `CurrentUser` and persist route results under `user.id`.
- [ ] Resolve and authorize the thread before returning a `StreamingResponse`; hold user ID and owned thread record in the generator closure for every write.
- [ ] Run backend route and stream tests and existing tests.

## Task 5: Durable LangGraph Context

**Files:** modify `backend/app/agent/graph.py`, `backend/app/main.py`, `backend/app/repositories/agent_context.py`; create `backend/tests/test_agent_checkpoint_isolation.py`.

- [ ] Write tests proving checkpoint config includes a non-colliding user/thread namespace and that summary/catalog restore after a new repository/service instance.
- [ ] Verify expected failures with MemorySaver and process-only state.
- [ ] Initialize the Postgres checkpointer using the shared async pool; use `thread_id` plus `checkpoint_ns=user:<user_id>` and persist paper catalog and rolling summary in repository tables transactionally with message updates.
- [ ] Pass authenticated user identity into every graph invocation and memory-context lookup.
- [ ] Run checkpoint, compaction, catalog, and restart persistence tests.

## Task 6: Edge Function Authorization Forwarding

**Files:** modify `functions/app/index.ts`; create `functions/tests/index_test.ts`.

- [ ] Write Deno tests proving incoming user Authorization reaches FastAPI, Edge shared credential is separately sent, missing user token is not replaced by shared token, and SSE response headers/body are preserved.
- [ ] Run tests and observe current overwrite behavior fail the forwarding assertion.
- [ ] Change proxy to forward inbound Authorization unchanged and send shared token via a dedicated `x-harness-gateway-token` header.
- [ ] Change FastAPI gateway validation to verify that dedicated header when configured while requiring Supabase bearer token for protected routes.
- [ ] Run Deno formatting/check/tests if Deno is installed; otherwise use the repo's available static check and report the environment limitation.

## Task 7: Vue Email OTP and Session-Aware API

**Files:** create `frontend/src/lib/supabase.ts`, `frontend/src/components/AuthGate.vue`, `frontend/tests/auth.test.ts`, `frontend/tests/api-auth.test.ts`; modify `frontend/src/main.ts`, `frontend/src/App.vue`, `frontend/src/lib/api.ts`, `frontend/src/style.css`, `frontend/src/types.ts`.

- [ ] Write tests for email request -> code verification -> session ready, invalid code, resend cooldown, sign-out cleanup, and bearer token on JSON/SSE calls.
- [ ] Run focused tests and observe failures before implementation.
- [ ] Implement Supabase client from `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`, OTP request and verify calls, session restoration/listener, and explicit sign-out.
- [ ] Add a current-session token accessor and attach Authorization on each API call; refresh once after a 401 before exposing retryable auth error.
- [ ] Gate the research workbench on a valid session; on sign-out abort streams, clear active thread/messages/profile/memory UI state, and return to login.
- [ ] Run frontend tests, typecheck, and production build.

## Task 8: Deployment Documentation and Full Verification

**Files:** modify `README.md`, `backend/.env.example`, `backend/Dockerfile`; create `frontend/.env.example`.

- [ ] Add deployment instructions for Supabase Auth email OTP settings, SQL migration, Postgres pooler connection, JWT issuer/audience/JWKS, Qoder Sites public variables, Edge secrets, and independent FastAPI server settings.
- [ ] Remove `MEMORY_FILE` from production persistence guidance and state that local JSON data is not imported.
- [ ] Run the full backend suite, frontend Vitest/typecheck/build, migration policy tests, and Deno checks where available.
- [ ] Review `git diff --check`, inspect the full diff, and confirm no env secrets or original `backend/env.env` were copied into the worktree.
- [ ] Commit each completed task with focused messages and report live Supabase credentials/database that must be configured before deployment.

## Self-Review Coverage

- OTP, session refresh, sign-out: Tasks 1 and 7.
- Verified JWT and unauthenticated access: Task 2.
- All required user-owned data tables and RLS: Task 3.
- Thread/memory ownership and persisted SSE writes: Task 4.
- LangGraph context, paper catalog, rolling summary: Task 5.
- Edge gateway Authorization pass-through and SSE: Task 6.
- Setup/env/deployment and complete checks: Task 8.
- Local unowned data policy: Task 8.

No acceptance criterion in the approved spec is intentionally omitted.
