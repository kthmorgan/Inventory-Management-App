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
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        with open(SCHEMA_PATH) as f:
            conn.executescript(f.read())
        conn.close()
    os.makedirs(PHOTO_DIR, exist_ok=True)


def item_from_row(row):
    d = dict(row)
    # Get photos for this item
    conn = get_db()
    photos = conn.execute("SELECT * FROM photos WHERE item_id = ?", (d['id'],)).fetchall()
    d['photos'] = [dict(p) for p in photos]
    conn.close()
    return d


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
            # FTS query already has WHERE, append AND for filters
            query += " AND " + " AND ".join(conditions)
        else:
            query += " WHERE " + " AND ".join(conditions)

    query += f" ORDER BY {sort} {sort_dir.upper()}"

    items = [item_from_row(row) for row in conn.execute(query, params).fetchall()]

    # Get distinct categories and locations for filters
    categories = [r[0] for r in conn.execute("SELECT DISTINCT category FROM items WHERE category != '' ORDER BY category").fetchall()]
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
                # Prepend item_id to avoid collisions
                filename = f"{item_id}_{filename}"
                f.save(os.path.join(PHOTO_DIR, filename))
                conn.execute("INSERT INTO photos (item_id, filename, original_name) VALUES (?, ?, ?)",
                           (item_id, filename, f.filename))

        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    return render_template('form.html', item=None)


@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
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
    return render_template('form.html', item=item)


@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    conn = get_db()
    # Delete photos from filesystem
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


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8480, debug=False)