# app.py
import os
import pymysql
pymysql.install_as_MySQLdb()
import MySQLdb  # for IntegrityError handling
import random
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, jsonify
)
from flask_mysqldb import MySQL
from flask_wtf.csrf import CSRFProtect, generate_csrf
import MySQLdb.cursors
from functools import wraps
from werkzeug.utils import secure_filename

# -----------------------
# Config
# -----------------------
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # replace with a secure value in production
csrf = CSRFProtect(app)

# MySQL / Flask-MySQLdb config (adjust as needed)
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '2003'
app.config['MYSQL_DB'] = 'inventory_db'
app.config['MYSQL_PORT'] = 3306

# Uploads
UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# Initialize MySQL
mysql = MySQL(app)

# Expose csrf_token() to templates
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

# -----------------------
# Utilities & Decorators
# -----------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def is_ajax_request():
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

def save_uploaded_file(file_obj):
    """
    Save an uploaded file to UPLOAD_FOLDER and return the path stored in DB
    (relative to the 'static' folder). Returns None if file_obj is falsy.
    """
    if not file_obj or file_obj.filename == '':
        return None
    filename = secure_filename(file_obj.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file_obj.save(save_path)
    # store path as 'static/uploads/<filename>' to match your template usage
    db_path = os.path.join('static', 'uploads', filename).replace('\\', '/')
    return db_path

def generate_unique_product_code():
    """
    Create a reasonably compact, unique-looking product code:
    PRD + UTC timestamp (YYYYMMDDHHMMSS) + 4 random digits
    Example: PRD202510301234561234
    """
    ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    rand = random.randint(1000, 9999)
    return f"PRD{ts}{rand}"

# -----------------------
# Authentication Routes
# -----------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect logged-in users
    if 'logged_in' in session and session.get('logged_in'):
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Simple default auth: change to DB-based auth for production
        if username == 'admin' and password == 'admin123':
            session['logged_in'] = True
            session['username'] = username
            flash('Welcome back, admin!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials!', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# -----------------------
# Dashboard / Home
# -----------------------
@app.route('/home')
@login_required
def home():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # recent activities (movements)
    cur.execute("""
        SELECT 
            'movement' as type, 
            m.id, 
            p.name as product_name,
            (SELECT branch_name FROM locations WHERE id = m.from_location) as from_loc,
            (SELECT branch_name FROM locations WHERE id = m.to_location) as to_loc,
            m.quantity, 
            m.created_at as timestamp
        FROM movements m 
        JOIN products p ON m.product_id = p.id
        ORDER BY m.created_at DESC LIMIT 5
    """)
    recent_activities = cur.fetchall()

    # insights
    cur.execute("SELECT COUNT(*) as total_products FROM products")
    total_products = cur.fetchone().get('total_products', 0)

    cur.execute("SELECT COUNT(*) as total_locations FROM locations")
    total_locations = cur.fetchone().get('total_locations', 0)

    cur.execute("SELECT SUM(quantity) as total_stock FROM products")
    total_stock = cur.fetchone().get('total_stock') or 0

    cur.execute("SELECT COUNT(*) as total_movements FROM movements")
    total_movements = cur.fetchone().get('total_movements', 0)

    cur.close()

    insights = {
        'total_products': total_products,
        'total_locations': total_locations,
        'total_stock': total_stock,
        'total_movements': total_movements
    }

    return render_template('home.html', activities=recent_activities, insights=insights)

# -----------------------
# Products
# -----------------------
@app.route('/products')
@login_required
def products():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT p.*, l.branch_name as location_name, l.city as location_city
        FROM products p 
        LEFT JOIN locations l ON p.location_id = l.id
        ORDER BY p.id DESC
    """)
    products = cur.fetchall()
    cur.execute("SELECT id, location_id, branch_name, city FROM locations ORDER BY branch_name ASC")
    locations = cur.fetchall()
    cur.close()
    return render_template('products.html', products=products, locations=locations)

@app.route('/add_product', methods=['POST'])
@login_required
def add_product():
    # read product_code early so duplicate error message can reference it
    product_code = (request.form.get('product_code') or '').strip()
    try:
        name = request.form.get('name')
        # Normalize numeric fields
        quantity = int(request.form.get('quantity') or 0)
        location_id = request.form.get('location_id') or None
        description = request.form.get('description') or None
        image_file = request.files.get('image')

        # If no product_code provided, generate one
        if not product_code:
            # try up to a few times to avoid improbable collision
            for _ in range(3):
                candidate = generate_unique_product_code()
                # quick check if exists
                cur_check = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cur_check.execute("SELECT id FROM products WHERE product_code = %s LIMIT 1", (candidate,))
                exists = cur_check.fetchone()
                cur_check.close()
                if not exists:
                    product_code = candidate
                    break
            # if still empty (extremely unlikely), fallback to UUID-like
            if not product_code:
                product_code = generate_unique_product_code()

        image_path = save_uploaded_file(image_file)

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO products (product_code, name, quantity, location_id, description, image_path, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (product_code, name, quantity, location_id, description, image_path, datetime.utcnow()))
        mysql.connection.commit()

        new_id = cur.lastrowid

        # Support AJAX + normal form
        if is_ajax_request():
            cur.execute("""
                SELECT p.*, l.branch_name as location_name, l.city as location_city
                FROM products p
                LEFT JOIN locations l ON p.location_id = l.id
                WHERE p.id = %s
            """, (new_id,))
            new_product = cur.fetchone()
            cur.close()
            return jsonify({'status': 'success', 'message': 'Product added', 'product': new_product}), 201

        cur.close()
        flash('✅ Product added successfully!', 'success')
        return redirect(url_for('products'))

    except MySQLdb.IntegrityError as e:
        mysql.connection.rollback()
        # If duplicate product_code (1062) show friendly message
        if e.args and e.args[0] == 1062:
            flash(f'❌ Error: Product Code "{product_code}" already exists. Try again.', 'error')
        else:
            flash(f'❌ Database integrity error: {e}', 'error')
        return redirect(url_for('products'))

    except Exception as e:
        print(f"Error adding product: {e}")
        mysql.connection.rollback()
        if is_ajax_request():
            return jsonify({'status': 'error', 'message': 'Error adding product'}), 500
        flash('❌ Error adding product', 'error')
        return redirect(url_for('products'))

@app.route('/update_product/<int:id>', methods=['POST'])
@login_required
def update_product(id):
    cur = None
    try:
        # We will *not* trust the incoming product_code for updates.
        # Instead, fetch the current product_code from DB and keep it unchanged.
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT product_code FROM products WHERE id = %s", (id,))
        existing = cur.fetchone()
        if not existing:
            flash('❌ Product not found', 'error')
            cur.close()
            return redirect(url_for('products'))
        product_code = existing['product_code']

        # get updated fields
        name = request.form.get('name')
        description = request.form.get('description')
        quantity = int(request.form.get('quantity') or 0)
        location_id = request.form.get('location_id') or None
        image = request.files.get('image')

        # Check if a new image is uploaded
        if image and image.filename:
            filename = secure_filename(image.filename)
            # store as 'static/uploads/filename' to match existing pattern
            db_path = os.path.join('static', 'uploads', filename).replace('\\', '/')
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(save_path)

            cur.execute("""
                UPDATE products 
                SET name=%s, description=%s, quantity=%s, location_id=%s, image_path=%s
                WHERE id=%s
            """, (name, description, quantity, location_id, db_path, id))
        else:
            cur.execute("""
                UPDATE products 
                SET name=%s, description=%s, quantity=%s, location_id=%s
                WHERE id=%s
            """, (name, description, quantity, location_id, id))

        mysql.connection.commit()
        cur.close()
        flash('✅ Product updated successfully!', 'success')
        return redirect(url_for('products'))

    except MySQLdb.IntegrityError as e:
        mysql.connection.rollback()
        # In case some other integrity error appears
        flash(f'❌ Database integrity error: {e}', 'error')
        if cur:
            cur.close()
        return redirect(url_for('products'))

    except Exception as e:
        print(f"Error updating product: {e}")
        mysql.connection.rollback()
        if cur:
            cur.close()
        flash('❌ Error updating product', 'error')
        return redirect(url_for('products'))

# -----------------------
# Delete product
# -----------------------
@app.route('/delete_product/<int:id>')
@login_required
def delete_product(id):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # check movements
        cur.execute("SELECT COUNT(*) as count FROM movements WHERE product_id = %s", (id,))
        result = cur.fetchone()
        if result and result.get('count', 0) > 0:
            cur.close()
            flash('❌ Cannot delete product because it has movement records. Delete movement records first.', 'error')
            return redirect(url_for('products'))

        cur.execute("DELETE FROM products WHERE id = %s", (id,))
        mysql.connection.commit()
        cur.close()

        flash('🗑️ Product deleted successfully!', 'success')
        return redirect(url_for('products'))
    except Exception as e:
        print(f"Error deleting product: {e}")
        mysql.connection.rollback()
        flash('❌ Error deleting product', 'error')
        return redirect(url_for('products'))

# -----------------------
# Locations
# -----------------------
@app.route('/locations')
@login_required
def locations():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT id, location_id, branch_name, city FROM locations ORDER BY branch_name ASC")
    locations = cur.fetchall()
    cur.close()
    return render_template('locations.html', locations=locations)

@app.route('/add_location', methods=['POST'])
@login_required
def add_location():
    try:
        location_id = request.form.get('location_id')
        branch_name = request.form.get('branch_name')
        city = request.form.get('city')

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO locations (location_id, branch_name, city)
            VALUES (%s, %s, %s)
        """, (location_id, branch_name, city))
        mysql.connection.commit()
        cur.close()

        flash('📍 Location added successfully!', 'success')
        return redirect(url_for('locations'))
    except Exception as e:
        print(f"Error adding location: {e}")
        mysql.connection.rollback()
        flash('❌ Error adding location', 'error')
        return redirect(url_for('locations'))

@app.route('/update_location/<int:id>', methods=['POST'])
@login_required
def update_location(id):
    try:
        branch_name = request.form.get('branch_name')
        city = request.form.get('city')

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("UPDATE locations SET branch_name=%s, city=%s WHERE id=%s", (branch_name, city, id))
        mysql.connection.commit()

        if cur.rowcount > 0:
            cur.execute("SELECT id, location_id, branch_name, city FROM locations WHERE id = %s", (id,))
            updated_loc = cur.fetchone()
            cur.close()
            return jsonify({'status': 'success', 'message': 'Location updated!', 'updated_location': updated_loc}), 200
        else:
            cur.close()
            return jsonify({'status': 'error', 'message': 'Location not found'}), 404
    except Exception as e:
        print(f"Error updating location: {e}")
        mysql.connection.rollback()
        return jsonify({'status': 'error', 'message': 'Error updating location'}), 500

from flask import request, jsonify

@app.route('/delete_location/<int:id>', methods=['POST'])
@login_required
def delete_location(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM locations WHERE id = %s", (id,))
        mysql.connection.commit()
        cur.close()

        if is_ajax_request():
            return jsonify({'status': 'success', 'message': 'Location deleted successfully!'}), 200
        flash('🗑️ Location deleted successfully!', 'success')
        return redirect(url_for('locations'))
    except Exception as e:
        print(f"Error deleting location: {e}")
        mysql.connection.rollback()
        if is_ajax_request():
            return jsonify({'status': 'error', 'message': str(e)}), 500
        flash('❌ Error deleting location', 'error')
        return redirect(url_for('locations'))



 



# -----------------------
# Movements (stock transfer)
# -----------------------
@app.route('/movements')
@login_required
def movements():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT m.id, p.name AS product, 
               l1.branch_name AS from_loc, l1.city AS from_city,
               l2.branch_name AS to_loc, l2.city AS to_city,
               m.quantity, m.created_at as timestamp
        FROM movements m 
        JOIN products p ON m.product_id = p.id
        JOIN locations l1 ON m.from_location = l1.id
        JOIN locations l2 ON m.to_location = l2.id
        ORDER BY m.created_at DESC
    """)
    movements = cur.fetchall()

    # products with quantity > 0 for movement selection
    cur.execute("""
        SELECT p.id, p.name, p.quantity, l.branch_name as location_name 
        FROM products p 
        LEFT JOIN locations l ON p.location_id = l.id 
        WHERE p.quantity > 0
        ORDER BY p.name ASC
    """)
    products = cur.fetchall()

    cur.execute("SELECT id, location_id, branch_name, city FROM locations ORDER BY branch_name ASC")
    locations = cur.fetchall()
    cur.close()

    return render_template('movements.html', movements=movements, products=products, locations=locations)

@app.route('/add_movement', methods=['POST'])
@login_required
def add_movement():
    try:
        product_id = request.form.get('product_id')
        from_location = request.form.get('from_location')
        to_location = request.form.get('to_location')
        quantity = int(request.form.get('quantity', 0))

        cur = mysql.connection.cursor()
        # Decrease quantity from product
        cur.execute("UPDATE products SET quantity = quantity - %s WHERE id = %s", (quantity, product_id))
        # Add movement record
        cur.execute("""
            INSERT INTO movements (product_id, from_location, to_location, quantity, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (product_id, from_location, to_location, quantity, datetime.utcnow()))
        mysql.connection.commit()
        cur.close()

        flash('📦 Stock movement recorded successfully!', 'success')
        return redirect(url_for('movements'))
    except Exception as e:
        print(f"Error adding movement: {e}")
        mysql.connection.rollback()
        flash('❌ Error recording movement', 'error')
        return redirect(url_for('movements'))

# -----------------------
# Stock / Search
# -----------------------
import pymysql

connection = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='2003',
    database='inventory_db'
)

try:
    with connection.cursor() as cursor:
        branch_name = 'branch 1'

        # Step 1: Get location ID
        cursor.execute("SELECT id FROM locations WHERE branch_name = %s", (branch_name,))
        loc = cursor.fetchone()

        if loc:
            loc_id = loc[0]

            # Step 2: Delete movements that reference this location
            cursor.execute("DELETE FROM movements WHERE from_location = %s OR to_location = %s", (loc_id, loc_id))

            # Step 3: Delete the location itself
            cursor.execute("DELETE FROM locations WHERE id = %s", (loc_id,))

            connection.commit()
            print(f"✅ Deleted location '{branch_name}' and related movements successfully!")
        else:
            print(f"⚠️ No location found with branch_name = '{branch_name}'")

except Exception as e:
    print(f"❌ Error deleting branch: {e}")
    connection.rollback()

finally:
    connection.close()

@app.route('/stock')
@login_required
def stock():
    search = request.args.get('search', '').strip()
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if search:
        like = f'%{search}%'
        cur.execute("""
            SELECT p.*, l.branch_name as location_name, l.city as location_city,
                   CONCAT(l.branch_name, ' (', l.city, ')') as location_display
            FROM products p 
            LEFT JOIN locations l ON p.location_id = l.id 
            WHERE p.name LIKE %s OR l.branch_name LIKE %s OR l.city LIKE %s OR p.product_code LIKE %s
            ORDER BY p.name ASC
        """, (like, like, like, like))
    else:
        cur.execute("""
            SELECT p.*, l.branch_name as location_name, l.city as location_city,
                   CONCAT(l.branch_name, ' (', l.city, ')') as location_display
            FROM products p 
            LEFT JOIN locations l ON p.location_id = l.id
            ORDER BY p.name ASC
        """)
    products = cur.fetchall()
    cur.close()
    return render_template('stock.html', products=products, search=search)

# -----------------------
# Main
# -----------------------
if __name__ == '__main__':
    # Ensure secret_key set
    app.secret_key = app.secret_key or 'supersecretkey'
    app.run(debug=True)
