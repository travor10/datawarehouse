-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Script: create_facts.sql
-- Target Engine: MySQL 8.0+
-- Description: Non-destructive DDL for Fact tables with robust SHA-256 idempotency.
-- =============================================================================

USE aura_data_mart;

-- -----------------------------------------------------------------------------
-- 1. Fact_Job_Performance
-- -----------------------------------------------------------------------------
-- Granularity: Exactly one record per service line delivered within a cleaning job.
--
-- Robust Idempotency Safeguard:
-- Composite uniqueness on (source_file_hash, source_record_locator) guarantees that
-- renaming a source file cannot bypass duplicate detection. The SHA-256 content
-- hash paired with the exact sheet/page/row locator prevents duplicate records.
-- -----------------------------------------------------------------------------
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


-- -----------------------------------------------------------------------------
-- 2. Fact_Job_Expenses
-- -----------------------------------------------------------------------------
-- Granularity: Exactly one record per individual expense transaction or voucher.
--
-- Robust Idempotency Safeguard:
-- Composite uniqueness on (source_file_hash, source_record_locator) guarantees
-- deterministic, non-duplicative ingestion across all expense vouchers.
-- -----------------------------------------------------------------------------
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
