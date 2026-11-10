# Aura Cleaning Solutions Data Mart
## Design and Implementation of a Data Mart for Financial and Operational Performance Analysis

**Academic Program:** Bachelor of Science in Computer Science — Data Warehousing & Business Intelligence  
**Case Study:** Aura Cleaning Solutions (Kampala, Uganda)  
**Database Name:** `aura_data_mart`  
**Authoritative Engine:** MySQL 8.0+ (Production Target)  
**Local Unit Testing:** Python 3.10+ / Isolated SQLite Foreign-Key Engine

---

## 1. Project Background & Academic Context

Aura Cleaning Solutions provides professional cleaning, fumigation, upholstery, and maintenance services across Uganda. The business operates across seven canonical service categories:
1. **Residential Cleaning** (Home deep cleans, move-in/move-out)
2. **Commercial Cleaning** (Offices, clinics, retail floor stripping/buffing)
3. **Sofa & Upholstery Cleaning** (Fabric steam cleaning, leather restoration)
4. **Carpet Cleaning** (Wall-to-wall office carpet extraction, area rugs)
5. **Pest Control & Fumigation** (Bedbugs, termites, cockroaches)
6. **Post-Construction Cleaning** (Paint and cement residue scraping)
7. **Laundry Services** (Bulk linen, drapes, curtains)

Historical records originate from disparate Excel workbooks, technician job cards, and signed PDF job completion reports. This data mart integrates these operational records into a Kimball Constellation (Galaxy) schema to enable reliable financial and operational performance analysis without data duplication or arbitrary cost allocations.

---

## 2. Dimensional Architecture & Granularity

The dimensional model implements **6 Dimension Tables** and **2 Fact Tables** connected via a conformed bridge dimension (`Dim_Job`), eliminating Cartesian traps and preventing fact-to-fact joins:

```
  Fact_Job_Performance Grain: Exactly one record per service line delivered within a cleaning job.
  Fact_Job_Expenses Grain:    Exactly one record per individual direct expense transaction / voucher.
  Conformed Bridge:          Dim_Job connects both fact tables at the job grain.
```

### Star Schema Entity Relationships
- `Dim_Date`: Calendar dimension (covers historical operations through 2026+; dynamically extensible via stored procedure).
- `Dim_Location`: Greater Kampala neighborhoods (Kololo, Nakasero, Ntinda, Bugolobi, etc.).
- `Dim_Customer`: Residential, commercial, and corporate client accounts.
- `Dim_Service`: 7 canonical service categories and specific service offerings.
- `Dim_Expense_Category`: Direct cost classifications (Labour Wages, Transport & Fuel, Cleaning Materials & Chemicals, Equipment Maintenance & Rentals, Subcontractor Fees, Other Direct Expenses).
- `Dim_Job`: Central conformed master holding job reference, customer/location links, data completeness flags, SHA-256 provenance hashes, and historical reported profit snapshots.
- `Fact_Job_Performance`: Atomic service delivery line items (quoted fees, delivered revenues). Enforces composite uniqueness on `(source_file_hash, source_record_locator)`.
- `Fact_Job_Expenses`: Atomic direct job expenses backed by physical receipts/vouchers. Enforces composite uniqueness on `(source_file_hash, source_record_locator)`.
- `vw_job_profitability_summary`: Job-level reporting view with strict financial completeness logic and null preservation.

---

## 3. Financial Completeness & Null Integrity Rules

1. **Unknown Financials:** Missing quotes, revenues, or expense figures are preserved strictly as `NULL`. They are **never** silently coerced to `0.00`.
2. **Expense Completeness Distinctions:**
   - **Confirmed Zero Expense (`CONFIRMED_ZERO`):** Work explicitly documented as having incurred zero direct cost (e.g. warranty return or adjacent follow-up).
   - **Missing Expense Information (`UNKNOWN` / `INCOMPLETE`):** No expense records linked or vouchers missing; verified expenses evaluate as `NULL`.
   - **Recorded Unverified Expenses (`UNVERIFIED`):** Vouchers present but unconfirmed.
   - **Verified Complete Expenses (`COMPLETE`):** All direct costs backed by confirmed receipts.
3. **Contribution & Variance Withholding:**
   - Confirmed gross contribution and margin return `NULL` unless both revenue completeness and verified expense completeness are established.
   - Profit variance discrepancy (comparing reported job profit against calculated contribution) is withheld (`NULL`) whenever underlying figures are incomplete.

---

## 4. Source-Record Idempotency Safeguards

To prevent duplicate data loading when reprocessing identical historical reports or renamed file copies:
- Every ingested file generates a **SHA-256 content hash** (`source_file_hash`).
- Every line item records a fine-grained locator (`source_record_locator`), such as `Sheet:Jobs|Row:14` or `Page:2|Table:Expenses|Line:4`.
- Fact tables enforce `UNIQUE KEY (source_file_hash, source_record_locator)`. Even if `March_Report.xlsx` is renamed to `Copy_of_March.xlsx`, the database engine detects identical content and blocks duplicate insertion.

---

## 5. Deployment Procedures: Authoritative Pipeline vs. Modular Reference Files

