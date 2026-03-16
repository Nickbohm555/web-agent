import * as ipaddr from "ipaddr.js";

export type IpAddressFamily = "ipv4" | "ipv6";

export type IpAddressSafetyClass =
  | "public"
  | "loopback"
  | "private"
  | "link_local"
  | "unique_local"
  | "multicast"
  | "unspecified"
  | "reserved"
  | "carrier_grade_nat"
  | "broadcast"
  | "as112"
  | "benchmarking"
  | "translation"
  | "amt";

export interface IpAddressPolicyMetadata {
  input: string;
  normalized: string;
  family: IpAddressFamily;
  classification: IpAddressSafetyClass;
}

export interface AllowedIpAddressPolicyDecision {
  outcome: "allow";
  metadata: IpAddressPolicyMetadata;
}

export interface DeniedIpAddressPolicyDecision {
  outcome: "deny";
  reason: "SSRF_BLOCKED_IP";
  metadata: IpAddressPolicyMetadata;
}

export type IpAddressPolicyDecision =
  | AllowedIpAddressPolicyDecision
  | DeniedIpAddressPolicyDecision;

export function evaluateIpAddressPolicy(address: string): IpAddressPolicyDecision {
  const parsedAddress = ipaddr.parse(address);
  const normalizedAddress = normalizeParsedAddress(parsedAddress);
  const family = inferFamily(parsedAddress);
  const classification = classifyParsedAddress(parsedAddress);
  const metadata: IpAddressPolicyMetadata = {
    input: address,
    normalized: normalizedAddress,
    family,
    classification,
  };

  if (classification === "public") {
    return {
      outcome: "allow",
      metadata,
    };
  }

  return {
    outcome: "deny",
    reason: "SSRF_BLOCKED_IP",
    metadata,
  };
}

export function isDisallowedIpAddress(address: string): boolean {
  return evaluateIpAddressPolicy(address).outcome === "deny";
}

function inferFamily(parsedAddress: ipaddr.IPv4 | ipaddr.IPv6): IpAddressFamily {
  if (parsedAddress.kind() === "ipv6") {
    const ipv6Address = parsedAddress as ipaddr.IPv6;

    if (isIpv4MappedIpv6Address(ipv6Address)) {
      return "ipv4";
    }
  }

  return parsedAddress.kind();
}

function normalizeParsedAddress(parsedAddress: ipaddr.IPv4 | ipaddr.IPv6): string {
  if (parsedAddress.kind() === "ipv6") {
    const ipv6Address = parsedAddress as ipaddr.IPv6;

    if (isIpv4MappedIpv6Address(ipv6Address)) {
      return ipv6Address.toIPv4Address().toString();
    }
  }

  return parsedAddress.toString();
}

function classifyParsedAddress(
  parsedAddress: ipaddr.IPv4 | ipaddr.IPv6,
): IpAddressSafetyClass {
  if (parsedAddress.kind() === "ipv6") {
    const ipv6Address = parsedAddress as ipaddr.IPv6;

    if (isIpv4MappedIpv6Address(ipv6Address)) {
      return classifyIpv4Range(ipv6Address.toIPv4Address().range());
    }

    return classifyIpv6Range(ipv6Address.range());
  }

  return classifyIpv4Range((parsedAddress as ipaddr.IPv4).range());
}

function classifyIpv4Range(range: ReturnType<ipaddr.IPv4["range"]>): IpAddressSafetyClass {
  switch (range) {
    case "unicast":
      return "public";
    case "loopback":
      return "loopback";
    case "private":
      return "private";
    case "linkLocal":
      return "link_local";
    case "multicast":
      return "multicast";
    case "unspecified":
      return "unspecified";
    case "carrierGradeNat":
      return "carrier_grade_nat";
    case "broadcast":
      return "broadcast";
    case "reserved":
      return "reserved";
    case "as112":
      return "as112";
    case "benchmarking":
      return "benchmarking";
    case "amt":
      return "amt";
    default:
      return "reserved";
  }
}

function classifyIpv6Range(range: ReturnType<ipaddr.IPv6["range"]>): IpAddressSafetyClass {
  switch (range) {
    case "unicast":
      return "public";
    case "loopback":
      return "loopback";
    case "uniqueLocal":
      return "unique_local";
    case "linkLocal":
      return "link_local";
    case "multicast":
      return "multicast";
    case "unspecified":
      return "unspecified";
    case "ipv4Mapped":
    case "rfc6145":
    case "rfc6052":
    case "6to4":
    case "teredo":
      return "translation";
    case "reserved":
      return "reserved";
    case "benchmarking":
      return "benchmarking";
    case "amt":
      return "amt";
    case "as112v6":
      return "as112";
    case "orchid2":
    case "droneRemoteIdProtocolEntityTags":
      return "reserved";
    default:
      return "reserved";
  }
}

function isIpv4MappedIpv6Address(parsedAddress: ipaddr.IPv6): boolean {
  return parsedAddress.isIPv4MappedAddress();
}
