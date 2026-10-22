import { existsSync } from "node:fs";
import type { DatabaseSync } from "node:sqlite";
import { inTransaction, openDatabase } from "./db.js";
import { LedgerError } from "./errors.js";
import { migrate, pendingMigrations } from "./migrations.js";
import { MAX_AMOUNT_MINOR, formatAmount, parseAmount } from "./money.js";

//^ coupled mirrors the 'equity' literal in migrations/0001_init.sql (entries_no_overdraft) => change both
export const EQUITY_ACCOUNT = "equity";

const MAX_NAME_LENGTH = 128;
const MAX_KEY_LENGTH = 255;
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/;
const CURRENCY = /^[A-Z]{3}$/;

export interface Account {
  id: number;
  name: string;
  currency: string;
  createdAt: string;
}

export interface TransferRecord {
  id: number;
  idempotencyKey: string;
  from: string;
  to: string;
  amountMinor: number;
  currency: string;
  description: string | null;
  createdAt: string;
  /** true when this call returned an already-existing transfer instead of creating one */
  replayed: boolean;
}

export interface HistoryEntry {
  transferId: number;
  createdAt: string;
  /** signed: negative when money left this account */
  amountMinor: number;
  currency: string;
  counterparty: string;
  description: string | null;
  idempotencyKey: string;
}

interface AccountRow {
  id: number;
  name: string;
  currency: string;
  created_at: string;
}

function toAccount(r: AccountRow): Account {
  return { id: r.id, name: r.name, currency: r.currency, createdAt: r.created_at };
}

function validateAccountName(name: string): void {
  if (name.length === 0 || name.length > MAX_NAME_LENGTH || name.trim() !== name || CONTROL_CHARS.test(name)) {
    throw new LedgerError(
      "INVALID_ACCOUNT",
      `invalid account name ${JSON.stringify(name)}: 1-${MAX_NAME_LENGTH} characters, no leading/trailing whitespace, no control characters`,
    );
  }
}

function validateIdempotencyKey(key: string): void {
  if (key.length === 0 || key.length > MAX_KEY_LENGTH) {
    throw new LedgerError("INVALID_KEY", `invalid idempotency key: expected 1-${MAX_KEY_LENGTH} characters`);
  }
}

export class Ledger {
  private readonly db: DatabaseSync;

  constructor(db: DatabaseSync) {
    this.db = db;
  }

  /** Creates the database file if needed and applies pending migrations. Returns the migrations applied. */
  static init(path: string): string[] {
    const db = openDatabase(path);
    try {
      return migrate(db);
    } finally {
      db.close();
    }
  }

  /** Opens an existing, fully migrated database. Never creates a file. */
  static open(path: string): Ledger {
    const notReady = new LedgerError("NOT_INITIALIZED", `database ${JSON.stringify(path)} is missing or not up to date; run "ledger init"`);
    if (!existsSync(path)) throw notReady;
    const db = openDatabase(path);
    try {
      if (pendingMigrations(db).length > 0) throw notReady;
    } catch (e) {
      db.close();
      throw e;
    }
    return new Ledger(db);
  }

  close(): void {
    this.db.close();
  }

  createAccount(name: string, currency: string): Account {
    validateAccountName(name);
    if (!CURRENCY.test(currency)) {
      throw new LedgerError("INVALID_CURRENCY", `invalid currency ${JSON.stringify(currency)}: expected 3 uppercase letters such as "USD"`);
    }
    return inTransaction(this.db, () => {
      if (this.findAccount(name) !== undefined) {
        throw new LedgerError("ACCOUNT_EXISTS", `account ${JSON.stringify(name)} already exists`);
      }
      //^ why double cast: RETURNING always yields a row, but node:sqlite types get() as Record|undefined
      const row = this.db
        .prepare("INSERT INTO accounts (name, currency) VALUES (?, ?) RETURNING id, name, currency, created_at")
        .get(name, currency) as unknown as AccountRow;
      return toAccount(row);
    });
  }

  /** Sum of the account's entries, in minor units. */
  balance(name: string): number {
    return this.balanceOf(this.getAccount(name).id);
  }

