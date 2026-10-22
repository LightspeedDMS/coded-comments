import { LedgerError } from "./errors.js";

/** Largest supported amount/balance in minor units: Number.MAX_SAFE_INTEGER, so sums stay exact. */
export const MAX_AMOUNT_MINOR = Number.MAX_SAFE_INTEGER;

const DECIMAL = /^(-)?(\d+)(?:\.(\d{1,2}))?$/;

/**
 * Parses a decimal string such as "12.34" into integer minor units (1234).
 * Pure string/BigInt arithmetic: no floating point is ever involved.
 * Returns a strictly positive amount; anything else throws INVALID_AMOUNT.
 */
export function parseAmount(input: string): number {
  const m = DECIMAL.exec(input);
  if (m === null) {
    throw new LedgerError(
      "INVALID_AMOUNT",
      `invalid amount ${JSON.stringify(input)}: expected a decimal like "12.34" with at most 2 decimal places`,
    );
  }
  const [, sign, whole = "0", fraction = ""] = m;
  if (sign !== undefined) {
    throw new LedgerError("INVALID_AMOUNT", `invalid amount ${JSON.stringify(input)}: negative amounts are not allowed`);
  }
  const minor = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
  if (minor === 0n) {
    throw new LedgerError("INVALID_AMOUNT", `invalid amount ${JSON.stringify(input)}: amount must be positive`);
  }
  if (minor > BigInt(MAX_AMOUNT_MINOR)) {
    throw new LedgerError("INVALID_AMOUNT", `invalid amount ${JSON.stringify(input)}: exceeds the maximum of ${formatAmount(MAX_AMOUNT_MINOR)}`);
  }
  return Number(minor);
}

/** Renders integer minor units as a 2-decimal string ("-12.34"). */
export function formatAmount(minor: number): string {
  if (!Number.isSafeInteger(minor)) {
    throw new RangeError(`minor units must be a safe integer, got ${minor}`);
  }
  const abs = Math.abs(minor);
  const whole = Math.floor(abs / 100);
  const cents = String(abs % 100).padStart(2, "0");
  return `${minor < 0 ? "-" : ""}${whole}.${cents}`;
}
