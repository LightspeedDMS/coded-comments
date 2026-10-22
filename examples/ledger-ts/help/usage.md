Usage: ledger <command> [arguments]

Commands:
  init                                  Create the database and apply pending migrations
  account create <name> <currency>      Create an account (currency: 3 uppercase letters, e.g. USD)
  transfer <from> <to> <amount> --key <k> [--desc <d>]
                                        Move <amount> (decimal, max 2 places) from one account to another.
                                        Re-running with the same --key and parameters is a no-op.
  balance <name>                        Print an account's balance
  history <name>                        Print an account's entries, oldest first

Options:
  --help                                Show this help

Environment:
  LEDGER_DB   Path of the SQLite database (default: ./ledger.db)

Notes:
  The account named "equity" may go negative; it is the source for seeding money.
  An amount starting with "-" must follow "--", e.g. ledger transfer a b --key k -- -5
