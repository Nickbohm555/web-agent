from .schemas.web_search import WebSearchInput

__all__ = ["WebSearchInput", "run_web_crawl", "run_web_search", "web_crawl", "web_search"]


def __getattr__(name: str):
    if name in {"run_web_crawl", "web_crawl"}:
        from .web_crawl import run_web_crawl, web_crawl

        return {
            "run_web_crawl": run_web_crawl,
            "web_crawl": web_crawl,
        }[name]
    if name in {"run_web_search", "web_search"}:
        from .web_search import run_web_search, web_search

        return {
            "run_web_search": run_web_search,
            "web_search": web_search,
        }[name]
    raise AttributeError(name)
