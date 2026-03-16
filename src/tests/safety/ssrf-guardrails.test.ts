import { describe, expect, it } from "vitest";

import {
  evaluateIpAddressPolicy,
  isDisallowedIpAddress,
} from "../../core/network/ip-policy.js";

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
});
