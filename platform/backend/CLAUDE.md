# APEX Platform — Backend (FastAPI)

## Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.12 |
| Framework | FastAPI 0.115+ |
| Validation | Pydantic v2 (`model_validate`, `model_dump`) |
| ORM | SQLAlchemy 2.x async (`AsyncSession`) |
| Migrations | Alembic (`alembic revision --autogenerate`) |
| Database | PostgreSQL 16 |
| Task queue | Celery 5 + Redis 7 broker |
| Logging | structlog (JSON format in production) |
| HTTP client | httpx async |
| AI SDK | anthropic (official Python SDK) |
| Testing | pytest, pytest-asyncio, httpx, factory-boy, pytest-mock |

## Directory Layout

```
backend/
  app/
    api/
      v1/
        __init__.py
        router.py             master router (includes all sub-routers)
        organisations.py      CRUD for organisations
        projects.py           CRUD + phase overview for projects
        phases.py             Phase status, gate evaluation
        artifacts.py          Artifact list, detail, version history, download URL
        agents.py             Trigger agent run, SSE stream endpoint
        governance.py         Audit log, PII events, policy violations
        auth.py               Login, token refresh (Phase 2)
    agents/
      base.py                 AgentContext, AgentResult, BaseAgent ABC
      requirements.py         RequirementsAgent
      architecture.py         ArchitectureAgent
      development.py          DevelopmentAgent (PR review)
      testing.py              TestingAgent
      cicd.py                 CICDAgent
      docs.py                 DocsAgent
      governance.py           GovernanceAgent
    integrations/
      github/
        client.py             Authenticated httpx client (PAT or App token)
        prs.py                List PRs, get diff, post review comments
        releases.py           Create/update GitHub Release
        repos.py              File read/write via GitHub contents API
        webhooks.py           Webhook signature verification + event routing
      jira/
        client.py             Jira Agile REST v1 client (absorbs automation/jira-bridge/)
        sprints.py            Active sprint, sprint issues
        stories.py            Create epic, create story, update status
        webhooks.py           Jira webhook receiver
      confluence/
        client.py             Confluence REST API v2 client (absorbs automation/confluence-writer/)
        pages.py              Create page, update page, get space info
      anthropic/
        client.py             Anthropic SDK wrapper (streaming, tool use, retry)
        tools.py              Tool definitions for GitHub/Jira/Confluence tool use
    middleware/
      pii_guard/
        guard.py              FastAPI middleware (absorbs governance/pii-guard/guard.py)
        patterns.py           PII regex patterns (absorbs governance/pii-guard/patterns.py)
        comprehend.py         AWS Comprehend layer (Phase 2)
      audit.py                Audit log middleware (every request + agent run)
      auth.py                 JWT verification middleware (Phase 2)
      correlation.py          Request correlation ID injection
    models/
      organisation.py
      project.py
      phase.py
      artifact.py
      agent_run.py
      audit.py
      governance.py
    schemas/
      organisation.py
      project.py
      phase.py
      artifact.py
      agent_run.py
      governance.py
      common.py               Pagination, error (RFC 7807), timestamps
    services/
      organisation_service.py
      project_service.py
      phase_service.py
      artifact_service.py     Includes S3 upload/pre-signed URL
      agent_service.py        Dispatch Celery task, manage run lifecycle
    db/
      session.py              AsyncEngine, AsyncSessionLocal, get_db dependency
      migrations/             Alembic versions/
    core/
      config.py               Settings via pydantic-settings (reads .env)
      logging.py              structlog JSON processor chain
      security.py             JWT encode/decode helpers
      storage.py              S3 boto3 async wrapper
  tasks/
    agent_tasks.py            Celery tasks: run_agent_task(run_id, agent_type, context)
    refresh_tasks.py          Periodic: refresh GitHub/Jira data per project
    celery_app.py             Celery app init, beat schedule
  tests/
    conftest.py               Async engine, test DB, httpx client fixtures
    factories/                factory_boy factories per model
    api/                      Router tests (one file per router)
    agents/                   Agent unit tests (mocked Claude API)
    integrations/             Integration tests (VCR cassettes)
    services/                 Service layer tests
  alembic.ini
  pyproject.toml
  Dockerfile
  .env.example
```

