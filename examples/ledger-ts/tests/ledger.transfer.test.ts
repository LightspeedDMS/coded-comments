import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { count, seededLedger } from "./helpers.js";

describe("Ledger.transfer (happy path)", () => {
  it("returns the created transfer", () => {
    const { ledger } = seededLedger();
    const t = ledger.transfer("alice", "bob", "30.25", "k-1", "rent share");
    assert.ok(t.id > 0);
    assert.equal(t.from, "alice");
    assert.equal(t.to, "bob");
    assert.equal(t.amountMinor, 3025);
    assert.equal(t.currency, "USD");
    assert.equal(t.idempotencyKey, "k-1");
    assert.equal(t.description, "rent share");
    assert.equal(t.replayed, false);
    assert.match(t.createdAt, /^\d{4}-\d{2}-\d{2}T/);
  });

  it("moves exactly the amount between the two balances", () => {
    const { ledger } = seededLedger();
    ledger.transfer("alice", "bob", "30.25", "k-1");
    assert.equal(ledger.balance("alice"), 6975);
    assert.equal(ledger.balance("bob"), 3025);
  });

  it("writes one transfer row and two entries: -amount for the source, +amount for the destination", () => {
    const { ledger, db } = seededLedger();
    const transfersBefore = count(db, "transfers");
    const entriesBefore = count(db, "entries");
    const t = ledger.transfer("alice", "bob", "10.00", "k-2");
    assert.equal(count(db, "transfers"), transfersBefore + 1);
    assert.equal(count(db, "entries"), entriesBefore + 2);
    const rows = db
      .prepare(
        "SELECT a.name AS name, e.amount_minor AS amount FROM entries e JOIN accounts a ON a.id = e.account_id WHERE e.transfer_id = ? ORDER BY e.id",
      )
      .all(t.id) as { name: string; amount: number }[];
    assert.deepEqual(
      rows.map((r) => ({ ...r })),
      [
        { name: "alice", amount: -1000 },
        { name: "bob", amount: 1000 },
      ],
    );
  });

  it("stores a missing description as null", () => {
    const { ledger } = seededLedger();
    assert.equal(ledger.transfer("alice", "bob", "1.00", "k-3").description, null);
  });

  it("uses whole-unit and one-decimal amounts exactly", () => {
    const { ledger } = seededLedger();
    ledger.transfer("alice", "bob", "5", "k-4");
    ledger.transfer("alice", "bob", "0.5", "k-5");
    assert.equal(ledger.balance("bob"), 550);
  });

  it("lets equity fund accounts and goes negative by the total seeded", () => {
    const { ledger } = seededLedger();
    ledger.transfer("equity", "bob", "25.00", "seed-bob");
    assert.equal(ledger.balance("equity"), -12500);
  });
});

describe("Ledger.history", () => {
  it("lists an account's entries oldest first with counterparty, sign and description", () => {
    const { ledger } = seededLedger();
    ledger.transfer("alice", "bob", "30.00", "k-1", "first");
    ledger.transfer("bob", "alice", "5.50", "k-2");
    const h = ledger.history("alice");
    assert.deepEqual(
      h.map((e) => [e.counterparty, e.amountMinor, e.description, e.idempotencyKey]),
      [
        ["equity", 10000, "seed", "seed-alice"],
        ["bob", -3000, "first", "k-1"],
        ["bob", 550, null, "k-2"],
      ],
    );
    assert.ok(h.every((e) => e.currency === "USD" && e.transferId > 0));
  });

  it("is empty for an account with no activity", () => {
    const { ledger } = seededLedger();
    assert.deepEqual(ledger.history("bob"), []);
  });
});
