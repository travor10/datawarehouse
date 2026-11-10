-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Script: insert_reference_data.sql
-- Target Engine: MySQL 8.0+
-- Description: Seeds initial reference dimensions with canonical metadata.
-- =============================================================================

USE aura_data_mart;

-- -----------------------------------------------------------------------------
-- 1. Seed Dim_Expense_Category
-- -----------------------------------------------------------------------------
INSERT INTO Dim_Expense_Category (expense_category_name, cost_type) VALUES
('Labour Wages', 'Direct Operational Cost'),
('Transport & Fuel', 'Direct Operational Cost'),
('Cleaning Materials & Chemicals', 'Direct Operational Cost'),
('Equipment Maintenance & Rentals', 'Direct Operational Cost'),
('Subcontractor Fees', 'Direct Operational Cost'),
('Other Direct Expenses', 'Direct Operational Cost')
ON DUPLICATE KEY UPDATE cost_type = VALUES(cost_type);


-- -----------------------------------------------------------------------------
-- 2. Seed Dim_Service (Aura's Canonical 7-Service Portfolio)
-- -----------------------------------------------------------------------------
INSERT INTO Dim_Service (service_code, service_name_clean, service_name_raw, service_category, requires_review) VALUES
-- 1. Residential Cleaning
('SRV-RES-STD', 'Residential Deep Cleaning', 'Residential Deep Cleaning', 'Residential Cleaning', FALSE),
('SRV-RES-MOV', 'Move-in / Move-out House Cleaning', 'Move-in / Move-out Cleaning', 'Residential Cleaning', FALSE),

-- 2. Commercial Cleaning
('SRV-COM-OFF', 'Commercial Office Cleaning', 'Commercial Office Cleaning', 'Commercial Cleaning', FALSE),
('SRV-COM-FLR', 'Commercial Floor Scrubbing & Polishing', 'Commercial Floor Buffing', 'Commercial Cleaning', FALSE),

-- 3. Sofa & Upholstery Cleaning
('SRV-UPH-SOF', 'Sofa & Upholstery Steam Cleaning', 'Sofa Cleaning', 'Sofa & Upholstery Cleaning', FALSE),
('SRV-UPH-MAT', 'Mattress Sanitization & Steam Clean', 'Mattress Cleaning', 'Sofa & Upholstery Cleaning', FALSE),

-- 4. Carpet Cleaning
('SRV-CPT-OFF', 'Wall-to-Wall Office Carpet Cleaning', 'Office Carpet Cleaning', 'Carpet Cleaning', FALSE),
('SRV-CPT-RUG', 'Area Rug Extraction & Deep Wash', 'Rug Wash', 'Carpet Cleaning', FALSE),

-- 5. Pest Control & Fumigation
('SRV-FUM-GEN', 'General Pest Control & Fumigation', 'General Fumigation', 'Pest Control & Fumigation', FALSE),
('SRV-FUM-BED', 'Bedbug Thermal & Chemical Eradication', 'Bedbug Eradication', 'Pest Control & Fumigation', FALSE),

-- 6. Post-Construction Cleaning
('SRV-PST-CON', 'Post-Construction Site Clean-up', 'Post-Construction Cleaning', 'Post-Construction Cleaning', FALSE),

-- 7. Laundry Services
('SRV-LND-BLK', 'Commercial Bulk Laundry Service', 'Bulk Laundry', 'Laundry Services', FALSE),
('SRV-LND-CUR', 'Curtains & Drapes Laundry Service', 'Curtains Laundry', 'Laundry Services', FALSE),

-- Catch-all for unmapped services flagged for review
('SRV-UNCLASS', 'Unclassified Service', 'Unclassified / Pending Review', 'Under Review', TRUE)
ON DUPLICATE KEY UPDATE 
    service_name_clean = VALUES(service_name_clean),
    service_category = VALUES(service_category);


-- -----------------------------------------------------------------------------
-- 3. Dynamic Stored Procedure: Generate Dim_Date Range
-- -----------------------------------------------------------------------------
-- Academic Rationale:
-- Generates date records strictly within the active operational boundary
-- of Aura's historical trading records.
-- -----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_populate_dim_date;

DELIMITER $$
CREATE PROCEDURE sp_populate_dim_date(IN start_date DATE, IN end_date DATE)
BEGIN
    DECLARE current_dt DATE;
    SET current_dt = start_date;

    WHILE current_dt <= end_date DO
        INSERT INTO Dim_Date (
            date_key,
            full_date,
            day_of_week,
            day_of_month,
            month_num,
            month_name,
            quarter,
            year_num,
            is_weekend
        ) VALUES (
            CAST(DATE_FORMAT(current_dt, '%Y%m%d') AS UNSIGNED),
            current_dt,
            DAYNAME(current_dt),
            DAY(current_dt),
            MONTH(current_dt),
            MONTHNAME(current_dt),
            CONCAT('Q', QUARTER(current_dt)),
            YEAR(current_dt),
            CASE WHEN DAYOFWEEK(current_dt) IN (1, 7) THEN TRUE ELSE FALSE END
        )
        ON DUPLICATE KEY UPDATE full_date = VALUES(full_date);

        SET current_dt = DATE_ADD(current_dt, INTERVAL 1 DAY);
    END WHILE;
END$$
DELIMITER ;

-- Generate initial calendar for 2023 through 2025 (Expanded dynamically by ETL if older/newer dates exist)
CALL sp_populate_dim_date('2023-01-01', '2025-12-31');

-- Verification counts
SELECT 'Dim_Expense_Category' AS table_name, COUNT(*) AS record_count FROM Dim_Expense_Category
UNION ALL
SELECT 'Dim_Service', COUNT(*) FROM Dim_Service
UNION ALL
SELECT 'Dim_Date', COUNT(*) FROM Dim_Date;
