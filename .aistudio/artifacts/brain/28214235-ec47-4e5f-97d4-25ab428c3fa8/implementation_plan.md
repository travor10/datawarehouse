# Technical Architecture and Implementation Plan (Approved with Safeguards)
## Aura Cleaning Solutions Data Mart

**Project Title:** Design and Implementation of a Data Mart for Financial and Operational Performance Analysis: A Case Study of Aura Cleaning Solutions  
**Academic Program:** Bachelor of Science in Computer Science — Data Warehousing & Business Intelligence  
**Target RDBMS:** `aura_data_mart` (MySQL 8 Authoritative Production; Isolated SQLite for Local Unit Testing)  
**Schema Architecture:** Ralph Kimball Constellation (Galaxy) Schema — 6 Dimensions, 2 Fact Tables, 1 Job Profitability Reporting View

---

## Incorporated Implementation Safeguards

1. **Expense Completeness & Profitability Safeguards:**
   - In `Dim_Job`, explicit audit attributes track data sufficiency: `is_revenue_complete` (BOOLEAN), `expense_completeness_status` ('COMPLETE', 'INCOMPLETE', 'UNVERIFIED', 'UNKNOWN'), and `profitability_status` ('CONFIRMED', 'PROVISIONAL_INCOMPLETE_COSTS', 'PROVISIONAL_INCOMPLETE_REVENUE', 'UNDETERMINED').
   - In `vw_job_profitability_summary`, **`confirmed_gross_contribution` returns `NULL`** whenever expenses or revenues are incomplete. It only populates when all direct expenses are verified and marked complete.
2. **Database-Level Source Record Uniqueness & Idempotent Loading:**
   - Database-level composite unique keys:
     - `Fact_Job_Performance`: `UNIQUE KEY uq_perf_source (source_file, source_row_id)`
     - `Fact_Job_Expenses`: `UNIQUE KEY uq_exp_source (source_file, source_row_id)`
     - `Dim_Job`: `UNIQUE KEY uq_job_reference (job_reference)`
   - Guarantees at the RDBMS engine level that re-running an ETL batch will never insert duplicate rows.
3. **Elimination of `MIN(customer_key)` and `MIN(location_key)`:**
   - A job in Aura’s business model represents a single service engagement at a single location for a single customer.
   - `Dim_Job` maintains direct foreign keys: `FK customer_key` and `FK location_key`.
   - The ETL validates that all service lines for a given job reference share the identical customer and location. Any conflicting line items are immediately quarantined for review rather than masked with `MIN()`.
4. **Distinction Between Reported, Verified, and Complete Expenses:**
   - `reported_job_profit`: Stored in `Dim_Job` as the unverified snapshot written on original job cards.
   - `aggregated_verified_expenses`: Aggregated sum of verified expense lines (`is_verified = TRUE`).
   - `total_unverified_expenses`: Sum of unverified expense lines (`is_verified = FALSE`).
   - `expense_completeness_status`: Explicitly identifies if vouchers are missing.
5. **Reconciled View, DDL, and Dimension/Fact Relationships:**
   - Direct correspondence between `create_database.sql`, `create_dimensions.sql`, `create_facts.sql`, `create_views.sql`, and `insert_reference_data.sql`.

---

## 1. Final Reconciled ER Diagram

