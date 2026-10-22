import assert from "node:assert/strict";
import type { DatabaseSync } from "node:sqlite";
import { openDatabase } from "../src/db.js";
import { LedgerError, type LedgerErrorCode } from "../src/errors.js";
import { Ledger } from "../src/ledger.js";
import { migrate } from "../src/migrations.js";

export interface TestLedger {
  ledger: Ledger;
  db: DatabaseSync;
}

/** A real, fully migrated SQLite database held in memory (no mocks). */
export function newLedger(): TestLedger {
  const db = openDatabase(":memory:");
  migrate(db);
  return { ledger: new Ledger(db), db };
}

/** Ledger with `equity` plus alice and bob (all USD); alice holds 100.00 and bob holds 0.00. */
export function seededLedger(): TestLedger {
  const t = newLedger();
  t.ledger.createAccount("equity", "USD");
  t.ledger.createAccount("alice", "USD");
  t.ledger.createAccount("bob", "USD");
  t.ledger.transfer("equity", "alice", "100.00", "seed-alice", "seed");
  return t;
}

export function assertLedgerError(fn: () => unknown, code: LedgerErrorCode, messagePart?: RegExp): void {
  assert.throws(fn, (e: unknown) => {
    assert.ok(e instanceof LedgerError, `expected LedgerError, got ${String(e)}`);
    assert.equal(e.code, code, `unexpected code, message was: ${e.message}`);
    if (messagePart !== undefined) assert.match(e.message, messagePart);
    return true;
  });
}

export function count(db: DatabaseSync, table: "accounts" | "transfers" | "entries"): number {
  const row = db.prepare(`SELECT COUNT(*) AS n FROM ${table}`).get() as { n: number };
  return row.n;
}
