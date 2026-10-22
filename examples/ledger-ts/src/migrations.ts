import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import type { DatabaseSync } from "node:sqlite";
import { inTransaction } from "./db.js";
import { LedgerError } from "./errors.js";

//^ coupled migrations/ sits at the project root, two levels above dist/src/ (and src/) => keep rootDir "." in tsconfig
export const DEFAULT_MIGRATIONS_DIR = fileURLToPath(new URL("../../migrations", import.meta.url));

const CREATE_MIGRATIONS_TABLE =
  "CREATE TABLE IF NOT EXISTS schema_migrations (" +
  "name TEXT PRIMARY KEY, " +
  "applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))" +
  ") STRICT";

function listMigrationFiles(dir: string): string[] {
  try {
    return readdirSync(dir)
      .filter((f) => f.endsWith(".sql"))
      .sort();
  } catch (e) {
    throw new LedgerError("MIGRATION_FAILED", `cannot read migrations directory ${dir}: ${(e as Error).message}`);
  }
}

function appliedMigrations(db: DatabaseSync): Set<string> {
  const exists = db.prepare("SELECT 1 AS ok FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'").get();
  if (exists === undefined) return new Set();
  const rows = db.prepare("SELECT name FROM schema_migrations").all() as { name: string }[];
  return new Set(rows.map((r) => r.name));
}

/** Migration files in dir that this database has not applied yet, in application order. */
export function pendingMigrations(db: DatabaseSync, dir: string = DEFAULT_MIGRATIONS_DIR): string[] {
  const done = appliedMigrations(db);
  return listMigrationFiles(dir).filter((f) => !done.has(f));
}

function readMigration(dir: string, name: string): string {
  try {
    return readFileSync(join(dir, name), "utf8");
  } catch (e) {
    throw new LedgerError("MIGRATION_FAILED", `cannot read migration ${name}: ${(e as Error).message}`);
  }
}

/**
 * Applies every pending migration in filename order, each in its own transaction together with its
 * schema_migrations row. Returns the names applied by this call (empty when already up to date).
 */
export function migrate(db: DatabaseSync, dir: string = DEFAULT_MIGRATIONS_DIR): string[] {
  db.exec(CREATE_MIGRATIONS_TABLE);
  const applied: string[] = [];
  for (const name of pendingMigrations(db, dir)) {
    const sql = readMigration(dir, name);
    try {
      const didApply = inTransaction(db, () => {
        //^ why re-check under the write lock: a concurrent migrator may have applied it since the pending scan
        if (db.prepare("SELECT 1 AS ok FROM schema_migrations WHERE name = ?").get(name) !== undefined) return false;
        db.exec(sql);
        db.prepare("INSERT INTO schema_migrations (name) VALUES (?)").run(name);
        return true;
      });
      if (didApply) applied.push(name);
    } catch (e) {
      throw new LedgerError("MIGRATION_FAILED", `migration ${name} failed and was rolled back: ${(e as Error).message}`);
    }
  }
  return applied;
}
