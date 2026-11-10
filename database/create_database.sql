-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Script: create_database.sql
-- Target Engine: MySQL 8.0+
-- Description: Non-destructive database creation with utf8mb4 collation.
-- =============================================================================

-- Academic Context:
-- Production deployment scripts must NEVER be destructive.
-- Using 'CREATE DATABASE IF NOT EXISTS' ensures that deploying or upgrading
-- schema objects preserves existing historical business records.
-- If a clean development reset is explicitly needed, run 'database/reset_database.sql'.

CREATE DATABASE IF NOT EXISTS aura_data_mart
    CHARACTER SET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;

USE aura_data_mart;

-- Output confirmation
SELECT 
    DATABASE() AS current_database,
    @@character_set_database AS default_charset,
    @@collation_database AS default_collation;
