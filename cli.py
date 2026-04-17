#!/usr/bin/env python3
"""Inventory Management CLI"""

import argparse
import json
import sys
import requests

BASE_URL = "http://localhost:8480/api/items"


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
    # First get current item
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
    }
    commands[args.command](args)


if __name__ == '__main__':
    main()