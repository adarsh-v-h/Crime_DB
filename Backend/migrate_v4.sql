-- ─────────────────────────────────────────────────────────────────────────────
-- CRMS Schema Migration v4
-- Bengaluru Police Department · Crime Record Management System
--
-- PURPOSE
-- Introduce admin role and seed one admin user account.
--
-- IMPORTANT
-- - Run AFTER setup_db.sql, migrate_v2.sql, and migrate_v3.sql
-- - Safe for MySQL 8.x
-- - Does NOT drop existing officers or cases data
-- - Additive only: extends ENUM, adds one admin user
--
-- USAGE
-- mysql -u root -p crms < migrate_v4.sql
-- ─────────────────────────────────────────────────────────────────────────────

USE crms;

-- ═════════════════════════════════════════════════════════════════════════════
-- 1. Extend role ENUM to include 'admin'
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE officers
    MODIFY COLUMN `role`
        ENUM('admin', 'inspector', 'viewer')
        NOT NULL
        DEFAULT 'viewer';

-- ═════════════════════════════════════════════════════════════════════════════
-- 2. Seed one admin account
-- Default password: crms1234 (same as other test accounts)
-- ═════════════════════════════════════════════════════════════════════════════

INSERT INTO officers (
    `name`,
    `rank`,
    badge,
    station,
    phone,
    email,
    join_date,
    password_hash,
    `role`
) VALUES (
    'Administrator',
    'Administrator',
    'ADM-0001',
    'Central Command',
    '+91-80-2000-0000',
    'admin@bpd.gov.in',
    CURDATE(),
    '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO',
    'admin'
);

-- ═════════════════════════════════════════════════════════════════════════════
-- 3. Verification Queries
-- ═════════════════════════════════════════════════════════════════════════════

SELECT
    'role ENUM extended' AS operation,
    COUNT(*) AS admin_count
FROM officers
WHERE `role` = 'admin';

SELECT
    officer_id,
    `name`,
    badge,
    `role`
FROM officers
WHERE `role` = 'admin'
LIMIT 1;
