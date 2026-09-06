# Database Reliability

TV Manager 14 centralizes SQLite access through `dbcore.py`.

## Live database policy
- 30-second SQLite busy timeout.
- WAL journaling.
- `synchronous=NORMAL`.
- Foreign-key enforcement.
- Shared transactions for logging that occurs during writes.

## Versioned migrations
`migrations.py` records schema changes in `schema_migrations`. Before the v13 migration, TV Manager creates a SQLite online backup under `backups/` once. Migration startup ends with `PRAGMA quick_check`; TV Manager does not silently continue after a failed integrity check.

## Lock fixes
Search result persistence and search-decision logging now use one writer transaction. SAB completion updates and activity logging also share the same connection. These remove two known nested-writer lock paths.

## Scheduler recovery
Every scheduler execution is recorded in `scheduler_runs` with start, finish, result status and a bounded message.

## Connection lifecycle
Connections opened through `dbcore.connect()` commit or roll back and then close when their `with` block exits. This prevents long-running scheduler and provider activity from accumulating SQLite file handles.