  /**
   * Verifies, straight from the stored entries, that: all entries sum to 0; every transfer has exactly two
   * entries that cancel; no account other than equity is overdrawn. Throws INVARIANT_VIOLATION on the first failure.
   */
  checkInvariant(): void {
    const total = (this.db.prepare("SELECT COALESCE(SUM(amount_minor), 0) AS total FROM entries").get() as { total: number }).total;
    if (total !== 0) {
      throw new LedgerError("INVARIANT_VIOLATION", `sum of all entries is ${total}, expected 0`);
    }
    const badTransfer = this.db
      .prepare(
        `SELECT t.id AS id, COUNT(e.id) AS n, COALESCE(SUM(e.amount_minor), 0) AS total
           FROM transfers t LEFT JOIN entries e ON e.transfer_id = t.id
          GROUP BY t.id HAVING n <> 2 OR total <> 0
          ORDER BY t.id LIMIT 1`,
      )
      .get() as { id: number; n: number; total: number } | undefined;
    if (badTransfer !== undefined) {
      const why = badTransfer.n !== 2 ? `has ${badTransfer.n} entries; expected exactly two entries` : `has entries that sum to ${badTransfer.total}, expected 0`;
      throw new LedgerError("INVARIANT_VIOLATION", `transfer #${badTransfer.id} ${why}`);
    }
    const overdrawn = this.db
      .prepare(
        `SELECT a.name AS name, SUM(e.amount_minor) AS balance
           FROM accounts a JOIN entries e ON e.account_id = a.id
          WHERE a.name <> ?
          GROUP BY a.id HAVING balance < 0
          ORDER BY a.id LIMIT 1`,
      )
      .get(EQUITY_ACCOUNT) as { name: string; balance: number } | undefined;
    if (overdrawn !== undefined) {
      throw new LedgerError("INVARIANT_VIOLATION", `account ${JSON.stringify(overdrawn.name)} is overdrawn: balance ${overdrawn.balance}`);
    }
  }

  transfer(from: string, to: string, amount: string, idempotencyKey: string, description?: string): TransferRecord {
    const amountMinor = parseAmount(amount);
    validateIdempotencyKey(idempotencyKey);
    if (from === to) {
      throw new LedgerError("SAME_ACCOUNT", `cannot transfer from ${JSON.stringify(from)} to itself`);
    }
    return inTransaction(this.db, () => {
      const existing = this.findTransferByKey(idempotencyKey);
      if (existing !== undefined) {
        const sameRequest =
          existing.from === from &&
          existing.to === to &&
          existing.amountMinor === amountMinor &&
          existing.description === (description ?? null);
        if (!sameRequest) {
          throw new LedgerError(
            "IDEMPOTENCY_CONFLICT",
            `idempotency key ${JSON.stringify(idempotencyKey)} was already used for a different transfer (#${existing.id}: ${existing.from} -> ${existing.to}, ${formatAmount(existing.amountMinor)} ${existing.currency})`,
          );
        }
        return { ...existing, replayed: true };
      }
      const source = this.getAccount(from);
      const destination = this.getAccount(to);
      this.assertCanTransfer(source, destination, amountMinor);
      const t = this.db
        .prepare("INSERT INTO transfers (idempotency_key, description) VALUES (?, ?) RETURNING id, created_at")
        .get(idempotencyKey, description ?? null) as { id: number; created_at: string };
      const insertEntry = this.db.prepare("INSERT INTO entries (transfer_id, account_id, amount_minor) VALUES (?, ?, ?)");
      insertEntry.run(t.id, source.id, -amountMinor);
      insertEntry.run(t.id, destination.id, amountMinor);
      return {
        id: t.id,
        idempotencyKey,
        from,
        to,
        amountMinor,
        currency: source.currency,
        description: description ?? null,
        createdAt: t.created_at,
        replayed: false,
      };
    });
  }

