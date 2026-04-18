#!/usr/bin/env python3
"""Inventory Management CLI"""

import argparse
import json
import sys
import requests

BASE_URL = "http://localhost:8480/api/items"
CATEGORIES_URL = "http://localhost:8480/api/categories"


def cmd_add(args):
    data = {"name": args.name}
    if args.description:
        data["description"] = args.description
    if args.notes:
        data["notes"] = args.notes
    if args.qty is not None:
        data["quantity"] = args.qty
    if args.location:
        data["location"] = args.location
    if args.serial:
        data["serial_number"] = args.serial
    if args.purchase_date:
        data["purchase_date"] = args.purchase_date
    if args.value is not None:
        data["purchase_value"] = args.value
    if args.category:
        data["category"] = args.category

    resp = requests.post(BASE_URL, json=data)
    if resp.status_code == 201:
        item = resp.json()
        print(f"✓ Added: #{item['id']} {item['name']}")
    else:
        print(f"✗ Error: {resp.status_code} {resp.text}")
        sys.exit(1)


def cmd_list(args):
    params = {}
    if args.category:
        params["category"] = args.category
    if args.location:
        params["location"] = args.location
    if args.search:
        params["search"] = args.search

    resp = requests.get(BASE_URL, params=params)
    items = resp.json()

    if not items:
        print("No items found.")
        return

    fmt = args.format
    if fmt == "json":
        print(json.dumps(items, indent=2))
        return

    if fmt == "short":
        for item in items:
            print(f"#{item['id']}\t{item['name']}\t×{item['quantity']}\t{item['location']}")
        return

    # Table format
    print(f"{'ID':>4}  {'Name':<30} {'Qty':>3} {'Location':<20} {'Category':<15} {'Value':>10}")
    print("─" * 85)
    for item in items:
        val = f"${item['purchase_value']:.2f}" if item['purchase_value'] else ""
        print(f"#{item['id']:<3} {item['name'][:30]:<30} {item['quantity']:>3} {item['location'][:20]:<20} {item['category'][:15]:<15} {val:>10}")


def cmd_show(args):
    resp = requests.get(f"{BASE_URL}/{args.id}")
    if resp.status_code == 404:
        print(f"✗ Item #{args.id} not found")
        sys.exit(1)
    item = resp.json()

    if args.format == "json":
        print(json.dumps(item, indent=2))
        return

    print(f"Item #{item['id']}")
    print(f"  Name:           {item['name']}")
    print(f"  Description:    {item['description'] or '—'}")
    print(f"  Notes:          {item['notes'] or '—'}")
    print(f"  Quantity:       {item['quantity']}")
    print(f"  Location:       {item['location'] or '—'}")
    print(f"  Category:       {item['category'] or '—'}")
    print(f"  Serial Number:  {item['serial_number'] or '—'}")
    print(f"  Purchase Date:  {item['purchase_date'] or '—'}")
    val = f"${item['purchase_value']:.2f}" if item['purchase_value'] else "—"
    print(f"  Purchase Value: {val}")
    print(f"  Photos:         {len(item.get('photos', []))}")
    print(f"  Created:        {item['created_at']}")
    print(f"  Updated:        {item['updated_at']}")


def cmd_update(args):
    resp = requests.get(f"{BASE_URL}/{args.id}")
    if resp.status_code == 404:
        print(f"✗ Item #{args.id} not found")
        sys.exit(1)

    data = {}
    if args.name:
        data["name"] = args.name
    if args.description is not None:
        data["description"] = args.description
    if args.notes is not None:
        data["notes"] = args.notes
    if args.qty is not None:
        data["quantity"] = args.qty
    if args.location is not None:
        data["location"] = args.location
    if args.serial is not None:
        data["serial_number"] = args.serial
    if args.purchase_date is not None:
        data["purchase_date"] = args.purchase_date
    if args.value is not None:
        data["purchase_value"] = args.value
    if args.category is not None:
        data["category"] = args.category

    if not data:
        print("No fields to update. Use --name, --description, etc.")
        sys.exit(1)

    resp = requests.put(f"{BASE_URL}/{args.id}", json=data)
    if resp.ok:
        item = resp.json()
        print(f"✓ Updated: #{item['id']} {item['name']}")
    else:
        print(f"✗ Error: {resp.status_code} {resp.text}")
        sys.exit(1)


def cmd_remove(args):
    resp = requests.delete(f"{BASE_URL}/{args.id}")
    if resp.ok:
        print(f"✓ Deleted item #{args.id}")
    else:
        print(f"✗ Error: {resp.status_code} {resp.text}")
        sys.exit(1)


def cmd_search(args):
    params = {"search": " ".join(args.query)}
    resp = requests.get(BASE_URL, params=params)
    items = resp.json()

    if not items:
        print("No results found.")
        return

    for item in items:
        val = f"${item['purchase_value']:.2f}" if item['purchase_value'] else ""
        print(f"#{item['id']}\t{item['name']}\t×{item['quantity']}\t{item['location']}\t{val}")


# ── Category Commands ───────────────────────────────────────────

