-- ─────────────────────────────────────────────────────────────────────────────
-- CRMS Schema Migration v2
-- Bengaluru Police Department · Crime Record Management System
--
-- PURPOSE
-- Additive-only migration for authentication + public complaint workflows.
--
-- IMPORTANT
-- - Run AFTER setup_db.sql
-- - Safe for MySQL 8.x
-- - Does NOT drop existing data
--
-- USAGE
-- mysql -u root -p crms < migrate_v2.sql
-- ─────────────────────────────────────────────────────────────────────────────

USE crms;

-- ═════════════════════════════════════════════════════════════════════════════
-- 2. cases
-- Add complainant verification + intake source fields
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE cases
    ADD COLUMN complainant_name
        VARCHAR(120)
        DEFAULT NULL,

    ADD COLUMN complainant_contact
        VARCHAR(120)
        DEFAULT NULL,

    ADD COLUMN complainant_aadhaar
        CHAR(4)
        DEFAULT NULL,

    ADD COLUMN `source`
        ENUM('public','officer')
        NOT NULL
        DEFAULT 'officer';

-- ═════════════════════════════════════════════════════════════════════════════
-- 3. public_complaints
-- Staging table for citizen-submitted complaints
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public_complaints (

    complaint_id INT NOT NULL AUTO_INCREMENT,

    complainant_name VARCHAR(120) NOT NULL,

    contact VARCHAR(120) NOT NULL,

    email VARCHAR(120) DEFAULT NULL,

    aadhaar_last4 CHAR(4) NOT NULL,

    crime_type VARCHAR(60) NOT NULL,

    `location` VARCHAR(120) NOT NULL,

    incident_desc TEXT NOT NULL,

    complaint_mode
        ENUM('Online','Offline')
        NOT NULL
        DEFAULT 'Online',

    `status`
        ENUM('Pending','Reviewed','Promoted','Rejected')
        NOT NULL
        DEFAULT 'Pending',

    promoted_case_id INT DEFAULT NULL,

    submitted_at DATETIME
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    reviewed_by INT DEFAULT NULL,

    reviewed_at DATETIME DEFAULT NULL,

    PRIMARY KEY (complaint_id),

    CONSTRAINT fk_public_case
        FOREIGN KEY (promoted_case_id)
        REFERENCES cases(case_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_public_reviewed_by
        FOREIGN KEY (reviewed_by)
        REFERENCES officers(officer_id)
        ON DELETE SET NULL

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- ═════════════════════════════════════════════════════════════════════════════
-- 4. Seed Development Passwords
--
-- Default password:
--   crms1234
--
-- NOTE:
-- Change before production deployment.
-- ═════════════════════════════════════════════════════════════════════════════

UPDATE officers
SET
    password_hash = '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO',
    `role`        = 'inspector'
WHERE `name` IN (
    'Inspector Arjun Nair',
    'Inspector Vikram Rao',
    'Inspector Meera Iyer'
);

UPDATE officers
SET
    password_hash = '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO',
    `role`        = 'viewer'
WHERE `name` NOT IN (
    'Inspector Arjun Nair',
    'Inspector Vikram Rao',
    'Inspector Meera Iyer'
);

-- ═════════════════════════════════════════════════════════════════════════════
-- 5. Verification Queries
-- ═════════════════════════════════════════════════════════════════════════════

SELECT
    'officers columns' AS chk,
    COUNT(*)           AS has_columns
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'crms'
  AND TABLE_NAME   = 'officers'
  AND COLUMN_NAME IN ('role', 'password_hash');

SELECT
    'cases columns' AS chk,
    COUNT(*)        AS has_columns
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'crms'
  AND TABLE_NAME   = 'cases'
  AND COLUMN_NAME IN (
      'complainant_name',
      'complainant_contact',
      'complainant_aadhaar',
      'source'
  );

SELECT
    'public_complaints table' AS chk,
    COUNT(*)                  AS rows_count
FROM public_complaints;

SELECT
    officer_id,
    `name`,
    `role`,
    IF(password_hash IS NOT NULL, 'SET', 'NULL') AS password_status
FROM officers
ORDER BY officer_id;

-- ═════════════════════════════════════════════════════════════════════════════
-- Migration Complete
-- ═════════════════════════════════════════════════════════════════════════════