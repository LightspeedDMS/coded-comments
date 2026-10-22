import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { formatAmount } from "../src/money.js";
import { assertLedgerError, count, newLedger } from "./helpers.js";

/** Small deterministic PRNG so a failing run can be reproduced from its seed. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const TARGET_SUCCESSES = 500;
const MAX_ATTEMPTS = 20000;
const USD_ACCOUNTS = ["a0", "a1", "a2", "a3", "a4", "a5"];

interface Sent {
  key: string;
  from: string;
  to: string;
  minor: number;
  id: number;
}

function run(seed: number): void {
  const rnd = mulberry32(seed);
  const int = (lo: number, hi: number): number => lo + Math.floor(rnd() * (hi - lo + 1));
  const pick = <T>(xs: readonly T[]): T => xs[int(0, xs.length - 1)] as T;

  const { ledger, db } = newLedger();
  ledger.createAccount("equity", "USD");
  for (const n of USD_ACCOUNTS) ledger.createAccount(n, "USD");
  ledger.createAccount("euro", "EUR");

  const shadow = new Map<string, number>([["equity", 0], ["euro", 0], ...USD_ACCOUNTS.map((n): [string, number] => [n, 0])]);
  const sent: Sent[] = [];
  let successes = 0;
  let rejected = 0;
  let replays = 0;

  const commit = (from: string, to: string, minor: number): void => {
    const key = `s${seed}-${sent.length}`;
    const t = ledger.transfer(from, to, formatAmount(minor), key, `desc ${key}`);
    assert.equal(t.replayed, false);
    shadow.set(from, (shadow.get(from) ?? 0) - minor);
    shadow.set(to, (shadow.get(to) ?? 0) + minor);
    sent.push({ key, from, to, minor, id: t.id });
    successes += 1;
  };

  let attempts = 0;
  while (successes < TARGET_SUCCESSES) {
    attempts += 1;
    assert.ok(attempts <= MAX_ATTEMPTS, "generator failed to reach the target; test bug");
    const roll = rnd();
    const from = pick(USD_ACCOUNTS);
    const to = pick(USD_ACCOUNTS.filter((n) => n !== from));
    const fromBalance = shadow.get(from) ?? 0;

    if (roll < 0.12 || fromBalance === 0) {
      commit("equity", pick(USD_ACCOUNTS), int(1, 250000));
    } else if (roll < 0.72) {
      commit(from, to, int(1, fromBalance));
    } else if (roll < 0.8) {
      assertLedgerError(() => ledger.transfer(from, to, formatAmount(fromBalance + 1), `over-${attempts}`), "INSUFFICIENT_FUNDS");
      rejected += 1;
    } else if (roll < 0.86) {
      assertLedgerError(() => ledger.transfer(from, "euro", "0.01", `fx-${attempts}`), "CURRENCY_MISMATCH");
      rejected += 1;
    } else if (roll < 0.93 && sent.length > 0) {
      const s = pick(sent);
      const again = ledger.transfer(s.from, s.to, formatAmount(s.minor), s.key, `desc ${s.key}`);
      assert.equal(again.replayed, true);
      assert.equal(again.id, s.id);
      replays += 1;
    } else if (sent.length > 0) {
      const s = pick(sent);
      assertLedgerError(() => ledger.transfer(s.from, s.to, formatAmount(s.minor + 1), s.key, `desc ${s.key}`), "IDEMPOTENCY_CONFLICT");
      rejected += 1;
    }
    if (attempts % 50 === 0) ledger.checkInvariant();
  }

  ledger.checkInvariant();

  assert.equal(count(db, "transfers"), TARGET_SUCCESSES);
  assert.equal(count(db, "entries"), TARGET_SUCCESSES * 2);
  let sum = 0;
  for (const [name, expected] of shadow) {
    const actual = ledger.balance(name);
    assert.equal(actual, expected, `balance of ${name}`);
    if (name !== "equity") assert.ok(actual >= 0, `${name} went negative`);
    sum += actual;
  }
  assert.equal(sum, 0);
  assert.ok(rejected > 0 && replays > 0, `scenario mix not exercised (rejected=${rejected}, replays=${replays})`);

  const hist = ledger.history("a0");
  assert.equal(
    hist.reduce((acc, e) => acc + e.amountMinor, 0),
    shadow.get("a0"),
  );
}

describe("randomized ledger", () => {
  for (const seed of [1, 42, 20260101, 987654321]) {
    it(`keeps every invariant across ${TARGET_SUCCESSES} transfers (seed ${seed})`, () => {
      run(seed);
    });
  }
});
