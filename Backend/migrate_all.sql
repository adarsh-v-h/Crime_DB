-- ─────────────────────────────────────────────────────────────────────────────
-- CRMS Consolidated Migration
-- This single migration creates the complete schema and seeds demo data.
-- It is intended to replace: setup_db.sql, migrate_v2.sql, migrate_v3.sql,
-- migrate_v4.sql, migrate_v5.sql, migrate_v6.sql, migrate_v7.sql
--
-- Usage:
--   mysql -u <user> -p crms < migrate_all.sql
-- Note: Safe to run on a new DB. If running against an existing DB,
-- review and backup first. This script is additive where possible.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS crms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE crms;

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: officers (final schema)
-- Includes credentials, role, and join information.
-- ────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS case_evidence;
DROP TABLE IF EXISTS case_updates;
DROP TABLE IF EXISTS assignment_recommendations;
DROP TABLE IF EXISTS case_access_requests;
DROP TABLE IF EXISTS public_complaints;
DROP TABLE IF EXISTS case_officer;
DROP TABLE IF EXISTS cases;
DROP TABLE IF EXISTS officers;

CREATE TABLE officers (
    officer_id  INT          NOT NULL AUTO_INCREMENT,
    `name`      VARCHAR(120) NOT NULL,
    `rank`      VARCHAR(80)  NOT NULL,
    badge       VARCHAR(20)  DEFAULT NULL,
    station     VARCHAR(120) DEFAULT NULL,
    phone       VARCHAR(20)  DEFAULT NULL,
    email       VARCHAR(120) DEFAULT NULL,
    join_date   DATE         DEFAULT NULL,
    password_hash VARCHAR(255) DEFAULT NULL,
    `role`      ENUM('admin','inspector','viewer') NOT NULL DEFAULT 'viewer',
    PRIMARY KEY (officer_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: cases (final schema)
-- Includes lifecycle statuses, complainant metadata, and audit timestamps.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE cases (
    case_id        INT          NOT NULL AUTO_INCREMENT,
    title          VARCHAR(255) NOT NULL,
    description    TEXT,
    crime_type     VARCHAR(60)  NOT NULL,
    `status`       ENUM('Pending Review','Recommended','Assigned','Active','Solved','Closed','Rejected') NOT NULL DEFAULT 'Pending Review',
    date_reported  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `location`     VARCHAR(120) NOT NULL,
    complaint_mode ENUM('Online','Offline')         NOT NULL DEFAULT 'Online',
    last_updated   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    complainant_name VARCHAR(120) DEFAULT NULL,
    complainant_contact VARCHAR(120) DEFAULT NULL,
    complainant_aadhaar CHAR(12) DEFAULT NULL,
    `source` ENUM('public','officer') NOT NULL DEFAULT 'officer',
    PRIMARY KEY (case_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: case_officer (junction)
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE case_officer (
    case_id    INT NOT NULL,
    officer_id INT NOT NULL,
    PRIMARY KEY (case_id, officer_id),
    FOREIGN KEY (case_id)    REFERENCES cases    (case_id)    ON DELETE CASCADE,
    FOREIGN KEY (officer_id) REFERENCES officers (officer_id) ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: public_complaints (staging for citizen-submitted complaints)
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public_complaints (
    complaint_id INT NOT NULL AUTO_INCREMENT,
    complainant_name VARCHAR(120) NOT NULL,
    contact VARCHAR(120) NOT NULL,
    email VARCHAR(120) DEFAULT NULL,
    aadhaar CHAR(12) NOT NULL,
    crime_type VARCHAR(60) NOT NULL,
    `location` VARCHAR(120) NOT NULL,
    incident_desc TEXT NOT NULL,
    complaint_mode ENUM('Online','Offline') NOT NULL DEFAULT 'Online',
    `status` ENUM('Pending','Reviewed','Promoted','Rejected') NOT NULL DEFAULT 'Pending',
    promoted_case_id INT DEFAULT NULL,
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_by INT DEFAULT NULL,
    reviewed_at DATETIME DEFAULT NULL,
    PRIMARY KEY (complaint_id),
    CONSTRAINT fk_public_case FOREIGN KEY (promoted_case_id) REFERENCES cases(case_id) ON DELETE SET NULL,
    CONSTRAINT fk_public_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES officers(officer_id) ON DELETE SET NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: case_access_requests (citizen requests to access case dossier)
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS case_access_requests (
    request_id       INT NOT NULL AUTO_INCREMENT,
    case_id          INT NOT NULL,
    requester_name   VARCHAR(120) NOT NULL,
    requester_email  VARCHAR(120) NOT NULL,
    requester_number VARCHAR(20)  NOT NULL,
    reason           TEXT         NOT NULL,
    `status`         ENUM('Pending', 'Rejected', 'Accepted') NOT NULL DEFAULT 'Pending',
    requested_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by       INT          DEFAULT NULL,
    decided_at       DATETIME     DEFAULT NULL,
    PRIMARY KEY (request_id),
    CONSTRAINT fk_access_request_case FOREIGN KEY (case_id) REFERENCES cases (case_id) ON DELETE CASCADE,
    CONSTRAINT fk_access_request_officer FOREIGN KEY (decided_by) REFERENCES officers (officer_id) ON DELETE SET NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: assignment_recommendations (admin review of algorithm suggestions)
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assignment_recommendations (
    recommendation_id INT NOT NULL AUTO_INCREMENT,
    complaint_id INT NOT NULL,
    recommended_officer_ids JSON NOT NULL,
    status ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
    admin_approved_officer_ids JSON DEFAULT NULL,
    approved_by INT DEFAULT NULL,
    approved_at DATETIME DEFAULT NULL,
    rejection_reason VARCHAR(255) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (recommendation_id),
    UNIQUE KEY uk_complaint_pending (complaint_id, status),
    CONSTRAINT fk_rec_complaint FOREIGN KEY (complaint_id) REFERENCES public_complaints(complaint_id) ON DELETE CASCADE,
    CONSTRAINT fk_rec_approved_by FOREIGN KEY (approved_by) REFERENCES officers(officer_id) ON DELETE SET NULL,
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: case_updates (timeline entries)
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS case_updates (
    update_id INT NOT NULL AUTO_INCREMENT,
    case_id INT NOT NULL,
    officer_id INT NOT NULL,
    update_text TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (update_id),
    CONSTRAINT fk_update_case FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    CONSTRAINT fk_update_officer FOREIGN KEY (officer_id) REFERENCES officers(officer_id) ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: case_evidence (file metadata)
-- ────────────────────────────────────────────────────────────────────────────
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
    CONSTRAINT fk_evidence_case FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    CONSTRAINT fk_evidence_officer FOREIGN KEY (officer_id) REFERENCES officers(officer_id) ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- SEED: officers (demo)
-- Default test password hash used across demo accounts. Change before prod.
-- ────────────────────────────────────────────────────────────────────────────
INSERT INTO officers (`name`, `rank`, badge, station, phone, email, join_date, password_hash, `role`) VALUES
('Inspector Arjun Nair',        'Inspector',      'BPD-7821', 'Cyber Crime Division',  '+91-80-2294-2101', 'arjun.nair@bpd.gov.in',     '2018-03-15', '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO', 'inspector'),
('Sub-Inspector Priya Menon',   'Sub-Inspector',  'BPD-6543', 'Whitefield PS',          '+91-80-2845-6789', 'priya.menon@bpd.gov.in',    '2019-07-22', '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO', 'inspector'),
('Inspector Vikram Rao',        'Inspector',      'BPD-8912', 'Cyber Crime Division',  '+91-80-2294-2102', 'vikram.rao@bpd.gov.in',     '2017-11-08', '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO', 'inspector'),
('Sub-Inspector Deepa Krishnan','Sub-Inspector',  'BPD-5432', 'HSR Layout PS',          '+91-80-2572-3456', 'deepa.krishnan@bpd.gov.in', '2020-01-14', '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO', 'inspector'),
('Constable Ravi Kumar',        'Head Constable', 'BPD-3210', 'Commercial Street PS',   '+91-80-2558-9012', 'ravi.kumar@bpd.gov.in',     '2021-05-30', '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO', 'inspector'),
('Inspector Meera Iyer',        'Inspector',      'BPD-7654', 'Economic Offences Wing', '+91-80-2221-4567', 'meera.iyer@bpd.gov.in',     '2016-09-03', '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO', 'inspector'),
('Sub-Inspector Karthik S',     'Sub-Inspector',  'BPD-4321', 'Cyber Crime Division',  '+91-80-2294-2103', 'karthik.s@bpd.gov.in',      '2019-04-11', '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO', 'inspector');


-- ────────────────────────────────────────────────────────────────────────────
-- SEED: admin account (from migrate_v4)
-- Default password: crms1234
-- ────────────────────────────────────────────────────────────────────────────
INSERT INTO officers (`name`, `rank`, badge, station, phone, email, join_date, password_hash, `role`) VALUES
('Administrator', 'Administrator', 'ADM-0001', 'Central Command', '+91-80-2000-0000', 'admin@bpd.gov.in', CURDATE(), '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO', 'admin');


-- ────────────────────────────────────────────────────────────────────────────
-- SEED: cases (demo)
-- Uses final status enum values — default is 'Pending Review' but we seed
-- realistic statuses to mirror previous seed data.
-- ────────────────────────────────────────────────────────────────────────────
INSERT INTO cases (title, description, crime_type, `status`, date_reported, `location`, complaint_mode, complainant_name, complainant_contact, complainant_aadhaar, `source`) VALUES
(
  'Cyber Fraud - Wire Transfer Scam',
  'Victim received fraudulent email impersonating bank official. Rs 12.5L transferred to unknown account. Digital forensics underway.',
  'Cyber Fraud', 'Active', '2026-04-12', 'Koramangala', 'Online', NULL, NULL, NULL, 'officer'
),
(
  'Vehicle Theft - Swift Dzire',
  'Vehicle stolen from residential parking. Recovered via GPS tracking in Electronic City. Two suspects apprehended.',
  'Theft', 'Solved', '2026-03-28', 'Whitefield', 'Offline', NULL, NULL, NULL, 'officer'
),
(
  'Assault at Commercial Street',
  'Physical altercation between shop owners. Victim sustained head injuries. CCTV footage obtained. Investigation ongoing.',
  'Assault', 'Active', '2026-04-15', 'Commercial Street', 'Offline', NULL, NULL, NULL, 'officer'
),
(
  'Real Estate Fraud - Land Document Forgery',
  'Forged land sale deed used to transfer property worth Rs 3.2Cr. Forensic document analysis in progress.',
  'Fraud', 'Active', '2026-04-10', 'Jayanagar', 'Online', NULL, NULL, NULL, 'officer'
),
(
  'ATM Card Skimming Ring',
  'Multi-city ATM skimming operation dismantled. 47 cloned cards recovered. Rs 8.7L fraud prevented.',
  'Cyber Fraud', 'Solved', '2026-03-05', 'MG Road', 'Online', NULL, NULL, NULL, 'officer'
),
(
  'Jewelry Heist - Commercial District',
  'Armed robbery at jewelry store. Rs 45L worth of gold ornaments stolen. Case closed after recovery.',
  'Theft', 'Closed', '2026-02-18', 'Commercial Street', 'Offline', NULL, NULL, NULL, 'officer'
),
(
  'Domestic Violence Report',
  'Multiple domestic violence complaints filed. Protection order issued. Counseling services engaged.',
  'Assault', 'Active', '2026-04-18', 'HSR Layout', 'Online', NULL, NULL, NULL, 'officer'
),
(
  'Investment Ponzi Scheme',
  'Fraudulent investment scheme targeting retirees. Rs 1.8Cr collected from 34 victims. Financial forensics active.',
  'Fraud', 'Active', '2026-04-08', 'Indiranagar', 'Online', NULL, NULL, NULL, 'officer'
),
(
  'Data Breach - Fintech Company',
  'Unauthorized database access exposing 2.3M user records. Cyber cell engaged. Server logs under analysis.',
  'Cyber Fraud', 'Active', '2026-04-20', 'Manyata Tech Park', 'Online', NULL, NULL, NULL, 'officer'
),
(
  'Street Robbery - Mobile Snatching',
  'Motorcycle-mounted snatching. Victim resisted, sustained minor injuries. Suspects identified via CCTV.',
  'Theft', 'Solved', '2026-03-22', 'Brigade Road', 'Offline', NULL, NULL, NULL, 'officer'
);


-- ────────────────────────────────────────────────────────────────────────────
-- SEED: case_officer assignments
-- Matches previous setup_db.sql assignments
-- ────────────────────────────────────────────────────────────────────────────
INSERT INTO case_officer VALUES (1, 1), (1, 3);
INSERT INTO case_officer VALUES (2, 2);
INSERT INTO case_officer VALUES (3, 4), (3, 5);
INSERT INTO case_officer VALUES (4, 1), (4, 6);
INSERT INTO case_officer VALUES (5, 3), (5, 7);
INSERT INTO case_officer VALUES (6, 2), (6, 5);
INSERT INTO case_officer VALUES (7, 4);
INSERT INTO case_officer VALUES (8, 6), (8, 7);
INSERT INTO case_officer VALUES (9, 1), (9, 3), (9, 7);
INSERT INTO case_officer VALUES (10, 2), (10, 5);


-- ────────────────────────────────────────────────────────────────────────────
-- SEED: public_complaints examples (optional)
-- ────────────────────────────────────────────────────────────────────────────
INSERT INTO public_complaints (complainant_name, contact, email, aadhaar, crime_type, `location`, incident_desc, complaint_mode, `status`, submitted_at)
VALUES
('John Doe', '+91-9000000001', 'john.doe@example.com', '123456789012', 'Theft', 'Indiranagar', 'Stolen wallet at cafe', 'Online', 'Pending', NOW() - INTERVAL 2 DAY);


-- ────────────────────────────────────────────────────────────────────────────
-- SEED: case_access_requests (from migrate_v3)
-- ────────────────────────────────────────────────────────────────────────────
INSERT INTO case_access_requests 
    (case_id, requester_name, requester_email, requester_number, reason, `status`, requested_at, decided_by, decided_at)
VALUES
(1, 'Arvind Swamy', 'arvind.swamy@example.com', '+91-9845012345', 'Legal defense counsel representing the victim requires authorized access to full incident logs and wire transfer forensic reports.', 'Pending', NOW() - INTERVAL 1 DAY, NULL, NULL),
(2, 'Sunita Rao', 'sunita.rao@example.com', '+91-9876543210', 'Journalistic enquiry regarding the swift vehicle recovery and GPS tracking efficiency of Bengaluru Police cyber cell.', 'Accepted', NOW() - INTERVAL 3 DAY, 1, NOW() - INTERVAL 2 DAY),
(3, 'Unknown Client', 'unknown@privacy.io', '+91-9000000000', 'Requests detailed dossier of commercial street altercation logs for private arbitration services.', 'Rejected', NOW() - INTERVAL 5 DAY, 4, NOW() - INTERVAL 4 DAY);


-- ────────────────────────────────────────────────────────────────────────────
-- SEED: assignment_recommendations (empty example)
-- ────────────────────────────────────────────────────────────────────────────
-- (Left empty by default; algorithm creates rows at runtime.)


-- ────────────────────────────────────────────────────────────────────────────
-- Done. Basic verification queries follow (optional to run interactively).
-- SELECT 'officers'    AS tbl, COUNT(*) AS `rows` FROM officers;
-- SELECT 'cases',             COUNT(*) FROM cases;
-- SELECT 'case_officer',      COUNT(*) FROM case_officer;
-- ────────────────────────────────────────────────────────────────────────────
