import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { count, seededLedger, type TestLedger } from "./helpers.js";

/**
 * Fault injection with a real SQLite trigger (no mocks): the debit entry is inserted first and
 * succeeds, then the credit entry to `bob` blows up, so the failure lands mid-transfer.
 */
function failCreditsTo(t: TestLedger, account: string): void {
  t.db.exec(
    `CREATE TRIGGER inject_credit_failure BEFORE INSERT ON entries
     WHEN NEW.amount_minor > 0 AND NEW.account_id = (SELECT id FROM accounts WHERE name = '${account}')
     BEGIN SELECT RAISE(ABORT, 'injected failure'); END`,
  );
}

function state(t: TestLedger): { transfers: number; entries: number; alice: number; bob: number; equity: number } {
  return {
    transfers: count(t.db, "transfers"),
    entries: count(t.db, "entries"),
    alice: t.ledger.balance("alice"),
    bob: t.ledger.balance("bob"),
    equity: t.ledger.balance("equity"),
  };
}

describe("transfer atomicity", () => {
  it("a failure after the debit entry was written leaves no partial entries", () => {
    const t = seededLedger();
    const before = state(t);
    failCreditsTo(t, "bob");

    assert.throws(() => t.ledger.transfer("alice", "bob", "40.00", "doomed", "x"), /injected failure/);

    assert.deepEqual(state(t), before);
    assert.equal(t.db.isTransaction, false);
    const orphan = t.db
      .prepare("SELECT COUNT(*) AS n FROM entries e LEFT JOIN transfers x ON x.id = e.transfer_id WHERE x.id IS NULL")
      .get() as { n: number };
    assert.equal(orphan.n, 0);
    t.ledger.checkInvariant();
  });

  it("does not burn the idempotency key: the same request succeeds once the fault is gone", () => {
    const t = seededLedger();
    failCreditsTo(t, "bob");
    assert.throws(() => t.ledger.transfer("alice", "bob", "40.00", "retry"), /injected failure/);
    t.db.exec("DROP TRIGGER inject_credit_failure");

    const ok = t.ledger.transfer("alice", "bob", "40.00", "retry");
    assert.equal(ok.replayed, false);
    assert.equal(t.ledger.balance("alice"), 6000);
    assert.equal(t.ledger.balance("bob"), 4000);
  });

  it("keeps working normally after a failed transfer (connection is not stuck in a transaction)", () => {
    const t = seededLedger();
    failCreditsTo(t, "bob");
    assert.throws(() => t.ledger.transfer("alice", "bob", "1.00", "a"), /injected failure/);
    const ok = t.ledger.transfer("alice", "equity", "1.00", "b");
    assert.equal(ok.replayed, false);
    assert.equal(t.ledger.balance("equity"), -9900);
  });

  it("a failed transfer does not disturb transfers that committed before it", () => {
    const t = seededLedger();
    t.ledger.transfer("alice", "bob", "10.00", "good-1");
    const before = state(t);
    failCreditsTo(t, "bob");
    assert.throws(() => t.ledger.transfer("alice", "bob", "10.00", "bad"), /injected failure/);
    assert.deepEqual(state(t), before);
    assert.equal(t.ledger.transfer("alice", "bob", "10.00", "good-1").replayed, true);
  });
});
