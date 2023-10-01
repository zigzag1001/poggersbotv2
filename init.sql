CREATE DATABASE bot_db;
CREATE USER 'bot_user'@'localhost' IDENTIFIED BY 'bot_password';
GRANT ALL PRIVILEGES ON bot_db.* TO 'bot_user'@'localhost';
FLUSH PRIVILEGES;
