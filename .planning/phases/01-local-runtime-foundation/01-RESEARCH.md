# Phase 01: Local Runtime Foundation - Research

**Researched:** 2026-03-17
**Domain:** Local Docker Compose runtime + Python backend environment-key validation
**Confidence:** HIGH

## Summary

This phase should establish a deterministic local runtime where backend and frontend start together via Docker Compose, and backend startup blocks immediately if required API keys are missing. The core technical choice is Docker Compose (plugin v2) for orchestration plus strict environment configuration validation in backend process initialization.

For runtime wiring, Compose should be treated as the source of truth for service topology, startup order, and health semantics. `depends_on` with `condition: service_healthy` and explicit `healthcheck` commands are the standard pattern to avoid race conditions. Compose variable interpolation should enforce required values for `OPENAI_API_KEY` and `SERPER_API_KEY` using `${VAR:?error}` so stack startup fails early and clearly when keys are absent.

For backend config loading, use `pydantic-settings` with `BaseSettings` in Python and instantiate settings at startup (or in app lifespan) so missing required fields raise a validation error before the API serves requests. This directly satisfies `RUNTIME-04` while preserving testability and typed config.

**Primary recommendation:** Use Docker Compose as the only local bootstrap entrypoint and enforce keys at both Compose interpolation time and backend `BaseSettings` validation time.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Docker Compose plugin | 2.x (require >=2.20) | Run backend + frontend together, networking, health-gated dependencies | Official Docker local multi-service workflow; supports `depends_on` conditions and `env_file`/`required` controls |
| FastAPI | 0.135.1 (current PyPI) | Backend API service runtime | Standard Python API framework with clean startup lifecycle hooks |
| pydantic-settings | 2.13.1 (current PyPI) | Typed env loading + required-field validation | Official FastAPI-recommended settings approach; fails clearly on missing required vars |
| Uvicorn | 0.42.0 (current PyPI) | ASGI server process for backend container | Standard FastAPI production/dev server runtime |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | latest 1.x | Parse `.env` for local-only convenience | Use when running backend outside Compose or when `BaseSettings` `env_file` is desired |
| Docker healthcheck | Compose spec feature | Define readiness for each service | Use for `backend` and `frontend` to support `docker compose up --wait` and robust startup checks |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Docker Compose | ad-hoc shell scripts (`npm run ...` + `uvicorn ...`) | Scripts are faster to sketch but brittle and violate `RUNTIME-01` single-entrypoint requirement |
| `pydantic-settings` | manual `os.getenv` checks | Manual checks are easy to miss, less typed, and less testable |
| Compose-only key checks | backend-only validation | Backend-only catches missing keys later and may allow partial startup confusion |

**Installation:**
```bash
pip install fastapi uvicorn pydantic-settings python-dotenv
```

## Architecture Patterns

### Recommended Project Structure
```text
infra/
  compose.yaml              # Two services + healthchecks + required env interpolation
backend/
  app/
    config.py               # BaseSettings model (required OPENAI_API_KEY, SERPER_API_KEY)
    main.py                 # FastAPI app + lifespan startup validation + /healthz
frontend/
  ...                       # Existing TS frontend with /health or root probe
```

### Pattern 1: Compose as Single Runtime Contract
**What:** One `compose.yaml` that defines both services, network, ports, startup order, and required env keys.
**When to use:** Always for local runtime in this project; avoid side-channel startup docs/scripts.
**Example:**
```yaml
# Source: https://docs.docker.com/compose/environment-variables/variable-interpolation/
# Source: https://docs.docker.com/compose/how-tos/startup-order/
services:
  backend:
    build: ./backend
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY:?OPENAI_API_KEY is required}
      SERPER_API_KEY: ${SERPER_API_KEY:?SERPER_API_KEY is required}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  frontend:
    build: ./frontend
    depends_on:
      backend:
        condition: service_healthy
```

