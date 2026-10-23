# Local Product Store (Flask + PostgreSQL)

A starter e-commerce catalogue you run on your own Windows laptop. It includes customer browsing, category/search filters, product detail/specifications, login, admin product editing and image uploads, category creation, and customer queries saved in PostgreSQL.

## What you need
- Python 3.11 or newer
- PostgreSQL installed and running locally
- VS Code (recommended)
- DBeaver (optional, for viewing the database)

## 1. Create a PostgreSQL database
In DBeaver, connect to your local PostgreSQL server and run:

```sql
CREATE DATABASE product_store;
```

Use the PostgreSQL username/password you already use in DBeaver. The app connects directly to PostgreSQL; DBeaver is just the database viewer/editor.

## 2. Open this folder in VS Code
Open the `local_product_store` folder in VS Code, then open Terminal > New Terminal.

Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt and run:
```bat
.venv\Scripts\activate.bat
```

Install dependencies:
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Set your environment variables
Generate a random secret key:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the generated value. In the same PowerShell terminal, set:
```powershell
$env:SECRET_KEY="paste-your-generated-secret-here"
$env:DATABASE_URL="postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/product_store"
```

Replace `postgres` and `YOUR_PASSWORD` with your PostgreSQL credentials. If your password contains special URL characters such as `@`, `:`, `/`, or `#`, URL-encode the password or create a dedicated PostgreSQL user with a simpler strong password. These variables apply to the current terminal session.

## 4. Create tables and demo products
```powershell
flask --app app init-db
```

This creates tables and inserts sample categories/products. It does not create a default admin account.

## 5. Create your admin login
```powershell
flask --app app create-admin
```

Follow the prompts. Use a unique password with at least 12 characters. There is no built-in default password.

## 6. Start the website
```powershell
flask --app app run --debug
```

Open http://127.0.0.1:5000 in your browser.

- Storefront: `http://127.0.0.1:5000/`
- Login: `http://127.0.0.1:5000/login`
- Admin dashboard: `http://127.0.0.1:5000/admin`

Stop the server with Ctrl+C in the terminal.

## Features
- Customer storefront with search and category filtering
- Product detail page with specifications, MRP, selling price and discount
- Admin-only product creation/editing and image upload (5 MB max)
- Admin-only category creation
- Customer product query/suggestion form
- Admin query inbox with Open / In progress / Resolved status
- Password hashing, session login, role checks and CSRF protection

## Database tables
- `user`
- `category`
- `product`
- `product_query`

Inspect these in DBeaver after running `init-db`.

## Important notes
- This is a starter project for local development, not yet a production-hardened public shop. Before exposing it to the internet, add HTTPS, rate limiting, email verification/password reset, stronger upload scanning, backups, logging and deployment-specific security settings.
- Do not expose your local PostgreSQL port to the internet.
- If you later host the website on a cloud platform, the deployed server cannot normally connect to `localhost` on your personal laptop. Use a managed PostgreSQL service or a private VPN/tunnel architecture. Free cloud database tiers and their limits can change.
- Local uploaded images are stored in `static/uploads`. Back them up; ephemeral cloud hosting may erase local uploads after restart/deployment.
- This starter stores suggestions even when the customer is not logged in. Do not collect sensitive personal information in the message field.
- Public customer account registration is not included yet; admin accounts are created through the CLI. Add customer registration only if you need it.
- Prices are validated server-side. Current rule prevents selling price from exceeding MRP.
