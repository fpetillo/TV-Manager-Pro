# Reliability and Database Safety

Version 13 centralizes SQLite connections with WAL, a 30-second busy timeout, foreign keys, and NORMAL synchronous mode. Search decisions now reuse the active transaction, reducing nested-writer lock risk. A `schema_migrations` ledger and database health endpoint were added.
