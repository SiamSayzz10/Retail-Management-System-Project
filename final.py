import mysql.connector
from flask import Flask, request, jsonify
from flask_cors import CORS
from decimal import Decimal
import json
from datetime import date

# --- Database Configuration ---
# IMPORTANT: Update these with your actual MySQL credentials
DB_CONFIG = {
    'user': 'root',    # e.g., 'root'
    'password': '', # e.g., 'password'
    'host': '127.0.0.1',
    'database': 'retail_management_db'
}

app = Flask(__name__)
# Enable CORS for the frontend (running on a different port/location)
CORS(app)

# --- Utility Functions ---

def get_db_connection():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection failed: {err}")
        return None

def fetch_all_data(query, params=None):
    """Executes a SELECT query and returns all results as a list of dictionaries."""
    conn = get_db_connection()
    if not conn:
        return {'error': 'Database connection failed'}, 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        records = cursor.fetchall()
        
        # --- CRITICAL FIX: Convert Decimal and Date types for JSON serialization ---
        def convert_data_types(data):
            """Converts Decimal to float and date objects to strings."""
            if isinstance(data, list):
                return [convert_data_types(item) for item in data]
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, Decimal):
                        data[key] = float(value)
                    elif isinstance(value, date):
                        data[key] = value.isoformat()
                    # Recursive call for nested structures if needed, though simple tables won't require it
                return data
            return data
            
        return convert_data_types(records)

    except mysql.connector.Error as err:
        return {'error': f'Database query failed: {err}'}, 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --- API Endpoints ---

