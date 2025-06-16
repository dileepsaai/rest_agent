-- Drop existing tables if they exist
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS product_coupons;
DROP TABLE IF EXISTS coupons;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;

-- Create categories table
CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_category_id INTEGER REFERENCES categories(category_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create products table
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    category_id INTEGER REFERENCES categories(category_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create coupons table
CREATE TABLE coupons (
    coupon_id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    discount_type VARCHAR(20) NOT NULL CHECK (discount_type IN ('percentage', 'fixed_amount')),
    discount_value DECIMAL(10,2) NOT NULL,
    min_purchase_amount DECIMAL(10,2),
    max_discount_amount DECIMAL(10,2),
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT true,
    usage_limit INTEGER,
    times_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_dates CHECK (end_date > start_date),
    CONSTRAINT valid_discount CHECK (
        (discount_type = 'percentage' AND discount_value BETWEEN 0 AND 100) OR
        (discount_type = 'fixed_amount' AND discount_value > 0)
    )
);

-- Create product_coupons table (many-to-many relationship between products and coupons)
CREATE TABLE product_coupons (
    product_id INTEGER REFERENCES products(product_id),
    coupon_id INTEGER REFERENCES coupons(coupon_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, coupon_id)
);

-- Create orders table
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    product_id INTEGER REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    final_amount DECIMAL(10,2) NOT NULL,
    coupon_id INTEGER REFERENCES coupons(coupon_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data for categories
INSERT INTO categories (name, description, parent_category_id) VALUES
('Electronics', 'Electronic devices and accessories', NULL),
('Clothing', 'Apparel and fashion items', NULL),
('Books', 'Books and publications', NULL),
('Smartphones', 'Mobile phones and accessories', 1),
('Laptops', 'Portable computers', 1),
('Men''s Clothing', 'Clothing for men', 2),
('Women''s Clothing', 'Clothing for women', 2),
('Fiction', 'Fiction books', 3),
('Non-Fiction', 'Non-fiction books', 3);

-- Insert sample data for products
INSERT INTO products (name, description, price, stock_quantity, category_id) VALUES
('iPhone 13', 'Latest Apple smartphone', 999.99, 50, 4),
('MacBook Pro', 'Professional laptop', 1299.99, 30, 5),
('Men''s T-Shirt', 'Cotton t-shirt for men', 29.99, 100, 6),
('Women''s Dress', 'Summer dress for women', 59.99, 75, 7),
('The Great Gatsby', 'Classic novel by F. Scott Fitzgerald', 14.99, 200, 8),
('Samsung Galaxy S21', 'Android smartphone', 799.99, 40, 4),
('Dell XPS 13', 'Ultrabook laptop', 999.99, 25, 5),
('Men''s Jeans', 'Denim jeans for men', 49.99, 80, 6),
('Women''s Blouse', 'Silk blouse for women', 39.99, 60, 7),
('Sapiens', 'Non-fiction book by Yuval Noah Harari', 19.99, 150, 9);

-- Insert sample data for coupons
INSERT INTO coupons (code, description, discount_type, discount_value, min_purchase_amount, max_discount_amount, start_date, end_date, usage_limit) VALUES
('SUMMER20', 'Summer sale 20% off', 'percentage', 20.00, 50.00, 100.00, '2024-06-01', '2024-08-31', 1000),
('WELCOME10', 'Welcome discount 10% off', 'percentage', 10.00, 25.00, 50.00, '2024-01-01', '2024-12-31', 5000),
('FLAT50', 'Flat $50 off', 'fixed_amount', 50.00, 200.00, 50.00, '2024-01-01', '2024-12-31', 2000),
('TECH15', '15% off on electronics', 'percentage', 15.00, 100.00, 150.00, '2024-01-01', '2024-12-31', 3000),
('BOOKS25', '25% off on books', 'percentage', 25.00, 30.00, 75.00, '2024-01-01', '2024-12-31', 1500);

-- Insert sample data for product_coupons
INSERT INTO product_coupons (product_id, coupon_id) VALUES
(1, 1), -- iPhone 13 with SUMMER20
(2, 1), -- MacBook Pro with SUMMER20
(6, 4), -- Samsung Galaxy S21 with TECH15
(7, 4), -- Dell XPS 13 with TECH15
(5, 5), -- The Great Gatsby with BOOKS25
(10, 5); -- Sapiens with BOOKS25

-- Insert sample data for orders
INSERT INTO orders (status, product_id, quantity, unit_price, total_amount, discount_amount, final_amount, coupon_id) VALUES
('completed', 1, 1, 999.99, 999.99, 199.99, 800.00, 1),
('processing', 2, 1, 1299.99, 1299.99, 194.99, 1105.00, 4),
('completed', 3, 2, 29.99, 59.98, 0.00, 59.98, NULL),
('pending', 4, 1, 59.99, 59.99, 14.99, 45.00, 2),
('completed', 6, 1, 799.99, 799.99, 120.00, 679.99, 4);

-- Create indexes for better query performance
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_coupons_code ON coupons(code);
CREATE INDEX idx_coupons_dates ON coupons(start_date, end_date);
CREATE INDEX idx_product_coupons_coupon ON product_coupons(coupon_id);
CREATE INDEX idx_orders_coupon ON orders(coupon_id);
CREATE INDEX idx_orders_product ON orders(product_id);

-- Add triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_categories_updated_at
    BEFORE UPDATE ON categories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_coupons_updated_at
    BEFORE UPDATE ON coupons
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add trigger for coupon usage tracking
CREATE OR REPLACE FUNCTION update_coupon_usage()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.coupon_id IS NOT NULL THEN
        UPDATE coupons
        SET times_used = times_used + 1
        WHERE coupon_id = NEW.coupon_id;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER track_coupon_usage
    AFTER INSERT ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_coupon_usage(); 