```
                               ┌───────────────────────────┐
                               │         Dim_Date          │
                               ├───────────────────────────┤
                               │PK  date_key (INT)         │
                               │    full_date (DATE)       │
                               │    day_of_week (VARCHAR)  │
                               │    day_of_month (TINYINT) │
                               │    month_num (TINYINT)    │
                               │    month_name (VARCHAR)   │
                               │    quarter (CHAR)         │
                               │    year_num (SMALLINT)    │
                               │    is_weekend (BOOLEAN)   │
                               └─────────────┬─────────────┘
                                             │
                   ┌─────────────────────────┴─────────────────────────┐
                 1 │                                                 1 │
                   │                                                   │
                 * │                                                 * │
  ┌────────────────┴─────────────┐                    ┌────────────────┴─────────────┐
  │     Fact_Job_Performance     │                    │       Fact_Job_Expenses      │
  ├──────────────────────────────┤                    ├──────────────────────────────┤
  │PK  performance_key (BIGINT)  │                    │PK  expense_key (BIGINT)      │
  │FK  job_key (INT) ────────────┼──────────┐         │FK  job_key (INT) ────────────┼─────┐
  │FK  date_key (INT)            │          │         │FK  date_key (INT)            │     │
  │FK  customer_key (INT) ───────┼─────┐    │         │FK  expense_cat_key (INT) ────┼──┐  │
  │FK  service_key (INT) ────────┼──┐  │    │         │FK  location_key (INT) ───────┼─┐│  │
  │FK  location_key (INT) ───────┼─┐│  │    │         │    expense_amount (DECIMAL)  │ ││  │
  │    quoted_amount (DECIMAL)   │ ││  │    │         │    expense_description       │ ││  │
  │    revenue_earned (DECIMAL)  │ ││  │    │         │    is_verified (BOOLEAN)     │ ││  │
  │    service_quantity (DECIMAL)│ ││  │    │         │    has_receipt (BOOLEAN)     │ ││  │
  │    source_file (VARCHAR)     │ ││  │    │         │    source_file (VARCHAR)     │ ││  │
  │    source_row_id (VARCHAR)   │ ││  │    │         │    source_row_id (VARCHAR)   │ ││  │
  │    etl_batch_id (VARCHAR)    │ ││  │    │         │    etl_batch_id (VARCHAR)    │ ││  │
  │UQ (source_file, source_row_id│ ││  │    │         │UQ (source_file, source_row_id│ ││  │
  └──────────────────────────────┘ ││  │    │         └──────────────────────────────┘ ││  │
                                   ││  │    │                                          ││  │
            ┌──────────────────────┘│  │    │          ┌───────────────────────────────┘│  │
            │                       │  │    │          │                                │  │
          * │                     * │  │    │        * │                              * │  │
┌───────────┴──────────┐ ┌──────────┴──┴────┴──────────┴─┐ ┌───────────────────────────┴──┤
│     Dim_Service      │ │                Dim_Job        │ │   Dim_Expense_Category        │
├──────────────────────┤ ├───────────────────────────────┤ ├───────────────────────────────┤
│PK  service_key (INT) │ │PK  job_key (INT)              │ │PK  expense_cat_key (INT)      │
│    service_code      │ │FK  customer_key (INT) ────────┼─┤    expense_category_name      │
│    service_name_clean│ │FK  location_key (INT) ────────┼─┤    cost_type                  │
│    service_name_raw  │ │    job_reference (UNIQUE)     │ └───────────────────────────────┘
│    service_category  │ │    is_reference_provisional   │
│    requires_review   │ │    job_status                 │
└──────────────────────┘ │    is_revenue_complete        │
                         │    expense_completeness_status│
                         │    profitability_status       │
                         │    reported_job_profit (NULL) │
                         │    lead_technician (NULL)     │
                         │    has_incomplete_date        │
                         │    source_file                │
                         │    source_record_id           │
                         │    created_at                 │
                         └───────────────┬───────────────┘
                                         │
           ┌─────────────────────────────┴─────────────────────────────┐
         * │                                                         * │
┌──────────┴───────────┐                                    ┌──────────┴───────────┐
│     Dim_Customer     │                                    │     Dim_Location     │
├──────────────────────┤                                    ├──────────────────────┤
│PK  customer_key (INT)│                                    │PK  location_key (INT)│
│    customer_code     │                                    │    location_name_raw │
│    customer_name_clea│                                    │    location_name_clea│
│    customer_name_raw │                                    │    source_file       │
│    customer_type     │                                    └──────────────────────┘
└──────────────────────┘
```

---

## 2. Module 1: Database Foundation & Reference Data Deliverables

The files generated in this stage form the foundational layer:
- `requirements.txt`: Python dependencies (`mysql-connector-python`, `PyMySQL`, `SQLAlchemy`, `pandas`, `openpyxl`, `pdfplumber`, `pytest`).
- `.env.example`: Safe environment configuration template for MySQL 8 credentials.
- `database/create_database.sql`: MySQL 8 script to initialize `aura_data_mart` with `utf8mb4` character set.
- `database/create_dimensions.sql`: DDL for all 6 Dimension tables, including the reinforced `Dim_Job` table with data quality and completeness indicators.
- `database/create_facts.sql`: DDL for `Fact_Job_Performance` and `Fact_Job_Expenses`, enforcing composite uniqueness constraints on `(source_file, source_row_id)`.
- `database/create_views.sql`: Implementation of `vw_job_profitability_summary` with strict null handling when data is incomplete.
- `database/insert_reference_data.sql`: Seed data for the 7 canonical Aura service categories and standard direct cost classifications.
- `config/database.py`: Robust SQLAlchemy connection factory supporting MySQL 8 and local SQLite compatibility for isolated unit tests.
- `tests/test_database.py`: Executable pytest suite validating schema creation, primary/foreign key enforcement, uniqueness violations, and view queries.
