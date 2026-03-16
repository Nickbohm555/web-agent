import {
  SafetyAllowDecisionSchema,
  SafetyDenyDecisionSchema,
  type SafetyAllowDecision,
  type SafetyDenyDecision,
} from "../../sdk/contracts/safety.js";
import { evaluateUrlPolicy } from "../policy/url-policy.js";
import {
  resolveAndClassifyTarget,
  type ResolveAndClassifyOptions,
} from "./resolve-and-classify.js";

const REDIRECT_PREFLIGHT_STAGE = "redirect_preflight";

export interface ValidateRedirectTargetOptions extends ResolveAndClassifyOptions {}

export interface RedirectTargetAllowResult {
  outcome: "allow";
  redirectUrl: string;
  decision: SafetyAllowDecision;
}

export interface RedirectTargetDenyResult {
  outcome: "deny";
  redirectUrl: string;
  decision: SafetyDenyDecision;
  resolverErrorCode: string | null;
}

export type RedirectTargetValidationResult =
  | RedirectTargetAllowResult
  | RedirectTargetDenyResult;

export async function validateRedirectTarget(
  currentUrl: string,
  location: string,
  options: ValidateRedirectTargetOptions = {},
): Promise<RedirectTargetValidationResult> {
  const redirectUrl = new URL(location, currentUrl).toString();
  const urlDecision = evaluateUrlPolicy(redirectUrl);

  if (urlDecision.outcome === "deny") {
    return {
      outcome: "deny",
      redirectUrl: urlDecision.target.url,
      decision: SafetyDenyDecisionSchema.parse({
        stage: REDIRECT_PREFLIGHT_STAGE,
        outcome: "deny",
        reason: urlDecision.reason,
        target: urlDecision.target,
      }),
      resolverErrorCode: null,
    };
  }

  const networkDecision = await resolveAndClassifyTarget(urlDecision.target, options);

  if (networkDecision.outcome === "deny") {
    return {
      outcome: "deny",
      redirectUrl: networkDecision.decision.target.url,
      decision: SafetyDenyDecisionSchema.parse({
        stage: REDIRECT_PREFLIGHT_STAGE,
        outcome: "deny",
        reason: networkDecision.decision.reason,
        target: networkDecision.decision.target,
      }),
      resolverErrorCode: networkDecision.resolverErrorCode,
    };
  }

  return {
    outcome: "allow",
    redirectUrl: urlDecision.target.url,
    decision: SafetyAllowDecisionSchema.parse({
      stage: REDIRECT_PREFLIGHT_STAGE,
      outcome: "allow",
      target: urlDecision.target,
    }),
  };
}

export const revalidateRedirectTarget = validateRedirectTarget;
