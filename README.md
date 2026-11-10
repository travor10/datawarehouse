# Aura Cleaning Solutions Data Mart
## Design and Implementation of a Data Mart for Financial and Operational Performance Analysis

**Academic Project:** Bachelor of Science in Computer Science — Data Warehousing and Business Intelligence  
**Case Study:** Aura Cleaning Solutions (Kampala, Uganda)  
**Database Name:** `aura_data_mart`  
**Authoritative Engine:** MySQL 8.0+  
**Local Test Runner:** Python 3.10+ / SQLite Foreign-Key Engine

---

## 1. Project Background & Academic Context

Aura Cleaning Solutions provides professional cleaning, fumigation, upholstery, and maintenance services in Uganda across seven canonical service categories:
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

### Star Schema Entity Relationship
- `Dim_Date`: Calendar dimension (role-playing, dynamically generated from confirmed job dates).
- `Dim_Location`: Greater Kampala neighborhoods (Kololo, Nakasero, Ntinda, Bugolobi, etc.).
- `Dim_Customer`: Residential, commercial, and corporate client accounts.
- `Dim_Service`: 7 canonical service categories and specific service offerings.
- `Dim_Expense_Category`: Direct cost classifications (Labour, Transport/Fuel, Cleaning Chemicals, Equipment Rentals, Subcontractor Fees, Other Direct Expenses).
- `Dim_Job`: Central conformed master holding job reference, customer/location links, completeness flags, and historical reported profit snapshots.
- `Fact_Job_Performance`: Atomic service delivery line items (quoted fees, delivered revenues).
- `Fact_Job_Expenses`: Atomic direct job expenses backed by physical receipts/vouchers.
- `vw_job_profitability_summary`: Job-level reporting view calculating contribution independently.

---

## 3. Academic Defensibility Guide (BSc Examination Preparation)

When defending this implementation before your lecturer or examination panel, use these explanations:

### A. Why use Surrogate Keys instead of Natural Keys?
- **Plain English:** *"If a customer changes their phone number, or if two reports spell 'Stanbic Bank Ltd' and 'Stanbic Bank' slightly differently, our internal database code (`customer_key = 3`) remains stable and doesn't break foreign key links."*
- **Formal Theory:** **Surrogate Key Decoupling:** Insulates the data warehouse from source operational schema anomalies, provides immutable integer join keys for high query performance, and supports historical tracking without relying on volatile natural business keys.

### B. Why are there two Fact Tables instead of one combined table?
- **Plain English:** *"A cleaning job might have three service lines (cleaning carpets, fumigation, washing curtains) and eight expense receipts (petrol, casual workers, soap). Putting them in one table would duplicate the fuel receipt three times or duplicate the service revenue eight times."*
- **Formal Theory:** **Fact Table Granularity Discipline (Cartesian Fan-Out Prevention):** Each fact table represents an independent business process with distinct measurement grains. Conjoining heterogeneous grains within a single relation violates Boyce-Codd Normal Form (BCNF) in the staging layer and causes multi-valued measure distortion during dimensional aggregation.

### C. Why is Gross Contribution calculated at the Job level rather than the Service level?
- **Plain English:** *"When Aura sends a van with four cleaners and two machines to clean an office, the van petrol receipt covers the entire job. We cannot honestly claim sofa cleaning was 10,000 UGX in petrol and carpet cleaning was 20,000 UGX unless someone measured the fuel for each machine. We evaluate revenue per service, and profitability only where costs are truly known: at the Job level."*
- **Formal Theory:** **Joint Cost Allocation Fallacy & Grain Alignment:** Non-separable joint operational expenses cannot be allocated to lower-grain service lines without verified activity-based costing (ABC) cost drivers. Imputing arbitrary cost splits generates fictitious service profitability figures.

### D. Why are missing values preserved as NULL instead of 0.00?
- **Plain English:** *"If an expense voucher is lost, entering 0.00 tells the company the petrol was free. That would make the job look falsely profitable. Keeping it empty (`NULL`) tells management that the cost is unknown."*
- **Formal Theory:** **Semantic Null Integrity vs. False Magnitude:** Zero ($0.00$) is an empirical measurement signifying absence of cost, whereas `NULL` denotes missing or unobserved data. Preserving `NULL` prevents statistical distortion in aggregations (`AVG`, `SUM`, `COUNT`).

---

## 4. Step-by-Step MySQL 8 and MySQL Workbench Execution Instructions (Windows)

Follow these steps to deploy and verify **Module 1** on a Windows computer running MySQL Server 8.0+ and MySQL Workbench:

### Step 1: Open MySQL Workbench
1. Launch **MySQL Workbench** from the Windows Start menu.
2. Click on your local MySQL connection (typically `Local instance MySQL80` on port `3306`).
3. Enter your MySQL `root` password when prompted.

### Step 2: Execute DDL Scripts in Sequence
In MySQL Workbench, open and execute each script from the `database/` folder using `File -> Open SQL Script...` (or `Ctrl + Shift + O`), and run using the lightning bolt icon (`Execute`):

1. **`database/create_database.sql`**
   - Creates the `aura_data_mart` database with `utf8mb4` encoding.
   - Confirm output: `Database created successfully`.
2. **`database/create_dimensions.sql`**
   - Creates all 6 Dimension tables (`Dim_Date`, `Dim_Location`, `Dim_Customer`, `Dim_Service`, `Dim_Expense_Category`, `Dim_Job`).
   - Sets primary keys, auto-increment surrogate keys, and foreign keys.
3. **`database/create_facts.sql`**
   - Creates `Fact_Job_Performance` and `Fact_Job_Expenses`.
   - Establishes composite unique constraints `(source_file, source_row_id)` for idempotent loading.
4. **`database/create_views.sql`**
   - Compiles `vw_job_profitability_summary` with financial completeness logic.
5. **`database/insert_reference_data.sql`**
   - Seeds the 6 direct expense categories and the 7 canonical Aura service categories.
   - Compiles and runs `sp_populate_dim_date` for 2023–2025 calendar days.

### Step 3: Verify MySQL Workbench Deployment
Run this query in a new Query Tab to confirm all tables and views are present:
```sql
USE aura_data_mart;

SHOW FULL TABLES;
```
Expected output:
- `Dim_Customer` (BASE TABLE)
- `Dim_Date` (BASE TABLE)
- `Dim_Expense_Category` (BASE TABLE)
- `Dim_Job` (BASE TABLE)
- `Dim_Location` (BASE TABLE)
- `Dim_Service` (BASE TABLE)
- `Fact_Job_Expenses` (BASE TABLE)
- `Fact_Job_Performance` (BASE TABLE)
- `vw_job_profitability_summary` (VIEW)

---

## 5. Automated Python Test Suite Execution

The repository contains an automated test suite in `tests/test_database.py` that verifies:
- Table creation and schema completeness.
- Sequential surrogate key auto-incrementation.
- Natural business key uniqueness.
- Idempotent composite source-record uniqueness (`source_file`, `source_row_id`).
- Referential integrity and foreign key cascades.
- Null preservation for unknown financial amounts.
- Job profitability view calculation and completeness guards.
- Reference data seeding for the 7 service categories and 6 expense categories.

To execute the tests:
```bash
python3 -m unittest discover tests -v
```

All 8 tests run and pass without requiring external pip dependencies.
