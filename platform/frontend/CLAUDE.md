# APEX Platform — Frontend (Next.js 14)

## Stack

| Component | Choice |
|-----------|--------|
| Framework | Next.js 14 App Router |
| Language | TypeScript 5.x strict |
| Data fetching | TanStack Query v5 |
| Styling | Tailwind CSS |
| Components | shadcn/ui |
| Forms | React Hook Form + Zod |
| HTTP client | fetch (native) wrapped in `lib/api.ts` |
| Icons | lucide-react |
| Markdown render | react-markdown + remark-gfm |
| Diagrams | mermaid.js (agent output diagrams) |
| Testing | Jest, Testing Library React, Playwright (e2e) |

## Directory Layout

```
frontend/
  src/
    app/                          Next.js App Router
      layout.tsx                  Root layout (fonts, providers, global nav)
      page.tsx                    Org home — project registry grid
      (projects)/
        layout.tsx                Projects shell layout (sidebar)
        projects/
          page.tsx                Project list view
          new/
            page.tsx              Onboard new project form
          [projectId]/
            page.tsx              Project detail — SDLC timeline + live metrics
            layout.tsx            Project shell (project nav, persona switcher)
            phase/
              [phase]/
                page.tsx          Phase detail — artifact gallery + "Run Agent" panel
            generate/
              page.tsx            Artifact generator (select phase, configure, run)
      governance/
        page.tsx                  Org governance — audit log, violations, gate status
        layout.tsx
      settings/
        page.tsx                  Org settings (integrations config, team management)
    components/
      ui/                         shadcn/ui primitives (auto-generated, do not edit)
      layout/
        TopNav.tsx                Logo, org switcher, user menu
        Sidebar.tsx               Project navigation, collapsible
        PersonaSwitcher.tsx       Role selector (persisted to localStorage)
      projects/
        ProjectCard.tsx           Summary card for org home grid
        ProjectGrid.tsx           Grid of ProjectCards with search/filter
        OnboardProjectForm.tsx    Multi-step form: name, repo, Jira, team
        SDLCTimeline.tsx          Horizontal phase timeline with status indicators
        LiveMetricsBar.tsx        GitHub PR count, Jira sprint progress, coverage
      phases/
        PhasePanel.tsx            Active phase detail: artifact list + run agent button
        ArtifactCard.tsx          Single artifact: title, type, created, actions
        ArtifactGallery.tsx       Grid/list of artifacts for a phase
        ArtifactViewer.tsx        Markdown render + Mermaid diagram support
        ArtifactVersionHistory.tsx  Version timeline with diff link
        RunAgentButton.tsx        Triggers agent; opens AgentProgressDrawer
      agents/
        AgentProgressDrawer.tsx   Slide-over panel with SSE streaming output
        AgentRunList.tsx          History of agent runs for a phase
        AgentRunDetail.tsx        Full run detail: messages, tokens, cost
      governance/
        AuditLogTable.tsx         Filterable audit log with expand-row
        ViolationsPanel.tsx       Policy violations with severity badges
        GateStatusGrid.tsx        Phase gate pass/fail across all projects
        PIIEventLog.tsx           PII detection events with pattern details
    lib/
      api.ts                      Base fetch wrapper (adds auth header, base URL)
      queries/
        projects.ts               TanStack Query hooks: useProjects, useProject
        phases.ts                 usePhases, usePhaseGate
        artifacts.ts              useArtifacts, useArtifact, useArtifactVersions
        agents.ts                 useAgentRuns, useAgentRun, useRunAgent (mutation)
        governance.ts             useAuditLog, useViolations, usePIIEvents
      sse.ts                      SSE hook: useAgentStream(runId)
      persona.ts                  Persona context (localStorage, filter helpers)
      formatters.ts               Date, token count, cost USD formatters
    types/
      project.ts                  Project, Phase, PhaseGate interfaces
      artifact.ts                 Artifact, ArtifactVersion interfaces
      agent.ts                    AgentRun, AgentRunMessage, AgentResult interfaces
      governance.ts               AuditLog, PIIEvent, PolicyViolation interfaces
      common.ts                   Pagination, ApiError, Persona enum
  public/
  Dockerfile
  next.config.ts
  tailwind.config.ts
  tsconfig.json
  package.json
```

## Key Patterns

### API Client
```typescript
// lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!res.ok) {
    const problem = await res.json();
    throw new ApiError(problem);
  }
  return res.json() as Promise<T>;
}
```