def cmd_categories_list(args):
    resp = requests.get(CATEGORIES_URL)
    categories = resp.json()

    if not categories:
        print("No categories defined.")
        return

    if args.format == "json":
        print(json.dumps(categories, indent=2))
        return

    print(f"{'ID':>4}  {'Category':<25} {'Items':>5}")
    print("─" * 40)
    for cat in categories:
        print(f"#{cat['id']:<3} {cat['name'][:25]:<25} {cat['item_count']:>5}")


def cmd_categories_add(args):
    resp = requests.post(CATEGORIES_URL, json={"name": args.name})
    if resp.status_code == 201:
        cat = resp.json()
        print(f"✓ Added category: {cat['name']}")
    elif resp.status_code == 409:
        print(f"✗ Category '{args.name}' already exists")
        sys.exit(1)
    else:
        print(f"✗ Error: {resp.status_code} {resp.text}")
        sys.exit(1)


def cmd_categories_rename(args):
    resp = requests.put(f"{CATEGORIES_URL}/{args.id}", json={"name": args.new_name})
    if resp.ok:
        data = resp.json()
        print(f"✓ Renamed: {data['old_name']} → {data['name']}")
    elif resp.status_code == 404:
        print(f"✗ Category #{args.id} not found")
        sys.exit(1)
    elif resp.status_code == 409:
        print(f"✗ Category '{args.new_name}' already exists")
        sys.exit(1)
    else:
        print(f"✗ Error: {resp.status_code} {resp.text}")
        sys.exit(1)


def cmd_categories_remove(args):
    resp = requests.delete(f"{CATEGORIES_URL}/{args.id}")
    if resp.ok:
        data = resp.json()
        print(f"✓ Deleted category: {data['name']} (items cleared)")
    elif resp.status_code == 404:
        print(f"✗ Category #{args.id} not found")
        sys.exit(1)
    else:
        print(f"✗ Error: {resp.status_code} {resp.text}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Inventory Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # add
    p_add = subparsers.add_parser("add", help="Add a new item")
    p_add.add_argument("--name", required=True, help="Item name")
    p_add.add_argument("--description", help="Description")
    p_add.add_argument("--notes", help="Notes")
    p_add.add_argument("--qty", type=int, help="Quantity")
    p_add.add_argument("--location", help="Location")
    p_add.add_argument("--serial", help="Serial number")
    p_add.add_argument("--purchase-date", help="Purchase date (YYYY-MM-DD)")
    p_add.add_argument("--value", type=float, help="Purchase value")
    p_add.add_argument("--category", help="Category")

    # list
    p_list = subparsers.add_parser("list", help="List items")
    p_list.add_argument("--category", help="Filter by category")
    p_list.add_argument("--location", help="Filter by location")
    p_list.add_argument("--search", help="Search terms")
    p_list.add_argument("--format", choices=["table", "short", "json"], default="table", help="Output format")

    # show
    p_show = subparsers.add_parser("show", help="Show item details")
    p_show.add_argument("id", type=int, help="Item ID")
    p_show.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    # update
    p_update = subparsers.add_parser("update", help="Update an item")
    p_update.add_argument("id", type=int, help="Item ID")
    p_update.add_argument("--name", help="Item name")
    p_update.add_argument("--description", help="Description")
    p_update.add_argument("--notes", help="Notes")
    p_update.add_argument("--qty", type=int, help="Quantity")
    p_update.add_argument("--location", help="Location")
    p_update.add_argument("--serial", help="Serial number")
    p_update.add_argument("--purchase-date", help="Purchase date")
    p_update.add_argument("--value", type=float, help="Purchase value")
    p_update.add_argument("--category", help="Category")

    # remove
    p_remove = subparsers.add_parser("remove", help="Remove an item")
    p_remove.add_argument("id", type=int, help="Item ID")

    # search
    p_search = subparsers.add_parser("search", help="Search items")
    p_search.add_argument("query", nargs="+", help="Search terms")

    # categories
    p_cats = subparsers.add_parser("categories", help="Manage categories")
    cat_sub = p_cats.add_subparsers(dest="cat_command", help="Category commands")

    p_cat_list = cat_sub.add_parser("list", help="List categories")
    p_cat_list.add_argument("--format", choices=["table", "json"], default="table", help="Output format")

    p_cat_add = cat_sub.add_parser("add", help="Add a category")
    p_cat_add.add_argument("--name", required=True, help="Category name")

    p_cat_rename = cat_sub.add_parser("rename", help="Rename a category")
    p_cat_rename.add_argument("id", type=int, help="Category ID")
    p_cat_rename.add_argument("--new-name", required=True, help="New name")

    p_cat_remove = cat_sub.add_parser("remove", help="Remove a category")
    p_cat_remove.add_argument("id", type=int, help="Category ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "add": cmd_add,
        "list": cmd_list,
        "show": cmd_show,
        "update": cmd_update,
        "remove": cmd_remove,
        "search": cmd_search,
        "categories": None,  # handled separately
    }

    if args.command == "categories":
        if not args.cat_command:
            p_cats.print_help()
            sys.exit(1)
        cat_commands = {
            "list": cmd_categories_list,
            "add": cmd_categories_add,
            "rename": cmd_categories_rename,
            "remove": cmd_categories_remove,
        }
        cat_commands[args.cat_command](args)
    else:
        commands[args.command](args)


if __name__ == '__main__':
    main()