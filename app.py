import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, session, redirect, g
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

load_dotenv()

app.secret_key = os.environ.get("SECRET_KEY")

# =========================
# MySQL Configuration
# =========================

app.config['MYSQL_HOST'] = os.environ.get("MYSQL_HOST")
app.config['MYSQL_USER'] = os.environ.get("MYSQL_USER")
app.config['MYSQL_PASSWORD'] = os.environ.get("MYSQL_PASSWORD")
app.config['MYSQL_DB'] = os.environ.get("MYSQL_DB")


# =========================
# PyMySQL Connection
# =========================

class MySQL:

    def __init__(self, app):
        self.app = app
        app.teardown_appcontext(self.close_connection)

    @property
    def connection(self):

        if "db" not in g:

            g.db = pymysql.connect(
                host=self.app.config["MYSQL_HOST"],
                user=self.app.config["MYSQL_USER"],
                password=self.app.config["MYSQL_PASSWORD"],
                database=self.app.config["MYSQL_DB"],
                cursorclass=pymysql.cursors.Cursor,
                autocommit=False
            )

        return g.db

    def close_connection(self, exception=None):

        db = g.pop("db", None)

        if db is not None:
            db.close()


mysql = MySQL(app)


# =========================
# Home
# =========================

@app.route("/")
def home():

    return render_template("login.html")


# =========================
# Products
# =========================

@app.route("/products")
def products():

    cursor = mysql.connection.cursor()

    cursor.execute("SELECT * FROM products")

    products = cursor.fetchall()

    cursor.close()

    return render_template(
        "products.html",
        products=products
    )


# =========================
# Register
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        password = generate_password_hash(password)

        cursor = mysql.connection.cursor()

        cursor.execute(
            """
            INSERT INTO users
            (name, email, password)
            VALUES (%s, %s, %s)
            """,
            (name, email, password)
        )

        mysql.connection.commit()

        cursor.close()

        return "Registration Successful"

    return render_template("register.html")


# =========================
# Login
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        cursor = mysql.connection.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()

        if user and check_password_hash(user[3], password):

            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["role"] = user[4]

            if user[4] == "ADMIN":

                return render_template(
                    "admin.html",
                    name=user[1],
                    role=user[4]
                )

            return render_template(
                "dashboard.html",
                name=user[1],
                role=user[4]
            )

        return "Invalid Email or Password"

    return render_template("login.html")


# =========================
# Admin Dashboard
# =========================

@app.route("/admin")
def admin():

    if "user_id" not in session:

        return "Please login first"

    if session.get("role") != "ADMIN":

        return "Access Denied"

    return render_template(
        "admin.html",
        name=session.get("user_name"),
        role=session.get("role")
    )


# =========================
# Add Product
# =========================

