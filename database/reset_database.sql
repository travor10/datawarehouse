-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Script: reset_database.sql
-- Target Engine: MySQL 8.0+
-- WARNING: DESTRUCTIVE SCRIPT - FOR LOCAL DEVELOPMENT / TEST ENVIRONMENTS ONLY
-- =============================================================================

-- Academic Context:
-- This script is strictly quarantined from standard deployment pipelines.
-- It tears down the aura_data_mart database completely and recreates a blank
-- instance for development iterations or integration test resets.

DROP DATABASE IF EXISTS aura_data_mart;

CREATE DATABASE aura_data_mart
    CHARACTER SET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;

USE aura_data_mart;

SELECT 
    'Aura Data Mart successfully reset. Ready for DDL execution.' AS status,
    DATABASE() AS current_database;
