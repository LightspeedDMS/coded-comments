import assert from "node:assert/strict";
import { spawnSync, type SpawnSyncReturns } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, it } from "node:test";
import { main } from "../src/cli.js";

let dir: string;
let db: string;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "ledger-cli-"));
  db = join(dir, "t.db");
});

afterEach(() => {
  rmSync(dir, { recursive: true, force: true });
});

interface Result {
  code: number;
  out: string[];
  err: string[];
}

function ledger(args: string[], env: Record<string, string | undefined> = { LEDGER_DB: db }): Result {
  const out: string[] = [];
  const err: string[] = [];
  const code = main(args, env, { out: (l) => out.push(l), err: (l) => err.push(l) });
  return { code, out, err };
}

function ok(args: string[]): Result {
  const r = ledger(args);
  assert.equal(r.code, 0, `ledger ${args.join(" ")} failed: ${r.err.join("\n")}`);
  assert.deepEqual(r.err, []);
  return r;
}

function fails(args: string[], code: number, message: RegExp): Result {
  const r = ledger(args);
  assert.equal(r.code, code, `expected exit ${code}, got ${r.code}; stdout=${r.out.join("|")} stderr=${r.err.join("|")}`);
  assert.match(r.err.join("\n"), message);
  assert.deepEqual(r.out, []);
  return r;
}

function seed(): void {
  ok(["init"]);
  ok(["account", "create", "equity", "USD"]);
  ok(["account", "create", "alice", "USD"]);
  ok(["account", "create", "bob", "USD"]);
  ok(["transfer", "equity", "alice", "100.00", "--key", "seed-1", "--desc", "opening"]);
}

describe("ledger init", () => {
  it("creates the database, applies migrations, and is a no-op the second time", () => {
    const first = ok(["init"]);
    assert.match(first.out.join("\n"), /initialized.*applied 1 migration.*0001_init\.sql/);
    assert.ok(existsSync(db));
    assert.match(ok(["init"]).out.join("\n"), /already up to date/);
  });
});

describe("ledger account create / balance", () => {
  it("creates accounts that start at zero", () => {
    ok(["init"]);
    assert.deepEqual(ok(["account", "create", "alice", "USD"]).out, ["created account alice (USD)"]);
    assert.deepEqual(ok(["balance", "alice"]).out, ["0.00 USD"]);
  });

  it("reports duplicate accounts and bad currencies as errors on stderr", () => {
    ok(["init"]);
    ok(["account", "create", "alice", "USD"]);
    fails(["account", "create", "alice", "USD"], 1, /error: account "alice" already exists/);
    fails(["account", "create", "carol", "usd"], 1, /error: invalid currency/);
  });

  it("reports an unknown account", () => {
    ok(["init"]);
    fails(["balance", "ghost"], 1, /error: account "ghost" does not exist/);
  });

  it("stores hostile account names literally", () => {
    ok(["init"]);
    const evil = "x'); DROP TABLE accounts; --";
    ok(["account", "create", evil, "USD"]);
    assert.deepEqual(ok(["balance", evil]).out, ["0.00 USD"]);
    ok(["account", "create", "alice", "USD"]);
  });
});

