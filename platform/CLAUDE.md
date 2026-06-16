# APEX SDLC Platform — Master Agent Context

## Project Brief

APEX SDLC Platform is an enterprise AI-powered SDLC operating system. It embeds autonomous AI agents at every phase of software delivery — Requirements through Governance — giving organisations a single control plane for project health, artifact generation, policy enforcement, and cross-team coordination.

This is **not** a reporting dashboard. It is an active participant in the SDLC: it generates Gherkin stories, writes ADRs, reviews PRs, produces test plans, publishes Confluence pages, and enforces phase gates. Every AI action is logged with model, token count, cost, actor, and full before/after state.

## Architecture

```
platform/
  backend/      FastAPI 0.115+ (Python 3.12) — REST API + agent orchestrator
  frontend/     Next.js 14 App Router (TypeScript strict) — persona-driven SPA
```

Data flow:
```
Next.js Portal → FastAPI /api/v1/ → Services → DB (PostgreSQL 16)
                                  ↓
                            Agent Orchestrator → Claude API (claude-opus-4-8)
                                  ↓
                   Integrations: GitHub API | Jira API | Confluence API
                                  ↓
                            Artifact Storage (S3) + Audit Log (DB)
```

Long-running agent jobs run as Celery tasks (broker: Redis). The frontend streams progress via SSE (`/api/v1/agents/{run_id}/stream`).

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.12, FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.x async, Alembic |
| Database | PostgreSQL 16 (JSONB for artifact metadata) |
| Cache / Queue | Redis 7, Celery 5 |
| AI | Anthropic SDK, claude-opus-4-8, streaming + tool use |
| Frontend | Next.js 14 App Router, TypeScript strict, TanStack Query v5 |
| Styling | Tailwind CSS, shadcn/ui |
| Infrastructure | Docker Compose (local), AWS ECS Fargate + RDS Aurora + ElastiCache (cloud) |

## Directory Structure

```
platform/
  backend/
    app/
      api/v1/             routers per resource
      agents/             per-phase agent classes
        requirements.py
        architecture.py
        development.py
        testing.py
        cicd.py
        docs.py
        governance.py
      integrations/
        github/           GitHub REST API v3 + webhook receiver
        jira/             Jira Agile REST API v1 (absorbs automation/jira-bridge/)
        confluence/       Confluence REST API v2 (absorbs automation/confluence-writer/)
        anthropic/        Claude API client wrapper
      middleware/
        pii_guard/        PII detection (absorbs governance/pii-guard/)
        audit.py          Audit log middleware
        auth.py           JWT auth (Phase 2+)
      models/             SQLAlchemy ORM models (one file per entity group)
      schemas/            Pydantic v2 schemas (request/response DTOs)
      services/           Business logic, no ORM calls here — delegates to models
      db/
        session.py        Async engine + session factory
        migrations/       Alembic env.py and versions/
      core/
        config.py         Settings (pydantic-settings, reads .env)
        logging.py        structlog configuration
        security.py       JWT helpers
    tests/
      conftest.py
      api/                httpx async client tests per router
      agents/             agent unit tests with mocked Claude API
      integrations/       integration tests (use VCR cassettes)
    alembic.ini
    pyproject.toml
    Dockerfile
    .env.example
  frontend/
    src/
      app/                Next.js App Router
      components/         Reusable UI components
      lib/                API client, query hooks, utilities
      types/              TypeScript interfaces
    Dockerfile
    next.config.ts
    package.json
  docker-compose.yml
  project-manifest.yaml
  CLAUDE.md               (this file)
  README.md
```

## Data Model

| Entity | Description |
|--------|-------------|
| `organisations` | Top-level tenant; owns projects, has governance context |
| `projects` | Software project: GitHub repo, Jira project, Confluence space, current phase |
| `teams` | Team within an org; assigned to projects |
| `members` | User with persona role (Developer/BA/PM/QA/Lead/Architect/CISO) |
| `phases` | SDLC phase instance per project (Requirements→Architecture→Dev→Test→CI/CD→Docs→Governance) |
| `phase_gates` | Gate criteria for phase transition: required artifacts, approvers, policy checks |
| `artifacts` | Agent-generated document: type, content_ref, phase, project |
| `artifact_versions` | Immutable snapshot: content hash, S3 key, Confluence page ID |
| `agent_runs` | Agent execution record: model, tokens, cost_usd, duration, status, actor |
| `agent_run_messages` | Message turns within a run (system/user/assistant) with token counts |
| `audit_log` | Append-only log of every AI action (actor, model, phase, before, after, timestamp) |
| `pii_events` | PII detection events: pattern matched, action taken, agent run reference |
| `policy_violations` | Policy check failures: policy ID, severity, project, remediation status |

## SDLC Phase Agents

Each agent is an async class in `backend/app/agents/{phase}.py` implementing:
```python
class BaseAgent:
    async def run(self, context: AgentContext) -> AgentResult: ...
```