## Key Patterns

### Dependency Injection (FastAPI `Depends`)
```python
# db/session.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# api/v1/projects.py
@router.get("/projects/{project_id}")
async def get_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    return await project_service.get(db, project_id)
```

### Agent Context / Result
```python
@dataclass
class AgentContext:
    project_id: UUID
    phase: PhaseType
    actor_id: str
    inputs: dict[str, Any]          # phase-specific context
    prompt_library: dict[str, str]  # loaded from prompts/
    run_id: UUID                    # pre-created agent_run record ID

@dataclass
class AgentResult:
    run_id: UUID
    status: Literal["completed", "failed"]
    artifacts: list[ArtifactCreate]
    token_usage: TokenUsage
    cost_usd: Decimal
    error: str | None = None
```

### SSE Stream
```python
@router.get("/agents/{run_id}/stream")
async def stream_agent(run_id: UUID, db: AsyncSession = Depends(get_db)):
    async def event_generator():
        async for message in agent_service.stream_run(db, run_id):
            yield f"data: {message.model_dump_json()}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### RFC 7807 Error Format
```python
# All errors must use this shape — never raise raw HTTPException with plain strings
raise HTTPException(
    status_code=404,
    detail={
        "type": "https://apex-sdlc/errors/project-not-found",
        "title": "Project Not Found",
        "status": 404,
        "detail": f"No project with id={project_id}",
    },
)
```

## Environment Variables

All loaded via `core/config.py` using `pydantic-settings`. Required in `.env`:

```
DATABASE_URL=postgresql+asyncpg://apex:apex_dev@localhost:5432/apex_platform
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
JIRA_BASE_URL=https://myorg.atlassian.net
JIRA_EMAIL=service@myorg.com
JIRA_API_TOKEN=...
CONFLUENCE_BASE_URL=https://myorg.atlassian.net/wiki
CONFLUENCE_TOKEN=...
S3_ARTIFACT_BUCKET=apex-artifacts-dev
AWS_REGION=eu-west-1
SECRET_KEY=random-64-char-string-for-jwt
ENVIRONMENT=development
LOG_LEVEL=INFO
```

## Non-Negotiables

- `async/await` everywhere — no sync SQLAlchemy calls, no sync httpx calls
- No lazy loading — always use `selectinload()` / `joinedload()` explicitly
- Pydantic v2 — `model_validate()`, `model_dump()`, `@model_validator`, `@field_validator`
- PII guard runs before every Claude API call — enforced in `anthropic/client.py`
- Every agent run creates an `audit_log` entry — enforced in `agent_service.py`
- No `print()` — structlog only
- No raw SQL string formatting — SQLAlchemy ORM or `text()` with `:param` binding

## Testing Pattern

```python
# tests/api/test_projects.py
@pytest.mark.asyncio
async def test_create_project(async_client: AsyncClient, db_session: AsyncSession):
    payload = ProjectFactory.build_dict()
    response = await async_client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
```

Run: `pytest --cov=app --cov-fail-under=80 -v`

## eeik Agents for This Directory

| Task | Command |
|------|---------|
| Implement a new router | "Using python-developer agent, implement the phases router with CRUD endpoints" |
| Add Alembic migration | `/migrate-db` or "Using dba-advisor, generate migration for the artifact_versions table" |
| Implement an agent class | "Using ai-engineer, implement the RequirementsAgent in agents/requirements.py" |
| Review before PR | `/review` |
| Security check | `/security-scan app/` |
| Estimate effort | `/estimate "implement all 7 agent classes"` |
