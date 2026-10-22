import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, it } from "node:test";
import type { DatabaseSync } from "node:sqlite";
import { openDatabase } from "../src/db.js";
import { LedgerError } from "../src/errors.js";
import { migrate, pendingMigrations } from "../src/migrations.js";

let dir: string;
let db: DatabaseSync;

function tables(): string[] {
  const rows = db
    .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    .all() as { name: string }[];
  return rows.map((r) => r.name);
}

function applied(): string[] {
  const rows = db.prepare("SELECT name FROM schema_migrations ORDER BY name").all() as { name: string }[];
  return rows.map((r) => r.name);
}

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "ledger-mig-"));
  db = openDatabase(":memory:");
});

afterEach(() => {
  db.close();
  rmSync(dir, { recursive: true, force: true });
});

describe("migrate with a scratch migrations directory", () => {
  it("applies .sql files in filename order and records each one", () => {
    writeFileSync(join(dir, "0002_b.sql"), "CREATE TABLE b (id INTEGER PRIMARY KEY);");
    writeFileSync(join(dir, "0001_a.sql"), "CREATE TABLE a (id INTEGER PRIMARY KEY);");
    const result = migrate(db, dir);
    assert.deepEqual(result, ["0001_a.sql", "0002_b.sql"]);
    assert.deepEqual(applied(), ["0001_a.sql", "0002_b.sql"]);
    assert.deepEqual(tables(), ["a", "b", "schema_migrations"]);
  });

  it("orders by name, not by creation order or numeric magnitude of the prefix", () => {
    writeFileSync(join(dir, "0010_c.sql"), "CREATE TABLE c (id INTEGER); INSERT INTO c VALUES ((SELECT COUNT(*) FROM b));");
    writeFileSync(join(dir, "0009_b.sql"), "CREATE TABLE b (id INTEGER);");
    assert.deepEqual(migrate(db, dir), ["0009_b.sql", "0010_c.sql"]);
  });

  it("is idempotent: a second run applies nothing", () => {
    writeFileSync(join(dir, "0001_a.sql"), "CREATE TABLE a (id INTEGER PRIMARY KEY);");
    assert.deepEqual(migrate(db, dir), ["0001_a.sql"]);
    assert.deepEqual(migrate(db, dir), []);
    assert.deepEqual(migrate(db, dir), []);
    assert.deepEqual(applied(), ["0001_a.sql"]);
  });

  it("applies each migration at most once even when its SQL is not re-runnable", () => {
    writeFileSync(join(dir, "0001_a.sql"), "CREATE TABLE a (id INTEGER PRIMARY KEY); INSERT INTO a (id) VALUES (1);");
    migrate(db, dir);
    migrate(db, dir);
    const row = db.prepare("SELECT COUNT(*) AS n FROM a").get() as { n: number };
    assert.equal(row.n, 1);
  });

  it("applies only the new files when more are added later", () => {
    writeFileSync(join(dir, "0001_a.sql"), "CREATE TABLE a (id INTEGER PRIMARY KEY);");
    migrate(db, dir);
    writeFileSync(join(dir, "0002_b.sql"), "CREATE TABLE b (id INTEGER PRIMARY KEY);");
    assert.deepEqual(pendingMigrations(db, dir), ["0002_b.sql"]);
    assert.deepEqual(migrate(db, dir), ["0002_b.sql"]);
    assert.deepEqual(pendingMigrations(db, dir), []);
  });

  it("ignores files that are not .sql", () => {
    writeFileSync(join(dir, "0001_a.sql"), "CREATE TABLE a (id INTEGER PRIMARY KEY);");
    writeFileSync(join(dir, "README.md"), "not a migration");
    writeFileSync(join(dir, "0002_b.sql.bak"), "DROP TABLE a;");
    assert.deepEqual(migrate(db, dir), ["0001_a.sql"]);
  });

  it("runs each migration in a transaction: a failure leaves no partial schema and is not recorded", () => {
    writeFileSync(join(dir, "0001_a.sql"), "CREATE TABLE a (id INTEGER PRIMARY KEY);");
    writeFileSync(
      join(dir, "0002_bad.sql"),
      "CREATE TABLE half_done (id INTEGER PRIMARY KEY); INSERT INTO table_that_does_not_exist VALUES (1);",
    );
    writeFileSync(join(dir, "0003_c.sql"), "CREATE TABLE c (id INTEGER PRIMARY KEY);");
    assert.throws(
      () => migrate(db, dir),
      (e: unknown) => e instanceof LedgerError && e.code === "MIGRATION_FAILED" && e.message.includes("0002_bad.sql"),
    );
    assert.deepEqual(applied(), ["0001_a.sql"]);
    assert.deepEqual(tables(), ["a", "schema_migrations"]);
    assert.equal(db.isTransaction, false);
  });

  it("retries a previously failed migration once it is fixed, without redoing earlier ones", () => {
    writeFileSync(join(dir, "0001_a.sql"), "CREATE TABLE a (id INTEGER PRIMARY KEY);");
    writeFileSync(join(dir, "0002_bad.sql"), "THIS IS NOT SQL;");
    assert.throws(() => migrate(db, dir), LedgerError);
    writeFileSync(join(dir, "0002_bad.sql"), "CREATE TABLE b (id INTEGER PRIMARY KEY);");
    assert.deepEqual(migrate(db, dir), ["0002_bad.sql"]);
  });

  it("fails fast when a migration file cannot be read, recording nothing", () => {
    mkdirSync(join(dir, "0001_unreadable.sql"));
    assert.throws(
      () => migrate(db, dir),
      (e: unknown) => e instanceof LedgerError && e.code === "MIGRATION_FAILED" && e.message.includes("0001_unreadable.sql"),
    );
    assert.deepEqual(applied(), []);
  });

  it("fails fast when the migrations directory does not exist", () => {
    assert.throws(
      () => migrate(db, join(dir, "nope")),
      (e: unknown) => e instanceof LedgerError && e.code === "MIGRATION_FAILED",
    );
  });
});

describe("the shipped migrations", () => {
  it("create accounts, transfers and entries, and are idempotent", () => {
    const first = migrate(db);
    assert.ok(first.length >= 1);
    assert.deepEqual(migrate(db), []);
    assert.deepEqual(tables(), ["accounts", "entries", "schema_migrations", "transfers"]);
    assert.deepEqual(pendingMigrations(db), []);
  });

  it("have the required columns", () => {
    migrate(db);
    const cols = (t: string): string[] =>
      (db.prepare(`SELECT name FROM pragma_table_info('${t}') ORDER BY cid`).all() as { name: string }[]).map((r) => r.name);
    assert.deepEqual(cols("accounts"), ["id", "name", "currency", "created_at"]);
    assert.deepEqual(cols("transfers"), ["id", "idempotency_key", "created_at", "description"]);
    assert.deepEqual(cols("entries"), ["id", "transfer_id", "account_id", "amount_minor"]);
  });
});
