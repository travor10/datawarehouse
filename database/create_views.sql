-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Script: create_views.sql
-- Target Engine: MySQL 8.0+
-- Description: Analytical reporting view for Job-Level Profitability.
-- =============================================================================

USE aura_data_mart;

-- -----------------------------------------------------------------------------
-- View: vw_job_profitability_summary
-- -----------------------------------------------------------------------------
-- Academic Rationale:
-- In Ralph Kimball dimensional modeling, when two business processes operate
-- at different grains (service lines vs. expense vouchers), direct joining
-- produces Cartesian fan-out and invalid cost duplication.
--
-- This view performs drill-across aggregation by:
-- 1. Aggregating service revenue lines independently at the job_key grain.
-- 2. Aggregating direct expense lines independently at the job_key grain.
-- 3. Merging the aggregated metrics at the conformed Dim_Job bridge.
--
-- Implementation Safeguard:
-- 'confirmed_gross_contribution' is strictly evaluated as NULL if expense or
-- revenue completeness is unverified. This guarantees management never relies
-- on premature or incomplete financial figures.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE VIEW vw_job_profitability_summary AS
SELECT
    j.job_key,
    j.job_reference,
    j.is_reference_provisional,
    j.job_status,
    j.is_revenue_complete,
    j.expense_completeness_status,
    j.profitability_status,
    j.has_incomplete_date,
    j.lead_technician,
    j.source_file,
    j.source_record_id,

    -- Customer & Location Context (Directly from Dim_Job Master - No MIN() aggregation)
    c.customer_key,
    c.customer_code,
    c.customer_name_clean,
    c.customer_type,
    loc.location_key,
    loc.location_name_clean,

    -- Aggregated Revenue Metrics (from Fact_Job_Performance)
    COALESCE(rev.total_quoted_amount, 0.00) AS total_quoted_amount,
    COALESCE(rev.total_revenue_earned, 0.00) AS total_revenue_earned,
    COALESCE(rev.service_lines_count, 0) AS service_lines_count,

    -- Aggregated Direct Cost Metrics (from Fact_Job_Expenses)
    COALESCE(exp_agg.total_verified_expenses, 0.00) AS total_verified_expenses,
    COALESCE(exp_agg.total_unverified_expenses, 0.00) AS total_unverified_expenses,
    (COALESCE(exp_agg.total_verified_expenses, 0.00) + COALESCE(exp_agg.total_unverified_expenses, 0.00)) AS total_recorded_expenses,
    COALESCE(exp_agg.verified_voucher_count, 0) AS verified_voucher_count,
    COALESCE(exp_agg.unverified_voucher_count, 0) AS unverified_voucher_count,

    -- Provisional Contribution (Mathematical difference between revenue and verified expenses)
    (COALESCE(rev.total_revenue_earned, 0.00) - COALESCE(exp_agg.total_verified_expenses, 0.00)) AS provisional_gross_contribution,

    -- Confirmed Contribution (SAFEGUARD: Strictly NULL if data is incomplete or unverified)
    CASE 
        WHEN j.profitability_status = 'CONFIRMED' 
             AND j.is_revenue_complete = TRUE 
             AND j.expense_completeness_status = 'COMPLETE'
        THEN (COALESCE(rev.total_revenue_earned, 0.00) - COALESCE(exp_agg.total_verified_expenses, 0.00))
        ELSE NULL 
    END AS confirmed_gross_contribution,

    -- Contribution Margin Percentage (Based on confirmed contribution)
    CASE 
        WHEN j.profitability_status = 'CONFIRMED' 
             AND j.is_revenue_complete = TRUE 
             AND j.expense_completeness_status = 'COMPLETE'
             AND COALESCE(rev.total_revenue_earned, 0.00) > 0
        THEN ROUND(((COALESCE(rev.total_revenue_earned, 0.00) - COALESCE(exp_agg.total_verified_expenses, 0.00)) * 100.0) / rev.total_revenue_earned, 2)
        ELSE NULL 
    END AS confirmed_gross_margin_pct,

    -- Historical Reported Profit Snapshot (from original job card)
    j.reported_job_profit,

    -- Profit Variance Discrepancy (Audits differences between reported snapshot and calculated contribution)
    CASE 
        WHEN j.reported_job_profit IS NOT NULL
        THEN (j.reported_job_profit - (COALESCE(rev.total_revenue_earned, 0.00) - COALESCE(exp_agg.total_verified_expenses, 0.00)))
        ELSE NULL 
    END AS profit_variance_discrepancy

FROM Dim_Job j
INNER JOIN Dim_Customer c 
    ON j.customer_key = c.customer_key
INNER JOIN Dim_Location loc 
    ON j.location_key = loc.location_key

-- Revenue Aggregation Subquery (Fact_Job_Performance)
LEFT JOIN (
    SELECT 
        job_key,
        SUM(quoted_amount) AS total_quoted_amount,
        SUM(revenue_earned) AS total_revenue_earned,
        COUNT(performance_key) AS service_lines_count
    FROM Fact_Job_Performance
    GROUP BY job_key
) rev ON j.job_key = rev.job_key

-- Expense Aggregation Subquery (Fact_Job_Expenses)
LEFT JOIN (
    SELECT 
        job_key,
        SUM(CASE WHEN is_verified = TRUE THEN expense_amount ELSE 0.00 END) AS total_verified_expenses,
        SUM(CASE WHEN is_verified = FALSE THEN expense_amount ELSE 0.00 END) AS total_unverified_expenses,
        SUM(CASE WHEN is_verified = TRUE THEN 1 ELSE 0 END) AS verified_voucher_count,
        SUM(CASE WHEN is_verified = FALSE THEN 1 ELSE 0 END) AS unverified_voucher_count
    FROM Fact_Job_Expenses
    GROUP BY job_key
) exp_agg ON j.job_key = exp_agg.job_key;
