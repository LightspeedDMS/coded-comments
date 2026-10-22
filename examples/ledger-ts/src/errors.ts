export type LedgerErrorCode =
  | "INVALID_AMOUNT"
  | "INVALID_ACCOUNT"
  | "INVALID_CURRENCY"
  | "INVALID_KEY"
  | "ACCOUNT_EXISTS"
  | "ACCOUNT_NOT_FOUND"
  | "SAME_ACCOUNT"
  | "CURRENCY_MISMATCH"
  | "INSUFFICIENT_FUNDS"
  | "IDEMPOTENCY_CONFLICT"
  | "BALANCE_OVERFLOW"
  | "INVARIANT_VIOLATION"
  | "NOT_INITIALIZED"
  | "DATABASE_ERROR"
  | "MIGRATION_FAILED";

/** Every expected, user-facing failure. Anything else is a bug and should crash loudly. */
export class LedgerError extends Error {
  readonly code: LedgerErrorCode;

  constructor(code: LedgerErrorCode, message: string) {
    super(message);
    this.name = "LedgerError";
    this.code = code;
  }
}
