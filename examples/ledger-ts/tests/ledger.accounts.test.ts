import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { assertLedgerError, count, newLedger } from "./helpers.js";

describe("Ledger.createAccount", () => {
  it("creates an account and returns it", () => {
    const { ledger } = newLedger();
    const a = ledger.createAccount("alice", "USD");
    assert.equal(a.name, "alice");
    assert.equal(a.currency, "USD");
    assert.ok(Number.isInteger(a.id) && a.id > 0);
    assert.match(a.createdAt, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
  });

  it("gives every account a distinct id and starts balances at zero", () => {
    const { ledger } = newLedger();
    const a = ledger.createAccount("alice", "USD");
    const b = ledger.createAccount("bob", "EUR");
    assert.notEqual(a.id, b.id);
    assert.equal(ledger.balance("alice"), 0);
    assert.equal(ledger.balance("bob"), 0);
  });

  it("rejects a duplicate name, even with a different currency", () => {
    const { ledger, db } = newLedger();
    ledger.createAccount("alice", "USD");
    assertLedgerError(() => ledger.createAccount("alice", "USD"), "ACCOUNT_EXISTS", /alice/);
    assertLedgerError(() => ledger.createAccount("alice", "EUR"), "ACCOUNT_EXISTS");
    assert.equal(count(db, "accounts"), 1);
  });

  it("treats names as case-sensitive", () => {
    const { ledger } = newLedger();
    ledger.createAccount("alice", "USD");
    ledger.createAccount("Alice", "USD");
    assert.equal(ledger.balance("Alice"), 0);
  });

  it("rejects anything but three uppercase ASCII letters as a currency", () => {
    const { ledger, db } = newLedger();
    for (const c of ["", "US", "USDD", "usd", "Usd", "U$D", "US1", "123", " USD", "USD ", "ÜSD", "US\nD"]) {
      assertLedgerError(() => ledger.createAccount("acct", c), "INVALID_CURRENCY");
    }
    assert.equal(count(db, "accounts"), 0);
  });

  it("rejects empty, over-long, padded and control-character names", () => {
    const { ledger, db } = newLedger();
    for (const n of ["", " ", " alice", "alice ", "a".repeat(129), "al\nice", "al\tice", "al\u0000ice"]) {
      assertLedgerError(() => ledger.createAccount(n, "USD"), "INVALID_ACCOUNT");
    }
    assert.equal(count(db, "accounts"), 0);
  });

  it("accepts the maximum-length name and unicode names", () => {
    const { ledger } = newLedger();
    ledger.createAccount("a".repeat(128), "USD");
    ledger.createAccount("Zoë-账户", "USD");
    assert.equal(ledger.balance("Zoë-账户"), 0);
  });

  it("stores hostile names literally: all SQL is parameterized", () => {
    const { ledger, db } = newLedger();
    const evil = "x'); DROP TABLE accounts; --";
    ledger.createAccount(evil, "USD");
    ledger.createAccount("equity", "USD");
    ledger.transfer("equity", evil, "5.00", "k1", "'); DELETE FROM entries; --");
    assert.equal(ledger.balance(evil), 500);
    assert.equal(count(db, "accounts"), 2);
    assert.equal(ledger.history(evil)[0]?.description, "'); DELETE FROM entries; --");
    assertLedgerError(() => ledger.balance("x' OR '1'='1"), "ACCOUNT_NOT_FOUND");
  });
});

describe("Ledger.getAccount", () => {
  it("returns the stored account", () => {
    const { ledger } = newLedger();
    const created = ledger.createAccount("alice", "EUR");
    assert.deepEqual(ledger.getAccount("alice"), created);
  });

  it("fails for an unknown account, naming it", () => {
    const { ledger } = newLedger();
    assertLedgerError(() => ledger.getAccount("ghost"), "ACCOUNT_NOT_FOUND", /ghost/);
  });
});

describe("Ledger.balance", () => {
  it("fails for an unknown account", () => {
    const { ledger } = newLedger();
    assertLedgerError(() => ledger.balance("ghost"), "ACCOUNT_NOT_FOUND", /ghost/);
  });
});
