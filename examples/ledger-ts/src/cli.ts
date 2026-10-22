import { readFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { LedgerError } from "./errors.js";
import { Ledger } from "./ledger.js";
import { formatAmount } from "./money.js";

export interface Io {
  out(line: string): void;
  err(line: string): void;
}
export type Env = Readonly<Record<string, string | undefined>>;

const DEFAULT_DB_PATH = "./ledger.db";
const EXIT_OK = 0;
const EXIT_FAILURE = 1;
const EXIT_USAGE = 2;
const EXIT_INTERNAL = 70;

/** Bad command line (as opposed to a rejected ledger operation). */
class UsageError extends Error {
  readonly withUsage: boolean;

  constructor(message: string, withUsage = false) {
    super(message);
    this.name = "UsageError";
    this.withUsage = withUsage;
  }
}

//^ coupled help/usage.md sits at the project root, two levels above dist/src/ => keep rootDir "." in tsconfig
function usageText(): string {
  return readFileSync(new URL("../../help/usage.md", import.meta.url), "utf8").trimEnd();
}

function dbPath(env: Env): string {
  const path = env["LEDGER_DB"];
  if (path === undefined) return DEFAULT_DB_PATH;
  if (path === "") throw new UsageError("LEDGER_DB is set but empty");
  return path;
}

function positionalsOf(args: readonly string[]): string[] {
  return parseArgs({ args: [...args], options: {}, allowPositionals: true }).positionals;
}

function withLedger<T>(path: string, fn: (ledger: Ledger) => T): T {
  const ledger = Ledger.open(path);
  try {
    return fn(ledger);
  } finally {
    ledger.close();
  }
}

function cmdInit(args: readonly string[], path: string, io: Io): void {
  if (positionalsOf(args).length !== 0) throw new UsageError("init takes no arguments");
  const applied = Ledger.init(path);
  if (applied.length === 0) {
    io.out(`ledger at ${path} is already up to date`);
    return;
  }
  const plural = applied.length === 1 ? "migration" : "migrations";
  io.out(`initialized ledger at ${path}: applied ${applied.length} ${plural} (${applied.join(", ")})`);
}

function cmdAccount(args: readonly string[], path: string, io: Io): void {
  const [sub, name, currency, ...rest] = positionalsOf(args);
  if (sub !== "create" || name === undefined || currency === undefined || rest.length > 0) {
    throw new UsageError("expected: account create <name> <currency>");
  }
  const account = withLedger(path, (l) => l.createAccount(name, currency));
  io.out(`created account ${account.name} (${account.currency})`);
}

function cmdTransfer(args: readonly string[], path: string, io: Io): void {
  const { values, positionals } = parseArgs({
    args: [...args],
    options: { key: { type: "string" }, desc: { type: "string" } },
    allowPositionals: true,
  });
  const [from, to, amount, ...rest] = positionals;
  if (from === undefined || to === undefined || amount === undefined || rest.length > 0) {
    throw new UsageError("expected <from> <to> <amount> --key <k> [--desc <d>]");
  }
  if (values.key === undefined) throw new UsageError("--key is required");
  const key = values.key;
  const t = withLedger(path, (l) => l.transfer(from, to, amount, key, values.desc));
  const suffix = t.replayed ? " [replayed, nothing changed]" : "";
  io.out(`transfer #${t.id}: ${formatAmount(t.amountMinor)} ${t.currency} ${t.from} -> ${t.to} (key=${t.idempotencyKey})${suffix}`);
}

function cmdBalance(args: readonly string[], path: string, io: Io): void {
  const [name, ...rest] = positionalsOf(args);
  if (name === undefined || rest.length > 0) throw new UsageError("expected <name>");
  const { minor, currency } = withLedger(path, (l) => ({ minor: l.balance(name), currency: l.getAccount(name).currency }));
  io.out(`${formatAmount(minor)} ${currency}`);
}

function cmdHistory(args: readonly string[], path: string, io: Io): void {
  const [name, ...rest] = positionalsOf(args);
  if (name === undefined || rest.length > 0) throw new UsageError("expected <name>");
  for (const e of withLedger(path, (l) => l.history(name))) {
    const amount = `${e.amountMinor > 0 ? "+" : ""}${formatAmount(e.amountMinor)} ${e.currency}`;
    const description = e.description === null ? "-" : JSON.stringify(e.description);
    io.out(`#${e.transferId}\t${e.createdAt}\t${amount}\t${e.counterparty}\t${description}\t${e.idempotencyKey}`);
  }
}

function dispatch(argv: readonly string[], env: Env, io: Io): void {
  const [command, ...args] = argv;
  if (command === undefined) throw new UsageError("missing command", true);
  if (command === "--help" || command === "help") {
    io.out(usageText());
    return;
  }
  const handlers: Record<string, (args: readonly string[], path: string, io: Io) => void> = {
    init: cmdInit,
    account: cmdAccount,
    transfer: cmdTransfer,
    balance: cmdBalance,
    history: cmdHistory,
  };
  const handler = Object.hasOwn(handlers, command) ? handlers[command] : undefined;
  if (handler === undefined) throw new UsageError(`unknown command ${JSON.stringify(command)}`, true);
  handler(args, dbPath(env), io);
}

function isParseError(e: unknown): e is Error {
  return e instanceof TypeError && String((e as { code?: unknown }).code).startsWith("ERR_PARSE_ARGS_");
}

/** Runs one CLI invocation and returns the process exit code: 0 ok, 1 rejected operation, 2 usage error, 70 bug. */
export function main(argv: readonly string[], env: Env, io: Io): number {
  try {
    dispatch(argv, env, io);
    return EXIT_OK;
  } catch (e) {
    if (e instanceof LedgerError) {
      io.err(`error: ${e.message}`);
      return EXIT_FAILURE;
    }
    if (e instanceof UsageError || isParseError(e)) {
      io.err(`error: ${e.message}`);
      if (e instanceof UsageError && e.withUsage) io.err(usageText());
      return EXIT_USAGE;
    }
    io.err(`unexpected error: ${e instanceof Error ? (e.stack ?? e.message) : String(e)}`);
    return EXIT_INTERNAL;
  }
}
