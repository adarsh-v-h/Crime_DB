-- ─────────────────────────────────────────────────────────────────────────────
-- CRMS Schema Migration v5
-- Admin-Reviewed Assignment Workflow
--
-- PURPOSE
-- Refactor automated assignment system to generate recommendations instead of
-- direct assignments. Admins review and approve recommendations before cases
-- are created.
--
-- IMPORTANT
-- - Run AFTER setup_db.sql and migrate_v2.sql, migrate_v3.sql, migrate_v4.sql
-- - Safe for MySQL 8.x / 5.7+
-- - Does NOT drop existing data
-- - Idempotent (safe to run multiple times)
--
-- USAGE
-- mysql -u root -p crms < migrate_v5.sql
-- ─────────────────────────────────────────────────────────────────────────────

USE crms;

-- ═════════════════════════════════════════════════════════════════════════════
-- 1. assignment_recommendations
-- Stores algorithm-generated recommendations and admin approval decisions
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS assignment_recommendations (
    recommendation_id INT NOT NULL AUTO_INCREMENT,
    
    complaint_id INT NOT NULL,
    
    recommended_officer_ids JSON NOT NULL,
    
    status ENUM('pending', 'approved', 'rejected')
        NOT NULL
        DEFAULT 'pending',
    
    admin_approved_officer_ids JSON DEFAULT NULL,
    
    approved_by INT DEFAULT NULL,
    
    approved_at DATETIME DEFAULT NULL,
    
    rejection_reason VARCHAR(255) DEFAULT NULL,
    
    created_at DATETIME
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,
    
    updated_at DATETIME
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (recommendation_id),
    
    UNIQUE KEY uk_complaint_pending (complaint_id, status),
    
    CONSTRAINT fk_rec_complaint
        FOREIGN KEY (complaint_id)
        REFERENCES public_complaints(complaint_id)
        ON DELETE CASCADE,
    
    CONSTRAINT fk_rec_approved_by
        FOREIGN KEY (approved_by)
        REFERENCES officers(officer_id)
        ON DELETE SET NULL,
    
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- ═════════════════════════════════════════════════════════════════════════════
-- 2. Verification Queries
-- ═════════════════════════════════════════════════════════════════════════════

SELECT
    'assignment_recommendations table' AS chk,
    COUNT(*) AS rows_count
FROM assignment_recommendations;

SELECT
    'assignment_recommendations columns' AS chk,
    GROUP_CONCAT(COLUMN_NAME) AS columns_present
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'crms'
  AND TABLE_NAME = 'assignment_recommendations';

-- ═════════════════════════════════════════════════════════════════════════════
-- Migration Complete
-- ═════════════════════════════════════════════════════════════════════════════
