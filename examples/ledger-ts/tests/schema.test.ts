import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { newLedger, type TestLedger } from "./helpers.js";

function setup(): TestLedger {
  const t = newLedger();
  t.db.exec(`
    INSERT INTO accounts (name, currency) VALUES ('equity', 'USD'), ('alice', 'USD'), ('bob', 'USD'), ('euro', 'EUR');
    INSERT INTO transfers (idempotency_key) VALUES ('seed');
    INSERT INTO entries (transfer_id, account_id, amount_minor) VALUES
      (1, (SELECT id FROM accounts WHERE name = 'equity'), -1000),
      (1, (SELECT id FROM accounts WHERE name = 'alice'), 1000);
  `);
  return t;
}

function id(t: TestLedger, name: string): number {
  return (t.db.prepare("SELECT id FROM accounts WHERE name = ?").get(name) as { id: number }).id;
}

function newTransfer(t: TestLedger, key: string): number {
  return (t.db.prepare("INSERT INTO transfers (idempotency_key) VALUES (?) RETURNING id").get(key) as { id: number }).id;
}

function insertEntry(t: TestLedger, transferId: number, account: string, amount: number): void {
  t.db.prepare("INSERT INTO entries (transfer_id, account_id, amount_minor) VALUES (?, ?, ?)").run(transferId, id(t, account), amount);
}

describe("SQL-level constraints", () => {
  it("rejects malformed currencies", () => {
    const t = setup();
    for (const c of ["usd", "US", "USDX", "U1D", "", "US$"]) {
      assert.throws(() => t.db.prepare("INSERT INTO accounts (name, currency) VALUES (?, ?)").run(`n-${c}`, c), /CHECK/);
    }
  });

  it("rejects empty and over-long account names and duplicate names", () => {
    const t = setup();
    assert.throws(() => t.db.prepare("INSERT INTO accounts (name, currency) VALUES ('', 'USD')").run(), /CHECK/);
    assert.throws(() => t.db.prepare("INSERT INTO accounts (name, currency) VALUES (?, 'USD')").run("x".repeat(129)), /CHECK/);
    assert.throws(() => t.db.prepare("INSERT INTO accounts (name, currency) VALUES ('alice', 'EUR')").run(), /UNIQUE/);
  });

  it("rejects duplicate and empty idempotency keys", () => {
    const t = setup();
    assert.throws(() => t.db.prepare("INSERT INTO transfers (idempotency_key) VALUES ('seed')").run(), /UNIQUE/);
    assert.throws(() => t.db.prepare("INSERT INTO transfers (idempotency_key) VALUES ('')").run(), /CHECK/);
  });

  it("rejects non-integer, zero and out-of-range amounts (STRICT integer column)", () => {
    const t = setup();
    const tr = newTransfer(t, "k");
    const ins = t.db.prepare("INSERT INTO entries (transfer_id, account_id, amount_minor) VALUES (?, ?, ?)");
    assert.throws(() => ins.run(tr, id(t, "equity"), 0), /CHECK/);
    assert.throws(() => ins.run(tr, id(t, "equity"), 12.5), /datatype|STRICT|cannot store/i);
    assert.throws(() => ins.run(tr, id(t, "equity"), "abc"), /datatype|STRICT|cannot store|CHECK/i);
    assert.throws(() => ins.run(tr, id(t, "equity"), -9007199254740992n), /CHECK/);
  });

  it("enforces foreign keys on entries", () => {
    const t = setup();
    const ins = t.db.prepare("INSERT INTO entries (transfer_id, account_id, amount_minor) VALUES (?, ?, ?)");
    assert.throws(() => ins.run(9999, id(t, "alice"), 1), /FOREIGN KEY/);
    const tr = newTransfer(t, "k");
    assert.throws(() => ins.run(tr, 9999, 1), /FOREIGN KEY/);
  });

  it("rejects a transfer touching the same account twice", () => {
    const t = setup();
    const tr = newTransfer(t, "k");
    insertEntry(t, tr, "alice", -100);
    assert.throws(() => insertEntry(t, tr, "alice", 100), /UNIQUE/);
  });

  it("rejects a second entry that does not cancel the first, and a third entry", () => {
    const t = setup();
    const tr = newTransfer(t, "k");
    insertEntry(t, tr, "alice", -100);
    assert.throws(() => insertEntry(t, tr, "bob", 99), /sum to zero/);
    insertEntry(t, tr, "bob", 100);
    assert.throws(() => insertEntry(t, tr, "equity", 5), /at most two/);
  });

  it("rejects entries of one transfer in different currencies", () => {
    const t = setup();
    const tr = newTransfer(t, "k");
    insertEntry(t, tr, "equity", -100);
    assert.throws(() => insertEntry(t, tr, "euro", 100), /share a currency/);
  });

  it("rejects overdrawing any account except equity", () => {
    const t = setup();
    const tr = newTransfer(t, "k");
    assert.throws(() => insertEntry(t, tr, "alice", -1001), /insufficient funds/);
    insertEntry(t, tr, "alice", -1000);
    insertEntry(t, tr, "bob", 1000);
    const tr2 = newTransfer(t, "k2");
    insertEntry(t, tr2, "equity", -5000);
    insertEntry(t, tr2, "bob", 5000);
  });

  it("makes entries and transfers append-only", () => {
    const t = setup();
    assert.throws(() => t.db.exec("UPDATE entries SET amount_minor = 5 WHERE id = 1"), /immutable/);
    assert.throws(() => t.db.exec("DELETE FROM entries WHERE id = 1"), /immutable/);
    assert.throws(() => t.db.exec("UPDATE transfers SET description = 'x' WHERE id = 1"), /immutable/);
    assert.throws(() => t.db.exec("DELETE FROM transfers WHERE id = 1"), /immutable/);
  });

  it("makes an account's currency immutable", () => {
    const t = setup();
    assert.throws(() => t.db.exec("UPDATE accounts SET currency = 'EUR' WHERE name = 'alice'"), /immutable/);
  });
});