@app.route("/add-product", methods=["GET", "POST"])
def add_product():

    if "user_id" not in session:

        return redirect("/login")

    if session.get("role") != "ADMIN":

        return "Access Denied"

    if request.method == "POST":

        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]
        category = request.form["category"]
        image_url = request.form["image_url"]
        stock = request.form["stock"]

        cursor = mysql.connection.cursor()

        cursor.execute(
            """
            INSERT INTO products
            (name, description, price, category, image_url, stock)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                name,
                description,
                price,
                category,
                image_url,
                stock
            )
        )

        mysql.connection.commit()

        cursor.close()

        return render_template("product_added.html")

    return render_template("add_product.html")


# =========================
# Edit Product
# =========================

@app.route("/edit-product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    if "user_id" not in session:

        return redirect("/login")

    if session.get("role") != "ADMIN":

        return "Access Denied"

    cursor = mysql.connection.cursor()

    if request.method == "POST":

        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]
        category = request.form["category"]
        image_url = request.form["image_url"]
        stock = request.form["stock"]

        cursor.execute(
            """
            UPDATE products
            SET name = %s,
                description = %s,
                price = %s,
                category = %s,
                image_url = %s,
                stock = %s
            WHERE id = %s
            """,
            (
                name,
                description,
                price,
                category,
                image_url,
                stock,
                id
            )
        )

        mysql.connection.commit()

        cursor.close()

        return "Product Updated Successfully"

    cursor.execute(
        "SELECT * FROM products WHERE id = %s",
        (id,)
    )

    product = cursor.fetchone()

    cursor.close()

    return render_template(
        "edit_product.html",
        product=product
    )


# =========================
# Delete Product
# =========================

@app.route("/delete-product/<int:id>")
def delete_product(id):

    if "user_id" not in session:

        return redirect("/login")

    if session.get("role") != "ADMIN":

        return "Access Denied"

    cursor = mysql.connection.cursor()

    cursor.execute(
        "DELETE FROM products WHERE id = %s",
        (id,)
    )

    mysql.connection.commit()

    cursor.close()

    return "Product Deleted Successfully"


# =========================
# Add Product to Cart
# =========================

@app.route("/add-to-cart/<int:product_id>")
def add_to_cart(product_id):

    if "user_id" not in session:

        return "Please login first"

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    # Get product stock

    cursor.execute(
        """
        SELECT stock
        FROM products
        WHERE id = %s
        """,
        (product_id,)
    )

    product = cursor.fetchone()

    if not product:

        cursor.close()

        return "Product Not Found"

    stock = product[0]

    # Check existing cart item

    cursor.execute(
        """
        SELECT quantity
        FROM cart
        WHERE user_id = %s
        AND product_id = %s
        """,
        (user_id, product_id)
    )

    existing_item = cursor.fetchone()

    if existing_item:

        current_quantity = existing_item[0]

        # Prevent quantity from exceeding stock

        if current_quantity >= stock:

            cursor.close()

            return "Stock Limit Reached"

        cursor.execute(
            """
            UPDATE cart
            SET quantity = quantity + 1
            WHERE user_id = %s
            AND product_id = %s
            """,
            (user_id, product_id)
        )

    else:

        # Product must have stock

        if stock <= 0:

            cursor.close()

            return "Out of Stock"

        cursor.execute(
            """
            INSERT INTO cart
            (user_id, product_id, quantity)
            VALUES (%s, %s, %s)
            """,
            (user_id, product_id, 1)
        )

    mysql.connection.commit()

    cursor.close()

    return render_template("cart_added.html")


# =========================
# View Cart
# =========================

@app.route("/cart")
def view_cart():

    if "user_id" not in session:

        return "Please login first"

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT cart.id,
               products.name,
               products.price,
               cart.quantity,
               (products.price * cart.quantity) AS total
        FROM cart
        JOIN products
        ON cart.product_id = products.id
        WHERE cart.user_id = %s
        """,
        (user_id,)
    )

    cart_items = cursor.fetchall()

    cursor.close()

    return render_template(
        "cart.html",
        cart_items=cart_items
    )


# =========================
# Increase Cart Quantity
# =========================

@app.route("/increase-cart/<int:cart_id>")
def increase_cart(cart_id):

    if "user_id" not in session:

        return redirect("/login")

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        UPDATE cart
        SET quantity = quantity + 1
        WHERE id = %s
        AND user_id = %s
        """,
        (cart_id, session["user_id"])
    )

    mysql.connection.commit()

    cursor.close()

    return redirect("/cart")


# =========================
# Decrease Cart Quantity
# =========================

@app.route("/decrease-cart/<int:cart_id>")
def decrease_cart(cart_id):

    if "user_id" not in session:

        return redirect("/login")

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        UPDATE cart
        SET quantity = quantity - 1
        WHERE id = %s
        AND user_id = %s
        AND quantity > 1
        """,
        (cart_id, session["user_id"])
    )

    mysql.connection.commit()

    cursor.close()

    return redirect("/cart")


# =========================
# Remove Cart Item
# =========================

@app.route("/remove-from-cart/<int:cart_id>")
def remove_from_cart(cart_id):

    if "user_id" not in session:

        return redirect("/login")

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        DELETE FROM cart
        WHERE id = %s
        AND user_id = %s
        """,
        (cart_id, session["user_id"])
    )

    mysql.connection.commit()

    cursor.close()

    return redirect("/cart")


# =========================
# Checkout
# =========================

@app.route("/checkout")
def checkout():

    if "user_id" not in session:

        return "Please login first"

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT products.name,
               products.price,
               cart.quantity,
               (products.price * cart.quantity) AS total
        FROM cart
        JOIN products
        ON cart.product_id = products.id
        WHERE cart.user_id = %s
        """,
        (user_id,)
    )

    cart_items = cursor.fetchall()

    cursor.close()

    return render_template(
        "checkout.html",
        cart_items=cart_items
    )


# =========================
# Place Order
# =========================

