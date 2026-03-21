## Feature: Multi-mode web search execution — OpenAI

Links:
- https://developers.openai.com/api/docs/guides/tools-web-search
- https://platform.openai.com/docs/guides/tools-web-search
- https://platform.openai.com/docs/guides/background

What it does:
OpenAI exposes three retrieval patterns with different latency and control profiles: fast non-reasoning web search, reasoning-driven agentic search, and long-running deep research. The API returns sourced answers, and the longer-running modes can sustain multi-step search behavior over time.

How it was built:
- Confirmed: The web search guide documents three modes: non-reasoning search, agentic search with reasoning models, and deep research. The same guide documents citations, complete `sources`, domain filtering, and reasoning-model support for `open_page` and `find_in_page`. The background guide documents asynchronous execution with `background=true`, polling/retrieval, and optional streaming for long-running jobs.
- Inferred: Internally, these modes are likely implemented as execution profiles over one shared Responses/tooling substrate rather than three unrelated systems. The main differences appear to be model class, reasoning budget, tool autonomy, and whether execution is synchronous or backgrounded.

Mapping to our product:
- Add a first-class run profile so quick lookup, agentic search, and deep research share one UX but use different execution policies.
- Keep normalized retrieval primitives (`web_search`, `web_crawl`) as the substrate, then layer planning depth and background execution above them.
- Use the existing run history and SSE surfaces for deep research rather than the older synchronous agent endpoint.

## Feature: Tool streaming and citation-rich web output — OpenAI

Links:
- https://developers.openai.com/api/docs/guides/tools-web-search
- https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses&lang=python

What it does:
OpenAI web-grounded responses expose both the retrieval process and the answer provenance. Tool activity can appear as explicit output items such as `web_search_call`, while final answer text can include inline `url_citation` annotations and a broader `sources` list of consulted pages.

How it was built:
- Confirmed: The web search guide shows response output items including `web_search_call` and assistant `message` content with `output_text` annotations of type `url_citation`, including `start_index`, `end_index`, `url`, and `title`. The guide also states that web-derived information shown to end users must have clearly visible, clickable inline citations, and documents a `sources` field that can return every retrieved source with site metadata.
- Inferred: OpenAI likely normalizes tool execution records and citation metadata into a unified response model so the UI can independently render process traces, inline citations, and source lists without parsing raw model text heuristically.

Mapping to our product:
- Extend run completion contracts from plain `final_answer` strings to structured answer blocks with citations and normalized sources.
- Expand SSE/history events from coarse `tool_call` lifecycle events to richer retrieval action records while keeping payload safety and truncation rules.
- Render clickable inline citations and a source list in the frontend instead of treating the answer as plain text only.
