-- ─────────────────────────────────────────────────────────────────────────────
-- CRMS Schema Migration v3
-- Bengaluru Police Department · Crime Record Management System
--
-- PURPOSE
-- Introduce case access request workflow staging table + seed developmental data.
--
-- IMPORTANT
-- - Run AFTER setup_db.sql and migrate_v2.sql
-- - Safe for MySQL 8.x
-- - Does NOT drop existing cases or officers data
--
-- USAGE
-- mysql -u root -p crms < migrate_v3.sql
-- ─────────────────────────────────────────────────────────────────────────────

USE crms;

-- ═════════════════════════════════════════════════════════════════════════════
-- 1. case_access_requests
-- Staging table for citizen-submitted case access requests
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS case_access_requests (
    request_id       INT          NOT NULL AUTO_INCREMENT,
    case_id          INT          NOT NULL,
    requester_name   VARCHAR(120) NOT NULL,
    requester_email  VARCHAR(120) NOT NULL,
    requester_number VARCHAR(20)  NOT NULL,
    reason           TEXT         NOT NULL,
    `status`         ENUM('Pending', 'Rejected', 'Accepted') NOT NULL DEFAULT 'Pending',
    requested_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by       INT          DEFAULT NULL,
    decided_at       DATETIME     DEFAULT NULL,
    
    PRIMARY KEY (request_id),
    
    CONSTRAINT fk_access_request_case
        FOREIGN KEY (case_id)
        REFERENCES cases (case_id)
        ON DELETE CASCADE,
        
    CONSTRAINT fk_access_request_officer
        FOREIGN KEY (decided_by)
        REFERENCES officers (officer_id)
        ON DELETE SET NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- ═════════════════════════════════════════════════════════════════════════════
-- 2. Seed Development Access Requests
--
-- Note: Case IDs match the seeded case IDs from setup_db.sql:
-- - Case ID 1: Cyber Fraud - Wire Transfer Scam (Assigned to Officer 1 Priya/Arjun)
-- - Case ID 2: Vehicle Theft - Swift Dzire (Assigned to Officer 2 Priya)
-- - Case ID 3: Assault at Commercial Street (Assigned to Officer 4 Deepa/Ravi)
-- ═════════════════════════════════════════════════════════════════════════════

INSERT INTO case_access_requests 
    (case_id, requester_name, requester_email, requester_number, reason, `status`, requested_at, decided_by, decided_at)
VALUES
(
    1, 
    'Arvind Swamy', 
    'arvind.swamy@example.com', 
    '+91-9845012345', 
    'Legal defense counsel representing the victim requires authorized access to full incident logs and wire transfer forensic reports.', 
    'Pending', 
    NOW() - INTERVAL 1 DAY, 
    NULL, 
    NULL
),
(
    2, 
    'Sunita Rao', 
    'sunita.rao@example.com', 
    '+91-9876543210', 
    'Journalistic enquiry regarding the swift vehicle recovery and GPS tracking efficiency of Bengaluru Police cyber cell.', 
    'Accepted', 
    NOW() - INTERVAL 3 DAY, 
    1, 
    NOW() - INTERVAL 2 DAY
),
(
    3, 
    'Unknown Client', 
    'unknown@privacy.io', 
    '+91-9000000000', 
    'Requests detailed dossier of commercial street altercation logs for private arbitration services.', 
    'Rejected', 
    NOW() - INTERVAL 5 DAY, 
    4, 
    NOW() - INTERVAL 4 DAY
);

-- ═════════════════════════════════════════════════════════════════════════════
-- 3. Verification Queries
-- ═════════════════════════════════════════════════════════════════════════════

SELECT
    'case_access_requests table' AS chk,
    COUNT(*)                     AS rows_count
FROM case_access_requests;

SELECT 
    request_id,
    case_id,
    requester_name,
    `status`
FROM case_access_requests;
