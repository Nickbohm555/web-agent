import { describe, expect, it } from "vitest";

import {
  evaluateIpAddressPolicy,
  isDisallowedIpAddress,
} from "../../core/network/ip-policy.js";
import { resolveAndClassifyTarget } from "../../core/network/resolve-and-classify.js";

describe("ssrf ip guardrails", () => {
  it("allows globally routable public addresses deterministically", () => {
    expect(evaluateIpAddressPolicy("8.8.8.8")).toEqual({
      outcome: "allow",
      metadata: {
        input: "8.8.8.8",
        normalized: "8.8.8.8",
        family: "ipv4",
        classification: "public",
      },
    });

    expect(evaluateIpAddressPolicy("2606:4700:4700::1111")).toEqual({
      outcome: "allow",
      metadata: {
        input: "2606:4700:4700::1111",
        normalized: "2606:4700:4700::1111",
        family: "ipv6",
        classification: "public",
      },
    });

    expect(evaluateIpAddressPolicy("::ffff:8.8.8.8")).toEqual({
      outcome: "allow",
      metadata: {
        input: "::ffff:8.8.8.8",
        normalized: "8.8.8.8",
        family: "ipv4",
        classification: "public",
      },
    });
  });

  it("denies private, loopback, link-local, multicast, and unique-local ranges with typed outcomes", () => {
    expect(evaluateIpAddressPolicy("127.0.0.1")).toEqual({
      outcome: "deny",
      reason: "SSRF_BLOCKED_IP",
      metadata: {
        input: "127.0.0.1",
        normalized: "127.0.0.1",
        family: "ipv4",
        classification: "loopback",
      },
    });

    expect(evaluateIpAddressPolicy("10.0.0.8")).toEqual({
      outcome: "deny",
      reason: "SSRF_BLOCKED_IP",
      metadata: {
        input: "10.0.0.8",
        normalized: "10.0.0.8",
        family: "ipv4",
        classification: "private",
      },
    });

    expect(evaluateIpAddressPolicy("169.254.169.254")).toEqual({
      outcome: "deny",
      reason: "SSRF_BLOCKED_IP",
      metadata: {
        input: "169.254.169.254",
        normalized: "169.254.169.254",
        family: "ipv4",
        classification: "link_local",
      },
    });

    expect(evaluateIpAddressPolicy("224.0.0.1")).toEqual({
      outcome: "deny",
      reason: "SSRF_BLOCKED_IP",
      metadata: {
        input: "224.0.0.1",
        normalized: "224.0.0.1",
        family: "ipv4",
        classification: "multicast",
      },
    });

    expect(evaluateIpAddressPolicy("::1")).toEqual({
      outcome: "deny",
      reason: "SSRF_BLOCKED_IP",
      metadata: {
        input: "::1",
        normalized: "::1",
        family: "ipv6",
        classification: "loopback",
      },
    });

    expect(evaluateIpAddressPolicy("fe80::1")).toEqual({
      outcome: "deny",
      reason: "SSRF_BLOCKED_IP",
      metadata: {
        input: "fe80::1",
        normalized: "fe80::1",
        family: "ipv6",
        classification: "link_local",
      },
    });

    expect(evaluateIpAddressPolicy("fc00::1")).toEqual({
      outcome: "deny",
      reason: "SSRF_BLOCKED_IP",
      metadata: {
        input: "fc00::1",
        normalized: "fc00::1",
        family: "ipv6",
        classification: "unique_local",
      },
    });
  });

  it("exposes a boolean helper for fast deny checks", () => {
    expect(isDisallowedIpAddress("10.1.2.3")).toBe(true);
    expect(isDisallowedIpAddress("8.8.4.4")).toBe(false);
  });

  it("allows hostnames when every resolved candidate is public and returns deterministic address ordering", async () => {
    const result = await resolveAndClassifyTarget(
      {
        url: "https://example.com/article",
        scheme: "https",
        hostname: "example.com",
        port: 443,
      },
      {
        lookupFn: async () => [
          { address: "2606:4700:4700::1111", family: 6 },
          { address: "8.8.8.8", family: 4 },
          { address: "8.8.8.8", family: 4 },
        ],
      },
    );

    expect(result).toEqual({
      outcome: "allow",
      decision: {
        stage: "network_preflight",
        outcome: "allow",
        target: {
          url: "https://example.com/article",
          scheme: "https",
          hostname: "example.com",
          port: 443,
        },
      },
      resolvedAddresses: [
        {
          address: "8.8.8.8",
          family: 4,
          normalized: "8.8.8.8",
          classification: "public",
          outcome: "allow",
        },
        {
          address: "2606:4700:4700::1111",
          family: 6,
          normalized: "2606:4700:4700::1111",
          classification: "public",
          outcome: "allow",
        },
      ],
    });
  });

  it("denies hostnames when any resolved candidate falls into a blocked SSRF range", async () => {
    const result = await resolveAndClassifyTarget(
      {
        url: "https://metadata.google.internal/computeMetadata/v1",
        scheme: "https",
        hostname: "metadata.google.internal",
        port: 443,
      },
      {
        lookupFn: async () => [
          { address: "8.8.8.8", family: 4 },
          { address: "169.254.169.254", family: 4 },
        ],
      },
    );

    expect(result).toEqual({
      outcome: "deny",
      decision: {
        stage: "network_preflight",
        outcome: "deny",
        reason: "SSRF_BLOCKED_IP",
        target: {
          url: "https://metadata.google.internal/computeMetadata/v1",
          scheme: "https",
          hostname: "metadata.google.internal",
          port: 443,
        },
      },
      resolvedAddresses: [
        {
          address: "169.254.169.254",
          family: 4,
          normalized: "169.254.169.254",
          classification: "link_local",
          outcome: "deny",
        },
        {
          address: "8.8.8.8",
          family: 4,
          normalized: "8.8.8.8",
          classification: "public",
          outcome: "allow",
        },
      ],
      resolverErrorCode: null,
    });
  });

  it("classifies direct ip hosts without requiring a dns lookup", async () => {
    const result = await resolveAndClassifyTarget({
      url: "https://127.0.0.1/admin",
      scheme: "https",
      hostname: "127.0.0.1",
      port: 443,
    });

    expect(result).toEqual({
      outcome: "deny",
      decision: {
        stage: "network_preflight",
        outcome: "deny",
        reason: "SSRF_BLOCKED_IP",
        target: {
          url: "https://127.0.0.1/admin",
          scheme: "https",
          hostname: "127.0.0.1",
          port: 443,
        },
      },
      resolvedAddresses: [
        {
          address: "127.0.0.1",
          family: 4,
          normalized: "127.0.0.1",
          classification: "loopback",
          outcome: "deny",
        },
      ],
      resolverErrorCode: null,
    });
  });

  it("returns an explicit deny outcome when dns resolution fails", async () => {
    const error = Object.assign(new Error("getaddrinfo ENOTFOUND"), {
      code: "ENOTFOUND",
    });
    const result = await resolveAndClassifyTarget(
      {
        url: "https://missing.example.com/report",
        scheme: "https",
        hostname: "missing.example.com",
        port: 443,
      },
      {
        lookupFn: async () => {
          throw error;
        },
      },
    );

    expect(result).toEqual({
      outcome: "deny",
      decision: {
        stage: "network_preflight",
        outcome: "deny",
        reason: "DNS_RESOLUTION_FAILED",
        target: {
          url: "https://missing.example.com/report",
          scheme: "https",
          hostname: "missing.example.com",
          port: 443,
        },
      },
      resolvedAddresses: [],
      resolverErrorCode: "ENOTFOUND",
    });
  });
});
