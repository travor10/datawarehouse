-- =============================================================================
-- Aura Cleaning Solutions Data Mart
-- Script: create_database.sql
-- Target Engine: MySQL 8.0+
-- Description: Creates the data mart database with utf8mb4 character set.
-- =============================================================================

-- Academic Context:
-- In Data Warehousing, the database instance hosts the dimensional schema.
-- Using utf8mb4 ensures full Unicode support for varied customer and location
-- names encountered in Uganda (e.g., Luganda names and special accents).

DROP DATABASE IF EXISTS aura_data_mart;

CREATE DATABASE aura_data_mart
    CHARACTER SET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;

USE aura_data_mart;

-- Display confirmation
SELECT 
    DATABASE() AS current_database,
    @@character_set_database AS default_charset,
    @@collation_database AS default_collation;
