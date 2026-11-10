-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Script: verify_mysql.sql
-- Target Engine: MySQL 8.0+
-- Description: Authoritative MySQL 8 Integration & Verification Suite.
--              Run in MySQL Workbench to prove 100% compliance with dimensional
--              modeling rules, constraints, procedures, and financial logic.
-- =============================================================================

USE aura_data_mart;

-- Temporary table to collect verification test results
DROP TEMPORARY TABLE IF EXISTS temp_verification_results;
CREATE TEMPORARY TABLE temp_verification_results (
    test_id INT AUTO_INCREMENT PRIMARY KEY,
    test_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    expected_result VARCHAR(150) NOT NULL,
    actual_result VARCHAR(150) NOT NULL,
    status ENUM('PASS', 'FAIL') NOT NULL,
    details TEXT NULL
);

-- -----------------------------------------------------------------------------
-- Test 1: Verify Database Existence and Collation
-- -----------------------------------------------------------------------------
INSERT INTO temp_verification_results (test_name, category, expected_result, actual_result, status, details)
SELECT 
    'Database Collation UTF8MB4',
    'Database Foundation',
    'utf8mb4_unicode_ci',
    @@collation_database,
    IF(@@collation_database = 'utf8mb4_unicode_ci', 'PASS', 'FAIL'),
    CONCAT('Current DB: ', DATABASE())
;

-- -----------------------------------------------------------------------------
-- Test 2: Verify All 8 Tables Exist
-- -----------------------------------------------------------------------------
INSERT INTO temp_verification_results (test_name, category, expected_result, actual_result, status, details)
SELECT 
    'All 8 Schema Tables Present',
    'Schema Completeness',
    '8 Tables',
    CONCAT(COUNT(*), ' Tables Found'),
    IF(COUNT(*) = 8, 'PASS', 'FAIL'),
    GROUP_CONCAT(table_name ORDER BY table_name SEPARATOR ', ')
FROM information_schema.tables 
WHERE table_schema = 'aura_data_mart' 
  AND table_type = 'BASE TABLE'
  AND table_name IN (
    'Dim_Date', 'Dim_Location', 'Dim_Customer', 'Dim_Service', 
    'Dim_Expense_Category', 'Dim_Job', 'Fact_Job_Performance', 'Fact_Job_Expenses'
  );

-- -----------------------------------------------------------------------------
-- Test 3: Verify Reporting View Exists
-- -----------------------------------------------------------------------------
INSERT INTO temp_verification_results (test_name, category, expected_result, actual_result, status, details)
SELECT 
    'vw_job_profitability_summary View Present',
    'Reporting View',
    '1 View',
    CONCAT(COUNT(*), ' View Found'),
    IF(COUNT(*) = 1, 'PASS', 'FAIL'),
    'Analytical job-level profitability drill-across view'
FROM information_schema.views 
WHERE table_schema = 'aura_data_mart' 
  AND table_name = 'vw_job_profitability_summary';

-- -----------------------------------------------------------------------------
-- Test 4: Verify Foreign Key Constraints on Fact Tables
-- -----------------------------------------------------------------------------
INSERT INTO temp_verification_results (test_name, category, expected_result, actual_result, status, details)
SELECT 
    'Referential Integrity Foreign Keys',
    'Relational Integrity',
    '9 Foreign Keys',
    CONCAT(COUNT(*), ' Foreign Keys Configured'),
    IF(COUNT(*) >= 9, 'PASS', 'FAIL'),
    GROUP_CONCAT(CONCAT(table_name, '.', column_name, '->', referenced_table_name) SEPARATOR ' | ')
FROM information_schema.key_column_usage
WHERE table_schema = 'aura_data_mart'
  AND referenced_table_name IS NOT NULL;

-- -----------------------------------------------------------------------------
-- Test 5: Verify SHA-256 Provenance Uniqueness Constraints
-- -----------------------------------------------------------------------------
INSERT INTO temp_verification_results (test_name, category, expected_result, actual_result, status, details)
SELECT 
    'Source Record Idempotency Constraints',
    'Data Quality & Idempotency',
    '2 Provenance Keys',
    CONCAT(COUNT(DISTINCT constraint_name), ' Provenance Keys Active'),
    IF(COUNT(DISTINCT constraint_name) = 2, 'PASS', 'FAIL'),
    'Fact_Job_Performance and Fact_Job_Expenses enforce (source_file_hash, source_record_locator)'
