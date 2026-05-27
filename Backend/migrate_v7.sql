-- Migration v7: Add unified intake statuses to `cases.status` enum and default to 'Pending Review'
-- This is an additive, non-destructive migration intended to enable public complaints
-- to create cases with a 'Pending Review' lifecycle state.

ALTER TABLE `cases`
MODIFY COLUMN `status` ENUM('Pending Review','Recommended','Assigned','Active','Solved','Closed','Rejected')
NOT NULL DEFAULT 'Pending Review';

-- Note: Run this migration after taking a DB backup. This migration preserves existing
-- rows whose status already matches one of the values above (e.g. 'Active','Solved','Closed').
-- For any legacy status values not listed above, consider mapping them prior to running.
