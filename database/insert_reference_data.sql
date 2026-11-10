-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Script: insert_reference_data.sql
-- Target Engine: MySQL 8.0+
-- Description: Seeds initial reference dimensions with canonical metadata and
--              dynamic date generation supporting historical data through 2026+.
-- =============================================================================

USE aura_data_mart;

-- -----------------------------------------------------------------------------
-- 1. Seed Dim_Expense_Category (Canonical Direct Costs)
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

-- Unclassified fallback flagged for human review
('SRV-UNCLASS', 'Unclassified Service', 'Unclassified / Pending Review', 'Under Review', TRUE)
ON DUPLICATE KEY UPDATE 
    service_name_clean = VALUES(service_name_clean),
    service_category = VALUES(service_category);


-- -----------------------------------------------------------------------------
-- 3. Stored Procedure: Populate Dim_Date for an Arbitrary Date Range
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


-- -----------------------------------------------------------------------------
-- 4. Dynamic Stored Procedure: Extend Calendar to Cover Any Target Date
-- -----------------------------------------------------------------------------
-- Academic Rationale:
-- When an ETL batch encounters a historical or future date outside the currently
-- seeded calendar, this procedure dynamically extends Dim_Date to that date,
-- ensuring referential integrity without manual DBA intervention.
-- -----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_extend_dim_date;

DELIMITER $$
CREATE PROCEDURE sp_extend_dim_date(IN target_date DATE)
BEGIN
    DECLARE min_existing DATE;
    DECLARE max_existing DATE;

    IF target_date IS NOT NULL THEN
        SELECT MIN(full_date), MAX(full_date) INTO min_existing, max_existing FROM Dim_Date;

        IF min_existing IS NULL THEN
            -- Table is empty; seed the single year around target_date
            CALL sp_populate_dim_date(
                STR_TO_DATE(CONCAT(YEAR(target_date), '-01-01'), '%Y-%m-%d'),
                STR_TO_DATE(CONCAT(YEAR(target_date), '-12-31'), '%Y-%m-%d')
            );
        ELSEIF target_date < min_existing THEN
            -- Prepend historical range
            CALL sp_populate_dim_date(target_date, DATE_SUB(min_existing, INTERVAL 1 DAY));
        ELSEIF target_date > max_existing THEN
            -- Append future range
            CALL sp_populate_dim_date(DATE_ADD(max_existing, INTERVAL 1 DAY), target_date);
        END IF;
    END IF;
END$$
DELIMITER ;

-- Seed calendar from 2023-01-01 through 2026-12-31 (encompassing Aura's full historical range)
CALL sp_populate_dim_date('2023-01-01', '2026-12-31');

-- Verification counts
SELECT 'Dim_Expense_Category' AS table_name, COUNT(*) AS record_count FROM Dim_Expense_Category
UNION ALL
SELECT 'Dim_Service', COUNT(*) FROM Dim_Service
UNION ALL
SELECT 'Dim_Date', COUNT(*) FROM Dim_Date;
