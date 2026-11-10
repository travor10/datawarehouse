-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Migration: 001_initial_schema.sql
-- Description: Baseline schema deployment (6 Dimensions, 2 Facts, 1 View, Reference Data)
-- Target Engine: MySQL 8.0+
-- =============================================================================

USE aura_data_mart;

-- 1. Dimensions
CREATE TABLE IF NOT EXISTS Dim_Date (
    date_key INT NOT NULL,
    full_date DATE NOT NULL,
    day_of_week VARCHAR(15) NOT NULL,
    day_of_month TINYINT UNSIGNED NOT NULL,
    month_num TINYINT UNSIGNED NOT NULL,
    month_name VARCHAR(15) NOT NULL,
    quarter CHAR(2) NOT NULL,
    year_num SMALLINT UNSIGNED NOT NULL,
    is_weekend BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT pk_dim_date PRIMARY KEY (date_key),
    CONSTRAINT uq_dim_date_full UNIQUE (full_date),
    INDEX idx_dim_date_year_month (year_num, month_num)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Dim_Location (
    location_key INT AUTO_INCREMENT NOT NULL,
    location_name_clean VARCHAR(100) NOT NULL,
    location_name_raw VARCHAR(100) NOT NULL,
    source_file VARCHAR(255) NULL,
    source_file_hash VARCHAR(64) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_location PRIMARY KEY (location_key),
    CONSTRAINT uq_dim_location_clean UNIQUE (location_name_clean)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Dim_Customer (
    customer_key INT AUTO_INCREMENT NOT NULL,
    customer_code VARCHAR(50) NOT NULL,
    customer_name_clean VARCHAR(150) NOT NULL,
    customer_name_raw VARCHAR(150) NOT NULL,
    customer_type VARCHAR(30) NOT NULL DEFAULT 'Individual',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_customer PRIMARY KEY (customer_key),
    CONSTRAINT uq_dim_customer_code UNIQUE (customer_code),
    INDEX idx_dim_customer_name (customer_name_clean),
    INDEX idx_dim_customer_type (customer_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Dim_Service (
    service_key INT AUTO_INCREMENT NOT NULL,
    service_code VARCHAR(30) NOT NULL,
    service_name_clean VARCHAR(100) NOT NULL,
    service_name_raw VARCHAR(100) NOT NULL,
    service_category VARCHAR(50) NOT NULL,
    requires_review BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_service PRIMARY KEY (service_key),
    CONSTRAINT uq_dim_service_code UNIQUE (service_code),
    INDEX idx_dim_service_category (service_category),
    INDEX idx_dim_service_clean_name (service_name_clean)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Dim_Expense_Category (
    expense_cat_key INT AUTO_INCREMENT NOT NULL,
    expense_category_name VARCHAR(50) NOT NULL,
    cost_type VARCHAR(30) NOT NULL DEFAULT 'Direct Operational Cost',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_expense_category PRIMARY KEY (expense_cat_key),
    CONSTRAINT uq_dim_expense_cat_name UNIQUE (expense_category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Dim_Job (
    job_key INT AUTO_INCREMENT NOT NULL,
    job_reference VARCHAR(50) NOT NULL,
    customer_key INT NOT NULL,
    location_key INT NOT NULL,
    is_reference_provisional BOOLEAN NOT NULL DEFAULT FALSE,
    job_status VARCHAR(30) NOT NULL DEFAULT 'Completed',
    is_revenue_complete BOOLEAN NOT NULL DEFAULT FALSE,
    expense_completeness_status VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
    profitability_status VARCHAR(40) NOT NULL DEFAULT 'UNDETERMINED',
    reported_job_profit DECIMAL(12,2) NULL,
    lead_technician VARCHAR(100) NULL,
    has_incomplete_date BOOLEAN NOT NULL DEFAULT FALSE,
    source_file VARCHAR(255) NOT NULL,
    source_file_hash VARCHAR(64) NOT NULL,
    source_record_locator VARCHAR(150) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_job PRIMARY KEY (job_key),
    CONSTRAINT uq_dim_job_reference UNIQUE (job_reference),
    CONSTRAINT fk_dim_job_customer FOREIGN KEY (customer_key) 
        REFERENCES Dim_Customer(customer_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_dim_job_location FOREIGN KEY (location_key) 
        REFERENCES Dim_Location(location_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_dim_job_customer (customer_key),
    INDEX idx_dim_job_location (location_key),
    INDEX idx_dim_job_profit_status (profitability_status),
    INDEX idx_dim_job_exp_complete (expense_completeness_status),
    INDEX idx_dim_job_provenance (source_file_hash, source_record_locator)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Fact Tables
CREATE TABLE IF NOT EXISTS Fact_Job_Performance (
    performance_key BIGINT AUTO_INCREMENT NOT NULL,
    job_key INT NOT NULL,
    date_key INT NULL,
    customer_key INT NOT NULL,
    service_key INT NOT NULL,
    location_key INT NOT NULL,
    quoted_amount DECIMAL(12,2) NULL,
    revenue_earned DECIMAL(12,2) NULL,
    service_quantity DECIMAL(8,2) NULL,
    source_file VARCHAR(255) NOT NULL,
    source_file_hash VARCHAR(64) NOT NULL,
    source_record_locator VARCHAR(150) NOT NULL,
    etl_batch_id VARCHAR(50) NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fact_job_perf PRIMARY KEY (performance_key),
    CONSTRAINT uq_perf_provenance UNIQUE (source_file_hash, source_record_locator),
    CONSTRAINT fk_perf_job FOREIGN KEY (job_key) 
        REFERENCES Dim_Job(job_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_perf_date FOREIGN KEY (date_key) 
        REFERENCES Dim_Date(date_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_perf_customer FOREIGN KEY (customer_key) 
        REFERENCES Dim_Customer(customer_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_perf_service FOREIGN KEY (service_key) 
        REFERENCES Dim_Service(service_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_perf_location FOREIGN KEY (location_key) 
        REFERENCES Dim_Location(location_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_perf_job_key (job_key),
    INDEX idx_perf_date_key (date_key),
    INDEX idx_perf_customer_key (customer_key),
    INDEX idx_perf_service_key (service_key),
    INDEX idx_perf_location_key (location_key),
    INDEX idx_perf_batch (etl_batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Fact_Job_Expenses (
    expense_key BIGINT AUTO_INCREMENT NOT NULL,
    job_key INT NOT NULL,
    date_key INT NULL,
    expense_cat_key INT NOT NULL,
    location_key INT NOT NULL,
    expense_amount DECIMAL(12,2) NOT NULL,
    expense_description VARCHAR(255) NULL,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    has_receipt BOOLEAN NOT NULL DEFAULT FALSE,
    source_file VARCHAR(255) NOT NULL,
    source_file_hash VARCHAR(64) NOT NULL,
    source_record_locator VARCHAR(150) NOT NULL,
    etl_batch_id VARCHAR(50) NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fact_job_expenses PRIMARY KEY (expense_key),
    CONSTRAINT uq_exp_provenance UNIQUE (source_file_hash, source_record_locator),
    CONSTRAINT chk_positive_expense CHECK (expense_amount >= 0.00),
    CONSTRAINT fk_exp_job FOREIGN KEY (job_key) 
        REFERENCES Dim_Job(job_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_exp_date FOREIGN KEY (date_key) 
        REFERENCES Dim_Date(date_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_exp_cat FOREIGN KEY (expense_cat_key) 
        REFERENCES Dim_Expense_Category(expense_cat_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_exp_location FOREIGN KEY (location_key) 
        REFERENCES Dim_Location(location_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_exp_job_key (job_key),
    INDEX idx_exp_date_key (date_key),
    INDEX idx_exp_cat_key (expense_cat_key),
    INDEX idx_exp_location_key (location_key),
    INDEX idx_exp_verified (is_verified),
    INDEX idx_exp_batch (etl_batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Profitability View
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
    c.customer_key,
    c.customer_code,
    c.customer_name_clean,
    c.customer_type,
    loc.location_key,
    loc.location_name_clean,
    rev.total_quoted_amount,
    rev.total_revenue_earned,
    COALESCE(rev.service_lines_count, 0) AS service_lines_count,
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
    j.reported_job_profit,
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
INNER JOIN Dim_Customer c ON j.customer_key = c.customer_key
INNER JOIN Dim_Location loc ON j.location_key = loc.location_key
LEFT JOIN (
    SELECT 
        job_key,
        SUM(quoted_amount) AS total_quoted_amount,
        SUM(revenue_earned) AS total_revenue_earned,
        COUNT(performance_key) AS service_lines_count
    FROM Fact_Job_Performance
    GROUP BY job_key
) rev ON j.job_key = rev.job_key
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

-- 4. Initial Reference Data
INSERT INTO Dim_Expense_Category (expense_category_name, cost_type) VALUES
('Labour Wages', 'Direct Operational Cost'),
('Transport & Fuel', 'Direct Operational Cost'),
('Cleaning Materials & Chemicals', 'Direct Operational Cost'),
('Equipment Maintenance & Rentals', 'Direct Operational Cost'),
('Subcontractor Fees', 'Direct Operational Cost'),
('Other Direct Expenses', 'Direct Operational Cost')
ON DUPLICATE KEY UPDATE cost_type = VALUES(cost_type);

INSERT INTO Dim_Service (service_code, service_name_clean, service_name_raw, service_category, requires_review) VALUES
('SRV-RES-STD', 'Residential Deep Cleaning', 'Residential Deep Cleaning', 'Residential Cleaning', FALSE),
('SRV-RES-MOV', 'Move-in / Move-out House Cleaning', 'Move-in / Move-out Cleaning', 'Residential Cleaning', FALSE),
('SRV-COM-OFF', 'Commercial Office Cleaning', 'Commercial Office Cleaning', 'Commercial Cleaning', FALSE),
('SRV-COM-FLR', 'Commercial Floor Scrubbing & Polishing', 'Commercial Floor Buffing', 'Commercial Cleaning', FALSE),
('SRV-UPH-SOF', 'Sofa & Upholstery Steam Cleaning', 'Sofa Cleaning', 'Sofa & Upholstery Cleaning', FALSE),
('SRV-UPH-MAT', 'Mattress Sanitization & Steam Clean', 'Mattress Cleaning', 'Sofa & Upholstery Cleaning', FALSE),
('SRV-CPT-OFF', 'Wall-to-Wall Office Carpet Cleaning', 'Office Carpet Cleaning', 'Carpet Cleaning', FALSE),
('SRV-CPT-RUG', 'Area Rug Extraction & Deep Wash', 'Rug Wash', 'Carpet Cleaning', FALSE),
('SRV-FUM-GEN', 'General Pest Control & Fumigation', 'General Fumigation', 'Pest Control & Fumigation', FALSE),
('SRV-FUM-BED', 'Bedbug Thermal & Chemical Eradication', 'Bedbug Eradication', 'Pest Control & Fumigation', FALSE),
('SRV-PST-CON', 'Post-Construction Site Clean-up', 'Post-Construction Cleaning', 'Post-Construction Cleaning', FALSE),
('SRV-LND-BLK', 'Commercial Bulk Laundry Service', 'Bulk Laundry', 'Laundry Services', FALSE),
('SRV-LND-CUR', 'Curtains & Drapes Laundry Service', 'Curtains Laundry', 'Laundry Services', FALSE),
('SRV-UNCLASS', 'Unclassified Service', 'Unclassified / Pending Review', 'Under Review', TRUE)
ON DUPLICATE KEY UPDATE 
    service_name_clean = VALUES(service_name_clean),
    service_category = VALUES(service_category);
