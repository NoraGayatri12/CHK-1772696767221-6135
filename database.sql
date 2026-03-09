CREATE DATABASE IF NOT EXISTS hopebridge;
USE hopebridge;

-- users table
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(150) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL,
  role ENUM('user','ngo') NOT NULL,
  latitude DECIMAL(10,7),        -- for GPS coordinates (NGO only)
  longitude DECIMAL(10,7),       -- for GPS coordinates (NGO only)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- reports table
CREATE TABLE IF NOT EXISTS reports (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  photo VARCHAR(255),
  description TEXT,
  location VARCHAR(255),          -- can store "lat,lon"
  priority ENUM('High','Medium','Low') DEFAULT 'Medium',
  assigned_ngo INT,               -- nearest NGO ID
  status ENUM('Pending','Resolved') DEFAULT 'Pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (assigned_ngo) REFERENCES users(id) ON DELETE SET NULL
);

-- feedback table
CREATE TABLE IF NOT EXISTS feedback (
  id INT AUTO_INCREMENT PRIMARY KEY,
  report_id INT NOT NULL,
  ngo_id INT NOT NULL,
  message TEXT,
  photo VARCHAR(255),
  date DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
  FOREIGN KEY (ngo_id) REFERENCES users(id) ON DELETE CASCADE
);
USE hopebridge;

