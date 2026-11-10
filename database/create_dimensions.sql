-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Script: create_dimensions.sql
-- Target Engine: MySQL 8.0+
-- Description: DDL for the 6 Dimension tables adhering to Kimball methodology.
-- =============================================================================

USE aura_data_mart;

-- Disable foreign key checks for clean re-creation
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS Dim_Job;
DROP TABLE IF EXISTS Dim_Service;
DROP TABLE IF EXISTS Dim_Customer;
DROP TABLE IF EXISTS Dim_Location;
DROP TABLE IF EXISTS Dim_Expense_Category;
DROP TABLE IF EXISTS Dim_Date;

SET FOREIGN_KEY_CHECKS = 1;

-- -----------------------------------------------------------------------------
-- 1. Dim_Date (Role-Playing Calendar Dimension)
-- -----------------------------------------------------------------------------
-- Academic Rationale:
-- Pre-calculates calendar hierarchies. Enables time-series slicing (quarter,
-- month, day-of-week) without expensive SQL runtime date conversions.
-- -----------------------------------------------------------------------------
CREATE TABLE Dim_Date (
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
    CONSTRAINT uq_dim_date_full UNIQUE (full_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_dim_date_year_month ON Dim_Date(year_num, month_num);


-- -----------------------------------------------------------------------------
-- 2. Dim_Location (Geographic Hierarchy Dimension)
-- -----------------------------------------------------------------------------
-- Academic Rationale:
-- Preserves verbatim text as well as standardized neighborhood/zone names
-- within the Greater Kampala metropolitan area.
-- -----------------------------------------------------------------------------
CREATE TABLE Dim_Location (
    location_key INT AUTO_INCREMENT NOT NULL,
    location_name_clean VARCHAR(100) NOT NULL,
    location_name_raw VARCHAR(100) NOT NULL,
    source_file VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_location PRIMARY KEY (location_key),
    CONSTRAINT uq_dim_location_clean UNIQUE (location_name_clean)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 3. Dim_Customer (Customer Dimension)
-- -----------------------------------------------------------------------------
-- Academic Rationale:
-- Captures individual clients, commercial establishments, and corporate accounts.
-- Surrogate key decouples the data mart from volatile natural names.
-- -----------------------------------------------------------------------------
CREATE TABLE Dim_Customer (
    customer_key INT AUTO_INCREMENT NOT NULL,
    customer_code VARCHAR(50) NOT NULL,
    customer_name_clean VARCHAR(150) NOT NULL,
    customer_name_raw VARCHAR(150) NOT NULL,
    customer_type VARCHAR(30) NOT NULL DEFAULT 'Individual',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_customer PRIMARY KEY (customer_key),
    CONSTRAINT uq_dim_customer_code UNIQUE (customer_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_dim_customer_name ON Dim_Customer(customer_name_clean);
CREATE INDEX idx_dim_customer_type ON Dim_Customer(customer_type);


-- -----------------------------------------------------------------------------
-- 4. Dim_Service (Service Portfolio Dimension)
-- -----------------------------------------------------------------------------
-- Academic Rationale:
-- Represents the 7 core service categories of Aura Cleaning Solutions:
-- (Residential, Commercial, Sofa/Upholstery, Carpet, Fumigation, Post-Construction, Laundry).
-- -----------------------------------------------------------------------------
CREATE TABLE Dim_Service (
    service_key INT AUTO_INCREMENT NOT NULL,
    service_code VARCHAR(30) NOT NULL,
    service_name_clean VARCHAR(100) NOT NULL,
    service_name_raw VARCHAR(100) NOT NULL,
    service_category VARCHAR(50) NOT NULL,
    requires_review BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_service PRIMARY KEY (service_key),
    CONSTRAINT uq_dim_service_code UNIQUE (service_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_dim_service_category ON Dim_Service(service_category);
CREATE INDEX idx_dim_service_clean_name ON Dim_Service(service_name_clean);


-- -----------------------------------------------------------------------------
-- 5. Dim_Expense_Category (Direct Operational Cost Dimension)
-- -----------------------------------------------------------------------------
-- Academic Rationale:
-- Classifies direct job costs (Labour, Fuel/Transport, Cleaning Chemicals, etc.)
-- to permit cost breakdown analysis without distorting service-line facts.
-- -----------------------------------------------------------------------------
CREATE TABLE Dim_Expense_Category (
    expense_cat_key INT AUTO_INCREMENT NOT NULL,
    expense_category_name VARCHAR(50) NOT NULL,
    cost_type VARCHAR(30) NOT NULL DEFAULT 'Direct Operational Cost',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_expense_category PRIMARY KEY (expense_cat_key),
    CONSTRAINT uq_dim_expense_cat_name UNIQUE (expense_category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 6. Dim_Job (Conformed Bridge Entity & Job Master Dimension)
-- -----------------------------------------------------------------------------
-- Academic Rationale:
-- Serves as the central conformed dimension bridging Fact_Job_Performance and
-- Fact_Job_Expenses without creating an invalid fact-to-fact relationship.
-- Embeds data completeness flags and audit indicators to enforce strict
-- financial integrity rules.
-- -----------------------------------------------------------------------------
CREATE TABLE Dim_Job (
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
    source_record_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_job PRIMARY KEY (job_key),
    CONSTRAINT uq_dim_job_reference UNIQUE (job_reference),
    CONSTRAINT fk_dim_job_customer FOREIGN KEY (customer_key) 
        REFERENCES Dim_Customer(customer_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_dim_job_location FOREIGN KEY (location_key) 
        REFERENCES Dim_Location(location_key)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_dim_job_customer ON Dim_Job(customer_key);
CREATE INDEX idx_dim_job_location ON Dim_Job(location_key);
CREATE INDEX idx_dim_job_profit_status ON Dim_Job(profitability_status);
CREATE INDEX idx_dim_job_exp_complete ON Dim_Job(expense_completeness_status);
CREATE INDEX idx_dim_job_source ON Dim_Job(source_file, source_record_id);