describe("ledger transfer", () => {
  it("seeds from equity, transfers, and reflects both in balances", () => {
    seed();
    const t = ok(["transfer", "alice", "bob", "30.25", "--key", "k1", "--desc", "lunch"]);
    assert.deepEqual(t.out, ["transfer #2: 30.25 USD alice -> bob (key=k1)"]);
    assert.deepEqual(ok(["balance", "alice"]).out, ["69.75 USD"]);
    assert.deepEqual(ok(["balance", "bob"]).out, ["30.25 USD"]);
    assert.deepEqual(ok(["balance", "equity"]).out, ["-100.00 USD"]);
  });

  it("replaying the same key and parameters succeeds without changing anything", () => {
    seed();
    ok(["transfer", "alice", "bob", "30.25", "--key", "k1", "--desc", "lunch"]);
    const again = ok(["transfer", "alice", "bob", "30.25", "--key", "k1", "--desc", "lunch"]);
    assert.deepEqual(again.out, ["transfer #2: 30.25 USD alice -> bob (key=k1) [replayed, nothing changed]"]);
    assert.deepEqual(ok(["balance", "bob"]).out, ["30.25 USD"]);
  });

  it("a conflicting replay is an error", () => {
    seed();
    ok(["transfer", "alice", "bob", "30.25", "--key", "k1"]);
    fails(["transfer", "alice", "bob", "99.00", "--key", "k1"], 1, /error: idempotency key "k1" was already used for a different transfer/);
    assert.deepEqual(ok(["balance", "bob"]).out, ["30.25 USD"]);
  });

  it("rejects an overdraft", () => {
    seed();
    fails(["transfer", "alice", "bob", "100.01", "--key", "k1"], 1, /error: insufficient funds: "alice" has 100\.00 USD, needs 100\.01/);
    assert.deepEqual(ok(["balance", "alice"]).out, ["100.00 USD"]);
  });

  it("rejects a currency mismatch", () => {
    seed();
    ok(["account", "create", "carol", "EUR"]);
    fails(["transfer", "alice", "carol", "1.00", "--key", "k1"], 1, /error: cannot transfer between "alice" \(USD\) and "carol" \(EUR\)/);
  });

  it("rejects bad amounts, including negatives given after --", () => {
    seed();
    fails(["transfer", "alice", "bob", "1.234", "--key", "k1"], 1, /error: invalid amount "1\.234"/);
    fails(["transfer", "alice", "bob", "1e3", "--key", "k2"], 1, /error: invalid amount "1e3"/);
    fails(["transfer", "alice", "bob", "--key", "k3", "--", "-5"], 1, /error: invalid amount "-5": negative/);
  });

  it("rejects a leading-dash amount that was not escaped with --, as a usage error", () => {
    seed();
    fails(["transfer", "alice", "bob", "-5", "--key", "k"], 2, /Unknown option '-5'/);
  });

  it("requires --key", () => {
    seed();
    fails(["transfer", "alice", "bob", "1.00"], 2, /--key is required/);
  });

  it("rejects the wrong number of positional arguments and unknown options", () => {
    seed();
    fails(["transfer", "alice", "1.00", "--key", "k"], 2, /expected <from> <to> <amount>/);
    fails(["transfer", "alice", "bob", "1.00", "extra", "--key", "k"], 2, /expected <from> <to> <amount>/);
    fails(["transfer", "alice", "bob", "1.00", "--key", "k", "--bogus"], 2, /Unknown option '--bogus'/);
  });

  it("passes hostile descriptions through untouched", () => {
    seed();
    ok(["transfer", "alice", "bob", "1.00", "--key", "k1", "--desc", "'); DROP TABLE entries; --"]);
    assert.match(ok(["history", "bob"]).out.join("\n"), /"'\); DROP TABLE entries; --"/);
  });
});

