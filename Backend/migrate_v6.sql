-- ─────────────────────────────────────────────────────────────────────────────
-- CRMS Schema Migration v6
-- Bengaluru Police Department · Crime Record Management System
--
-- PURPOSE
-- Introduce case_updates (Timeline) and case_evidence (Files metadata) tables.
--
-- IMPORTANT
-- - Run AFTER setup_db.sql and migrate_v2.sql through migrate_v5.sql
-- - Safe for MySQL 8.x
-- - Does NOT drop existing cases or officers data
--
-- USAGE
-- mysql -u root -p crms < migrate_v6.sql
-- ─────────────────────────────────────────────────────────────────────────────

USE crms;

-- ═════════════════════════════════════════════════════════════════════════════
-- 1. Table: case_updates
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS case_updates (
    update_id INT NOT NULL AUTO_INCREMENT,
    case_id INT NOT NULL,
    officer_id INT NOT NULL,
    update_text TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (update_id),
    CONSTRAINT fk_update_case
        FOREIGN KEY (case_id)
        REFERENCES cases(case_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_update_officer
        FOREIGN KEY (officer_id)
        REFERENCES officers(officer_id)
        ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- ═════════════════════════════════════════════════════════════════════════════
-- 2. Table: case_evidence
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS case_evidence (
    evidence_id INT NOT NULL AUTO_INCREMENT,
    case_id INT NOT NULL,
    officer_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size INT NOT NULL,
    description VARCHAR(255) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (evidence_id),
    CONSTRAINT fk_evidence_case
        FOREIGN KEY (case_id)
        REFERENCES cases(case_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_evidence_officer
        FOREIGN KEY (officer_id)
        REFERENCES officers(officer_id)
        ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- ═════════════════════════════════════════════════════════════════════════════
-- 3. Verification Queries
-- ═════════════════════════════════════════════════════════════════════════════

SELECT
    'case_updates table' AS chk,
    COUNT(*) AS rows_count
FROM case_updates;

SELECT
    'case_evidence table' AS chk,
    COUNT(*) AS rows_count
FROM case_evidence;

-- ═════════════════════════════════════════════════════════════════════════════
-- Migration Complete
-- ═════════════════════════════════════════════════════════════════════════════
