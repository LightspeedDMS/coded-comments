-- Core double-entry schema. Amounts are integer minor units (cents), never floats.
-- Applied by src/migrations.ts inside a transaction: no BEGIN/COMMIT in this file.

CREATE TABLE accounts (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL UNIQUE CHECK (length(name) BETWEEN 1 AND 128),
  currency   TEXT NOT NULL CHECK (length(currency) = 3 AND currency NOT GLOB '*[^A-Z]*'),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

CREATE TABLE transfers (
  id              INTEGER PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE CHECK (length(idempotency_key) BETWEEN 1 AND 255),
  created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  description     TEXT
) STRICT;

-- amount_minor is signed: negative = debit (money leaves the account), positive = credit.
-- UNIQUE (transfer_id, account_id) means a transfer cannot touch the same account twice (from <> to).
CREATE TABLE entries (
  id           INTEGER PRIMARY KEY,
  transfer_id  INTEGER NOT NULL REFERENCES transfers (id),
  account_id   INTEGER NOT NULL REFERENCES accounts (id),
  amount_minor INTEGER NOT NULL CHECK (amount_minor <> 0 AND abs(amount_minor) <= 9007199254740991),
  UNIQUE (transfer_id, account_id)
) STRICT;

CREATE INDEX entries_account_idx ON entries (account_id);

-- A transfer has exactly two entries that cancel out, so the sum of all entries is always 0.
-- (SQLite has no deferred multi-row constraints; the second entry is validated against the first on insert.)
CREATE TRIGGER entries_pair_check BEFORE INSERT ON entries
BEGIN
  SELECT RAISE(ABORT, 'a transfer has at most two entries')
   WHERE (SELECT COUNT(*) FROM entries WHERE transfer_id = NEW.transfer_id) >= 2;
  SELECT RAISE(ABORT, 'the entries of a transfer must sum to zero')
   WHERE EXISTS (SELECT 1 FROM entries WHERE transfer_id = NEW.transfer_id AND amount_minor + NEW.amount_minor <> 0);
END;

CREATE TRIGGER entries_currency_check BEFORE INSERT ON entries
WHEN EXISTS (
  SELECT 1
    FROM entries e
    JOIN accounts ea ON ea.id = e.account_id
    JOIN accounts na ON na.id = NEW.account_id
   WHERE e.transfer_id = NEW.transfer_id AND ea.currency <> na.currency
)
BEGIN
  SELECT RAISE(ABORT, 'both accounts of a transfer must share a currency');
END;

--^ coupled 'equity' literal mirrors EQUITY_ACCOUNT in src/ledger.ts => change both
CREATE TRIGGER entries_no_overdraft BEFORE INSERT ON entries
WHEN NEW.amount_minor < 0
 AND (SELECT name FROM accounts WHERE id = NEW.account_id) <> 'equity'
 AND (SELECT COALESCE(SUM(amount_minor), 0) FROM entries WHERE account_id = NEW.account_id) + NEW.amount_minor < 0
BEGIN
  SELECT RAISE(ABORT, 'insufficient funds');
END;

-- The ledger is append-only: corrections are new transfers, never edits.
CREATE TRIGGER entries_no_update BEFORE UPDATE ON entries
BEGIN SELECT RAISE(ABORT, 'entries are immutable'); END;

CREATE TRIGGER entries_no_delete BEFORE DELETE ON entries
BEGIN SELECT RAISE(ABORT, 'entries are immutable'); END;

CREATE TRIGGER transfers_no_update BEFORE UPDATE ON transfers
BEGIN SELECT RAISE(ABORT, 'transfers are immutable'); END;

CREATE TRIGGER transfers_no_delete BEFORE DELETE ON transfers
BEGIN SELECT RAISE(ABORT, 'transfers are immutable'); END;

CREATE TRIGGER accounts_currency_immutable BEFORE UPDATE OF currency ON accounts
BEGIN SELECT RAISE(ABORT, 'account currency is immutable'); END;