### Pattern 2: Typed Settings + Startup-Time Validation
**What:** Define required keys on a `BaseSettings` model and instantiate on startup so missing keys stop boot immediately.
**When to use:** Backend initialization for every environment (local, CI, future deploys).
**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/settings/
# Source: https://fastapi.tiangolo.com/advanced/events/
# Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    OPENAI_API_KEY: str
    SERPER_API_KEY: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = Settings()  # Raises ValidationError if keys are missing
    yield

app = FastAPI(lifespan=lifespan)
```

### Pattern 3: Reachability Verification as Runtime Acceptance
**What:** Verify startup via Compose state + HTTP probes after `up`.
**When to use:** Required for phase success criteria and CI smoke check.
**Example:**
```bash
# Source: https://docs.docker.com/reference/cli/docker/compose/up/
# Source: https://docs.docker.com/reference/cli/docker/compose/ps/
docker compose up --build --wait
docker compose ps --status running
curl -f http://localhost:8000/healthz
curl -f http://localhost:3000/
```

### Anti-Patterns to Avoid
- **Manual multi-terminal bootstrap:** Violates `RUNTIME-01`; creates non-reproducible local startup.
- **Optional key defaults (empty string fallback):** Masks configuration errors and violates `RUNTIME-04`.
- **`depends_on` without healthchecks:** Starts order only, not readiness; causes flaky frontend-to-backend failures.
- **Storing secrets in committed Compose files:** Use environment variables and ignored `.env` files only.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Env parsing/validation | Custom parser around `os.environ` | `pydantic-settings` | Built-in typing, validation, dotenv support, clear failures |
| Service orchestration | Bash process manager for two apps | Docker Compose | Native dependency graph, logs, healthchecks, lifecycle commands |
| Readiness gating | Sleep/retry scripts in shell | Compose `healthcheck` + `depends_on.condition: service_healthy` | Deterministic and self-documenting |

**Key insight:** Runtime foundation failures are usually lifecycle/order/config issues; standards (Compose + Pydantic settings) already solve these reliably.

## Common Pitfalls

### Pitfall 1: Confusing Compose `.env` interpolation with container runtime env
**What goes wrong:** Team expects `.env` interpolation behavior to match container `environment` values exactly.
**Why it happens:** Compose uses `.env` for model interpolation; container env precedence differs when `env_file` and `environment` are combined.
**How to avoid:** Keep key requirements explicit in `environment` using `${VAR:?error}` and validate inside backend too.
**Warning signs:** Compose config resolves but backend still reports missing keys.

### Pitfall 2: Assuming `depends_on` means "ready"
**What goes wrong:** Frontend starts before backend endpoint is healthy.
**Why it happens:** Default `depends_on` only guarantees "started", not "healthy."
**How to avoid:** Add backend `healthcheck` and use long-form `depends_on` with `condition: service_healthy`.
**Warning signs:** Intermittent connection refused on first frontend requests.

### Pitfall 3: Weak or late key validation
**What goes wrong:** Backend process runs until first API call before failing on missing key.
**Why it happens:** Keys are read lazily in tool functions.
**How to avoid:** Instantiate `Settings()` in startup/lifespan and fail process immediately.
**Warning signs:** App starts fine but first tool invocation crashes.

### Pitfall 4: Dotenv strictness surprises in Pydantic v2 settings
**What goes wrong:** Unknown keys in dotenv trigger validation errors unexpectedly.
**Why it happens:** `extra=forbid` behavior in settings construction unless configured.
**How to avoid:** Keep `.env` minimal for backend settings model or intentionally set `extra='ignore'` if compatibility is required.
**Warning signs:** Startup `ValidationError` references fields not present in settings class.

## Code Examples

Verified patterns from official sources:

### Required Compose variable interpolation
```yaml
# Source: https://docs.docker.com/compose/environment-variables/variable-interpolation/
services:
  backend:
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY:?OPENAI_API_KEY is required}
      SERPER_API_KEY: ${SERPER_API_KEY:?SERPER_API_KEY is required}
