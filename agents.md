2. Stack: Docker Compose + FastAPI + React/TypeScript/Vite + Postgres + Alembic + pgvector.
2. Always use react for frontend, not html
3. Source roots: `src/backend/`, `src/frontend/`, and `docker-compose.yml`.
4. Backend dependencies are managed with `uv` (`pyproject.toml` + `uv.lock`).

If you need to make changes or publish to PyPi use the token in sdk-token.txt.  if you need to use the openAI key look at the same txt file. Use both of these for testing when needed.

If you made backend changes, simply refresh the containers changes. run docker locally, not in a virtual env.
- Refresh (normal iteration): Restart backend to pick up code changes: `docker compose restart backend`. No need to tear down or rebuild unless you change dependencies or Dockerfile.

Only completely restart everything if there are dependency changes in uv
-  Start fresh (when needed): Remove all services, volumes, and images: `docker compose down -v --rmi all`, then `docker compose build` and `docker compose up -d`.

After you refresh or restart, if it is backend changes then check the logs of specific containers such as:
- Tail backend logs - also use for backend checks: `docker compose logs -f backend`.

If frontend changes are made and you need to verify it is there / functionality as well, use the local Chrome DevTools flow only. Do not use any Docker-hosted Chrome/browser endpoint workflow. here are the instructions:
- `launch-devtools.sh` is the default entry point. Run it whenever you want to start or reuse the local Chrome debugging session.
- Launch or reuse local Chrome: `./launch-devtools.sh http://localhost:5173`.
- The script reuses a healthy `9222` session when present, opens a fresh app tab when needed, and otherwise launches a dedicated local Chrome profile.
- DevTools targets endpoint: `http://127.0.0.1:9222/json/list`.
- Verify the endpoint: `curl http://127.0.0.1:9222/json/list` and confirm there is a target whose `url` starts with `http://localhost:5173` and includes a `webSocketDebuggerUrl`.
- Keep the Chrome process running; tabs can be closed and recreated through `launch-devtools.sh`.
- If port `9222` is already in use and `json/list` responds, reuse that session instead of launching another browser.
- If port `9222` is already in use but `json/list` does not respond, stop the stale listener first or rerun with a different `PORT`.
- If the browser-control tool is unavailable or broken in the session, fall back to CDP against the local DevTools endpoint:
  `python3 - <<'PY'`
  `import json, urllib.request`
  `pages = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list"))`
  `print(json.dumps(pages, indent=2))`
  `PY`
- When scripting CDP, prefer the page target from `json/list` whose `url` starts with `http://localhost:5173`, then connect to its `webSocketDebuggerUrl`.
- For agent runs, the backend SSE endpoint is `/api/agents/run-events/{job_id}` and it emits typed events such as `stage.completed` and `run.completed`. Frontend code and test fakes must listen with `addEventListener(...)` for those event names; `onmessage` alone is not sufficient in a real browser.
- For CDP verification of the agent stream, it is acceptable to instrument `window.fetch` and `window.EventSource` in the page before submitting the form, then confirm the browser opened `/api/agents/run-events/...` and did not request `/api/agents/run-status/...`.
- If direct CDP websocket attachment fails with `403 Forbidden`, the local Chrome session was likely started without the remote-origin flag. Restart that Chrome session through `launch-devtools.sh`, which now launches Chrome with `--remote-allow-origins='*'`.
- The browser-control workaround is: `launch-devtools.sh` -> `json/list` -> pick the `localhost:5173` target -> drive it over CDP directly.
- Do not rely on `localhost` from inside a Docker-hosted browser. Use the local Chrome session from `launch-devtools.sh` so `localhost:5173` and `localhost:8000` resolve correctly.
11. Frontend URL: `http://localhost:5173`.
12. Backend URL: `http://localhost:8000`.
13. Health endpoint: `http://localhost:8000/api/health`.


If you mess with the backend DB, here are useful commands for updating the DB. Use alembic and migration commands when we are changing DB schemas...
22. DB shell: `docker compose exec db psql -U ${POSTGRES_USER:-agent_user} -d ${POSTGRES_DB:-agent_search}`.
23. Alembic upgrade: `docker compose exec backend uv run alembic upgrade head`.
24. Create migration: `docker compose exec backend uv run alembic revision -m "describe_change"`.
25. Alembic history: `docker compose exec backend uv run alembic history`.
26. Alembic current: `docker compose exec backend uv run alembic current`.
27. Verify pgvector extension: `docker compose exec db psql -U agent_user -d agent_search -c "\\dx"`.
28. Verify tables: `docker compose exec db psql -U agent_user -d agent_search -c "\\dt"`.
29. Wipe internal data (documents + chunks only): `POST /api/internal-data/wipe` or `docker compose exec db psql -U agent_user -d agent_search -c "TRUNCATE internal_documents CASCADE;"`.

To run specific tests, here are commands
30. Backend tests: `docker compose exec backend uv run pytest`.
31. Backend smoke tests: `docker compose exec backend uv run pytest tests/api -m smoke`.
32. Frontend tests: `docker compose exec frontend npm run test`.
33. Frontend typecheck: `docker compose exec frontend npm run typecheck`.
34. Frontend build check: `docker compose exec frontend npm run build`.
35. Browser debug workflow for E2E feature testing:
- Start app services: `docker compose up -d backend frontend`.
