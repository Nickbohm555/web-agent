import { type SafetyDecision } from "../../sdk/contracts/safety.js";
import { evaluateUrlPolicy } from "./url-policy.js";

export function evaluateSafetyPreflight(candidateUrl: string): SafetyDecision {
  return evaluateUrlPolicy(candidateUrl);
}

export function runSafetyPreflight(candidateUrl: string): SafetyDecision {
  return evaluateSafetyPreflight(candidateUrl);
}