```

### Health-gated dependency startup
```yaml
# Source: https://docs.docker.com/compose/how-tos/startup-order/
services:
  frontend:
    depends_on:
      backend:
        condition: service_healthy

  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### FastAPI lifespan startup validation with typed settings
```python
# Source: https://fastapi.tiangolo.com/advanced/events/
# Source: https://fastapi.tiangolo.com/advanced/settings/
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    SERPER_API_KEY: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = Settings()
    yield

app = FastAPI(lifespan=lifespan)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FastAPI `@app.on_event("startup")` handlers | `lifespan` async context manager | Modern FastAPI guidance (documented as recommended; startup/shutdown events described as alternative/deprecated path) | Cleaner startup/shutdown wiring and fewer lifecycle edge cases |
| Manual env parsing with `os.getenv` scattered in code | Centralized typed `BaseSettings` | Pydantic v2 ecosystem maturity | Early failure and better config testability |
| Start Compose and poll manually | `docker compose up --wait` + healthchecks | Newer Compose CLI capabilities | Faster, deterministic runtime verification |

**Deprecated/outdated:**
- FastAPI startup/shutdown event handlers as primary lifecycle pattern when `lifespan` can be used.
- Ad-hoc shell-based local startup instructions when Compose is available.

## Open Questions

1. **Backend and frontend exact port contract**
   - What we know: Phase requires both locally reachable after startup.
   - What's unclear: Final chosen host ports (`8000/3000` assumed).
   - Recommendation: Lock ports in `compose.yaml` and mirror in README + smoke test script.

2. **Health endpoint path and semantics**
   - What we know: Reachability checks are required.
   - What's unclear: Whether frontend should expose dedicated `/healthz` vs root probe.
   - Recommendation: Require backend `/healthz`; for frontend, accept `/` initially unless explicit API health route is needed.

3. **Single root `.env` vs per-service env files**
   - What we know: Both patterns are supported by Compose and Pydantic.
   - What's unclear: Desired repo convention for future phases.
   - Recommendation: Start with root `.env` for speed; migrate to per-service env files only if complexity grows.

## Sources

### Primary (HIGH confidence)
- Docker Docs - variable interpolation: https://docs.docker.com/compose/environment-variables/variable-interpolation/
- Docker Docs - startup order and readiness: https://docs.docker.com/compose/how-tos/startup-order/
- Docker Docs - Compose services reference (`depends_on`, `env_file`, `healthcheck`, `environment`): https://docs.docker.com/reference/compose-file/services/
- Docker CLI reference - `docker compose up`: https://docs.docker.com/reference/cli/docker/compose/up/
- Docker CLI reference - `docker compose ps`: https://docs.docker.com/reference/cli/docker/compose/ps/
- FastAPI docs - settings and environment variables: https://fastapi.tiangolo.com/advanced/settings/
- FastAPI docs - lifespan events: https://fastapi.tiangolo.com/advanced/events/
- Pydantic docs - settings management: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- PyPI metadata - FastAPI: https://pypi.org/pypi/fastapi/json
- PyPI metadata - pydantic-settings: https://pypi.org/pypi/pydantic-settings/json
- PyPI metadata - uvicorn: https://pypi.org/pypi/uvicorn/json

### Secondary (MEDIUM confidence)
- None needed; primary sources were sufficient.

### Tertiary (LOW confidence)
- None retained in final recommendations.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - based on official Docker/FastAPI/Pydantic docs plus current PyPI metadata.
- Architecture: HIGH - directly derived from official lifecycle/orchestration docs.
- Pitfalls: HIGH - mapped from explicit docs behavior (interpolation, precedence, readiness, validation).

**Research date:** 2026-03-17
**Valid until:** 2026-04-16 (30 days)
