import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, it } from "node:test";
import type { DatabaseSync } from "node:sqlite";
import { inTransaction, openDatabase } from "../src/db.js";
import { LedgerError } from "../src/errors.js";

let dir: string;
let handles: DatabaseSync[];

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "ledger-db-"));
  handles = [];
});

afterEach(() => {
  for (const h of handles) {
    if (h.isOpen) h.close();
  }
  rmSync(dir, { recursive: true, force: true });
});

/** Opens through the code under test and registers the handle for cleanup. */
function open(path: string): DatabaseSync {
  const db = openDatabase(path);
  handles.push(db);
  return db;
}

function tableDb(): DatabaseSync {
  const db = open(":memory:");
  db.exec("CREATE TABLE t (x INTEGER)");
  return db;
}

function rows(db: DatabaseSync, table = "t"): number {
  return (db.prepare(`SELECT COUNT(*) AS n FROM ${table}`).get() as { n: number }).n;
}

describe("openDatabase", () => {
  it("turns foreign key enforcement on", () => {
    const db = open(":memory:");
    const row = db.prepare("PRAGMA foreign_keys").get() as { foreign_keys: number };
    assert.equal(row.foreign_keys, 1);
  });

  it("throws, instead of returning a half-usable handle, when the file is not a database", () => {
    const path = join(dir, "garbage.db");
    writeFileSync(path, "this is definitely not a sqlite database file, just text".repeat(20));
    assert.throws(
      () => openDatabase(path),
      (e: unknown) => e instanceof LedgerError && e.code === "DATABASE_ERROR" && e.message.includes("garbage.db") && /not a database/i.test(e.message),
    );
  });

  it("raises DATABASE_ERROR when the file cannot be opened at all (missing directory)", () => {
    assert.throws(
      () => openDatabase(join(dir, "no-such-dir", "x.db")),
      (e: unknown) => e instanceof LedgerError && e.code === "DATABASE_ERROR" && /unable to open/i.test(e.message),
    );
  });
});

describe("inTransaction", () => {
  it("commits and returns fn's value", () => {
    const db = tableDb();
    const v = inTransaction(db, () => {
      db.exec("INSERT INTO t VALUES (1)");
      return "done";
    });
    assert.equal(v, "done");
    assert.equal(rows(db), 1);
    assert.equal(db.isTransaction, false);
  });

  it("rolls back and rethrows the very same error when fn throws", () => {
    const db = tableDb();
    const boom = new Error("boom");
    assert.throws(
      () =>
        inTransaction(db, () => {
          db.exec("INSERT INTO t VALUES (1)");
          throw boom;
        }),
      (e: unknown) => e === boom,
    );
    assert.equal(rows(db), 0);
    assert.equal(db.isTransaction, false);
  });

  it("rolls back when COMMIT itself fails (deferred foreign key violation)", () => {
    const db = open(":memory:");
    db.exec("CREATE TABLE p (id INTEGER PRIMARY KEY); CREATE TABLE c (pid INTEGER REFERENCES p(id) DEFERRABLE INITIALLY DEFERRED)");
    assert.throws(() => inTransaction(db, () => db.exec("INSERT INTO c VALUES (42)")), /FOREIGN KEY/);
    assert.equal(db.isTransaction, false);
    assert.equal(rows(db, "c"), 0);
  });

  it("still propagates the original error when fn already ended the transaction", () => {
    const db = tableDb();
    const boom = new Error("boom");
    assert.throws(
      () =>
        inTransaction(db, () => {
          db.exec("ROLLBACK");
          throw boom;
        }),
      (e: unknown) => e === boom,
    );
    assert.equal(db.isTransaction, false);
  });

  it("takes the write lock up front: a second connection cannot start writing meanwhile", () => {
    const path = join(dir, "lock.db");
    const a = open(path);
    a.exec("CREATE TABLE t (x INTEGER)");
    const b = open(path);
    b.exec("PRAGMA busy_timeout = 0");
    inTransaction(a, () => {
      assert.throws(() => b.exec("BEGIN IMMEDIATE"), /locked|busy/i);
    });
    b.exec("BEGIN IMMEDIATE");
    b.exec("ROLLBACK");
  });
});
