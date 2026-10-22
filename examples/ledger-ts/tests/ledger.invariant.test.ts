import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { assertLedgerError, newLedger, seededLedger, type TestLedger } from "./helpers.js";

function accountId(t: TestLedger, name: string): number {
  return (t.db.prepare("SELECT id FROM accounts WHERE name = ?").get(name) as { id: number }).id;
}

function rawTransfer(t: TestLedger, key: string): number {
  const row = t.db.prepare("INSERT INTO transfers (idempotency_key) VALUES (?) RETURNING id").get(key) as { id: number };
  return row.id;
}

function rawEntry(t: TestLedger, transferId: number, account: string, amount: number): void {
  t.db
    .prepare("INSERT INTO entries (transfer_id, account_id, amount_minor) VALUES (?, ?, ?)")
    .run(transferId, accountId(t, account), amount);
}

describe("Ledger.checkInvariant", () => {
  it("holds on an empty ledger", () => {
    newLedger().ledger.checkInvariant();
  });

  it("holds after seeding and transfers", () => {
    const t = seededLedger();
    t.ledger.transfer("alice", "bob", "12.34", "k1");
    t.ledger.transfer("bob", "alice", "2.00", "k2");
    t.ledger.checkInvariant();
  });

  it("holds after rejected transfers", () => {
    const t = seededLedger();
    assert.throws(() => t.ledger.transfer("bob", "alice", "999.00", "k"));
    t.ledger.checkInvariant();
  });

  it("detects an unbalanced transfer", () => {
    const t = seededLedger();
    t.db.exec("DROP TRIGGER entries_pair_check");
    const id = rawTransfer(t, "corrupt");
    rawEntry(t, id, "alice", -500);
    rawEntry(t, id, "bob", 300);
    assertLedgerError(() => t.ledger.checkInvariant(), "INVARIANT_VIOLATION", /sum/i);
  });

  it("detects a transfer left with a single entry", () => {
    const t = seededLedger();
    t.db.exec("DROP TRIGGER entries_pair_check");
    const id = rawTransfer(t, "corrupt");
    rawEntry(t, id, "equity", 100);
    assertLedgerError(() => t.ledger.checkInvariant(), "INVARIANT_VIOLATION");
  });

  it("detects a transfer with more than two entries even when they sum to zero", () => {
    const t = seededLedger();
    t.ledger.createAccount("carol", "USD");
    t.db.exec("DROP TRIGGER entries_pair_check");
    const id = rawTransfer(t, "corrupt");
    rawEntry(t, id, "alice", -500);
    rawEntry(t, id, "bob", 300);
    rawEntry(t, id, "carol", 200);
    assertLedgerError(() => t.ledger.checkInvariant(), "INVARIANT_VIOLATION", /two entries/i);
  });

  it("detects a negative balance on a non-equity account", () => {
    const t = seededLedger();
    t.db.exec("DROP TRIGGER entries_no_overdraft");
    const id = rawTransfer(t, "corrupt");
    rawEntry(t, id, "bob", -100);
    rawEntry(t, id, "alice", 100);
    assertLedgerError(() => t.ledger.checkInvariant(), "INVARIANT_VIOLATION", /bob/);
  });

  it("detects entries whose total is not zero", () => {
    const t = seededLedger();
    t.db.exec("DROP TRIGGER entries_pair_check");
    const id = rawTransfer(t, "corrupt");
    rawEntry(t, id, "equity", -100);
    rawEntry(t, id, "alice", 100);
    t.db.exec("DROP TRIGGER entries_no_update");
    t.db.exec("UPDATE entries SET amount_minor = amount_minor + 1 WHERE transfer_id = " + id + " AND amount_minor > 0");
    assertLedgerError(() => t.ledger.checkInvariant(), "INVARIANT_VIOLATION");
  });
});
