import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from flask_wtf.csrf import CSRFProtect

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("Set SECRET_KEY in your environment before starting the app.")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/product_store"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    products = db.relationship("Product", backref="category", lazy=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, default="")
    specifications = db.Column(db.Text, default="")
    mrp = db.Column(db.Numeric(10, 2), nullable=False)
    selling_price = db.Column(db.Numeric(10, 2), nullable=False)
    image_filename = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)

    @property
    def discount_percent(self):
        if not self.mrp or self.mrp <= 0 or self.selling_price >= self.mrp:
            return 0
        return round((float(self.mrp - self.selling_price) / float(self.mrp)) * 100)


class ProductQuery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), default="")
    message = db.Column(db.Text, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    status = db.Column(db.String(30), default="Open", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    product = db.relationship("Product", backref="queries")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_price(value, field_name):
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0:
            raise InvalidOperation
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field_name} must be a valid non-negative amount.")


@app.context_processor
def inject_globals():
    return {"now": datetime.utcnow}


@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)
    query = Product.query.filter_by(is_active=True)
    if search:
        term = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(term), Product.description.ilike(term),
                                 Product.specifications.ilike(term)))
    if category_id:
        query = query.filter_by(category_id=category_id)
    products = query.order_by(Product.created_at.desc()).all()
    categories = Category.query.order_by(Category.name).all()
    return render_template("index.html", products=products, categories=categories,
                           search=search, selected_category=category_id)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    return render_template("product_detail.html", product=product)


@app.route("/suggestion", methods=["GET", "POST"])
def suggestion():
    product_id = request.args.get("product_id", type=int)
    product = db.session.get(Product, product_id) if product_id else None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        posted_product_id = request.form.get("product_id", type=int)
        if not name or not message:
            flash("Please enter your name and message.", "error")
        elif len(message) > 5000:
            flash("Message is too long (maximum 5,000 characters).", "error")
        else:
            linked_product = db.session.get(Product, posted_product_id) if posted_product_id else None
            item = ProductQuery(name=name, email=email, message=message,
                                product_id=linked_product.id if linked_product else None)
            db.session.add(item)
            db.session.commit()
            flash("Thanks! Your query has been saved.", "success")
            return redirect(url_for("index"))
    return render_template("suggestion.html", product=product)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard" if current_user.role == "admin" else "index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Welcome back.", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("admin_dashboard" if user.role == "admin" else "index"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template(
        "admin_dashboard.html",
        product_count=Product.query.count(),
        category_count=Category.query.count(),
        query_count=ProductQuery.query.filter_by(status="Open").count(),
        recent_queries=ProductQuery.query.order_by(ProductQuery.created_at.desc()).limit(8).all()
    )


@app.route("/admin/products")
@admin_required
def admin_products():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin_products.html", products=products)


@app.route("/admin/products/new", methods=["GET", "POST"])
@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_product(product_id=None):
    product = db.session.get(Product, product_id) if product_id else Product()
    if product_id and product is None:
        abort(404)
    categories = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        specifications = request.form.get("specifications", "").strip()
        category_id = request.form.get("category_id", type=int)
        category = db.session.get(Category, category_id) if category_id else None
        if not name or not category:
            flash("Product name and a valid category are required.", "error")
            return render_template("product_form.html", product=product, categories=categories)
        try:
            mrp = parse_price(request.form.get("mrp", ""), "MRP")
            selling_price = parse_price(request.form.get("selling_price", ""), "Selling price")
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("product_form.html", product=product, categories=categories)
        if mrp <= 0:
            flash("MRP must be greater than zero.", "error")
            return render_template("product_form.html", product=product, categories=categories)
        if selling_price > mrp:
            flash("Selling price cannot exceed MRP. If you need to show a premium price, adjust this validation.", "error")
            return render_template("product_form.html", product=product, categories=categories)

        product.name = name
        product.description = description
        product.specifications = specifications
        product.category_id = category.id
        product.mrp = mrp
        product.selling_price = selling_price
        product.is_active = request.form.get("is_active") == "on"

        image = request.files.get("image")
        if image and image.filename:
            if not allowed_file(image.filename):
                flash("Image must be PNG, JPG, JPEG, WEBP or GIF.", "error")
                return render_template("product_form.html", product=product, categories=categories)
            safe_name = secure_filename(image.filename)
            unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{safe_name}"
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
            product.image_filename = unique_name

        if not product_id:
            db.session.add(product)
        db.session.commit()
        flash("Product saved.", "success")
        return redirect(url_for("admin_products"))
    return render_template("product_form.html", product=product, categories=categories)


