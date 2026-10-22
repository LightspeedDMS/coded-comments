import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { assertLedgerError, count, seededLedger } from "./helpers.js";

describe("idempotent replay", () => {
  it("returns the original transfer, without creating another", () => {
    const { ledger, db } = seededLedger();
    const first = ledger.transfer("alice", "bob", "30.00", "pay-1", "rent");
    const transfers = count(db, "transfers");
    const entries = count(db, "entries");

    const again = ledger.transfer("alice", "bob", "30.00", "pay-1", "rent");

    assert.equal(first.replayed, false);
    assert.equal(again.replayed, true);
    assert.deepEqual({ ...again, replayed: false }, first);
    assert.equal(count(db, "transfers"), transfers);
    assert.equal(count(db, "entries"), entries);
    assert.equal(ledger.balance("alice"), 7000);
    assert.equal(ledger.balance("bob"), 3000);
  });

  it("can be replayed any number of times", () => {
    const { ledger, db } = seededLedger();
    const first = ledger.transfer("alice", "bob", "1.00", "k");
    const before = count(db, "transfers");
    for (let i = 0; i < 5; i++) assert.equal(ledger.transfer("alice", "bob", "1.00", "k").id, first.id);
    assert.equal(count(db, "transfers"), before);
    assert.equal(ledger.balance("bob"), 100);
  });

  it("treats equal amounts written differently as the same parameters", () => {
    const { ledger } = seededLedger();
    const first = ledger.transfer("alice", "bob", "10", "k");
    assert.equal(ledger.transfer("alice", "bob", "10.00", "k").id, first.id);
  });

  it("replays a transfer that had no description", () => {
    const { ledger } = seededLedger();
    const first = ledger.transfer("alice", "bob", "2.00", "k");
    const again = ledger.transfer("alice", "bob", "2.00", "k");
    assert.equal(again.id, first.id);
    assert.equal(again.description, null);
  });

  it("still returns the original after the source can no longer afford it", () => {
    const { ledger } = seededLedger();
    const first = ledger.transfer("alice", "bob", "100.00", "all-in");
    assert.equal(ledger.balance("alice"), 0);
    const again = ledger.transfer("alice", "bob", "100.00", "all-in");
    assert.equal(again.id, first.id);
    assert.equal(again.replayed, true);
    assert.equal(ledger.balance("alice"), 0);
  });

  it("replays seed transfers from equity too", () => {
    const { ledger } = seededLedger();
    assert.equal(ledger.transfer("equity", "alice", "100.00", "seed-alice", "seed").replayed, true);
    assert.equal(ledger.balance("alice"), 10000);
  });

  it("validates the replayed request: a malformed amount is still rejected", () => {
    const { ledger } = seededLedger();
    ledger.transfer("alice", "bob", "1.00", "k");
    assertLedgerError(() => ledger.transfer("alice", "bob", "1.001", "k"), "INVALID_AMOUNT");
  });
});

describe("conflicting replay", () => {
  const variants: [string, [string, string, string, string | undefined]][] = [
    ["a different amount", ["alice", "bob", "30.01", "rent"]],
    ["a different source", ["bob", "alice", "30.00", "rent"]],
    ["a different destination", ["alice", "equity", "30.00", "rent"]],
    ["a different description", ["alice", "bob", "30.00", "other"]],
    ["a missing description", ["alice", "bob", "30.00", undefined]],
  ];

  for (const [label, [from, to, amount, desc]] of variants) {
    it(`rejects the same key with ${label}, changing nothing`, () => {
      const { ledger, db } = seededLedger();
      ledger.transfer("alice", "bob", "30.00", "pay-1", "rent");
      const transfers = count(db, "transfers");
      const entries = count(db, "entries");
      const alice = ledger.balance("alice");
      const bob = ledger.balance("bob");

      assertLedgerError(() => ledger.transfer(from, to, amount, "pay-1", desc), "IDEMPOTENCY_CONFLICT", /pay-1/);

      assert.equal(count(db, "transfers"), transfers);
      assert.equal(count(db, "entries"), entries);
      assert.equal(ledger.balance("alice"), alice);
      assert.equal(ledger.balance("bob"), bob);
    });
  }

  it("rejects a description supplied on replay when the original had none", () => {
    const { ledger } = seededLedger();
    ledger.transfer("alice", "bob", "1.00", "k");
    assertLedgerError(() => ledger.transfer("alice", "bob", "1.00", "k", "late note"), "IDEMPOTENCY_CONFLICT");
  });

  it("distinguishes an empty description from a missing one", () => {
    const { ledger } = seededLedger();
    ledger.transfer("alice", "bob", "1.00", "k", "");
    assertLedgerError(() => ledger.transfer("alice", "bob", "1.00", "k"), "IDEMPOTENCY_CONFLICT");
  });

  it("does not let a conflicting key through to account checks", () => {
    const { ledger } = seededLedger();
    ledger.transfer("alice", "bob", "1.00", "k");
    assertLedgerError(() => ledger.transfer("alice", "ghost", "1.00", "k"), "IDEMPOTENCY_CONFLICT");
  });
});

describe("keys and failures", () => {
  it("lets a key be reused after its earlier attempt was rejected", () => {
    const { ledger } = seededLedger();
    assertLedgerError(() => ledger.transfer("bob", "alice", "5.00", "retry-me"), "INSUFFICIENT_FUNDS");
    ledger.transfer("alice", "bob", "5.00", "other");
    const t = ledger.transfer("bob", "alice", "5.00", "retry-me");
    assert.equal(t.replayed, false);
    assert.equal(ledger.balance("alice"), 10000);
  });

  it("keeps different keys independent, so identical transfers under new keys do happen twice", () => {
    const { ledger } = seededLedger();
    const a = ledger.transfer("alice", "bob", "1.00", "k1");
    const b = ledger.transfer("alice", "bob", "1.00", "k2");
    assert.notEqual(a.id, b.id);
    assert.equal(ledger.balance("bob"), 200);
  });

  it("treats keys as case-sensitive and exact", () => {
    const { ledger } = seededLedger();
    const a = ledger.transfer("alice", "bob", "1.00", "Key");
    const b = ledger.transfer("alice", "bob", "1.00", "key");
    assert.notEqual(a.id, b.id);
  });
});
