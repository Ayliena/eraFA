-- MySQL dump 10.13  Distrib 5.7.23, for Linux (x86_64)
--
-- Host: erafa.mysql.pythonanywhere-services.com    Database: erafa$data
-- ------------------------------------------------------
-- Server version	5.6.40-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `cats`
--

DROP TABLE IF EXISTS `cats`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cats` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `owner_id` int(11) NOT NULL,
  `temp_owner` varchar(64) DEFAULT NULL,
  `name` varchar(32) DEFAULT NULL,
  `sex` int(11) DEFAULT NULL,
  `color` int(11) DEFAULT NULL,
  `longhair` int(11) DEFAULT NULL,
  `birthdate` datetime DEFAULT NULL,
  `regnum` int(11) NOT NULL,
  `identif` varchar(16) DEFAULT NULL,
  `description` varchar(2048) DEFAULT NULL,
  `comments` varchar(1024) DEFAULT NULL,
  `vetshort` varchar(16) DEFAULT NULL,
  `adoptable` tinyint(1) DEFAULT NULL,
  `lastop` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `regnum` (`regnum`),
  KEY `owner_id` (`owner_id`),
  CONSTRAINT `cats_ibfk_1` FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=532 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cats`
--

LOCK TABLES `cats` WRITE;
/*!40000 ALTER TABLE `cats` DISABLE KEYS */;
/*!40000 ALTER TABLE `cats` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `events`
--

DROP TABLE IF EXISTS `events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `events` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cat_id` int(11) NOT NULL,
  `edate` datetime DEFAULT NULL,
  `etext` varchar(1024) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `cat_id` (`cat_id`),
  CONSTRAINT `events_ibfk_1` FOREIGN KEY (`cat_id`) REFERENCES `cats` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1706 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `events`
--

LOCK TABLES `events` WRITE;
/*!40000 ALTER TABLE `events` DISABLE KEYS */;
/*!40000 ALTER TABLE `events` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(128) NOT NULL,
  `password_hash` varchar(128) NOT NULL,
  `FAname` varchar(128) NOT NULL,
  `FAid` varchar(64) DEFAULT NULL,
  `FAemail` varchar(128) DEFAULT NULL,
  `FAlastop` datetime DEFAULT NULL,
  `FAresp_id` int(11) DEFAULT NULL,
  `numcats` int(11) DEFAULT NULL,
  `FAisFA` tinyint(1) NOT NULL,
  `FAisRF` tinyint(1) NOT NULL,
  `FAisOV` tinyint(1) NOT NULL,
  `FAisADM` tinyint(1) NOT NULL,
  `FAisAD` tinyint(1) NOT NULL,
  `FAisDCD` tinyint(1) NOT NULL,
  `FAisVET` tinyint(1) NOT NULL,
  `FAisHIST` tinyint(1) NOT NULL,
  `FAisREF` tinyint(1) NOT NULL,
  `FAisTEMP` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `username_2` (`username`),
  KEY `users_iblk_1` (`FAresp_id`),
  CONSTRAINT `users_iblk_1` FOREIGN KEY (`FAresp_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=92 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `vetinfo`
--

DROP TABLE IF EXISTS `vetinfo`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `vetinfo` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cat_id` int(11) NOT NULL,
  `doneby_id` int(11) NOT NULL,
  `vet_id` int(11) NOT NULL,
  `vtype` varchar(16) DEFAULT NULL,
  `vdate` datetime DEFAULT NULL,
  `planned` tinyint(1) DEFAULT NULL,
  `requested` tinyint(1) DEFAULT NULL,
  `validated` tinyint(1) DEFAULT NULL,
  `comments` varchar(1024) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `cat_id` (`cat_id`),
  KEY `doneby_id` (`doneby_id`),
  KEY `vet_id` (`vet_id`),
  CONSTRAINT `vetinfo_ibfk_1` FOREIGN KEY (`cat_id`) REFERENCES `cats` (`id`),
  CONSTRAINT `vetinfo_ibfk_2` FOREIGN KEY (`doneby_id`) REFERENCES `users` (`id`),
  CONSTRAINT `vetinfo_ibfk_3` FOREIGN KEY (`vet_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=569 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `vetinfo`
--

LOCK TABLES `vetinfo` WRITE;
/*!40000 ALTER TABLE `vetinfo` DISABLE KEYS */;
/*!40000 ALTER TABLE `vetinfo` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2019-07-02 21:44:30
