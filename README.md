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

## 5. Deployment Procedures: MySQL 8 (Authoritative)

### Non-Destructive Standard Deployment
All standard DDL scripts use `CREATE DATABASE IF NOT EXISTS` and `CREATE TABLE IF NOT EXISTS` to ensure repeated deployment safety without data loss:

1. **`database/create_database.sql`**: Initializes `aura_data_mart` non-destructively.
2. **`database/create_dimensions.sql`**: Deploys the 6 Dimension tables.
3. **`database/create_facts.sql`**: Deploys the 2 Fact tables with foreign keys and SHA-256 idempotency.
4. **`database/create_views.sql`**: Compiles `vw_job_profitability_summary`.
5. **`database/insert_reference_data.sql`**: Seeds reference data and populates calendar dates from 2023 through 2026.

### Dedicated Development Reset (Destructive)
For local development or testing environments where a fresh reset is explicitly required:
- Run **`database/reset_database.sql`** (contains `DROP DATABASE IF EXISTS`).
- Never run this script in production.

---

## 6. Step-by-Step MySQL Workbench Execution Instructions (Windows)

1. **Launch MySQL Workbench** and connect to your local MySQL 8 instance (`localhost:3306`).
2. **Open and execute scripts** via `File -> Open SQL Script...` in this exact order:
   - `database/create_database.sql`
   - `database/create_dimensions.sql`
   - `database/create_facts.sql`
   - `database/create_views.sql`
   - `database/insert_reference_data.sql`
3. **Execute Integration Verification:**
   - Open and run **`database/verify_mysql.sql`**.
   - This script runs a 9-point verification check and outputs an automated scorecard:
     - Database collation (`utf8mb4_unicode_ci`)
     - Table count (8 base tables)
     - Reporting view presence
     - Foreign key constraint count
     - SHA-256 provenance keys
     - Positive expense check constraint
     - Stored procedures (`sp_populate_dim_date`, `sp_extend_dim_date`)
     - 7 canonical service categories & 6 expense categories
     - Date dimension coverage through 2026-12-31

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
