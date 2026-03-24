from __future__ import annotations

from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

from backend.agent.deep_agents.persistence.artifacts import (
    DEFAULT_DEEP_RESEARCH_NAMESPACE,
    namespace_from_backend_context,
)


def build_deep_research_backend(
    runtime: object,
    *,
    namespace_root: str = DEFAULT_DEEP_RESEARCH_NAMESPACE,
) -> CompositeBackend:
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={
            "/runs/": StoreBackend(
                runtime,
                namespace=lambda ctx: namespace_from_backend_context(
                    ctx,
                    namespace_root=namespace_root,
                ),
            ),
            "/plans/": StoreBackend(
                runtime,
                namespace=lambda ctx: namespace_from_backend_context(
                    ctx,
                    namespace_root=namespace_root,
                ),
            ),
        },
    )
