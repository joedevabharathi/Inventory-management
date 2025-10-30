-- Create database
CREATE DATABASE IF NOT EXISTS inventory_db;
USE inventory_db;

-- Create locations table
CREATE TABLE IF NOT EXISTS locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    location_id VARCHAR(10) NOT NULL UNIQUE,
    branch_name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create products table
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    quantity INT NOT NULL DEFAULT 0,
    location_id INT,
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- Create movements table
CREATE TABLE IF NOT EXISTS movements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    from_location INT NOT NULL,
    to_location INT NOT NULL,
    quantity INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (from_location) REFERENCES locations(id),
    FOREIGN KEY (to_location) REFERENCES locations(id)
);

-- Insert sample locations
INSERT INTO locations (location_id, branch_name, city) VALUES
('LOC001', 'Main Warehouse', 'New York'),
('LOC002', 'South Branch', 'Miami'),
('LOC003', 'West Coast Center', 'Los Angeles'),
('LOC004', 'North Storage', 'Chicago');

-- Insert sample products
INSERT INTO products (name, description, quantity, location_id) VALUES
('Laptop XPS 15', 'Dell XPS 15 Gaming Laptop', 50, 1),
('iPhone 13 Pro', 'Apple iPhone 13 Pro 256GB', 100, 1),
('Samsung TV', '65" Samsung QLED Smart TV', 30, 2),
('Gaming Mouse', 'Logitech G Pro Wireless', 200, 3),
('Printer', 'HP LaserJet Pro', 45, 4),
('Keyboard', 'Mechanical RGB Keyboard', 150, 2);

-- Insert sample movements
INSERT INTO movements (product_id, from_location, to_location, quantity) VALUES
(1, 1, 2, 5),
(2, 1, 3, 10),
(3, 2, 4, 2),
(4, 3, 1, 15),
(5, 4, 2, 3);