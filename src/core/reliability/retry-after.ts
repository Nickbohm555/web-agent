export function parseRetryAfter(
  value: string | null | undefined,
  now = Date.now(),
): number | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }

  const normalized = value.trim();

  if (normalized.length === 0) {
    return undefined;
  }

  const seconds = Number(normalized);

  if (Number.isFinite(seconds) && seconds >= 0) {
    return Math.round(seconds * 1_000);
  }

  const retryAt = Date.parse(normalized);

  if (Number.isNaN(retryAt)) {
    return undefined;
  }

  return Math.max(0, retryAt - now);
}
