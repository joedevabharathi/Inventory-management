-- Add created_at column to movements table if it doesn't exist
ALTER TABLE movements ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Update locations table structure
ALTER TABLE locations MODIFY COLUMN name VARCHAR(100);
ALTER TABLE locations ADD COLUMN IF NOT EXISTS branch_name VARCHAR(100);
ALTER TABLE locations ADD COLUMN IF NOT EXISTS city VARCHAR(100);
UPDATE locations SET branch_name = name WHERE branch_name IS NULL;

-- Update products table structure
ALTER TABLE products ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS image_path VARCHAR(255);
ALTER TABLE products ADD COLUMN IF NOT EXISTS location_id INT;
ALTER TABLE products ADD FOREIGN KEY IF NOT EXISTS (location_id) REFERENCES locations(id);
ALTER TABLE products ADD COLUMN product_code VARCHAR(100) UNIQUE;
UPDATE products SET product_code = CONCAT('SKU-', id) WHERE product_code IS NULL;
ALTER TABLE products MODIFY COLUMN product_code VARCHAR(100) UNIQUE NOT NULL;
ALTER TABLE products
ADD UNIQUE KEY uq_product_code (product_code);
ALTER TABLE products
ADD UNIQUE KEY uq_product_code (product_code);
DELETE FROM locations
WHERE branch_name = 'branch 1';
ALTER TABLE movements
DROP FOREIGN KEY movements_ibfk_2;

ALTER TABLE movements
ADD CONSTRAINT movements_ibfk_2
FOREIGN KEY (from_location)
REFERENCES locations(id)
ON DELETE CASCADE;