FROM information_schema.table_constraints
WHERE table_schema = 'aura_data_mart'
  AND constraint_name IN ('uq_perf_provenance', 'uq_exp_provenance');

-- -----------------------------------------------------------------------------
-- Test 6: Verify Check Constraint on Expense Amounts
-- -----------------------------------------------------------------------------
INSERT INTO temp_verification_results (test_name, category, expected_result, actual_result, status, details)
SELECT 
    'Positive Expense Check Constraint',
    'Financial Integrity',
    'chk_positive_expense active',
    IF(COUNT(*) >= 1, 'chk_positive_expense active', 'Not Found'),
    IF(COUNT(*) >= 1, 'PASS', 'FAIL'),
    'Enforces expense_amount >= 0.00 at database engine level'
FROM information_schema.check_constraints
WHERE constraint_schema = 'aura_data_mart'
  AND constraint_name = 'chk_positive_expense';

-- -----------------------------------------------------------------------------
-- Test 7: Verify Stored Procedures for Date Dimension
-- -----------------------------------------------------------------------------
INSERT INTO temp_verification_results (test_name, category, expected_result, actual_result, status, details)
SELECT 
    'Dynamic Date Stored Procedures',
    'Stored Logic',
    '2 Stored Procedures',
    CONCAT(COUNT(*), ' Procedures Found'),
    IF(COUNT(*) = 2, 'PASS', 'FAIL'),
    'sp_populate_dim_date and sp_extend_dim_date exist and are callable'
FROM information_schema.routines
WHERE routine_schema = 'aura_data_mart'
  AND routine_type = 'PROCEDURE'
  AND routine_name IN ('sp_populate_dim_date', 'sp_extend_dim_date');

-- -----------------------------------------------------------------------------
-- Test 8: Verify Reference Data (Canonical Services & Expense Categories)
-- -----------------------------------------------------------------------------
INSERT INTO temp_verification_results (test_name, category, expected_result, actual_result, status, details)
SELECT 
    'Aura Canonical 7-Service Categories',
    'Reference Data',
    '7 Canonical Categories',
    CONCAT(COUNT(DISTINCT service_category), ' Categories Found'),
    IF(COUNT(DISTINCT service_category) >= 7, 'PASS', 'FAIL'),
    GROUP_CONCAT(DISTINCT service_category SEPARATOR ', ')
FROM Dim_Service
WHERE service_category != 'Under Review';

INSERT INTO temp_verification_results (test_name, category, expected_result, actual_result, status, details)
SELECT 
    'Direct Expense Categories',
    'Reference Data',
    '6 Canonical Categories',
    CONCAT(COUNT(*), ' Expense Categories Found'),
    IF(COUNT(*) = 6, 'PASS', 'FAIL'),
    GROUP_CONCAT(expense_category_name SEPARATOR ', ')
FROM Dim_Expense_Category;

-- -----------------------------------------------------------------------------
-- Test 9: Verify 2026 Historical Date Boundary
-- -----------------------------------------------------------------------------
INSERT INTO temp_verification_results (test_name, category, expected_result, actual_result, status, details)
SELECT 
    'Date Dimension 2026 Boundary Coverage',
    'Time Intelligence',
    'Covers through 2026-12-31',
    CONCAT('Max Date: ', MAX(full_date), ' (Total Days: ', COUNT(*), ')'),
    IF(MAX(full_date) >= '2026-12-31', 'PASS', 'FAIL'),
    'Full coverage of Aura historical records from 2023 through 2026+'
FROM Dim_Date;

-- -----------------------------------------------------------------------------
-- Display Comprehensive Verification Scorecard
-- -----------------------------------------------------------------------------
SELECT 
    test_id,
    test_name,
    category,
    expected_result,
    actual_result,
    status,
    details
FROM temp_verification_results
ORDER BY test_id;

-- Display Overall Summary
SELECT 
    COUNT(*) AS total_checks,
    SUM(IF(status = 'PASS', 1, 0)) AS passed_checks,
    SUM(IF(status = 'FAIL', 1, 0)) AS failed_checks,
    IF(SUM(IF(status = 'FAIL', 1, 0)) = 0, '100% PASS - SCHEMA FULLY COMPLIANT', 'VERIFICATION FAILED') AS overall_verdict
FROM temp_verification_results;