@app.route("/place-order", methods=["POST"])
def place_order():

    if "user_id" not in session:

        return "Please login first"

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    # Get cart items

    cursor.execute(
        """
        SELECT cart.product_id,
               cart.quantity,
               products.price
        FROM cart
        JOIN products
        ON cart.product_id = products.id
        WHERE cart.user_id = %s
        """,
        (user_id,)
    )

    cart_items = cursor.fetchall()

    if not cart_items:

        cursor.close()

        return "Your cart is empty"

    # Check product stock

    for item in cart_items:

        product_id = item[0]
        quantity = item[1]

        cursor.execute(
            "SELECT stock FROM products WHERE id = %s",
            (product_id,)
        )

        stock = cursor.fetchone()

        if stock is None:

            cursor.close()

            return "Product not found"

        if stock[0] < quantity:

            cursor.close()

            return "Not enough stock available"

    # Calculate total amount

    total_amount = 0

    for item in cart_items:

        total_amount += item[1] * item[2]

    # Create order

    cursor.execute(
        """
        INSERT INTO orders
        (user_id, total_amount)
        VALUES (%s, %s)
        """,
        (user_id, total_amount)
    )

    mysql.connection.commit()

    # Get newly created order ID

    order_id = cursor.lastrowid

    # Store products in order_items
    # Reduce product stock

    for item in cart_items:

        product_id = item[0]
        quantity = item[1]
        price = item[2]

        cursor.execute(
            """
            INSERT INTO order_items
            (order_id, product_id, quantity, price)
            VALUES (%s, %s, %s, %s)
            """,
            (
                order_id,
                product_id,
                quantity,
                price
            )
        )

        cursor.execute(
            """
            UPDATE products
            SET stock = stock - %s
            WHERE id = %s
            """,
            (quantity, product_id)
        )

    mysql.connection.commit()

    # Clear cart

    cursor.execute(
        "DELETE FROM cart WHERE user_id = %s",
        (user_id,)
    )

    mysql.connection.commit()

    cursor.close()

    return render_template("order_success.html")


# =========================
# My Orders
# =========================

@app.route("/my-orders")
def my_orders():

    if "user_id" not in session:

        return "Please login first"

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT id,
               total_amount,
               status,
               order_date
        FROM orders
        WHERE user_id = %s
        ORDER BY order_date DESC
        """,
        (user_id,)
    )

    orders = cursor.fetchall()

    cursor.close()

    return render_template(
        "my_orders.html",
        orders=orders
    )


# =========================
# Admin Orders
# =========================

@app.route("/admin-orders")
def admin_orders():

    if "user_id" not in session:

        return "Please login first"

    if session.get("role") != "ADMIN":

        return "Access Denied"

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT orders.id,
               users.name,
               users.email,
               orders.total_amount,
               orders.status,
               orders.order_date
        FROM orders
        JOIN users
        ON orders.user_id = users.id
        ORDER BY orders.order_date DESC
        """
    )

    orders = cursor.fetchall()

    cursor.close()

    return render_template(
        "admin_orders.html",
        orders=orders
    )


# =========================
# Update Order Status
# =========================

@app.route(
    "/update-order-status/<int:order_id>",
    methods=["POST"]
)
def update_order_status(order_id):

    if "user_id" not in session:

        return "Please login first"

    if session.get("role") != "ADMIN":

        return "Access Denied"

    status = request.form["status"]

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        UPDATE orders
        SET status = %s
        WHERE id = %s
        """,
        (status, order_id)
    )

    mysql.connection.commit()

    cursor.close()

    return render_template("order_status_updated.html")


# =========================
# Order Details
# =========================

@app.route("/order-details/<int:order_id>")
def order_details(order_id):

    if "user_id" not in session:

        return redirect("/login")

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT order_items.product_id,
               products.name,
               order_items.quantity,
               order_items.price,
               (order_items.quantity * order_items.price) AS total
        FROM order_items
        JOIN products
        ON order_items.product_id = products.id
        JOIN orders
        ON order_items.order_id = orders.id
        WHERE order_items.order_id = %s
        AND orders.user_id = %s
        """,
        (order_id, user_id)
    )

    items = cursor.fetchall()

    cursor.close()

    return render_template(
        "order_details.html",
        items=items,
        order_id=order_id
    )


# =========================
# Logout
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return render_template("logout.html")


# =========================
# Run Application
# =========================

if __name__ == "__main__":

    app.run(debug=False)