| Phase | Agent class | Context inputs | Artifact outputs | Writes to |
|-------|-------------|---------------|-----------------|-----------|
| Requirements | `RequirementsAgent` | Problem brief, Jira project key, existing stories | Gherkin user stories, gap analysis, acceptance criteria | Jira epics/stories + artifact DB |
| Architecture | `ArchitectureAgent` | Requirements artifacts, tech stack, team size | ADRs, project CLAUDE.md, Mermaid component diagram | Confluence + repo root via GitHub API |
| Development | `DevelopmentAgent` | PR diff, repo CLAUDE.md, coverage data | PR review (inline comments), test generation hints, quality report | GitHub PR comments + artifact DB |
| Testing | `TestingAgent` | Feature specs, existing test coverage | Test plan, test cases, coverage gap analysis, QA checklist | Confluence QA space + artifact DB |
| CI/CD | `CICDAgent` | Commit range, deployment target, changelog | Release notes, deployment checklist, rollback plan | GitHub Releases + Confluence |
| Docs | `DocsAgent` | OpenAPI spec, architecture artifacts, codebase summary | API reference, onboarding guide, README, changelog | Confluence + GitHub repo |
| Governance | `GovernanceAgent` | Audit log snapshot, policy violations, PII events | Audit report, ARB prep document, risk register update | Confluence governance space + artifact DB |

## Agent Invocation Pattern

1. Portal sends `POST /api/v1/projects/{id}/phases/{phase}/agents/run` with input payload
2. API validates, runs PII guard on inputs, creates `agent_run` record (status=pending)
3. Celery task dispatched → agent class `run()` called with `AgentContext`
4. Agent streams Claude API response; each chunk appended to `agent_run_messages`
5. On completion: artifact saved → S3 upload → `artifacts` record created → audit_log entry
6. Frontend polls SSE endpoint `GET /api/v1/agents/{run_id}/stream` for live progress

## eeik-bootstrap Agent Map

Use these agents from eeik-bootstrap for implementation work:

| Task | Agent |
|------|-------|
| FastAPI routers, services, schemas | `python-developer` |
| SQLAlchemy models, Alembic migrations | `dba-advisor` |
| Claude API agent implementation | `ai-engineer` |
| Celery task queue setup | `python-developer` |
| AWS CDK stacks | `cdk-terraform-helper` |
| ECS/RDS/ElastiCache architecture | `aws-architect` |
| Next.js components, pages, hooks | `react-developer` |
| GitHub Actions pipelines | `ci-engineer` |
| Docker, docker-compose | `containerisation-helper` |
| PR review before merge | `code-reviewer` |
| Security audit | `security-auditor` |
| API design / OpenAPI spec | `architect` |
| ADR creation | `architect` + `/adr` command |
| Effort estimates | `estimator` + `/estimate` command |
| PII guard, audit middleware | `devsecops-engineer` |

## Non-Negotiables (Golden Rules)

1. **Dependency injection** via FastAPI `Depends()` — no global singletons for services
2. **No hardcoded secrets** — all credentials via `core/config.py` (pydantic-settings reads `.env`)
3. **Structured logging** — `structlog` only, never `print()` or `logging.basicConfig()`
4. **No `SELECT *`** — explicit column lists in all SQLAlchemy queries
5. **Parameterised queries** — ORM only; no string-formatted SQL ever
6. **Pydantic v2 everywhere** — `model_validate()` not `parse_obj()`; `model_dump()` not `dict()`
7. **Async throughout** — all DB calls, HTTP calls, and agent runs use `async/await`
8. **RFC 7807 errors** — all API errors return `{"type": ..., "title": ..., "status": ..., "detail": ...}`
9. **PII guard on all agent I/O** — no raw user data reaches Claude API without PII scan
10. **Every agent run logged** — `audit_log` entry mandatory; agent run without audit entry is a bug

## API Design

- Base path: `/api/v1/`
- Auth header: `Authorization: Bearer {jwt}` (Phase 2; open in Phase 1)
- Error format: RFC 7807 (`application/problem+json`)
- Pagination: cursor-based (`?after={cursor}&limit={n}`)
- Filtering: query params (`?status=active&phase=development`)
- OpenAPI docs: `/docs` (Swagger UI), `/redoc`

## Security

- PII guard middleware runs on ALL agent inputs before reaching Claude API
- All agent outputs scanned before storing in DB or writing to GitHub/Jira
- JWT RS256 tokens (Phase 2); API keys for service-to-service (Phase 1)
- GitHub/Jira/Confluence credentials stored in AWS Secrets Manager (cloud) or `.env` (local)
- S3 artifact bucket: server-side encryption (SSE-S3), no public access
- Audit log is append-only; no UPDATE or DELETE on `audit_log` table

## Testing Standards

- `pytest` + `pytest-asyncio` (asyncio_mode = "auto")
- `httpx.AsyncClient` for API integration tests
- `factory_boy` for test fixtures
- `pytest-mock` for mocking external APIs (Claude, GitHub, Jira, Confluence)
- Coverage: 80% minimum; enforced in CI with `--cov-fail-under=80`
- Test layout mirrors `app/` structure under `tests/`
