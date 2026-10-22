import { DatabaseSync } from "node:sqlite";
import { LedgerError } from "./errors.js";

const BUSY_TIMEOUT_MS = 5000;

/** Opens (creating if absent) a SQLite file. A file that is not a SQLite database fails here, not on first query. */
export function openDatabase(path: string): DatabaseSync {
  let db: DatabaseSync | undefined;
  try {
    db = new DatabaseSync(path);
    //^ hazard foreign_keys is per-connection and a no-op inside a transaction => set at open, never later
    db.exec(`PRAGMA foreign_keys = ON; PRAGMA busy_timeout = ${BUSY_TIMEOUT_MS};`);
    //^ why PRAGMAs never read the file, so reading the schema is what rejects a non-database file
    db.prepare("SELECT 1 FROM sqlite_master LIMIT 1").get();
    return db;
  } catch (e) {
    db?.close();
    throw new LedgerError("DATABASE_ERROR", `cannot open database ${JSON.stringify(path)}: ${(e as Error).message}`);
  }
}

/**
 * Runs fn inside BEGIN IMMEDIATE ... COMMIT. Any throw (including a failed COMMIT) rolls back and rethrows.
 * IMMEDIATE takes the write lock up front, so read-then-write sequences inside fn cannot interleave with other writers.
 */
export function inTransaction<T>(db: DatabaseSync, fn: () => T): T {
  db.exec("BEGIN IMMEDIATE");
  try {
    const result = fn();
    db.exec("COMMIT");
    return result;
  } catch (e) {
    if (db.isTransaction) {
      try {
        db.exec("ROLLBACK");
      } catch (rollbackError) {
        throw new AggregateError([e, rollbackError], "transaction failed and rollback also failed");
      }
    }
    throw e;
  }
}
