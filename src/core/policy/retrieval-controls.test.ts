import { describe, expect, it } from "vitest";

import {
  resolveFetchControls,
  resolveSearchControls,
} from "./retrieval-controls.js";

describe("retrieval controls policy", () => {
  it("applies US and English defaults when locale controls are omitted", () => {
    expect(resolveSearchControls()).toEqual({
      maxResults: 10,
      timeoutMs: 5_000,
      country: "US",
      language: "en",
      freshness: "any",
      domainScope: {
        includeDomains: [],
        excludeDomains: [],
      },
    });
  });

  it("enforces maxResults and timeout bounds deterministically", () => {
    expect(() => resolveSearchControls({ maxResults: 0 })).toThrow();
    expect(() => resolveSearchControls({ maxResults: 21 })).toThrow();
    expect(() => resolveSearchControls({ timeoutMs: 249 })).toThrow();
    expect(() => resolveSearchControls({ timeoutMs: 30_001 })).toThrow();
    expect(() => resolveFetchControls({ timeoutMs: 249 })).toThrow();
    expect(() => resolveFetchControls({ timeoutMs: 30_001 })).toThrow();
    expect(() => resolveFetchControls({ maxAgeMs: -1 })).toThrow();
  });

  it("represents fresh fetch semantics explicitly in normalized controls", () => {
    expect(resolveFetchControls({ fresh: true })).toEqual({
      timeoutMs: 5_000,
      maxAgeMs: 5 * 60 * 1_000,
      fresh: true,
    });

    expect(resolveFetchControls()).toEqual({
      timeoutMs: 5_000,
      maxAgeMs: 5 * 60 * 1_000,
      fresh: false,
    });
  });

  it("canonicalizes, dedupes, and stabilizes include/exclude domain scope with exclude precedence", () => {
    const resolved = resolveSearchControls({
      includeDomains: [
        "HTTPS://Blog.Example.com/path",
        "example.com",
        "docs.github.com",
        "invalid input",
      ],
      excludeDomains: [
        "https://EXAMPLE.com",
        "github.com",
        "github.com/docs",
      ],
    });

    const equivalent = resolveSearchControls({
      includeDomains: ["docs.github.com", "example.com", "blog.example.com"],
      excludeDomains: ["github.com", "example.com"],
    });

    expect(resolved.domainScope).toEqual({
      includeDomains: [],
      excludeDomains: ["example.com", "github.com"],
    });
    expect(equivalent.domainScope).toEqual(resolved.domainScope);
  });
});
