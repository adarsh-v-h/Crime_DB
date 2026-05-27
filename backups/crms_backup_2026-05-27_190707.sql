-- MySQL dump 10.13  Distrib 8.0.45, for Linux (x86_64)
--
-- Host: localhost    Database: crms
-- ------------------------------------------------------
-- Server version	8.0.45-0ubuntu0.22.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `assignment_recommendations`
--

DROP TABLE IF EXISTS `assignment_recommendations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `assignment_recommendations` (
  `recommendation_id` int NOT NULL AUTO_INCREMENT,
  `complaint_id` int NOT NULL,
  `recommended_officer_ids` json NOT NULL,
  `status` enum('pending','approved','rejected') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `admin_approved_officer_ids` json DEFAULT NULL,
  `approved_by` int DEFAULT NULL,
  `approved_at` datetime DEFAULT NULL,
  `rejection_reason` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`recommendation_id`),
  UNIQUE KEY `uk_complaint_pending` (`complaint_id`,`status`),
  KEY `fk_rec_approved_by` (`approved_by`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `fk_rec_approved_by` FOREIGN KEY (`approved_by`) REFERENCES `officers` (`officer_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_rec_complaint` FOREIGN KEY (`complaint_id`) REFERENCES `public_complaints` (`complaint_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `assignment_recommendations`
--