To prevent schema drift and ensure reproducible schema evolution, this project enforces a single authoritative deployment hierarchy:

```
                  AUTHORITATIVE SOURCE OF TRUTH
                  database/migrations/*.sql
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
            ▼                                   ▼
   AUTOMATED PIPELINE                  MODULAR ARCHITECTURAL VIEW
python database/run_migrations.py      database/*.sql (Reference Only)
- 001_initial_schema.sql               - create_dimensions.sql
- SHA-256 Checksum Guard               - create_facts.sql
- Retry Recovery via Upsert            - create_views.sql
- Logs in _schema_migrations           - insert_reference_data.sql
```

### Path A: Automated Migration Runner (Primary & Authoritative)
The migration engine tracks version history in `_schema_migrations`, verifies cryptographic SHA-256 checksums to detect schema tampering, and applies changes in deterministic alphanumeric sequence.

1. **Create the target database (if not already existing):**
   ```bash
   mysql -u root -p < database/create_database.sql
   ```
2. **Execute the automated migration pipeline:**
   ```bash
   python database/run_migrations.py
   # Or explicitly specifying the engine:
   python database/run_migrations.py --engine mysql
   ```
3. **Dedicated Development Reset (Destructive):**
   - For local development teardowns only: `mysql -u root -p < database/reset_database.sql`
   - *Never execute the reset script in production environments.*

### MySQL DDL Implicit Commit & Retry Recovery
In MySQL 8, all Data Definition Language (DDL) statements (`CREATE TABLE`, `ALTER TABLE`, `CREATE PROCEDURE`, `DROP PROCEDURE`) trigger an **implicit commit**. Unlike SQLite, if a multi-statement migration encounters an error midway through execution, MySQL cannot roll back the preceding DDL statements via a transactional `ROLLBACK`.

To handle this behavior safely:
- All DDL statements in migration files are designed with idempotent guards (`CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE VIEW`, `DROP PROCEDURE IF EXISTS`).
- If an error occurs, the migration is recorded with `status = 'FAILED'`.
- Upon fixing the underlying condition (e.g. permission or syntax issue), re-running `run_migrations()` safely skips already-created objects and **updates the existing audit record** from `FAILED` to `SUCCESS` via an upsert query, preventing duplicate key violations on the unique `version` column.

---

## 6. MySQL Workbench Execution Instructions (Windows / GUI Alternative)

For manual review, academic demonstration, or environments where Python CLI execution is restricted, MySQL Workbench can be used.

### Authoritative Full Baseline via Workbench
1. Launch **MySQL Workbench** and connect to your local MySQL 8 instance (`localhost:3306`).
2. Open and execute **`database/create_database.sql`** to initialize `aura_data_mart`.
3. Open and execute **`database/migrations/001_initial_schema.sql`**:
   - MySQL Workbench handles `DELIMITER $$` directives natively.
   - Click the **Execute (Lightning Bolt)** icon to deploy all dimensions, facts, views, reference data, and calendar procedures in one pass.

### Modular Reference Files (`database/*.sql`)
The individual files in `database/` are decomposed architectural representations maintained for modular academic defense and targeted inspection:
- `database/create_dimensions.sql`: 6 Dimension table DDLs.
- `database/create_facts.sql`: 2 Fact table DDLs with provenance keys.
- `database/create_views.sql`: `vw_job_profitability_summary` view DDL.
- `database/insert_reference_data.sql`: Taxonomy seeds and date generation stored procedures.

### Post-Deployment Verification Audit
Open and execute **`database/verify_mysql.sql`** in Workbench. This script runs a 9-point audit and outputs a structured compliance scorecard:
1. Database collation (`utf8mb4_unicode_ci`)
2. Table count (8 base tables)
3. Reporting view presence (`vw_job_profitability_summary`)
4. Foreign key constraint count (8 relational FKs)
5. SHA-256 provenance idempotency keys on facts
6. Positive expense check constraint
7. Stored procedures (`sp_populate_dim_date`, `sp_extend_dim_date`)
8. Canonical taxonomies (7 service categories, 6 expense categories)
9. Date dimension coverage through 2026-12-31

---

## 7. Automated Test Suites

### A. Isolated SQLite Unit Tests (Offline / Local)
Verifies relational schema creation, surrogate key incrementation, natural key uniqueness, SHA-256 provenance idempotency, referential foreign key enforcement, and financial completeness logic:
```bash
python3 -m unittest tests/test_database.py -v
```
*(Runs in ~0.03 seconds using Python's standard library; requires zero external pip packages).*

### B. Live MySQL 8 Integration Tests
Verifies repeated deployment safety, stored procedures, check constraints, and view calculations against a live MySQL 8 server:
1. Configure credentials in `.env`:
   ```env
   DB_ENGINE=mysql
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_DATABASE=aura_data_mart
   MYSQL_USER=root
   MYSQL_PASSWORD=your_password
   ```
2. Run the integration test suite:
   ```bash
   python3 -m unittest tests/test_mysql_integration.py -v
   ```
   *(If MySQL is not currently running or credentials are unconfigured, tests skip gracefully with clear setup instructions).*
