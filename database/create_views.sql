-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Script: create_views.sql
-- Target Engine: MySQL 8.0+
-- Description: Analytical reporting view for Job-Level Profitability with strict
--              financial completeness and null preservation logic.
-- =============================================================================

USE aura_data_mart;

-- -----------------------------------------------------------------------------
-- View: vw_job_profitability_summary
-- -----------------------------------------------------------------------------
-- Academic Rationale & Financial Rules:
-- 1. Missing Financials: Unknown revenue or unrecorded expenses are preserved
--    strictly as NULL (never silently coerced to 0.00).
-- 2. Expense Status Distinction:
--    - 'CONFIRMED_ZERO': Work performed with verified zero direct cost (e.g. adjacent follow-up).
--    - 'COMPLETE': All vouchers verified and reconciled.
--    - 'INCOMPLETE': Known expense vouchers are missing from records.
--    - 'UNVERIFIED': Expenses recorded but lacking verified receipts.
--    - 'UNKNOWN': Expense status not established.
-- 3. Contribution Withholding: Confirmed gross contribution and margin return
--    NULL unless both revenue completeness and verified expense completeness
--    are fully established.
-- 4. Profit Variance Withholding: Discrepancy between reported snapshot and
--    calculated contribution is withheld (NULL) whenever underlying figures
--    are incomplete.
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
    j.source_file_hash,
    j.source_record_locator,

    -- Customer & Location Context (Directly from Dim_Job Master - No MIN() aggregation)
    c.customer_key,
    c.customer_code,
    c.customer_name_clean,
    c.customer_type,
    loc.location_key,
    loc.location_name_clean,

    -- Aggregated Revenue Metrics (Preserves NULL if no service lines exist)
    rev.total_quoted_amount,
    rev.total_revenue_earned,
    COALESCE(rev.service_lines_count, 0) AS service_lines_count,

    -- Aggregated Direct Cost Metrics
    -- If no expense records exist:
    --   - If expense_completeness_status = 'CONFIRMED_ZERO', amount is 0.00.
    --   - Otherwise, amount is NULL (missing/unknown, NOT zero).
    CASE 
        WHEN exp_agg.expense_records_count > 0 THEN exp_agg.total_verified_expenses
        WHEN j.expense_completeness_status = 'CONFIRMED_ZERO' THEN 0.00
        ELSE NULL 
    END AS total_verified_expenses,

    CASE 
        WHEN exp_agg.expense_records_count > 0 THEN exp_agg.total_unverified_expenses
        WHEN j.expense_completeness_status = 'CONFIRMED_ZERO' THEN 0.00
        ELSE NULL 
    END AS total_unverified_expenses,

    CASE 
        WHEN exp_agg.expense_records_count > 0 
        THEN (COALESCE(exp_agg.total_verified_expenses, 0.00) + COALESCE(exp_agg.total_unverified_expenses, 0.00))
        WHEN j.expense_completeness_status = 'CONFIRMED_ZERO' THEN 0.00
        ELSE NULL 
    END AS total_recorded_expenses,

    COALESCE(exp_agg.verified_voucher_count, 0) AS verified_voucher_count,
    COALESCE(exp_agg.unverified_voucher_count, 0) AS unverified_voucher_count,

    -- Provisional Contribution (Only computed if both revenue and verified cost are known)
    CASE
        WHEN rev.total_revenue_earned IS NOT NULL AND (
            exp_agg.expense_records_count > 0 OR j.expense_completeness_status = 'CONFIRMED_ZERO'
        )
        THEN (rev.total_revenue_earned - CASE 
            WHEN exp_agg.expense_records_count > 0 THEN exp_agg.total_verified_expenses 
            ELSE 0.00 
        END)
        ELSE NULL
    END AS provisional_gross_contribution,

    -- Confirmed Contribution: Strictly NULL unless both revenue and expense completeness are established
    CASE 
        WHEN j.profitability_status = 'CONFIRMED' 
             AND j.is_revenue_complete = TRUE 
             AND j.expense_completeness_status IN ('COMPLETE', 'CONFIRMED_ZERO')
             AND rev.total_revenue_earned IS NOT NULL
        THEN (rev.total_revenue_earned - CASE 
            WHEN exp_agg.expense_records_count > 0 THEN exp_agg.total_verified_expenses 
            ELSE 0.00 
        END)
        ELSE NULL 
    END AS confirmed_gross_contribution,

    -- Confirmed Margin Percentage: Withheld (NULL) if contribution or revenue is incomplete
    CASE 
        WHEN j.profitability_status = 'CONFIRMED' 
             AND j.is_revenue_complete = TRUE 
             AND j.expense_completeness_status IN ('COMPLETE', 'CONFIRMED_ZERO')
             AND rev.total_revenue_earned IS NOT NULL
             AND rev.total_revenue_earned > 0.00
        THEN ROUND(((rev.total_revenue_earned - CASE 
            WHEN exp_agg.expense_records_count > 0 THEN exp_agg.total_verified_expenses 
            ELSE 0.00 
        END) * 100.0) / rev.total_revenue_earned, 2)
        ELSE NULL 
    END AS confirmed_gross_margin_pct,

    -- Historical Reported Profit Snapshot (from original job card)
    j.reported_job_profit,

    -- Profit Variance Discrepancy: Withheld (NULL) unless BOTH reported profit and confirmed contribution exist
    CASE 
        WHEN j.reported_job_profit IS NOT NULL
             AND j.profitability_status = 'CONFIRMED' 
             AND j.is_revenue_complete = TRUE 
             AND j.expense_completeness_status IN ('COMPLETE', 'CONFIRMED_ZERO')
             AND rev.total_revenue_earned IS NOT NULL
        THEN (j.reported_job_profit - (rev.total_revenue_earned - CASE 
            WHEN exp_agg.expense_records_count > 0 THEN exp_agg.total_verified_expenses 
            ELSE 0.00 
        END))
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
        SUM(CASE WHEN is_verified = FALSE THEN 1 ELSE 0 END) AS unverified_voucher_count,
        COUNT(expense_key) AS expense_records_count
    FROM Fact_Job_Expenses
    GROUP BY job_key
) exp_agg ON j.job_key = exp_agg.job_key;