@app.route("/admin/categories", methods=["GET", "POST"])
@admin_required
def admin_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = "-".join(name.lower().split())
        if not name:
            flash("Category name is required.", "error")
        elif Category.query.filter(or_(Category.name.ilike(name), Category.slug == slug)).first():
            flash("That category already exists.", "error")
        else:
            db.session.add(Category(name=name, slug=slug))
            db.session.commit()
            flash("Category added.", "success")
            return redirect(url_for("admin_categories"))
    return render_template("admin_categories.html", categories=Category.query.order_by(Category.name).all())


@app.route("/admin/queries")
@admin_required
def admin_queries():
    queries = ProductQuery.query.order_by(ProductQuery.created_at.desc()).all()
    return render_template("admin_queries.html", queries=queries)


@app.route("/admin/queries/<int:query_id>/status", methods=["POST"])
@admin_required
def update_query_status(query_id):
    item = db.session.get(ProductQuery, query_id)
    if not item:
        abort(404)
    status = request.form.get("status")
    if status not in {"Open", "In progress", "Resolved"}:
        abort(400)
    item.status = status
    db.session.commit()
    flash("Query status updated.", "success")
    return redirect(url_for("admin_queries"))


@app.cli.command("init-db")
def init_db():
    """Create tables and a few demo categories/products."""
    db.create_all()
    if Category.query.count() == 0:
        categories = [
            Category(name="Electronics", slug="electronics"),
            Category(name="Home & Living", slug="home-living"),
            Category(name="Accessories", slug="accessories"),
        ]
        db.session.add_all(categories)
        db.session.flush()
        db.session.add_all([
            Product(name="Wireless Headphones", description="Comfortable wireless headphones for everyday use.",
                    specifications="Connectivity: Bluetooth\nBattery: Up to 20 hours\nWarranty: 1 year",
                    mrp=Decimal("2999.00"), selling_price=Decimal("2199.00"),
                    category_id=categories[0].id, is_active=True),
            Product(name="Desk Lamp", description="Adjustable LED desk lamp for work and study.",
                    specifications="Type: LED\nPower: 8W\nColour: Warm white",
                    mrp=Decimal("1499.00"), selling_price=Decimal("999.00"),
                    category_id=categories[1].id, is_active=True),
            Product(name="Everyday Backpack", description="A practical backpack for commuting.",
                    specifications="Capacity: 22L\nMaterial: Polyester\nCompartments: 3",
                    mrp=Decimal("1999.00"), selling_price=Decimal("1599.00"),
                    category_id=categories[2].id, is_active=True),
        ])
        db.session.commit()
    print("Database tables and demo data are ready.")


@app.cli.command("create-admin")
def create_admin():
    """Create an admin interactively; no default credentials are created."""
    import getpass
    username = input("Admin username: ").strip()
    email = input("Admin email: ").strip()
    password = getpass.getpass("Admin password (min 12 characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if len(password) < 12 or password != confirm:
        print("Passwords must match and be at least 12 characters.")
        return
    if User.query.filter(or_(User.username == username, User.email == email)).first():
        print("That username or email is already registered.")
        return
    user = User(username=username, email=email, role="admin")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print("Admin account created.")


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403


@app.errorhandler(413)
def too_large(_error):
    return render_template("error.html", code=413, message="That upload is too large. Maximum image size is 5 MB."), 413


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
