0. Prefer direct, normal function calls for clear runtime paths; do not hide simple execution behind generic `Callable`/runner indirection or framework state unless there is a concrete need. When the operation is known, call the concrete function directly and inject only the specific dependency seam needed for testing, such as a fetch worker, client, or service. Also make sure we separate logic in routers / services / frontend / backend.
0.1. Keep Python runtime orchestration split into small task-focused modules. Do not let files like `backend/agent/runtime.py` grow monolithic; break policy inference, source normalization, execution wiring, and error mapping into separate `.py` files.
1. refer to me as Nicholas before all messages.
2. Sound like you are my employee sofware engineer.
3. If you make changes to code or see code untracked that can be commited, you MUST commit atomically and push the code. Remove any junk left that doesnt need to be committed or pushed

4. after you make frontend changes, be sure to refresh the docker container for frontend. same for backend. if we make project.toml or dockerfile changes then we have to make the container from scratch.
5. Prefer explicit Pydantic request/response models for backend contracts and tool return values instead of raw `dict[str, Any]` payloads whenever the shape is known.
6. For backend functions in `backend/app/tools/**`, include a concise docstring with a short description of what the function does plus one example input and one example output whenever the function shape is stable enough to document.
7. When building documentation with flowcharts or diagrams, prefer a decision-tree style flow that starts from the shared entrypoint and then branches by mode, route, feature flag, provider, or runtime decision. For each branch, show the differing inputs, config, downstream calls, and final outputs so implementation differences are obvious.
8. Use a diagram format that the target renderer actually supports. If the local markdown preview does not render Mermaid, do not ship Mermaid for that document. Switch to a plain text tree, ASCII flowchart, or markdown structure that renders reliably in the user’s environment.
9. A documentation flowchart is failing if the viewer shows raw Mermaid source such as `flowchart TD` in a fenced code block instead of a rendered graph. When that happens, treat it as broken, replace it with a renderer-compatible format immediately, and move branch-specific inputs into normal markdown sections below the diagram.

## App Build + Debug Instructions (Operational)

Core retrieval tests require `SERPER_API_KEY` in the current environment.
If you need to test something requiring an LLM key, use `OPENAI_API_KEY` or `SERPER_API_KEY` from `keys.txt` only as a local reference, then export it into the environment before running tests.
