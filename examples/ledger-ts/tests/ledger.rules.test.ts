import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { assertLedgerError, count, newLedger, seededLedger } from "./helpers.js";

function snapshot(t: ReturnType<typeof seededLedger>): [number, number, number, number] {
  return [count(t.db, "transfers"), count(t.db, "entries"), t.ledger.balance("alice"), t.ledger.balance("bob")];
}

describe("Ledger.transfer rules", () => {
  it("rejects transferring an account to itself", () => {
    const t = seededLedger();
    const before = snapshot(t);
    assertLedgerError(() => t.ledger.transfer("alice", "alice", "1.00", "k"), "SAME_ACCOUNT");
    assert.deepEqual(snapshot(t), before);
  });

  it("rejects equity to equity as well", () => {
    const t = seededLedger();
    assertLedgerError(() => t.ledger.transfer("equity", "equity", "1.00", "k"), "SAME_ACCOUNT");
  });

  it("rejects an unknown source or destination, naming it", () => {
    const t = seededLedger();
    const before = snapshot(t);
    assertLedgerError(() => t.ledger.transfer("ghost", "bob", "1.00", "k1"), "ACCOUNT_NOT_FOUND", /ghost/);
    assertLedgerError(() => t.ledger.transfer("alice", "phantom", "1.00", "k2"), "ACCOUNT_NOT_FOUND", /phantom/);
    assert.deepEqual(snapshot(t), before);
  });

  it("rejects a currency mismatch in either direction, even for equity", () => {
    const t = seededLedger();
    t.ledger.createAccount("carol", "EUR");
    const before = snapshot(t);
    assertLedgerError(() => t.ledger.transfer("alice", "carol", "1.00", "k1"), "CURRENCY_MISMATCH", /USD.*EUR|EUR.*USD/);
    assertLedgerError(() => t.ledger.transfer("carol", "alice", "1.00", "k2"), "CURRENCY_MISMATCH");
    assertLedgerError(() => t.ledger.transfer("equity", "carol", "1.00", "k3"), "CURRENCY_MISMATCH");
    assert.deepEqual(snapshot(t), before);
    assert.equal(t.ledger.balance("carol"), 0);
  });

  it("reports a currency mismatch rather than insufficient funds when both apply", () => {
    const t = seededLedger();
    t.ledger.createAccount("carol", "EUR");
    assertLedgerError(() => t.ledger.transfer("carol", "alice", "1.00", "k"), "CURRENCY_MISMATCH");
  });

  it("rejects insufficient funds, by a single cent", () => {
    const t = seededLedger();
    const before = snapshot(t);
    assertLedgerError(() => t.ledger.transfer("alice", "bob", "100.01", "k"), "INSUFFICIENT_FUNDS", /alice/);
    assertLedgerError(() => t.ledger.transfer("bob", "alice", "0.01", "k2"), "INSUFFICIENT_FUNDS");
    assert.deepEqual(snapshot(t), before);
  });

  it("allows spending exactly the whole balance, leaving zero", () => {
    const t = seededLedger();
    t.ledger.transfer("alice", "bob", "100.00", "k");
    assert.equal(t.ledger.balance("alice"), 0);
    assert.equal(t.ledger.balance("bob"), 10000);
    assertLedgerError(() => t.ledger.transfer("alice", "bob", "0.01", "k2"), "INSUFFICIENT_FUNDS");
  });

  it("lets only the equity account go negative", () => {
    const t = newLedger();
    t.ledger.createAccount("equity", "USD");
    t.ledger.createAccount("alice", "USD");
    t.ledger.transfer("equity", "alice", "1000000.00", "k1");
    assert.equal(t.ledger.balance("equity"), -100000000);
    assertLedgerError(() => t.ledger.transfer("alice", "equity", "1000000.01", "k2"), "INSUFFICIENT_FUNDS");
    t.ledger.transfer("alice", "equity", "1000000.00", "k3");
    assert.equal(t.ledger.balance("equity"), 0);
  });

  it("does not treat names that merely resemble equity as special", () => {
    const t = seededLedger();
    t.ledger.createAccount("Equity", "USD");
    t.ledger.createAccount("equity2", "USD");
    assertLedgerError(() => t.ledger.transfer("Equity", "bob", "1.00", "k1"), "INSUFFICIENT_FUNDS");
    assertLedgerError(() => t.ledger.transfer("equity2", "bob", "1.00", "k2"), "INSUFFICIENT_FUNDS");
  });

  it("rejects invalid amounts without touching the database", () => {
    const t = seededLedger();
    const before = snapshot(t);
    for (const bad of ["", "abc", "1e3", "NaN", "-1.00", "0", "1.001", "0.00"]) {
      assertLedgerError(() => t.ledger.transfer("alice", "bob", bad, "k"), "INVALID_AMOUNT");
    }
    assert.deepEqual(snapshot(t), before);
  });

  it("rejects an empty or over-long idempotency key", () => {
    const t = seededLedger();
    const before = snapshot(t);
    assertLedgerError(() => t.ledger.transfer("alice", "bob", "1.00", ""), "INVALID_KEY");
    assertLedgerError(() => t.ledger.transfer("alice", "bob", "1.00", "k".repeat(256)), "INVALID_KEY");
    assert.deepEqual(snapshot(t), before);
    t.ledger.transfer("alice", "bob", "1.00", "k".repeat(255));
  });

  it("refuses a transfer that would push a balance past the exact-integer limit", () => {
    const t = newLedger();
    t.ledger.createAccount("equity", "USD");
    t.ledger.createAccount("whale", "USD");
    t.ledger.transfer("equity", "whale", "90071992547409.91", "k1");
    const before = [count(t.db, "transfers"), t.ledger.balance("whale"), t.ledger.balance("equity")];
    assertLedgerError(() => t.ledger.transfer("equity", "whale", "0.01", "k2"), "BALANCE_OVERFLOW");
    assert.deepEqual([count(t.db, "transfers"), t.ledger.balance("whale"), t.ledger.balance("equity")], before);
  });
});
