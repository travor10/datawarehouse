-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Script: create_facts.sql
-- Target Engine: MySQL 8.0+
-- Description: DDL for the 2 Fact tables adhering to strict grain discipline.
-- =============================================================================

USE aura_data_mart;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS Fact_Job_Expenses;
DROP TABLE IF EXISTS Fact_Job_Performance;

SET FOREIGN_KEY_CHECKS = 1;

-- -----------------------------------------------------------------------------
-- 1. Fact_Job_Performance
-- -----------------------------------------------------------------------------
-- Granularity: Exactly one record per service line delivered within a cleaning job.
--
-- Academic Rationale:
-- Preserves the atomic service revenue transaction. If a job entails two distinct
-- services (e.g. Sofa Cleaning and Carpet Cleaning), each service appears as its
-- own line item with its respective quantity, quoted estimate, and earned revenue.
-- Job-level expenses are strictly EXCLUDED from this table to avoid multi-valued
-- cost duplication.
--
-- Database Safeguard:
-- Composite uniqueness on (source_file, source_row_id) guarantees idempotent
-- ETL processing and prevents duplicate rows if a report is reprocessed.
-- -----------------------------------------------------------------------------
CREATE TABLE Fact_Job_Performance (
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
    source_row_id VARCHAR(100) NOT NULL,
    etl_batch_id VARCHAR(50) NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fact_job_perf PRIMARY KEY (performance_key),
    CONSTRAINT uq_perf_source_record UNIQUE (source_file, source_row_id),
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
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_perf_job_key ON Fact_Job_Performance(job_key);
CREATE INDEX idx_perf_date_key ON Fact_Job_Performance(date_key);
CREATE INDEX idx_perf_customer_key ON Fact_Job_Performance(customer_key);
CREATE INDEX idx_perf_service_key ON Fact_Job_Performance(service_key);
CREATE INDEX idx_perf_location_key ON Fact_Job_Performance(location_key);
CREATE INDEX idx_perf_batch ON Fact_Job_Performance(etl_batch_id);


-- -----------------------------------------------------------------------------
-- 2. Fact_Job_Expenses
-- -----------------------------------------------------------------------------
-- Granularity: Exactly one record per individual expense transaction or voucher.
--
-- Academic Rationale:
-- Captures direct job expenses at their natural disbursement grain (individual
-- receipts for fuel, casual labour day-wages, cleaning chemicals, equipment rentals).
-- Expenses are tied to the parent job via job_key. They are NEVER allocated
-- to individual service lines without empirical activity-based cost drivers.
--
-- Database Safeguard:
-- Composite uniqueness on (source_file, source_row_id) guarantees idempotent
-- ETL processing and prevents duplicate rows if a report is reprocessed.
-- -----------------------------------------------------------------------------
CREATE TABLE Fact_Job_Expenses (
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
    source_row_id VARCHAR(100) NOT NULL,
    etl_batch_id VARCHAR(50) NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fact_job_expenses PRIMARY KEY (expense_key),
    CONSTRAINT uq_exp_source_record UNIQUE (source_file, source_row_id),
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
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_exp_job_key ON Fact_Job_Expenses(job_key);
CREATE INDEX idx_exp_date_key ON Fact_Job_Expenses(date_key);
CREATE INDEX idx_exp_cat_key ON Fact_Job_Expenses(expense_cat_key);
CREATE INDEX idx_exp_location_key ON Fact_Job_Expenses(location_key);
CREATE INDEX idx_exp_verified ON Fact_Job_Expenses(is_verified);
CREATE INDEX idx_exp_batch ON Fact_Job_Expenses(etl_batch_id);
