import type { ResolvedDomainScope } from "../../core/policy/domain-scope.js";
import { normalizeDomain } from "../../core/policy/domain-scope.js";
import type { SearchResultItem } from "../../sdk/contracts/search.js";

export function filterSearchResultsByDomainScope(
  results: readonly SearchResultItem[],
  domainScope: ResolvedDomainScope,
): SearchResultItem[] {
  if (!domainScope.includeDomains.length && !domainScope.excludeDomains.length) {
    return [...results];
  }

  const includedDomains = new Set(domainScope.includeDomains);
  const excludedDomains = new Set(domainScope.excludeDomains);

  return results.filter((result) => {
    const domain = normalizeDomain(result.url);

    if (!domain) {
      return false;
    }

    if (excludedDomains.has(domain)) {
      return false;
    }

    if (includedDomains.size > 0 && !includedDomains.has(domain)) {
      return false;
    }

    return true;
  });
}