# Login Endpoint
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('userId')
    password = data.get('password')
    role = data.get('role')

    if not user_id or not password or not role:
        return jsonify({'error': 'Missing credentials or role'}), 400

    query = "SELECT user_id FROM users WHERE user_id = %s AND password = %s AND role = %s"
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, (user_id, password, role))
        user = cursor.fetchone()

        if user:
            return jsonify({'userId': user['user_id']}), 200
        else:
            return jsonify({'error': 'Invalid credentials or role mismatch'}), 401
    except mysql.connector.Error as err:
        return jsonify({'error': f'Login error: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --- Products (Inventory Manager & Staff) ---

@app.route('/api/products', methods=['GET'])
def get_products():
    query = "SELECT product_id, name, price, stock FROM products ORDER BY product_id"
    result = fetch_all_data(query)
    if isinstance(result, tuple): # Check if error tuple was returned
        return jsonify(result[0]), result[1]
    return jsonify(result), 200

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    name = data.get('name')
    price = data.get('price')
    stock = data.get('stock')
    
    if not name or price is None or stock is None:
        return jsonify({'error': 'Missing product data'}), 400

    query = "INSERT INTO products (name, price, stock) VALUES (%s, %s, %s)"
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute(query, (name, price, stock))
        conn.commit()
        return jsonify({'message': 'Product added', 'product_id': cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        return jsonify({'error': f'Product insertion failed: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --- NEW: UPDATE PRODUCT ENDPOINT ---
@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.json
    name = data.get('name')
    price = data.get('price')
    stock = data.get('stock')

    if not name or price is None or stock is None:
        return jsonify({'error': 'Missing product data'}), 400

    query = "UPDATE products SET name = %s, price = %s, stock = %s WHERE product_id = %s"
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute(query, (name, price, stock, product_id))
        conn.commit()
        
        if cursor.rowcount == 0:
             return jsonify({'error': 'Product not found or no changes made'}), 404
             
        return jsonify({'message': 'Product updated successfully'}), 200
    except mysql.connector.Error as err:
        return jsonify({'error': f'Product update failed: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    query = "DELETE FROM products WHERE product_id = %s"
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute(query, (product_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'error': 'Product not found'}), 404
        return jsonify({'message': 'Product deleted'}), 200
    except mysql.connector.Error as err:
        return jsonify({'error': f'Product deletion failed: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --- Shipments (Shipment Manager) ---

@app.route('/api/shipments', methods=['GET'])
def get_shipments():
    query = "SELECT shipment_id, customer_name, shipping_address, tracking_number, status FROM shipments ORDER BY shipment_id DESC"
    result = fetch_all_data(query)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result), 200

@app.route('/api/shipments', methods=['POST'])
def add_shipment():
    data = request.json
    customer = data.get('customer')
    address = data.get('address')
    
    if not customer or not address:
        return jsonify({'error': 'Missing customer name or address'}), 400

    query = "INSERT INTO shipments (customer_name, shipping_address, status) VALUES (%s, %s, 'Pending')"
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute(query, (customer, address))
        conn.commit()
        return jsonify({'message': 'Shipment added', 'shipment_id': cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        return jsonify({'error': f'Shipment insertion failed: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/api/shipments/<int:shipment_id>', methods=['PUT'])
def update_shipment(shipment_id):
    data = request.json
    new_status = data.get('status')
    
    if new_status not in ['Pending', 'Done']:
        return jsonify({'error': 'Invalid status provided'}), 400

    # If marking as 'Done', generate a simple tracking number
    tracking = f'TRK{shipment_id}{date.today().strftime("%m%d")}' if new_status == 'Done' else None
    
    query = "UPDATE shipments SET status = %s, tracking_number = %s WHERE shipment_id = %s"
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute(query, (new_status, tracking, shipment_id))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'error': 'Shipment not found'}), 404
        return jsonify({'message': 'Shipment updated', 'tracking_number': tracking}), 200
    except mysql.connector.Error as err:
        return jsonify({'error': f'Shipment update failed: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


# --- Sales (Cashier & Owner) ---

@app.route('/api/sales', methods=['GET'])
def get_sales():
    query = "SELECT sale_id, sale_date, cashier_id, total, items_count FROM sales ORDER BY sale_id DESC"
    result = fetch_all_data(query)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result), 200

@app.route('/api/sales', methods=['POST'])
def finalize_sale():
    data = request.json
    cart = data.get('cart')
    cashier_id = data.get('cashierId')
    total = data.get('total')
    items_count = data.get('itemsCount')
    sale_date = date.today()

    if not all([cart, cashier_id, total, items_count]):
        return jsonify({'error': 'Missing sales data for finalization'}), 400
        
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # 1. Record the sale transaction
        sale_query = "INSERT INTO sales (sale_date, cashier_id, total, items_count) VALUES (%s, %s, %s, %s)"
        cursor.execute(sale_query, (sale_date, cashier_id, total, items_count))
        
        # 2. Update inventory for each item in the cart
        inventory_query = "UPDATE products SET stock = stock - %s WHERE product_id = %s"
        for item in cart:
            cursor.execute(inventory_query, (item['quantity'], item['id']))
        
        conn.commit()
        return jsonify({'message': 'Sale finalized and inventory updated'}), 201
        
    except mysql.connector.Error as err:
        conn.rollback() # Important: Rollback on error
        return jsonify({'error': f'Transaction failed during sale or inventory update: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --- Users (Owner Only) ---

@app.route('/api/users', methods=['GET'])
def get_users():
    # Note: Passwords are included here for Owner's view as requested.
    query = "SELECT user_id, role, password FROM users ORDER BY user_id"
    result = fetch_all_data(query)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result), 200

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    userId = data.get('userId')
    password = data.get('password')
    role = data.get('role')
    
    if not all([userId, password, role]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # *** BACKEND VALIDATION: Password length check ***
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters long.'}), 400
        
    query = "INSERT INTO users (user_id, password, role) VALUES (%s, %s, %s)"
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute(query, (userId, password, role))
        conn.commit()
        return jsonify({'message': f'User {userId} created'}), 201
    except mysql.connector.IntegrityError:
        return jsonify({'error': f'User ID {userId} already exists.'}), 409
    except mysql.connector.Error as err:
        return jsonify({'error': f'User creation failed: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # 1. Start Transaction
        conn.start_transaction()
        
        # 2. Delete Dependent Sales Records (Fixing Foreign Key Constraint issue via API)
        delete_sales_query = "DELETE FROM sales WHERE cashier_id = %s"
        cursor.execute(delete_sales_query, (user_id,))
        
        # 3. Delete User Record
        delete_user_query = "DELETE FROM users WHERE user_id = %s"
        cursor.execute(delete_user_query, (user_id,))
        
        if cursor.rowcount == 0:
            # If user wasn't found in the users table, rollback and return 404
            conn.rollback()
            return jsonify({'error': 'User not found'}), 404
            
        # 4. Commit Transaction
        conn.commit()
        
        return jsonify({'message': f'User {user_id} and associated sales records deleted'}), 200
        
    except mysql.connector.Error as err:
        conn.rollback() # Rollback on any failure
        return jsonify({'error': f'User deletion failed during transaction: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/api/users/<user_id>/password', methods=['PUT'])
def update_user_password(user_id):
    data = request.json
    new_password = data.get('newPassword')
    
    if not new_password or len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters long.'}), 400
        
    query = "UPDATE users SET password = %s WHERE user_id = %s"
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute(query, (new_password, user_id))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'error': 'User not found'}), 404
        return jsonify({'message': f'Password for {user_id} updated'}), 200
    except mysql.connector.Error as err:
        return jsonify({'error': f'Password update failed: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


if __name__ == '__main__':
    # Flask defaults to 127.0.0.1:5000, which matches the API_BASE_URL in the HTML
    app.run(debug=True)