### TanStack Query Hook
```typescript
// lib/queries/projects.ts
export function useProject(projectId: string) {
  return useQuery({
    queryKey: ['projects', projectId],
    queryFn: () => apiFetch<Project>(`/projects/${projectId}`),
    staleTime: 30_000,
  });
}
```

### SSE Agent Stream
```typescript
// lib/sse.ts
export function useAgentStream(runId: string | null) {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  useEffect(() => {
    if (!runId) return;
    const es = new EventSource(`${API_BASE}/api/v1/agents/${runId}/stream`);
    es.onmessage = (e) => setMessages(prev => [...prev, JSON.parse(e.data)]);
    return () => es.close();
  }, [runId]);
  return messages;
}
```

### Persona Switcher
```typescript
// lib/persona.ts
export type Persona = 'developer' | 'ba' | 'qa' | 'pm' | 'lead' | 'architect' | 'ciso';

export function usePersona() {
  const [persona, setPersona] = useState<Persona>(() =>
    (localStorage.getItem('apex_persona') as Persona) ?? 'developer'
  );
  const switchPersona = (p: Persona) => {
    localStorage.setItem('apex_persona', p);
    setPersona(p);
  };
  return { persona, switchPersona };
}
```

## Page Designs

### Org Home (`/`)
- Hero: org name, total projects, overall AI adoption %
- Project grid: ProjectCard per project (name, type, current phase, sprint progress, last agent run)
- Actions: "Onboard Project" button (opens wizard)
- Filter: by phase, by project type (spring-boot / angular / mainframe / python)

### Project Detail (`/projects/[projectId]`)
- Top: project name, tech type badge, GitHub link, Jira board link
- PersonaSwitcher — changes KPI cards shown below
- SDLCTimeline — horizontal bar showing 7 phases; current phase highlighted; click to navigate
- LiveMetricsBar — open PRs, sprint velocity, coverage %, last deployment
- Below timeline: PhasePanel for active phase (artifacts + Run Agent)

### Phase Detail (`/projects/[projectId]/phase/[phase]`)
- Phase header: name, status (active/complete/pending), started date
- ArtifactGallery: grid of ArtifactCards for this phase
- "Run Agent" button → opens AgentProgressDrawer with SSE stream
- AgentRunList: history of previous runs for this phase

### Governance (`/governance`)
- Org-level only (visible to Lead/Architect/CISO personas)
- GateStatusGrid: all projects × all phases → pass/fail matrix
- AuditLogTable: filterable by project, actor, model, date range
- ViolationsPanel: open violations with severity + assigned remediation
- PIIEventLog: PII detection events with blocked/redacted flag

## Environment Variables

```
NEXT_PUBLIC_API_URL=http://localhost:8000   # FastAPI backend URL
NEXT_PUBLIC_APP_NAME=APEX SDLC Platform
```

## Non-Negotiables

- App Router only — no `pages/` directory, no `getServerSideProps`
- Server components by default — add `"use client"` only when needed (event handlers, hooks, browser APIs)
- No `any` types — strict TypeScript; use `unknown` + type guards when needed
- TanStack Query for all API state — no raw `useEffect` + `fetch` combos
- Zod schemas must mirror backend Pydantic schemas — keep in sync
- `"use client"` on PersonaSwitcher, AgentProgressDrawer, AuditLogTable (interactive)
- Mermaid diagrams rendered client-side only (dynamic import with `ssr: false`)
- No inline styles — Tailwind utility classes only

## Component Guidelines

- shadcn/ui for all primitive UI (Button, Card, Dialog, Table, Badge, Sheet, Tabs)
- Extend primitives with Tailwind; never override shadcn CSS variables
- `AgentProgressDrawer` uses shadcn `Sheet` component (slide-over)
- `ArtifactViewer` dynamically imports `mermaid` with `{ ssr: false }`
- All data tables (AuditLog, Violations, PRs) use shadcn `DataTable` pattern with column definitions

## eeik Agents for This Directory

| Task | Agent |
|------|-------|
| Implement a new page | "Using react-developer agent, implement the phase detail page" |
| Create a component | "Using react-developer agent, create the SDLCTimeline component" |
| Set up TanStack Query hook | "Using react-developer agent, create query hooks for artifacts" |
| Review before PR | `/review` |
| TypeScript strict errors | "Using react-developer agent, fix all TypeScript errors in lib/queries/" |
| Add Playwright e2e test | "Using react-developer agent, write Playwright test for the onboard project flow" |
