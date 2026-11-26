# Supabase Passwordless Identity and User-Isolated Persistence

## Status

Design proposal for review. This document does not change runtime behavior.

## Goal

Add passwordless email + one-time-code authentication and make every durable
research artifact private to the authenticated Supabase user. The existing Vue
workbench, FastAPI/LangGraph runtime, and Qoder Edge Function gateway remain in
place.

## Constraints and decisions

- Supabase Auth sends email OTPs and owns the browser session.
- Vue is deployed to Qoder Sites.
- FastAPI runs on an independent server and is the only service that executes
  LangGraph and model/tool calls.
- The Qoder Edge Function forwards browser requests and their
  `Authorization` header to FastAPI.
- Supabase PostgreSQL is the source of truth for threads, messages, memories,
  LangGraph context, paper catalog entries, and rolling summaries.
- `user_id` is always taken from a verified JWT `sub`; clients cannot choose it.
- Existing demo mode remains available only after authentication, and demo data
  is generated in the authenticated user's namespace.

## Alternatives considered

1. **Recommended: FastAPI verifies JWTs and uses a repository layer.** Each
   request is authenticated once, then repository methods require `user_id` and
   include it in every query. This is easiest to test and keeps the service-role
   key off the browser. PostgreSQL RLS is enabled as a defense-in-depth layer.
2. **Pass the user's JWT through Supabase PostgREST for every query.** This
   makes RLS the primary enforcement mechanism, but couples the Python domain
   code to PostgREST request handling and complicates LangGraph transactions.
3. **Use Supabase Auth only and keep the existing JSON/process stores.** This is
   quick but fails the persistence and isolation requirement across restarts and
   multiple server instances.

The recommended option gives one explicit authorization boundary in FastAPI,
with database RLS and ownership predicates as independent safeguards.

## Authentication flow

1. The Vue app starts on an auth gate. The user submits an email address.
2. Supabase JS calls `signInWithOtp({ email, options: { shouldCreateUser: true
   } })` and shows the code entry state.
3. The user submits the email OTP. Supabase JS calls `verifyOtp({ email, token,
   type: "email" })`.
4. The client stores no custom token. Supabase manages the session and refreshes
   it; an API helper reads the current access token before each request.
5. FastAPI validates the bearer token using Supabase JWT configuration (issuer,
   audience, and JWKS or the configured JWT secret), returning a normalized
   `CurrentUser(id, email)` object.
6. Sign-out clears the Supabase session, aborts active streams, clears the
   active thread selection, and returns to the auth gate.

The UI handles invalid/expired codes, rate-limit responses, resend cooldown,
expired sessions, and API 401 responses without exposing provider internals.

## Backend boundaries

- `auth.py`: bearer extraction, JWT verification, and FastAPI dependencies.
- `db.py`: Supabase/Postgres connection and transaction lifecycle.
- `repositories/`: typed methods whose first required argument is `user_id`.
- `main.py`: route authentication, request validation, SSE orchestration, and
  conversion from repository records to the existing API shape.
- `agent/graph.py`: receives a user-scoped checkpoint/config and loads/saves
  context through the durable checkpointer rather than `MemorySaver`.
- `memory.py` and `store.py`: become repository-backed services or thin domain
  adapters; JSON files and process-global stores are removed from the runtime
  path after migration.

Every route that reads or mutates user data is protected: thread list/detail,
chat stream, memory list/create/review/delete, and any future paper/context
endpoints. `/api/health` stays public but reports whether auth/database are
configured without returning secrets.

## Database model and isolation

The migration creates UUID primary keys where practical and `user_id uuid not
null references auth.users(id)` on every user-owned table:

- `threads`: title and timestamps.
- `messages`: thread, role, content, profile, sources, trace, sequence.
- `memories`: text, kind, importance, stability, last reviewed, forgotten state,
  source thread.
- `paper_catalog`: canonical URL, title, authors, year, venue, citation count,
  summary, first/last seen.
- `tool_runs`: thread, tool name, input summary, result summary, status,
  timestamps.
- `context_summaries`: thread, rolling summary, summarized-through sequence,
  metadata, timestamps.
- LangGraph checkpoint tables: configured through the Postgres checkpointer,
  keyed by a user-scoped thread namespace.

Foreign keys use `on delete cascade` from user to owned records and from thread
to its child records. Unique constraints are scoped by `user_id` (for example,
`(user_id, canonical_url)`). RLS is enabled on every user-owned table with
policies comparing `user_id` to `auth.uid()`. FastAPI still includes explicit
ownership predicates and rejects a thread ID belonging to another user as 404
to avoid leaking existence.

## Request and streaming behavior

The frontend API helper adds the bearer token to JSON and `fetch` streaming
requests. The Edge Function copies the header and does not mint or transform
tokens. FastAPI authenticates before opening an SSE response, then keeps the
resolved `user_id` in the generator closure. All writes made during a stream
use that same identity and thread ownership check.

If a token expires during a stream, the backend emits the existing `error` SSE
event and closes the stream; the frontend refreshes the Supabase session once,
then offers retry. No partial response is silently attributed to a different
user.

## Migration and compatibility

- Add a Supabase SQL migration and environment template containing URL, anon
  key, backend JWT/JWKS settings, and database connection settings.
- Do not automatically copy local JSON data into a user account because it has
  no trustworthy owner. Keep an explicit local-only migration command for a
  selected email/user ID if needed later.
- Preserve existing response fields and SSE event names so the workbench UI
  remains compatible.
- Existing `thread_id` values may remain opaque strings, but new records are
  generated server-side and always resolved through `(user_id, thread_id)`.

## Testing strategy

Backend tests are written first for:

- valid, missing, malformed, expired, and wrong-audience JWTs;
- route rejection without authentication;
- user A cannot list, read, append to, review, or delete user B data;
- thread ownership is checked before streaming begins;
- repository transactions persist messages, memories, catalog entries, and
  summaries across a new service instance;
- LangGraph checkpoint/config namespaces include both user and thread;
- Edge Function forwards `Authorization` and preserves SSE behavior.

Frontend tests cover the auth gate, OTP state transitions, resend cooldown,
session refresh, sign-out cleanup, and API 401 handling. SQL migration checks
verify RLS is enabled and policies exist for every owned table. Existing
typecheck/build and backend test suites remain required.

## Environment variables

Frontend:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- existing `VITE_API_BASE`

FastAPI:

- `SUPABASE_URL`
- `SUPABASE_JWT_ISSUER`
- `SUPABASE_JWT_AUDIENCE`
- `SUPABASE_JWT_SECRET` or JWKS configuration
- `SUPABASE_DB_URL` (or the selected Postgres connection setting)
- existing model/search/CORS settings

Edge Function:

- existing `HARNESS_BACKEND_URL`
- existing `HARNESS_SHARED_TOKEN` for server-to-server protection

Secrets are never committed, returned by `/api/health`, or exposed to the
browser except the public Supabase URL and anon key.

## Acceptance criteria

1. A new user can request and verify an email OTP, reload the page, and remain
   signed in until sign-out or session expiry.
2. An unauthenticated browser cannot access user-data endpoints.
3. Two users can create same-named threads and same-text memories without any
   cross-user reads, writes, summaries, paper catalog entries, or LangGraph
   checkpoints.
4. Data survives FastAPI restart and is available through the existing thread,
   memory, and streaming UI flows.
5. Qoder Edge Function continues to proxy authenticated JSON and SSE traffic.
6. Automated tests cover authentication, ownership, persistence, and the
   frontend auth states, with typecheck/build passing.
