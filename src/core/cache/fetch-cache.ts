import { LRUCache } from "lru-cache";

import type { FetchRequest, FetchResponse } from "../../sdk/contracts/fetch.js";

export interface FetchCacheReadPolicy {
  mode: "eligible" | "bypass";
  maxAgeMs: number;
}

export interface FetchCacheEntry {
  key: string;
  response: FetchResponse;
  storedAt: number;
}

export type FetchCacheReadResult =
  | {
      kind: "hit";
      entry: FetchCacheEntry;
      ageMs: number;
    }
  | {
      kind: "miss" | "stale" | "bypass";
      entry?: FetchCacheEntry;
      ageMs?: number;
    };

export interface FetchCacheOptions {
  maxEntries?: number;
  now?: () => number;
}

const DEFAULT_MAX_ENTRIES = 500;

export class FetchCache {
  private readonly cache: LRUCache<string, FetchCacheEntry>;
  private readonly now: () => number;

  constructor(options: FetchCacheOptions = {}) {
    this.cache = new LRUCache<string, FetchCacheEntry>({
      max: options.maxEntries ?? DEFAULT_MAX_ENTRIES,
    });
    this.now = options.now ?? Date.now;
  }

  read(
    request: FetchRequest,
    policy: FetchCacheReadPolicy,
  ): FetchCacheReadResult {
    if (policy.mode === "bypass") {
      return {
        kind: "bypass",
      };
    }

    const key = createFetchCacheKey(request);
    const entry = this.cache.get(key);

    if (!entry) {
      return {
        kind: "miss",
      };
    }

    const ageMs = Math.max(0, this.now() - entry.storedAt);

    if (ageMs > policy.maxAgeMs) {
      return {
        kind: "stale",
        entry: cloneEntry(entry),
        ageMs,
      };
    }

    return {
      kind: "hit",
      entry: cloneEntry(entry),
      ageMs,
    };
  }

  write(request: FetchRequest, response: FetchResponse): FetchCacheEntry {
    const entry: FetchCacheEntry = {
      key: createFetchCacheKey(request),
      response: cloneResponse(response),
      storedAt: this.now(),
    };

    this.cache.set(entry.key, entry);

    return cloneEntry(entry);
  }
}

export function createFetchCache(options?: FetchCacheOptions): FetchCache {
  return new FetchCache(options);
}

export function createFetchCacheKey(request: FetchRequest): string {
  return request.url;
}

function cloneEntry(entry: FetchCacheEntry): FetchCacheEntry {
  return {
    key: entry.key,
    response: cloneResponse(entry.response),
    storedAt: entry.storedAt,
  };
}

function cloneResponse(response: FetchResponse): FetchResponse {
  return structuredClone(response);
}
