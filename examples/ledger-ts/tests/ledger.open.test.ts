import assert from "node:assert/strict";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, it } from "node:test";
import { Ledger } from "../src/ledger.js";
import { assertLedgerError } from "./helpers.js";

let dir: string;
let path: string;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "ledger-open-"));
  path = join(dir, "ledger.db");
});

afterEach(() => {
  rmSync(dir, { recursive: true, force: true });
});

describe("Ledger.init / Ledger.open", () => {
  it("init creates the database file and applies every migration once", () => {
    const applied = Ledger.init(path);
    assert.ok(applied.length >= 1);
    assert.ok(existsSync(path));
    assert.deepEqual(Ledger.init(path), []);
  });

  it("open refuses a missing file and does not create it", () => {
    assertLedgerError(() => Ledger.open(path), "NOT_INITIALIZED", /ledger init/);
    assert.equal(existsSync(path), false);
  });

  it("open refuses a database that has not been migrated", () => {
    writeFileSync(path, "");
    assertLedgerError(() => Ledger.open(path), "NOT_INITIALIZED", /ledger init/);
  });

  it("persists accounts and transfers across close and reopen", () => {
    Ledger.init(path);
    const first = Ledger.open(path);
    first.createAccount("equity", "USD");
    first.createAccount("alice", "USD");
    first.transfer("equity", "alice", "12.34", "k1", "seed");
    first.close();

    const second = Ledger.open(path);
    assert.equal(second.balance("alice"), 1234);
    assert.equal(second.transfer("equity", "alice", "12.34", "k1", "seed").replayed, true);
    second.checkInvariant();
    second.close();
  });

  it("two connections to one file see each other's committed transfers", () => {
    Ledger.init(path);
    const a = Ledger.open(path);
    const b = Ledger.open(path);
    a.createAccount("equity", "USD");
    a.createAccount("alice", "USD");
    a.transfer("equity", "alice", "5.00", "k1");
    assert.equal(b.balance("alice"), 500);
    assert.equal(b.transfer("equity", "alice", "5.00", "k1").replayed, true);
    a.close();
    b.close();
  });
});