LOCK TABLES `assignment_recommendations` WRITE;
/*!40000 ALTER TABLE `assignment_recommendations` DISABLE KEYS */;
/*!40000 ALTER TABLE `assignment_recommendations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `case_access_requests`
--

DROP TABLE IF EXISTS `case_access_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `case_access_requests` (
  `request_id` int NOT NULL AUTO_INCREMENT,
  `case_id` int NOT NULL,
  `requester_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `requester_email` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `requester_number` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `reason` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('Pending','Rejected','Accepted') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Pending',
  `requested_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `decided_by` int DEFAULT NULL,
  `decided_at` datetime DEFAULT NULL,
  PRIMARY KEY (`request_id`),
  KEY `fk_access_request_case` (`case_id`),
  KEY `fk_access_request_officer` (`decided_by`),
  CONSTRAINT `fk_access_request_case` FOREIGN KEY (`case_id`) REFERENCES `cases` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_access_request_officer` FOREIGN KEY (`decided_by`) REFERENCES `officers` (`officer_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `case_access_requests`
--

LOCK TABLES `case_access_requests` WRITE;
/*!40000 ALTER TABLE `case_access_requests` DISABLE KEYS */;
INSERT INTO `case_access_requests` VALUES (1,1,'Arvind Swamy','arvind.swamy@example.com','+91-9845012345','Legal defense counsel representing the victim requires authorized access to full incident logs and wire transfer forensic reports.','Rejected','2026-05-23 16:46:36',1,'2026-05-24 20:28:58'),(2,2,'Sunita Rao','sunita.rao@example.com','+91-9876543210','Journalistic enquiry regarding the swift vehicle recovery and GPS tracking efficiency of Bengaluru Police cyber cell.','Accepted','2026-05-21 16:46:36',1,'2026-05-22 16:46:36'),(3,3,'Unknown Client','unknown@privacy.io','+91-9000000000','Requests detailed dossier of commercial street altercation logs for private arbitration services.','Rejected','2026-05-19 16:46:36',4,'2026-05-20 16:46:36'),(4,1,'Adarsh V H','snapouting@gmail.com','8762987365','Finished all crime based movies, now want to read real ones.','Accepted','2026-05-24 20:27:17',1,'2026-05-24 20:28:52'),(5,19,'Aditi AM','snapouting@gmail.com','8762987365','I need it for my paper on crimes in Bangalore','Rejected','2026-05-25 09:34:42',1,'2026-05-25 09:35:15'),(6,19,'Adarsh V H','snapouting@gamil.com','87629831234','Test','Accepted','2026-05-25 11:06:39',5,'2026-05-25 11:09:41'),(7,19,'BK','bkadikuppur@gmail.com','1234567890','Research','Accepted','2026-05-25 15:03:16',5,'2026-05-25 15:05:45'),(8,19,'BK','bkadikuppur@gmail.com','1234567890','Research','Rejected','2026-05-25 15:06:54',5,'2026-05-25 15:07:16'),(9,21,'Ranjitha Maam','ranjithasr@jssateb.ac.in','8762987365','Research','Accepted','2026-05-25 15:59:19',5,'2026-05-25 16:00:44'),(10,21,'bb','snapouting@gmail.com','1234567890','asd','Accepted','2026-05-25 16:20:16',2,'2026-05-25 20:43:35');
/*!40000 ALTER TABLE `case_access_requests` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `case_evidence`
--

DROP TABLE IF EXISTS `case_evidence`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `case_evidence` (
  `evidence_id` int NOT NULL AUTO_INCREMENT,
  `case_id` int NOT NULL,
  `officer_id` int NOT NULL,
  `file_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `original_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_path` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  `mime_type` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_size` int NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`evidence_id`),
  KEY `fk_evidence_case` (`case_id`),
  KEY `fk_evidence_officer` (`officer_id`),
  CONSTRAINT `fk_evidence_case` FOREIGN KEY (`case_id`) REFERENCES `cases` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_evidence_officer` FOREIGN KEY (`officer_id`) REFERENCES `officers` (`officer_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `case_evidence`
--

LOCK TABLES `case_evidence` WRITE;
/*!40000 ALTER TABLE `case_evidence` DISABLE KEYS */;
/*!40000 ALTER TABLE `case_evidence` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `case_officer`
--

DROP TABLE IF EXISTS `case_officer`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `case_officer` (
  `case_id` int NOT NULL,
  `officer_id` int NOT NULL,
  `role` enum('Supervisor','Lead IO','Assist') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`case_id`,`officer_id`),
  KEY `officer_id` (`officer_id`),
  CONSTRAINT `case_officer_ibfk_1` FOREIGN KEY (`case_id`) REFERENCES `cases` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `case_officer_ibfk_2` FOREIGN KEY (`officer_id`) REFERENCES `officers` (`officer_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `case_officer`
--

LOCK TABLES `case_officer` WRITE;
/*!40000 ALTER TABLE `case_officer` DISABLE KEYS */;
INSERT INTO `case_officer` VALUES (1,1,'Supervisor'),(1,3,'Supervisor'),(2,2,'Supervisor'),(3,4,'Supervisor'),(3,5,'Supervisor'),(4,1,'Supervisor'),(4,6,'Supervisor'),(5,3,'Supervisor'),(5,7,'Supervisor'),(6,2,'Supervisor'),(6,5,'Supervisor'),(7,4,'Supervisor'),(8,6,'Supervisor'),(8,7,'Supervisor'),(9,1,'Supervisor'),(9,3,'Supervisor'),(9,7,'Supervisor'),(10,2,'Supervisor'),(10,5,'Supervisor'),(14,2,'Supervisor'),(14,5,'Supervisor'),(15,2,'Supervisor'),(15,5,'Supervisor'),(15,6,'Supervisor'),(16,5,'Supervisor'),(16,7,'Supervisor'),(17,2,'Supervisor'),(17,5,'Supervisor'),(18,4,'Supervisor'),(18,5,'Supervisor'),(19,3,'Supervisor'),(19,5,'Supervisor'),(19,7,'Supervisor'),(20,2,'Supervisor'),(20,5,'Supervisor'),(21,1,'Supervisor'),(21,2,'Supervisor'),(21,5,'Supervisor');
/*!40000 ALTER TABLE `case_officer` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `case_updates`
--

DROP TABLE IF EXISTS `case_updates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `case_updates` (
  `update_id` int NOT NULL AUTO_INCREMENT,
  `case_id` int NOT NULL,
  `officer_id` int NOT NULL,
  `update_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`update_id`),
  KEY `fk_update_case` (`case_id`),
  KEY `fk_update_officer` (`officer_id`),
  CONSTRAINT `fk_update_case` FOREIGN KEY (`case_id`) REFERENCES `cases` (`case_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_update_officer` FOREIGN KEY (`officer_id`) REFERENCES `officers` (`officer_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `case_updates`
--

LOCK TABLES `case_updates` WRITE;
/*!40000 ALTER TABLE `case_updates` DISABLE KEYS */;
/*!40000 ALTER TABLE `case_updates` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `cases`
--

DROP TABLE IF EXISTS `cases`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cases` (
  `case_id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `crime_type` varchar(60) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('Active','Solved','Closed') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Active',
  `date_reported` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `location` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `complaint_mode` enum('Online','Offline') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Online',
  `last_updated` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `complainant_name` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `complainant_contact` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `complainant_aadhaar` char(4) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `source` enum('public','officer') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'officer',
  PRIMARY KEY (`case_id`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cases`
--

LOCK TABLES `cases` WRITE;
/*!40000 ALTER TABLE `cases` DISABLE KEYS */;
INSERT INTO `cases` VALUES (1,'Cyber Fraud - Wire Transfer Scam','Victim received fraudulent email impersonating bank official. Rs 12.5L transferred to unknown account. Digital forensics underway.','Cyber Fraud','Active','2026-04-12 00:00:00','Koramangala','Online','2026-05-13 13:33:10',NULL,NULL,NULL,'officer'),(2,'Vehicle Theft - Swift Dzire','Vehicle stolen from residential parking. Recovered via GPS tracking in Electronic City. Two suspects apprehended.','Theft','Solved','2026-03-28 00:00:00','Whitefield','Offline','2026-05-13 13:33:10',NULL,NULL,NULL,'officer'),(3,'Assault at Commercial Street','Physical altercation between shop owners. Victim sustained head injuries. CCTV footage obtained. Investigation ongoing.','Assault','Active','2026-04-15 00:00:00','Commercial Street','Offline','2026-05-13 13:33:10',NULL,NULL,NULL,'officer'),(4,'Real Estate Fraud - Land Document Forgery','Forged land sale deed used to transfer property worth Rs 3.2Cr. Forensic document analysis in progress.','Fraud','Solved','2026-04-10 00:00:00','Jayanagar','Online','2026-05-24 16:05:18',NULL,NULL,NULL,'officer'),(5,'ATM Card Skimming Ring','Multi-city ATM skimming operation dismantled. 47 cloned cards recovered. Rs 8.7L fraud prevented.','Cyber Fraud','Solved','2026-03-05 00:00:00','MG Road','Online','2026-05-13 13:33:10',NULL,NULL,NULL,'officer'),(6,'Jewelry Heist - Commercial District','Armed robbery at jewelry store. Rs 45L worth of gold ornaments stolen. Case closed after recovery.','Theft','Closed','2026-02-18 00:00:00','Commercial Street','Offline','2026-05-13 13:33:10',NULL,NULL,NULL,'officer'),(7,'Domestic Violence Report','Multiple domestic violence complaints filed. Protection order issued. Counseling services engaged.','Assault','Closed','2026-04-18 00:00:00','HSR Layout','Online','2026-05-24 16:05:15',NULL,NULL,NULL,'officer'),(8,'Investment Ponzi Scheme','Fraudulent investment scheme targeting retirees. Rs 1.8Cr collected from 34 victims. Financial forensics active.','Fraud','Active','2026-04-08 00:00:00','Indiranagar','Online','2026-05-13 13:33:10',NULL,NULL,NULL,'officer'),(9,'Data Breach - Fintech Company','Unauthorized database access exposing 2.3M user records. Cyber cell engaged. Server logs under analysis.','Cyber Fraud','Active','2026-04-20 00:00:00','Manyata Tech Park','Online','2026-05-13 13:33:10',NULL,NULL,NULL,'officer'),(10,'Street Robbery - Mobile Snatching','Motorcycle-mounted snatching. Victim resisted, sustained minor injuries. Suspects identified via CCTV.','Theft','Solved','2026-03-22 00:00:00','Brigade Road','Offline','2026-05-13 13:33:10',NULL,NULL,NULL,'officer'),(11,'Theft — Kengeri','some nigga took my bag','Theft','Closed','2026-05-13 13:51:41','Kengeri','Online','2026-05-13 13:55:17',NULL,NULL,NULL,'officer'),(12,'Fraud — kengri','Blah blah','Fraud','Active','2026-05-13 14:47:34','kengri','Online','2026-05-13 14:47:34',NULL,NULL,NULL,'officer'),(13,'Blah','Blah','Cyber Fraud','Active','2026-05-14 07:21:13','Blah','Online','2026-05-14 07:21:13',NULL,NULL,NULL,'officer'),(14,'Cyber Fraud - Kengeri','Some guy called and money gone','Cyber Fraud','Active','2026-05-24 14:55:56','Kengeri','Online','2026-05-24 14:55:56','Adarsh V H','+91-8762987365','8762','public'),(15,'Assault - asdsa','1asdsaas','Assault','Closed','2026-05-24 14:55:56','asdsa','Online','2026-05-24 16:05:07','adarsh','8762987365','1233','public'),(16,'Cyber Fraud - Kengeri','UPI fraud','Cyber Fraud','Active','2026-05-24 14:55:56','Kengeri','Online','2026-05-24 14:55:56','adarsh V h','8762987365','1234','public'),(17,'Theft - asdsaf','afefdfdads','Theft','Closed','2026-05-24 14:55:56','asdsaf','Online','2026-05-24 16:05:11','Adarsh V H','8762987365','1123','public'),(18,'Cyber Fraud - Kengeri','Some nigga called me, now my UPI died','Cyber Fraud','Solved','2026-05-24 14:57:26','Kengeri','Online','2026-05-24 16:05:23','Adarsh V H','8762987365','1234','public'),(19,'Assault - kengri','Adarsh died','Assault','Active','2026-05-24 15:00:17','kengri','Online','2026-05-24 21:20:25','Adarsh V H','8762987365','1234','public'),(20,'Theft - Majestic','Some dude stole my wallet','Theft','Solved','2026-05-25 09:37:50','Majestic','Online','2026-05-25 09:39:21','Adarsh V H','8762987365','1234','public'),(21,'Cyber Fraud - Kengeri','Amount of 10k was lost on clicking unlegitement link','Cyber Fraud','Active','2026-05-25 15:39:45','Kengeri','Online','2026-05-25 15:39:45','Adaasd','1233456212','1234','public');
/*!40000 ALTER TABLE `cases` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `officers`
--

DROP TABLE IF EXISTS `officers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `officers` (
  `officer_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `rank` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `badge` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `station` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `join_date` date DEFAULT NULL,
  `role` enum('admin','inspector','viewer') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'viewer',
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`officer_id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `officers`
--

LOCK TABLES `officers` WRITE;
/*!40000 ALTER TABLE `officers` DISABLE KEYS */;
INSERT INTO `officers` VALUES (1,'Inspector Arjun Nair','Inspector','BPD-7821','Cyber Crime Division','+91-80-2294-2101','arjun.nair@bpd.gov.in','2018-03-15','inspector','$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO'),(2,'Sub-Inspector Priya Menon','Sub-Inspector','BPD-6543','Whitefield PS','+91-80-2845-6789','priya.menon@bpd.gov.in','2019-07-22','viewer','$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO'),(3,'Inspector Vikram Rao','Inspector','BPD-8912','Cyber Crime Division','+91-80-2294-2102','vikram.rao@bpd.gov.in','2017-11-08','inspector','$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO'),(4,'Sub-Inspector Deepa Krishnan','Sub-Inspector','BPD-5432','HSR Layout PS','+91-80-2572-3456','deepa.krishnan@bpd.gov.in','2020-01-14','viewer','$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO'),(5,'Constable Ravi Kumar','Head Constable','BPD-3210','Commercial Street PS','+91-80-2558-9012','ravi.kumar@bpd.gov.in','2021-05-30','viewer','$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO'),(6,'Inspector Meera Iyer','Inspector','BPD-7654','Economic Offences Wing','+91-80-2221-4567','meera.iyer@bpd.gov.in','2016-09-03','inspector','$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO'),(7,'Sub-Inspector Karthik S','Sub-Inspector','BPD-4321','Cyber Crime Division','+91-80-2294-2103','karthik.s@bpd.gov.in','2019-04-11','viewer','$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO'),(8,'Administrator','Administrator','ADM-0001','Central Command','+91-80-2000-0000','admin@bpd.gov.in','2026-05-25','admin','$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO'),(9,'Administrator','Administrator','ADM-0001','Central Command','+91-80-2000-0000','admin@bpd.gov.in','2026-05-26','admin','$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO');
/*!40000 ALTER TABLE `officers` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `public_complaints`
--

DROP TABLE IF EXISTS `public_complaints`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `public_complaints` (
  `complaint_id` int NOT NULL AUTO_INCREMENT,
  `complainant_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `contact` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `aadhaar_last4` char(4) COLLATE utf8mb4_unicode_ci NOT NULL,
  `crime_type` varchar(60) COLLATE utf8mb4_unicode_ci NOT NULL,
  `location` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `incident_desc` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `complaint_mode` enum('Online','Offline') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Online',
  `status` enum('Pending','Reviewed','Promoted','Rejected') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Pending',
  `promoted_case_id` int DEFAULT NULL,
  `submitted_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `reviewed_by` int DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`complaint_id`),
  KEY `fk_public_case` (`promoted_case_id`),
  KEY `fk_public_reviewed_by` (`reviewed_by`),
  CONSTRAINT `fk_public_case` FOREIGN KEY (`promoted_case_id`) REFERENCES `cases` (`case_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_public_reviewed_by` FOREIGN KEY (`reviewed_by`) REFERENCES `officers` (`officer_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `public_complaints`
--

LOCK TABLES `public_complaints` WRITE;
/*!40000 ALTER TABLE `public_complaints` DISABLE KEYS */;
INSERT INTO `public_complaints` VALUES (1,'Adarsh V H','+91-8762987365','adarshvh2005@gmail.com','8762','Cyber Fraud','Kengeri','Some guy called and money gone','Online','Promoted',14,'2026-05-19 17:59:16',2,'2026-05-24 14:55:56'),(2,'adarsh','8762987365','adarshvh2005@gmail.com','1233','Assault','asdsa','1asdsaas','Online','Promoted',15,'2026-05-19 18:36:46',6,'2026-05-24 14:55:56'),(3,'adarsh V h','8762987365','adarshvh2005@gmail.com','1234','Cyber Fraud','Kengeri','UPI fraud','Online','Promoted',16,'2026-05-20 07:04:09',7,'2026-05-24 14:55:56'),(4,'Adarsh V H','8762987365','adarshvh2005@gmail.com','1123','Theft','asdsaf','afefdfdads','Online','Promoted',17,'2026-05-22 10:48:05',2,'2026-05-24 14:55:56'),(5,'Adarsh V H','8762987365','adarshvh2005@gmail.com','1234','Cyber Fraud','Kengeri','Some nigga called me, now my UPI died','Online','Promoted',18,'2026-05-24 14:57:19',4,'2026-05-24 14:57:26'),(6,'Adarsh V H','8762987365','adarshvh2005@gmail.com','1234','Assault','kengri','Adarsh died','Online','Promoted',19,'2026-05-24 15:00:13',3,'2026-05-24 15:00:17'),(7,'Adarsh V H','8762987365','snapouting@gmail.com','1234','Theft','Majestic','Some dude stole my wallet','Online','Promoted',20,'2026-05-25 09:37:48',2,'2026-05-25 09:37:50'),(8,'Adaasd','1233456212','asdas@gamil.com','1234','Cyber Fraud','Kengeri','Amount of 10k was lost on clicking unlegitement link','Online','Promoted',21,'2026-05-25 15:39:37',2,'2026-05-25 15:39:45');
/*!40000 ALTER TABLE `public_complaints` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-05-27 19:07:07
