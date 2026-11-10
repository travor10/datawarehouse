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
2. **Never Drop Existing Data Columns or Tables:**
   - Existing foreign keys, surrogate keys, and measure columns must never be dropped in production.
   - Deprecated columns are flagged or nullable, preserving historical query reproducibility.
3. **Idempotent and Replay-Safe:**
   - Every migration script must be replay-safe: re-running a migration script against an already migrated database must either be a no-op or succeed cleanly.
4. **Automated Version Tracking (`_schema_migrations`):**
   - The database maintains an audit relation:
     ```sql
     CREATE TABLE IF NOT EXISTS _schema_migrations (
         migration_id INT AUTO_INCREMENT PRIMARY KEY,
         version VARCHAR(50) NOT NULL UNIQUE,
         description VARCHAR(255) NOT NULL,
         applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         execution_time_ms INT NULL,
         status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS'
     );
     ```
   - Before applying a migration, `DatabaseManager.run_migrations()` checks `_schema_migrations`. If the version string is already recorded, the migration is skipped.

---

## 3. Migration File Naming Convention

Migration scripts inside `database/migrations/` follow zero-padded alphanumeric numbering:
- `001_initial_schema.sql` (Baseline: 6 Dimensions, 2 Facts, 1 Profitability View, Reference Data)
- `002_add_customer_segmentation.sql` (Future: e.g. adding RFM scoring attributes)
- `003_add_equipment_meter_hours.sql` (Future: e.g. equipment run-time tracking)
