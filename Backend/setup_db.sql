-- ─── CRMS MySQL Setup ──────────────────────────────────────────────────────
-- Run once to create the schema and seed demo data.
-- Usage: mysql -u adarsh -p < setup_db.sql

CREATE DATABASE IF NOT EXISTS crms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE crms;

-- ─── DROP EXISTING TABLES (clean slate) ───────────────────────────────────────

DROP TABLE IF EXISTS case_officer;
DROP TABLE IF EXISTS cases;
DROP TABLE IF EXISTS officers;

-- ─── TABLE: officers ──────────────────────────────────────────────────────────
-- `rank` and `name` are reserved words in MySQL 8 — must be backtick-quoted.

CREATE TABLE officers (
    officer_id  INT          NOT NULL AUTO_INCREMENT,
    `name`      VARCHAR(120) NOT NULL,
    `rank`      VARCHAR(80)  NOT NULL,
    badge       VARCHAR(20)  DEFAULT NULL,
    station     VARCHAR(120) DEFAULT NULL,
    phone       VARCHAR(20)  DEFAULT NULL,
    email       VARCHAR(120) DEFAULT NULL,
    join_date   DATE         DEFAULT NULL,
    PRIMARY KEY (officer_id)
) ENGINE=InnoDB;

-- ─── TABLE: cases ─────────────────────────────────────────────────────────────
-- `status` and `location` are reserved in some MySQL versions — backtick-quoted.

CREATE TABLE cases (
    case_id        INT          NOT NULL AUTO_INCREMENT,
    title          VARCHAR(255) NOT NULL,
    description    TEXT,
    crime_type     VARCHAR(60)  NOT NULL,
    `status`       ENUM('Active','Solved','Closed') NOT NULL DEFAULT 'Active',
    date_reported  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `location`     VARCHAR(120) NOT NULL,
    complaint_mode ENUM('Online','Offline')         NOT NULL DEFAULT 'Online',
    last_updated   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (case_id)
) ENGINE=InnoDB;

-- ─── TABLE: case_officer (junction) ───────────────────────────────────────────

CREATE TABLE case_officer (
    case_id    INT NOT NULL,
    officer_id INT NOT NULL,
    PRIMARY KEY (case_id, officer_id),
    FOREIGN KEY (case_id)    REFERENCES cases    (case_id)    ON DELETE CASCADE,
    FOREIGN KEY (officer_id) REFERENCES officers (officer_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─── SEED: officers ───────────────────────────────────────────────────────────

INSERT INTO officers (`name`, `rank`, badge, station, phone, email, join_date) VALUES
('Inspector Arjun Nair',        'Inspector',      'BPD-7821', 'Cyber Crime Division',  '+91-80-2294-2101', 'arjun.nair@bpd.gov.in',     '2018-03-15'),
('Sub-Inspector Priya Menon',   'Sub-Inspector',  'BPD-6543', 'Whitefield PS',          '+91-80-2845-6789', 'priya.menon@bpd.gov.in',    '2019-07-22'),
('Inspector Vikram Rao',        'Inspector',      'BPD-8912', 'Cyber Crime Division',  '+91-80-2294-2102', 'vikram.rao@bpd.gov.in',     '2017-11-08'),
('Sub-Inspector Deepa Krishnan','Sub-Inspector',  'BPD-5432', 'HSR Layout PS',          '+91-80-2572-3456', 'deepa.krishnan@bpd.gov.in', '2020-01-14'),
('Constable Ravi Kumar',        'Head Constable', 'BPD-3210', 'Commercial Street PS',   '+91-80-2558-9012', 'ravi.kumar@bpd.gov.in',     '2021-05-30'),
('Inspector Meera Iyer',        'Inspector',      'BPD-7654', 'Economic Offences Wing', '+91-80-2221-4567', 'meera.iyer@bpd.gov.in',     '2016-09-03'),
('Sub-Inspector Karthik S',     'Sub-Inspector',  'BPD-4321', 'Cyber Crime Division',  '+91-80-2294-2103', 'karthik.s@bpd.gov.in',      '2019-04-11');

-- ─── SEED: cases ──────────────────────────────────────────────────────────────

INSERT INTO cases (title, description, crime_type, `status`, date_reported, `location`, complaint_mode) VALUES
(
  'Cyber Fraud - Wire Transfer Scam',
  'Victim received fraudulent email impersonating bank official. Rs 12.5L transferred to unknown account. Digital forensics underway.',
  'Cyber Fraud', 'Active', '2026-04-12', 'Koramangala', 'Online'
),
(
  'Vehicle Theft - Swift Dzire',
  'Vehicle stolen from residential parking. Recovered via GPS tracking in Electronic City. Two suspects apprehended.',
  'Theft', 'Solved', '2026-03-28', 'Whitefield', 'Offline'
),
(
  'Assault at Commercial Street',
  'Physical altercation between shop owners. Victim sustained head injuries. CCTV footage obtained. Investigation ongoing.',
  'Assault', 'Active', '2026-04-15', 'Commercial Street', 'Offline'
),
(
  'Real Estate Fraud - Land Document Forgery',
  'Forged land sale deed used to transfer property worth Rs 3.2Cr. Forensic document analysis in progress.',
  'Fraud', 'Active', '2026-04-10', 'Jayanagar', 'Online'
),
(
  'ATM Card Skimming Ring',
  'Multi-city ATM skimming operation dismantled. 47 cloned cards recovered. Rs 8.7L fraud prevented.',
  'Cyber Fraud', 'Solved', '2026-03-05', 'MG Road', 'Online'
),
(
  'Jewelry Heist - Commercial District',
  'Armed robbery at jewelry store. Rs 45L worth of gold ornaments stolen. Case closed after recovery.',
  'Theft', 'Closed', '2026-02-18', 'Commercial Street', 'Offline'
),
(
  'Domestic Violence Report',
  'Multiple domestic violence complaints filed. Protection order issued. Counseling services engaged.',
  'Assault', 'Active', '2026-04-18', 'HSR Layout', 'Online'
),
(
  'Investment Ponzi Scheme',
  'Fraudulent investment scheme targeting retirees. Rs 1.8Cr collected from 34 victims. Financial forensics active.',
  'Fraud', 'Active', '2026-04-08', 'Indiranagar', 'Online'
),
(
  'Data Breach - Fintech Company',
  'Unauthorized database access exposing 2.3M user records. Cyber cell engaged. Server logs under analysis.',
  'Cyber Fraud', 'Active', '2026-04-20', 'Manyata Tech Park', 'Online'
),
(
  'Street Robbery - Mobile Snatching',
  'Motorcycle-mounted snatching. Victim resisted, sustained minor injuries. Suspects identified via CCTV.',
  'Theft', 'Solved', '2026-03-22', 'Brigade Road', 'Offline'
);

-- ─── SEED: case_officer ───────────────────────────────────────────────────────

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

-- ─── VERIFY ───────────────────────────────────────────────────────────────────

SELECT 'officers'    AS tbl, COUNT(*) AS `rows` FROM officers
UNION ALL
SELECT 'cases',             COUNT(*)                    FROM cases
UNION ALL
SELECT 'case_officer',      COUNT(*)                    FROM case_officer;
