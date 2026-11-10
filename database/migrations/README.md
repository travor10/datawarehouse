# Aura Cleaning Solutions Data Mart — Schema Migration Policy

## 1. Academic Rationale & Context
In enterprise Data Warehousing, database schemas evolve as new business lines (e.g. specialized medical sanitation), additional transactional systems, or regulatory reporting requirements emerge. 

Unlike transactional (OLTP) applications that frequently drop and rewrite tables during prototyping, **Data Marts host irreplaceable historical facts and dimension histories**. Therefore, data warehouse architecture mandates a strict **Forward-Only, Non-Destructive Migration Policy**.

---

## 2. Core Migration Rules

1. **Forward-Only Evolution:**
   - Schema modifications are applied strictly through additive migrations:
     - `ALTER TABLE <dim> ADD COLUMN <new_attribute> <type>;`
     - `CREATE TABLE IF NOT EXISTS <new_dimension_or_fact> (...);`
     - `CREATE INDEX IF NOT EXISTS <idx_name> ON <table> (<cols>);`
     - `CREATE OR REPLACE VIEW <view_name> AS ...;`
2. **Cryptographic Checksum Tracking & Immutability:**
   - When a migration script is executed, `DatabaseManager.run_migrations()` calculates the SHA-256 cryptographic digest of the file contents and records it in `_schema_migrations.checksum`.
   - On every subsequent run, all previously applied migration files are re-hashed.
   - If an applied migration file has been modified or tampered with, the system raises `MigrationChecksumError` and refuses to continue.
3. **Transaction & Failure Handling:**
   - If a migration statement fails, the migration is **never** recorded as `SUCCESS`.
   - In SQLite, the operation is rolled back transactionally.
   - **MySQL DDL Limitation Note:** In MySQL 8, data definition language (DDL) statements (such as `CREATE TABLE`, `ALTER TABLE`, and `CREATE PROCEDURE`) cause an **implicit commit**. Therefore, DDL statements in MySQL cannot be rolled back with `ROLLBACK`. If a DDL statement fails, `DatabaseManager` logs the exact statement, records a `'FAILED'` status, and raises `MigrationExecutionError`.
4. **Automated Version Tracking (`_schema_migrations`):**
   ```sql
   CREATE TABLE IF NOT EXISTS _schema_migrations (
       migration_id INT AUTO_INCREMENT PRIMARY KEY,
       version VARCHAR(50) NOT NULL UNIQUE,
       description VARCHAR(255) NOT NULL,
       checksum VARCHAR(64) NOT NULL,
       applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       execution_time_ms INT NULL,
       status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS'
   );
   ```

---

## 3. Migration Sequence

- `001_initial_schema.sql` (Baseline: 6 Dimensions, 2 Facts, 1 Profitability View, Reference Data, Stored Procedures, and Calendar from 2023 through 2026+)
