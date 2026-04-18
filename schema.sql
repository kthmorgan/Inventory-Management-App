CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    quantity INTEGER DEFAULT 1,
    location TEXT DEFAULT '',
    serial_number TEXT DEFAULT '',
    purchase_date TEXT DEFAULT '',
    purchase_value REAL DEFAULT 0.0,
    category TEXT DEFAULT '',
    photo TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    original_name TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(name, description, notes, location, serial_number, category, content=items, content_rowid=id);

CREATE TRIGGER IF NOT EXISTS items_update_trigger AFTER UPDATE ON items
BEGIN
    UPDATE items SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS items_fts_insert AFTER INSERT ON items
BEGIN
    INSERT INTO items_fts(rowid, name, description, notes, location, serial_number, category)
    VALUES (NEW.id, NEW.name, NEW.description, NEW.notes, NEW.location, NEW.serial_number, NEW.category);
END;

CREATE TRIGGER IF NOT EXISTS items_fts_delete AFTER DELETE ON items
BEGIN
    INSERT INTO items_fts(items_fts, rowid, name, description, notes, location, serial_number, category)
    VALUES ('delete', OLD.id, OLD.name, OLD.description, OLD.notes, OLD.location, OLD.serial_number, OLD.category);
END;

CREATE TRIGGER IF NOT EXISTS items_fts_update AFTER UPDATE ON items
BEGIN
    INSERT INTO items_fts(items_fts, rowid, name, description, notes, location, serial_number, category)
    VALUES ('delete', OLD.id, OLD.name, OLD.description, OLD.notes, OLD.location, OLD.serial_number, OLD.category);
    INSERT INTO items_fts(rowid, name, description, notes, location, serial_number, category)
    VALUES (NEW.id, NEW.name, NEW.description, NEW.notes, NEW.location, NEW.serial_number, NEW.category);
END;