import type { ResolvedSearchControls } from "../../core/policy/retrieval-controls.js";

export interface SerperSearchRequest {
  q: string;
  num: number;
  gl: string;
  hl: string;
  tbs?: string;
}

export function buildSerperSearchRequest(
  query: string,
  controls: ResolvedSearchControls,
): SerperSearchRequest {
  const freshnessTbs = mapFreshnessToTbs(controls.freshness);

  return {
    q: applyDomainScopeToQuery(query, controls),
    num: controls.maxResults,
    gl: controls.country.toLowerCase(),
    hl: controls.language,
    ...(freshnessTbs ? { tbs: freshnessTbs } : {}),
  };
}

function applyDomainScopeToQuery(
  query: string,
  controls: ResolvedSearchControls,
): string {
  const includeTerms = controls.domainScope.includeDomains.map((domain) => `site:${domain}`);
  const excludeTerms = controls.domainScope.excludeDomains.map((domain) => `-site:${domain}`);

  return [query, ...includeTerms, ...excludeTerms].filter(Boolean).join(" ").trim();
}

function mapFreshnessToTbs(
  freshness: ResolvedSearchControls["freshness"],
): string | undefined {
  switch (freshness) {
    case "day":
      return "qdr:d";
    case "week":
      return "qdr:w";
    case "month":
      return "qdr:m";
    case "year":
      return "qdr:y";
    case "any":
    default:
      return undefined;
  }
}
