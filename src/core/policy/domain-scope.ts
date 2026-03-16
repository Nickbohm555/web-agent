import { getDomain } from "tldts";

export interface ResolvedDomainScope {
  includeDomains: string[];
  excludeDomains: string[];
}

export function resolveDomainScope(input?: {
  includeDomains?: readonly string[] | undefined;
  excludeDomains?: readonly string[] | undefined;
}): ResolvedDomainScope {
  const excludeDomains = normalizeDomainList(input?.excludeDomains);
  const excludeSet = new Set(excludeDomains);
  const includeDomains = normalizeDomainList(input?.includeDomains).filter(
    (domain) => !excludeSet.has(domain),
  );

  return {
    includeDomains,
    excludeDomains,
  };
}

export function normalizeDomainList(
  input?: readonly string[] | undefined,
): string[] {
  if (!input?.length) {
    return [];
  }

  const domains = new Set<string>();

  for (const value of input) {
    const domain = normalizeDomain(value);

    if (domain) {
      domains.add(domain);
    }
  }

  return [...domains].sort((left, right) => left.localeCompare(right));
}

export function normalizeDomain(input: string | undefined): string | null {
  const value = input?.trim().toLowerCase();

  if (!value) {
    return null;
  }

  const normalizedInput = value.includes("://") ? value : `https://${value}`;
  const domain = getDomain(normalizedInput, { allowPrivateDomains: true });

  return domain?.toLowerCase() ?? null;
}
