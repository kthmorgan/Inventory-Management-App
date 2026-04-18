#!/usr/bin/env python3
"""Inventory Management Web App"""

import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'inventory.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')
PHOTO_DIR = os.path.join(BASE_DIR, 'static', 'photos')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    new_db = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())

    # Migration: if categories table is empty but items have categories, migrate them
    if not new_db:
        migrate_categories(conn)

    conn.close()
    os.makedirs(PHOTO_DIR, exist_ok=True)


def migrate_categories(conn):
    """Migrate existing freeform categories from items table into the categories table."""
    # Check if categories table exists (graceful for old DBs)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if 'categories' not in tables:
        conn.execute("""CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()

    # Get existing categories from the categories table
    existing = set(r[0] for r in conn.execute("SELECT name FROM categories").fetchall())

    # Get distinct categories currently in use by items
    item_categories = [r[0] for r in conn.execute(
        "SELECT DISTINCT category FROM items WHERE category IS NOT NULL AND category != ''"
    ).fetchall()]

    # Insert any categories from items that aren't already in the categories table
    added = 0
    for cat in item_categories:
        if cat not in existing:
            try:
                conn.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
                added += 1
            except sqlite3.IntegrityError:
                pass  # already exists (race condition)

    if added:
        conn.commit()
        print(f"Migrated {added} existing categories into categories table")


def get_categories():
    """Get all categories from the categories table."""
    conn = get_db()
    cats = [dict(r) for r in conn.execute("SELECT * FROM categories ORDER BY name").fetchall()]
    conn.close()
    return cats


def item_from_row(row):
    d = dict(row)
    conn = get_db()
    photos = conn.execute("SELECT * FROM photos WHERE item_id = ?", (d['id'],)).fetchall()
    d['photos'] = [dict(p) for p in photos]
    conn.close()
    return d


# ── Category Management ─────────────────────────────────────────

@app.route('/categories')
def categories_page():
    conn = get_db()
    categories = conn.execute("SELECT c.*, (SELECT COUNT(*) FROM items WHERE category = c.name) as item_count FROM categories c ORDER BY c.name").fetchall()
    conn.close()
    return render_template('categories.html', categories=categories)


@app.route('/categories/add', methods=['POST'])
def category_add():
    name = request.form.get('name', '').strip()
    if not name:
        return redirect(url_for('categories_page'))
    conn = get_db()
    try:
        conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # already exists
    conn.close()
    return redirect(url_for('categories_page'))


@app.route('/categories/rename/<int:cat_id>', methods=['POST'])
def category_rename(cat_id):
    new_name = request.form.get('name', '').strip()
    if not new_name:
        return redirect(url_for('categories_page'))
    conn = get_db()
    # Get old name
    row = conn.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)).fetchone()
    if row:
        old_name = row['name']
        try:
            conn.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, cat_id))
            # Update all items with the old category name
            conn.execute("UPDATE items SET category = ? WHERE category = ?", (new_name, old_name))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # new name already exists
    conn.close()
    return redirect(url_for('categories_page'))


@app.route('/categories/delete/<int:cat_id>', methods=['POST'])
def category_delete(cat_id):
    conn = get_db()
    row = conn.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)).fetchone()
    if row:
        # Clear category from items that use it
        conn.execute("UPDATE items SET category = '' WHERE category = ?", (row['name'],))
        conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('categories_page'))


# ── Web Routes ──────────────────────────────────────────────────

@app.route('/')
def index():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '')
    location = request.args.get('location', '')
    sort = request.args.get('sort', 'name')
    sort_dir = request.args.get('dir', 'asc')

    valid_sorts = {'name', 'created_at', 'purchase_value', 'quantity', 'location', 'category'}
    if sort not in valid_sorts:
        sort = 'name'
    if sort_dir not in ('asc', 'desc'):
        sort_dir = 'asc'

    conn = get_db()

    # Build query
    query = "SELECT * FROM items"
    conditions = []
    params = []

    if search:
        query = """SELECT items.* FROM items 
                   JOIN items_fts ON items.id = items_fts.rowid 
                   WHERE items_fts MATCH ?"""
        conditions.append("1")  # already using MATCH
        params.insert(0, search)
    
    if category:
        conditions.append("category = ?")
        params.append(category)
    if location:
        conditions.append("location = ?")
        params.append(location)

    if conditions:
        if search:
            query += " AND " + " AND ".join(conditions)
        else:
            query += " WHERE " + " AND ".join(conditions)

    query += f" ORDER BY {sort} {sort_dir.upper()}"

    items = [item_from_row(row) for row in conn.execute(query, params).fetchall()]

    # Get categories from categories table (not distinct from items)
    categories = [r['name'] for r in conn.execute("SELECT name FROM categories ORDER BY name").fetchall()]
    locations = [r[0] for r in conn.execute("SELECT DISTINCT location FROM items WHERE location != '' ORDER BY location").fetchall()]

    # Stats
    total_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    total_value = conn.execute("SELECT COALESCE(SUM(purchase_value * quantity), 0) FROM items").fetchone()[0]

    conn.close()

    return render_template('index.html', items=items, categories=categories,
                           locations=locations, search=search, category=category,
                           location=location, sort=sort, sort_dir=sort_dir,
                           total_items=total_items, total_value=total_value)


@app.route('/item/<int:item_id>')
def item_detail(item_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        return "Item not found", 404
    item = item_from_row(row)
    conn.close()
    return render_template('detail.html', item=item)


@app.route('/add', methods=['GET', 'POST'])
def add_item():
    categories = get_categories()
    if request.method == 'POST':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO items (name, description, notes, quantity, location, serial_number, purchase_date, purchase_value, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form.get('name', ''),
            request.form.get('description', ''),
            request.form.get('notes', ''),
            int(request.form.get('quantity', 1)),
            request.form.get('location', ''),
            request.form.get('serial_number', ''),
            request.form.get('purchase_date', ''),
            float(request.form.get('purchase_value', 0)),
            request.form.get('category', ''),
        ))
        item_id = cursor.lastrowid

        # Handle photo uploads
        files = request.files.getlist('photos')
        for f in files:
            if f and allowed_file(f.filename):
                filename = secure_filename(f.filename)
                filename = f"{item_id}_{filename}"
                f.save(os.path.join(PHOTO_DIR, filename))
                conn.execute("INSERT INTO photos (item_id, filename, original_name) VALUES (?, ?, ?)",
                           (item_id, filename, f.filename))

        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    return render_template('form.html', item=None, categories=categories)


@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    categories = get_categories()
    conn = get_db()
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        return "Item not found", 404

    if request.method == 'POST':
        conn.execute("""
            UPDATE items SET name=?, description=?, notes=?, quantity=?, location=?,
            serial_number=?, purchase_date=?, purchase_value=?, category=?
            WHERE id=?
        """, (
            request.form.get('name', ''),
            request.form.get('description', ''),
            request.form.get('notes', ''),
            int(request.form.get('quantity', 1)),
            request.form.get('location', ''),
            request.form.get('serial_number', ''),
            request.form.get('purchase_date', ''),
            float(request.form.get('purchase_value', 0)),
            request.form.get('category', ''),
            item_id,
        ))

        # Handle new photo uploads
        files = request.files.getlist('photos')
        for f in files:
            if f and allowed_file(f.filename):
                filename = secure_filename(f.filename)
                filename = f"{item_id}_{filename}"
                f.save(os.path.join(PHOTO_DIR, filename))
                conn.execute("INSERT INTO photos (item_id, filename, original_name) VALUES (?, ?, ?)",
                           (item_id, filename, f.filename))

        # Handle photo deletions
        delete_photos = request.form.getlist('delete_photos')
        for photo_id in delete_photos:
            photo = conn.execute("SELECT * FROM photos WHERE id = ? AND item_id = ?", (photo_id, item_id)).fetchone()
            if photo:
                filepath = os.path.join(PHOTO_DIR, photo['filename'])
                if os.path.exists(filepath):
                    os.remove(filepath)
                conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))

        conn.commit()
        conn.close()
        return redirect(url_for('item_detail', item_id=item_id))

    item = item_from_row(row)
    conn.close()
    return render_template('form.html', item=item, categories=categories)


@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    conn = get_db()
    photos = conn.execute("SELECT * FROM photos WHERE item_id = ?", (item_id,)).fetchall()
    for photo in photos:
        filepath = os.path.join(PHOTO_DIR, photo['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


# ── REST API ────────────────────────────────────────────────────

@app.route('/api/items', methods=['GET'])
def api_list():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '')
    location = request.args.get('location', '')

    conn = get_db()
    query = "SELECT * FROM items"
    conditions = []
    params = []

    if search:
        query = """SELECT items.* FROM items 
                   JOIN items_fts ON items.id = items_fts.rowid 
                   WHERE items_fts MATCH ?"""
        params.insert(0, search)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if location:
        conditions.append("location = ?")
        params.append(location)

    if conditions:
        if search:
            query += " AND " + " AND ".join(conditions)
        else:
            query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY name"
    items = [item_from_row(row) for row in conn.execute(query, params).fetchall()]
    conn.close()
    return jsonify(items)


@app.route('/api/items/<int:item_id>', methods=['GET'])
def api_get(item_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not found"}), 404
    item = item_from_row(row)
    conn.close()
    return jsonify(item)


@app.route('/api/items', methods=['POST'])
def api_add():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "name is required"}), 400

    # Validate category exists
    if data.get('category'):
        conn = get_db()
        cat_exists = conn.execute("SELECT 1 FROM categories WHERE name = ?", (data['category'],)).fetchone()
        conn.close()
        if not cat_exists:
            return jsonify({"error": f"category '{data['category']}' does not exist"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO items (name, description, notes, quantity, location, serial_number, purchase_date, purchase_value, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('name', ''),
        data.get('description', ''),
        data.get('notes', ''),
        int(data.get('quantity', 1)),
        data.get('location', ''),
        data.get('serial_number', ''),
        data.get('purchase_date', ''),
        float(data.get('purchase_value', 0)),
        data.get('category', ''),
    ))
    item_id = cursor.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    item = item_from_row(row)
    conn.close()
    return jsonify(item), 201


@app.route('/api/items/<int:item_id>', methods=['PUT'])
def api_update(item_id):
    data = request.get_json()
    conn = get_db()
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not found"}), 404

    # Validate category if being changed
    if 'category' in data and data['category']:
        cat_exists = conn.execute("SELECT 1 FROM categories WHERE name = ?", (data['category'],)).fetchone()
        if not cat_exists:
            conn.close()
            return jsonify({"error": f"category '{data['category']}' does not exist"}), 400

    fields = []
    values = []
    for key in ['name', 'description', 'notes', 'quantity', 'location', 'serial_number', 'purchase_date', 'purchase_value', 'category']:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])

    if fields:
        values.append(item_id)
        conn.execute(f"UPDATE items SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()

    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    item = item_from_row(row)
    conn.close()
    return jsonify(item)


@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def api_delete(item_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not found"}), 404

    photos = conn.execute("SELECT * FROM photos WHERE item_id = ?", (item_id,)).fetchall()
    for photo in photos:
        filepath = os.path.join(PHOTO_DIR, photo['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)

    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": item_id})


# ── Categories REST API ─────────────────────────────────────────

@app.route('/api/categories', methods=['GET'])
def api_categories_list():
    conn = get_db()
    categories = conn.execute("SELECT c.*, (SELECT COUNT(*) FROM items WHERE category = c.name) as item_count FROM categories c ORDER BY c.name").fetchall()
    result = [{"id": r['id'], "name": r['name'], "item_count": r['item_count'], "created_at": r['created_at']} for r in categories]
    conn.close()
    return jsonify(result)


@app.route('/api/categories', methods=['POST'])
def api_categories_add():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "name is required"}), 400
    name = data['name'].strip()
    conn = get_db()
    try:
        conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        row = conn.execute("SELECT * FROM categories WHERE name = ?", (name,)).fetchone()
        result = {"id": row['id'], "name": row['name'], "created_at": row['created_at']}
        conn.close()
        return jsonify(result), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": f"category '{name}' already exists"}), 409


@app.route('/api/categories/<int:cat_id>', methods=['PUT'])
def api_categories_rename(cat_id):
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "name is required"}), 400
    new_name = data['name'].strip()
    conn = get_db()
    row = conn.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not found"}), 404
    old_name = row['name']
    try:
        conn.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, cat_id))
        conn.execute("UPDATE items SET category = ? WHERE category = ?", (new_name, old_name))
        conn.commit()
        conn.close()
        return jsonify({"id": cat_id, "name": new_name, "old_name": old_name})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": f"category '{new_name}' already exists"}), 409


@app.route('/api/categories/<int:cat_id>', methods=['DELETE'])
def api_categories_delete(cat_id):
    conn = get_db()
    row = conn.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not found"}), 404
    # Clear category from items
    conn.execute("UPDATE items SET category = '' WHERE category = ?", (row['name'],))
    conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": cat_id, "name": row['name']})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8480, debug=False)