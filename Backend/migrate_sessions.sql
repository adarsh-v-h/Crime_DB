-- Adds single-device officer login sessions.
-- Safe to run on an existing database.
USE crms;

CREATE TABLE IF NOT EXISTS officer_sessions (
    session_id INT NOT NULL AUTO_INCREMENT,
    officer_id INT NOT NULL,
    session_token CHAR(64) NOT NULL,
    user_agent VARCHAR(255) DEFAULT NULL,
    ip_address VARCHAR(64) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    revoked_at DATETIME DEFAULT NULL,
    PRIMARY KEY (session_id),
    UNIQUE KEY uk_session_token (session_token),
    INDEX idx_officer_active (officer_id, revoked_at, expires_at),
    CONSTRAINT fk_session_officer
        FOREIGN KEY (officer_id) REFERENCES officers(officer_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