describe("ledger history", () => {
  it("prints one tab-separated line per entry, oldest first, with signed amounts", () => {
    seed();
    ok(["transfer", "alice", "bob", "30.25", "--key", "k1", "--desc", "lunch"]);
    ok(["transfer", "bob", "alice", "5.00", "--key", "k2"]);
    const lines = ok(["history", "alice"]).out;
    assert.equal(lines.length, 3);
    const cols = lines.map((l) => l.split("\t"));
    assert.deepEqual(cols.map((c) => [c[0], c[2], c[3], c[4], c[5]]), [
      ["#1", "+100.00 USD", "equity", '"opening"', "seed-1"],
      ["#2", "-30.25 USD", "bob", '"lunch"', "k1"],
      ["#3", "+5.00 USD", "bob", "-", "k2"],
    ]);
    assert.match(cols[0]?.[1] ?? "", /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
  });

  it("prints nothing for an account without entries", () => {
    seed();
    assert.deepEqual(ok(["history", "bob"]).out, []);
  });

  it("reports an unknown account", () => {
    seed();
    fails(["history", "ghost"], 1, /does not exist/);
  });
});

describe("usage and environment", () => {
  it("prints usage on --help and on help, exit 0, to stdout", () => {
    for (const args of [["--help"], ["help"]]) {
      const r = ledger(args);
      assert.equal(r.code, 0);
      assert.match(r.out.join("\n"), /Usage: ledger <command>/);
      assert.deepEqual(r.err, []);
    }
  });

  it("prints usage to stderr with exit 2 when no command or an unknown command is given", () => {
    const none = ledger([]);
    assert.equal(none.code, 2);
    assert.match(none.err.join("\n"), /Usage: ledger <command>/);
    fails(["frobnicate"], 2, /unknown command "frobnicate"/);
    fails(["account"], 2, /expected: account create <name> <currency>/);
    fails(["account", "delete", "x"], 2, /expected: account create <name> <currency>/);
  });

  it("checks argument counts for the simple commands", () => {
    ok(["init"]);
    fails(["init", "extra"], 2, /init takes no arguments/);
    fails(["balance"], 2, /expected <name>/);
    fails(["history", "a", "b"], 2, /expected <name>/);
    fails(["account", "create", "only-name"], 2, /expected: account create <name> <currency>/);
  });

  it("refuses commands on a database that was never initialized, without creating it", () => {
    fails(["balance", "alice"], 1, /error: database .* is missing or not up to date; run "ledger init"/);
    assert.equal(existsSync(db), false);
  });

  it("reports a LEDGER_DB that is not a SQLite database as a normal error, not a crash", () => {
    writeFileSync(db, "not a database at all, just some text. ".repeat(40));
    fails(["balance", "alice"], 1, /error: cannot open database .*not a database/i);
    fails(["init"], 1, /error: cannot open database .*not a database/i);
  });

  it("rejects an empty LEDGER_DB", () => {
    const r = ledger(["init"], { LEDGER_DB: "" });
    assert.equal(r.code, 2);
    assert.match(r.err.join("\n"), /LEDGER_DB is set but empty/);
  });

  it("uses ./ledger.db when LEDGER_DB is unset (spawned process, cwd = temp dir)", () => {
    const p = spawnBin(["init"], { cwd: dir, env: {} });
    assert.equal(p.status, 0, p.stderr);
    assert.ok(existsSync(join(dir, "ledger.db")));
  });
});

const binPath = fileURLToPath(new URL("../src/bin.js", import.meta.url));

function spawnBin(args: string[], opts: { cwd?: string; env: Record<string, string> }): SpawnSyncReturns<string> {
  return spawnSync(process.execPath, ["--disable-warning=ExperimentalWarning", binPath, ...args], {
    encoding: "utf8",
    cwd: opts.cwd ?? dir,
    env: { PATH: process.env.PATH ?? "", ...opts.env },
  });
}

describe("the real executable", () => {
  it("separates stdout from stderr and sets exit codes", () => {
    const env = { LEDGER_DB: db };
    assert.equal(spawnBin(["init"], { env }).status, 0);
    assert.equal(spawnBin(["account", "create", "equity", "USD"], { env }).status, 0);
    assert.equal(spawnBin(["account", "create", "alice", "USD"], { env }).status, 0);
    assert.equal(spawnBin(["transfer", "equity", "alice", "10.00", "--key", "s1"], { env }).status, 0);

    const bal = spawnBin(["balance", "alice"], { env });
    assert.equal(bal.status, 0);
    assert.equal(bal.stdout, "10.00 USD\n");
    assert.equal(bal.stderr, "");

    const bad = spawnBin(["transfer", "alice", "equity", "99.00", "--key", "s2"], { env });
    assert.equal(bad.status, 1);
    assert.equal(bad.stdout, "");
    assert.match(bad.stderr, /^error: insufficient funds/);

    const usage = spawnBin(["nope"], { env });
    assert.equal(usage.status, 2);
    assert.equal(usage.stdout, "");
  });

  it("ships its usage text as help/usage.md", () => {
    const text = readFileSync(fileURLToPath(new URL("../../help/usage.md", import.meta.url)), "utf8");
    const r = spawnBin(["--help"], { env: { LEDGER_DB: db } });
    assert.equal(r.stdout.trimEnd(), text.trimEnd());
  });
});
