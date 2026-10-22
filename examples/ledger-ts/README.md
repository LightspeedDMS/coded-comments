# ledger-ts

A small double-entry ledger in strict TypeScript on SQLite (Node's built-in `node:sqlite`, no native dependencies).

Every transfer writes exactly two entries, `-amount` on the source and `+amount` on the destination, so the sum of all entries is always 0 and an account's balance is the sum of its entries.

## Setup

Requires Node >= 22.16 and npm.

```sh
npm install
npm run build        # tsc, strict mode -> dist/
npm test             # build + node:test suite
npm run test:coverage
```

## CLI

The database path comes from `LEDGER_DB` (default `./ledger.db`).

```sh
export LEDGER_DB=/tmp/demo.db
npm run -s ledger -- init
npm run -s ledger -- account create equity USD
npm run -s ledger -- account create alice USD
npm run -s ledger -- account create bob USD
npm run -s ledger -- transfer equity alice 100.00 --key seed-1 --desc "opening balance"
npm run -s ledger -- transfer alice bob 30.25 --key lunch-1 --desc "lunch"
npm run -s ledger -- balance alice        # 69.75 USD
npm run -s ledger -- history alice
```

You can also run `node --disable-warning=ExperimentalWarning dist/src/bin.js <command>` directly, or `npm link` to get a `ledger` command. The warning flag only hides Node's "SQLite is an experimental feature" notice from stderr.

| Command | Meaning |
| --- | --- |
| `ledger init` | Create the database and apply pending migrations (safe to repeat). |
| `ledger account create <name> <currency>` | Create an account; currency is 3 uppercase letters. |
| `ledger transfer <from> <to> <amount> --key <k> [--desc <d>]` | Move money. Same key and same parameters again is a no-op that returns the original. |
| `ledger balance <name>` | Print the balance, e.g. `69.75 USD`. |
| `ledger history <name>` | One tab-separated line per entry, oldest first: `#transfer`, timestamp, signed amount, counterparty, description (JSON string or `-`), key. |

Errors print `error: <message>` on stderr. Exit codes: `0` ok, `1` the operation was rejected (insufficient funds, conflict, unknown account, ...), `2` bad command line, `70` internal bug.

An amount beginning with `-` must come after `--` (`ledger transfer a b --key k -- -5`), otherwise it is parsed as an option. It is rejected either way.

## Rules

- **Money is integer minor units** (cents) end to end. Amounts arrive as decimal strings and are parsed with string/BigInt arithmetic, never floats. Accepted: `12`, `12.3`, `12.34`. Rejected: more than 2 decimals (even `1.230`), exponents (`1e3`), `NaN`, empty, padded, signed (`+1`), negative, zero, and anything above 90071992547409.91 (`Number.MAX_SAFE_INTEGER` cents, so sums stay exact).
- **Transfers** need two distinct, existing accounts with the same currency.
- **Overdrafts are rejected**, except for the account named exactly `equity`, which is how money is seeded and which therefore carries the negative of everything issued. The `equity` account has one currency like any other account, so seeding a second currency needs a second ledger database.
- **Idempotency**: `--key` is required. The same key with the same from, to, amount and description returns the original transfer (`replayed`); the same key with anything different is an `IDEMPOTENCY_CONFLICT` error. A missing description and an empty one are different. A key whose earlier attempt was rejected is not consumed.
- **Atomicity**: each transfer is one `BEGIN IMMEDIATE` transaction, so a failure part-way leaves no transfer row and no entries.
- **Currency codes** are checked for shape (3 uppercase ASCII letters), not against the ISO-4217 list. Amounts assume 2 minor-unit digits.

## Schema and migrations

Plain SQL files in `migrations/`, applied in filename order, each in its own transaction together with its row in `schema_migrations`, each at most once. Add a new file (`0002_...sql`) to change the schema; never edit an applied one. Do not put `BEGIN`/`COMMIT` in a migration.

`migrations/0001_init.sql` enforces in SQL what SQL can: STRICT integer columns, `CHECK`s on currency shape, name and key length and non-zero amounts, `UNIQUE` account names and idempotency keys, foreign keys, one entry per account per transfer, triggers that make a transfer exactly two cancelling entries in one currency, block overdrafts except for `equity`, and make entries and transfers append-only. SQLite has no deferred multi-row constraints, so "a transfer's entries sum to zero" is enforced on the second insert and re-verified by `checkInvariant()`.

All SQL is parameterized; account names and descriptions are only ever bound as parameters.

## Library use

```ts
import { Ledger } from "./dist/src/ledger.js";

Ledger.init("ledger.db");
const ledger = Ledger.open("ledger.db");
ledger.createAccount("equity", "USD");
ledger.createAccount("alice", "USD");
ledger.transfer("equity", "alice", "10.00", "seed-1");
ledger.balance("alice");     // 1000 (minor units)
ledger.checkInvariant();     // throws LedgerError INVARIANT_VIOLATION if anything is off
ledger.close();
```

## Layout

```
src/        money.ts errors.ts db.ts migrations.ts ledger.ts cli.ts bin.ts
migrations/ SQL migrations
help/       usage.md (CLI help text)
tests/      node:test suites (built to dist/tests and run from there)
```

## Tests

`npm test` builds and runs everything with `node:test` against real SQLite databases (in memory, or temp files for the CLI and reopen tests). There are no mocks: the atomicity tests inject a real failure with a SQLite trigger, the randomized test drives 500 transfers (four fixed seeds) against an independent shadow model of the balances, and the CLI tests run both `main()` in-process and the real executable.

## Known limitations

- Balances are computed by summing entries (indexed by account), not cached; fine for a small ledger.
- One `equity` account, therefore one seeded currency per database.
- `node:sqlite` is still flagged experimental by Node.