  /** The account's entries, oldest first. */
  history(name: string): HistoryEntry[] {
    const account = this.getAccount(name);
    const rows = this.db
      .prepare(
        `SELECT e.transfer_id AS transfer_id, t.created_at AS created_at, e.amount_minor AS amount_minor,
                a.currency AS currency, cp.name AS counterparty, t.description AS description,
                t.idempotency_key AS idempotency_key
           FROM entries e
           JOIN transfers t ON t.id = e.transfer_id
           JOIN accounts a ON a.id = e.account_id
           JOIN entries ce ON ce.transfer_id = e.transfer_id AND ce.id <> e.id
           JOIN accounts cp ON cp.id = ce.account_id
          WHERE e.account_id = ?
          ORDER BY e.id`,
      )
      .all(account.id) as {
      transfer_id: number;
      created_at: string;
      amount_minor: number;
      currency: string;
      counterparty: string;
      description: string | null;
      idempotency_key: string;
    }[];
    return rows.map((r) => ({
      transferId: r.transfer_id,
      createdAt: r.created_at,
      amountMinor: r.amount_minor,
      currency: r.currency,
      counterparty: r.counterparty,
      description: r.description,
      idempotencyKey: r.idempotency_key,
    }));
  }

  private findTransferByKey(idempotencyKey: string): TransferRecord | undefined {
    const r = this.db
      .prepare(
        `SELECT t.id AS id, t.created_at AS created_at, t.description AS description,
                src.name AS from_name, dst.name AS to_name, dst.currency AS currency,
                credit.amount_minor AS amount_minor
           FROM transfers t
           JOIN entries debit ON debit.transfer_id = t.id AND debit.amount_minor < 0
           JOIN accounts src ON src.id = debit.account_id
           JOIN entries credit ON credit.transfer_id = t.id AND credit.amount_minor > 0
           JOIN accounts dst ON dst.id = credit.account_id
          WHERE t.idempotency_key = ?`,
      )
      .get(idempotencyKey) as
      | { id: number; created_at: string; description: string | null; from_name: string; to_name: string; currency: string; amount_minor: number }
      | undefined;
    if (r === undefined) return undefined;
    return {
      id: r.id,
      idempotencyKey,
      from: r.from_name,
      to: r.to_name,
      amountMinor: r.amount_minor,
      currency: r.currency,
      description: r.description,
      createdAt: r.created_at,
      replayed: false,
    };
  }

  /** Must run inside the write transaction: balances are read and then relied on by the INSERTs that follow. */
  private assertCanTransfer(source: Account, destination: Account, amountMinor: number): void {
    if (source.currency !== destination.currency) {
      throw new LedgerError(
        "CURRENCY_MISMATCH",
        `cannot transfer between ${JSON.stringify(source.name)} (${source.currency}) and ${JSON.stringify(destination.name)} (${destination.currency})`,
      );
    }
    const sourceBalance = this.balanceOf(source.id);
    if (source.name !== EQUITY_ACCOUNT && sourceBalance < amountMinor) {
      throw new LedgerError(
        "INSUFFICIENT_FUNDS",
        `insufficient funds: ${JSON.stringify(source.name)} has ${formatAmount(sourceBalance)} ${source.currency}, needs ${formatAmount(amountMinor)}`,
      );
    }
    const destinationBalance = this.balanceOf(destination.id);
    if (destinationBalance + amountMinor > MAX_AMOUNT_MINOR || sourceBalance - amountMinor < -MAX_AMOUNT_MINOR) {
      throw new LedgerError("BALANCE_OVERFLOW", `transfer would push a balance beyond ${formatAmount(MAX_AMOUNT_MINOR)} ${source.currency}`);
    }
  }

  private findAccount(name: string): Account | undefined {
    const row = this.db
      .prepare("SELECT id, name, currency, created_at FROM accounts WHERE name = ?")
      .get(name) as AccountRow | undefined;
    return row === undefined ? undefined : toAccount(row);
  }

  /** The named account, or ACCOUNT_NOT_FOUND. */
  getAccount(name: string): Account {
    const account = this.findAccount(name);
    if (account === undefined) {
      throw new LedgerError("ACCOUNT_NOT_FOUND", `account ${JSON.stringify(name)} does not exist`);
    }
    return account;
  }

  private balanceOf(accountId: number): number {
    const row = this.db
      .prepare("SELECT COALESCE(SUM(amount_minor), 0) AS balance FROM entries WHERE account_id = ?")
      .get(accountId) as { balance: number };
    return row.balance;
  }
}
