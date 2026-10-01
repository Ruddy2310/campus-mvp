-- Campus MVP database schema (MySQL 8+)
-- Run:  mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS campus_mvp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE campus_mvp;

CREATE TABLE users (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(100) NOT NULL,
  email         VARCHAR(150) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role          ENUM('admin', 'faculty', 'student') NOT NULL,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE students (
  user_id    INT UNSIGNED PRIMARY KEY,
  roll_no    VARCHAR(30) NOT NULL UNIQUE,
  class_name VARCHAR(50) NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE faculty (
  user_id    INT UNSIGNED PRIMARY KEY,
  department VARCHAR(100) NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE subjects (
  id   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(20)  NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL
) ENGINE=InnoDB;

-- Which faculty member teaches which subject. The heart of all faculty authorization.
CREATE TABLE faculty_subjects (
  faculty_id INT UNSIGNED NOT NULL,
  subject_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (faculty_id, subject_id),
  FOREIGN KEY (faculty_id) REFERENCES faculty(user_id),
  FOREIGN KEY (subject_id) REFERENCES subjects(id)
) ENGINE=InnoDB;

-- Which student is enrolled in which subject.
CREATE TABLE enrollments (
  student_id INT UNSIGNED NOT NULL,
  subject_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (student_id, subject_id),
  INDEX idx_enrollments_subject (subject_id),
  FOREIGN KEY (student_id) REFERENCES students(user_id),
  FOREIGN KEY (subject_id) REFERENCES subjects(id)
) ENGINE=InnoDB;

-- One attendance session per subject per day.
CREATE TABLE attendance_sessions (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  subject_id   INT UNSIGNED NOT NULL,
  session_date DATE NOT NULL,
  marked_by    INT UNSIGNED NOT NULL,
  created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_subject_day (subject_id, session_date),
  FOREIGN KEY (subject_id) REFERENCES subjects(id),
  FOREIGN KEY (marked_by)  REFERENCES faculty(user_id)
) ENGINE=InnoDB;

CREATE TABLE attendance_records (
  session_id INT UNSIGNED NOT NULL,
  student_id INT UNSIGNED NOT NULL,
  status     ENUM('present', 'absent') NOT NULL,
  PRIMARY KEY (session_id, student_id),
  FOREIGN KEY (session_id) REFERENCES attendance_sessions(id),
  FOREIGN KEY (student_id) REFERENCES students(user_id)
) ENGINE=InnoDB;

CREATE TABLE leave_requests (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_id  INT UNSIGNED NOT NULL,
  from_date   DATE NOT NULL,
  to_date     DATE NOT NULL,
  reason      VARCHAR(500) NOT NULL,
  status      ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
  reviewed_by INT UNSIGNED NULL,
  reviewed_at TIMESTAMP NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_leave_status (status),
  FOREIGN KEY (student_id)  REFERENCES students(user_id),
  FOREIGN KEY (reviewed_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE notices (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title        VARCHAR(200) NOT NULL,
  body         TEXT NOT NULL,
  status       ENUM('draft', 'published') NOT NULL DEFAULT 'draft',
  created_by   INT UNSIGNED NOT NULL,
  created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  published_at TIMESTAMP NULL,
  INDEX idx_notice_status (status, published_at),
  FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB;
