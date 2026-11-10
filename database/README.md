# Aura Cleaning Solutions Data Mart — Database Architecture & Authoritative Schema Policy

## 1. Single Authoritative Source of Truth: The Migration Pipeline

To eliminate schema drift and ensure reproducible deployments across local testing, continuous integration, and production MySQL 8 instances, this project establishes a formal **Authoritative Schema Hierarchy**:

```
                       AUTHORITATIVE SOURCE OF TRUTH
                      database/migrations/*.sql
                                   │
                 ┌─────────────────┴─────────────────┐
                 │                                   │
                 ▼                                   ▼
        AUTOMATED PIPELINE                 MODULAR ARCHITECTURAL VIEW
     DatabaseManager.run_migrations()      database/*.sql (Reference Only)
     - 001_initial_schema.sql              - create_dimensions.sql
     - Checked by SHA-256 checksums        - create_facts.sql
     - Logged in _schema_migrations        - create_views.sql
     - Enforces forward-only rules         - insert_reference_data.sql
```

### Hierarchy Rules
1. **The Migration Directory is Authoritative:**
   - `database/migrations/` is the **sole authoritative source of truth** for all database objects.
   - Deployments executed via Python (`DatabaseManager.run_migrations()`) or production CI/CD pipelines consume files from `database/migrations/`.
2. **Modular Reference Files (`database/*.sql`):**
   - The files `create_dimensions.sql`, `create_facts.sql`, `create_views.sql`, and `insert_reference_data.sql` are modular, decomposed representations maintained specifically for academic review, modular reading, and interactive execution inside GUI tools such as MySQL Workbench.
3. **Synchronization Protocol:**
   - New schema features (e.g. adding new attributes or tables) MUST NOT be introduced by editing old files.
   - Every change must be created as a new numbered forward migration script in `database/migrations/` (e.g. `002_add_technician_certifications.sql`).
   - Editing an already applied migration script is blocked by automated SHA-256 checksum verification (`MigrationChecksumError`).

---

## 2. Directory Structure and Roles

| Path | Deployment Role | Description |
| :--- | :--- | :--- |
| `database/migrations/001_initial_schema.sql` | **Authoritative Baseline** | Complete initial schema: 6 dimensions, 2 facts, view, reference data, procedures, and calendar. |
| `database/migrations/` | **Authoritative History** | Forward-only migration sequence with cryptographic checksum audit. |
| `database/create_database.sql` | **Deployment Helper** | Non-destructive `CREATE DATABASE IF NOT EXISTS aura_data_mart`. |
| `database/reset_database.sql` | **Development Only** | Destructive `DROP DATABASE IF EXISTS` for test resets (never run in production). |
| `database/verify_mysql.sql` | **Verification Suite** | Standalone 9-point compliance scorecard for MySQL Workbench. |
| `database/create_dimensions.sql` | Modular Reference | Dimension table DDL for documentation and Workbench reference. |
| `database/create_facts.sql` | Modular Reference | Fact table DDL with SHA-256 idempotency constraints. |
| `database/create_views.sql` | Modular Reference | Analytical reporting view with five-state completeness logic. |
| `database/insert_reference_data.sql` | Modular Reference | Reference seeding and calendar procedures for 2023–2026+. |

---

## 3. Financial Integrity & Completeness Boundary

The analytical view `vw_job_profitability_summary` enforces management accounting discipline:
- **No Receipt-Only Inference:** The view does NOT assume a job's expenses are complete simply because receipts are verified. 
- **ETL Responsibility:** The ETL validation module (`etl/validate.py`) is the sole authority responsible for validating voucher completeness and setting `expense_completeness_status`.
- **The Five Completeness States:**
  1. `COMPLETE`: All expected vouchers accounted for and verified $\to$ Gross Contribution is confirmed.
  2. `CONFIRMED_ZERO`: Zero expenses confirmed $\to$ Gross Contribution = Invoiced Revenue.
  3. `UNKNOWN`: No expense records linked $\to$ Gross Contribution is `NULL`.
  4. `INCOMPLETE`: Known vouchers missing $\to$ Gross Contribution is `NULL`, variance is `NULL`.
  5. `UNVERIFIED`: Vouchers recorded without proof $\to$ Gross Contribution is `NULL`, variance is `NULL`.
