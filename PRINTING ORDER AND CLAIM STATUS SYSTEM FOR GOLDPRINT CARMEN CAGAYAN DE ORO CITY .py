import json
import os
import shutil
from datetime import datetime

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
DATA_FILE = "goldprint_orders.json"
BACKUP_FILE = "goldprint_orders_backup.json"

# Change these before using the program in the shop.
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "goldprint123"
MAX_LOGIN_ATTEMPTS = 3

PRINT_TYPES = ["Black-and-White", "Colored"]
PRINTING_STATUSES = ["Pending", "Printing", "Completed"]
CLAIM_STATUSES = ["Unclaimed", "Claimed"]

DATE_FORMAT = "%Y-%m-%d %H:%M"

# Columns of the order table: (heading, width)
ORDER_COLUMNS = [
    ("No.", 4),
    ("Customer", 14),
    ("Document", 16),
    ("Pages", 5),
    ("Copies", 6),
    ("Print Type", 15),
    ("Received", 12),
    ("Printing", 10),
    ("Claim", 9),
    ("Waiting", 8),
]

# Columns of the customer claim summary table
SUMMARY_COLUMNS = [
    ("Customer", 24),
    ("Completed", 9),
    ("Claimed", 7),
    ("Unclaimed", 9),
    ("Claim Status", 12),
]


class GoBack(Exception):
    """Raised when the staff enter 0 to return to the main menu."""


# ---------------------------------------------------------------------------
# Saving and loading records
# ---------------------------------------------------------------------------
def load_data():
    """Load the saved orders. Returns a dictionary with the next order
    number and the list of orders."""
    empty = {"next_number": 1, "orders": []}

    if not os.path.exists(DATA_FILE):
        return empty

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        orders = data["orders"]
        next_number = int(data["next_number"])
        if not isinstance(orders, list):
            raise ValueError("orders must be a list")
        # Make sure order numbers are never reused.
        highest = max((int(order["order_number"]) for order in orders), default=0)
        next_number = max(next_number, highest + 1)
        return {"next_number": next_number, "orders": orders}
    except (OSError, ValueError, KeyError, TypeError):
        backup = DATA_FILE + ".bak"
        try:
            os.replace(DATA_FILE, backup)
            print(f"Warning: the records file could not be read. "
                  f"It was kept as '{backup}' and a new file will be started.")
        except OSError:
            print("Warning: the records file could not be read. "
                  "Starting with empty records.")
        return empty


def save_data(data):
    """Save all orders to the file. Returns True if saved."""
    temp_file = DATA_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
        os.replace(temp_file, DATA_FILE)
        return True
    except OSError:
        print("Error: the records could not be saved. "
              "Please check the folder and try again.")
        return False


def backup_data():
    """Keep a copy of the records every time the program is opened, so the
    records can be restored if the main file is lost or damaged."""
    if os.path.exists(DATA_FILE):
        try:
            shutil.copyfile(DATA_FILE, BACKUP_FILE)
        except OSError:
            print("Warning: a backup copy of the records could not be made.")


# ---------------------------------------------------------------------------
# Input helpers. Every entry is checked and the question is asked again when
# the entry is not valid. Entering 0 goes back to the main menu.
# ---------------------------------------------------------------------------
def show_title(title):
    print(f"\n--- {title} ---")
    print("(Enter 0 at any question to go back to the main menu.)")


def ask_text(prompt, default=None):
    """Ask for text that cannot be empty. If a default is given, pressing
    Enter keeps it."""
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if value == "0":
            raise GoBack
        if value == "" and default is not None:
            return default
        if value:
            return value
        print("This field cannot be empty. Please try again.")


def ask_positive_int(prompt, default=None):
    """Ask for a whole number of at least 1."""
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if value == "0":
            raise GoBack
        if value == "" and default is not None:
            return default
        if value.isdecimal() and int(value) >= 1:
            return int(value)
        print("Please enter a whole number of at least 1.")


def ask_choice(title, options, default=None):
    """Show a numbered list of options and return the chosen option."""
    print(title)
    for number, option in enumerate(options, start=1):
        print(f"  {number}. {option}")
    print("  0. Back")
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input(f"Enter choice (1-{len(options)}, 0 = Back){suffix}: ").strip()
        if value == "0":
            raise GoBack
        if value == "" and default is not None:
            return default
        if value.isdecimal() and 1 <= int(value) <= len(options):
            return options[int(value) - 1]
        print(f"Please enter a number from 1 to {len(options)}, or 0 to go back.")


def ask_yes_no(prompt):
    """Ask a yes/no question. Returns True for yes."""
    while True:
        value = input(f"{prompt} (y/n, 0 = Back): ").strip().lower()
        if value == "0":
            raise GoBack
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("Please type y or n, or 0 to go back.")


def ask_order(data):
    """Ask for an order number and return that order."""
    while True:
        value = input("Enter the order number (0 = Back): ").strip()
        if value == "0":
            raise GoBack
        if not value.isdecimal():
            print("Please enter a valid order number.")
            continue
        for order in data["orders"]:
            if order["order_number"] == int(value):
                return order
        print(f"No order found with number {value}.")


def require_orders(data):
    """Return True if there is at least one order. Otherwise tell the staff."""
    if data["orders"]:
        return True
    print("\nThere are no orders yet.")
    return False


def clean_name(name, data):
    """Tidy a customer name so the same customer is not recorded twice with
    different spacing or capital letters. A name typed in all small or all
    capital letters is changed to capitalized words. If the customer already
    has an order, the saved spelling is used."""
    name = " ".join(name.split())
    if name.islower() or name.isupper():
        name = name.title()
    for order in data["orders"]:
        if order["customer_name"].lower() == name.lower():
            return order["customer_name"]
    return name


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def clip(text, width):
    """Shorten text so the table columns stay aligned."""
    text = str(text)
    if len(text) <= width:
        return text
    return text[:width - 3] + "..."


def print_table(title, columns, rows, unit):
    """Print a clean table with only two lines: one under the heading
    and one at the end."""
    print()
    print(title)
    if not rows:
        print(f"No {unit}s to show.")
        return

    width = sum(w for _, w in columns) + 2 * (len(columns) - 1)
    rule = "-" * width

    print("  ".join(f"{name:<{w}}" for name, w in columns).rstrip())
    print(rule)
    for row in rows:
        line = "  ".join(
            f"{clip(value, w):<{w}}" for value, (_, w) in zip(row, columns)
        )
        print(line.rstrip())
    print(rule)
    print(f"Total: {len(rows)} {unit}(s)")


def format_minutes(minutes):
    """Write minutes in a short form, for example 35m, 2h 05m, or 3d 4h."""
    days, rest = divmod(minutes, 24 * 60)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {mins:02d}m"
    return f"{mins}m"


def waiting_time(order):
    """How long the customer waited for an order.
    Pending and Printing orders: the time since the order was received.
    Completed orders: the time from received to completed."""
    try:
        received = datetime.strptime(order["date_received"], DATE_FORMAT)
        if order["printing_status"] == "Completed":
            if not order.get("date_completed"):
                return "-"
            end = datetime.strptime(order["date_completed"], DATE_FORMAT)
        else:
            end = datetime.now()
    except (ValueError, KeyError, TypeError):
        return "-"
    return format_minutes(max(0, int((end - received).total_seconds() // 60)))


def short_date(text):
    """Shorter date for the table, for example 'Oct 16 04:10'."""
    try:
        return datetime.strptime(text, DATE_FORMAT).strftime("%b %d %H:%M")
    except (ValueError, TypeError):
        return text


def print_orders(orders, title):
    """Print a list of orders as a table."""
    rows = [
        [
            order["order_number"],
            order["customer_name"],
            order["document_name"],
            order["pages"],
            order["copies"],
            order["print_type"],
            short_date(order["date_received"]),
            order["printing_status"],
            order["claim_status"],
            waiting_time(order),
        ]
        for order in orders
    ]
    print_table(title, ORDER_COLUMNS, rows, "order")


def print_order_details(order):
    """Print all details of one order."""
    print()
    print(f"Order No.:        {order['order_number']}")
    print(f"Customer:         {order['customer_name']}")
    print(f"Document:         {order['document_name']}")
    print(f"Pages:            {order['pages']}")
    print(f"Copies:           {order['copies']}")
    print(f"Print type:       {order['print_type']}")
    print(f"Date received:    {order['date_received']}")
    print(f"Printing status:  {order['printing_status']}")
    print(f"Claim status:     {order['claim_status']}")
    print(f"Date completed:   {order.get('date_completed') or '-'}")
    print(f"Date claimed:     {order.get('date_claimed') or '-'}")


# ---------------------------------------------------------------------------
# Menu options
# ---------------------------------------------------------------------------
def add_order(data):
    """1. Add order"""
    show_title("Add Order")
    customer_name = clean_name(ask_text("Customer name"), data)
    document_name = ask_text("Document name")
    pages = ask_positive_int("Number of pages")
    copies = ask_positive_int("Number of copies")
    print_type = ask_choice("Print type:", PRINT_TYPES)

    order = {
        "order_number": data["next_number"],
        "customer_name": customer_name,
        "document_name": document_name,
        "pages": pages,
        "copies": copies,
        "print_type": print_type,
        "date_received": datetime.now().strftime(DATE_FORMAT),
        "printing_status": "Pending",
        "claim_status": "Unclaimed",
        "date_completed": None,
        "date_claimed": None,
    }
    data["orders"].append(order)
    data["next_number"] += 1

    if save_data(data):
        print(f"\nOrder saved. Order number: {order['order_number']}")


def view_all_orders(data):
    """2. View all orders"""
    print_orders(data["orders"], "--- All Orders ---")


def view_orders_by_printing_status(data):
    """3. View orders by printing status"""
    show_title("View Orders by Printing Status")
    status = ask_choice("Printing status:", PRINTING_STATUSES)
    matches = [o for o in data["orders"] if o["printing_status"] == status]
    print_orders(matches, f"--- {status} Orders ---")


def update_order_information(data):
    """4. Update order information"""
    show_title("Update Order Information")
    if not require_orders(data):
        return
    order = ask_order(data)

    print_order_details(order)
    print("\nPress Enter to keep the current value.")
    customer_name = clean_name(
        ask_text("Customer name", order["customer_name"]), data)
    document_name = ask_text("Document name", order["document_name"])
    pages = ask_positive_int("Number of pages", order["pages"])
    copies = ask_positive_int("Number of copies", order["copies"])
    print_type = ask_choice("Print type:", PRINT_TYPES, order["print_type"])

    # Changes are applied only after every question was answered, so going
    # back in the middle leaves the order unchanged.
    order["customer_name"] = customer_name
    order["document_name"] = document_name
    order["pages"] = pages
    order["copies"] = copies
    order["print_type"] = print_type

    if save_data(data):
        print("\nOrder updated.")


def delete_order(data):
    """5. Delete order"""
    show_title("Delete Order")
    if not require_orders(data):
        return
    order = ask_order(data)

    print_order_details(order)
    if ask_yes_no("\nAre you sure you want to delete this order?"):
        data["orders"].remove(order)
        if save_data(data):
            print("Order deleted.")
    else:
        print("The order was not deleted.")


def update_printing_status(data):
    """6. Update printing status"""
    show_title("Update Printing Status")
    if not require_orders(data):
        return
    order = ask_order(data)

    print_order_details(order)

    if order["claim_status"] == "Claimed":
        print("\nThis order is already Claimed, so its printing status cannot "
              "be changed.")
        print("Set the claim status back to Unclaimed first (menu option 7).")
        return

    print()
    new_status = ask_choice("New printing status:", PRINTING_STATUSES,
                            order["printing_status"])
    if new_status == order["printing_status"]:
        print("The printing status was not changed.")
        return

    order["printing_status"] = new_status
    if new_status == "Completed":
        order["date_completed"] = datetime.now().strftime(DATE_FORMAT)
    else:
        order["date_completed"] = None
    if save_data(data):
        print(f"\nPrinting status of order {order['order_number']} is now "
              f"{new_status}.")


def update_claim_status(data):
    """7. Update claim status"""
    show_title("Update Claim Status")
    if not require_orders(data):
        return
    order = ask_order(data)

    print_order_details(order)
    print()
    new_status = ask_choice("New claim status:", CLAIM_STATUSES,
                            order["claim_status"])

    if new_status == order["claim_status"]:
        print("The claim status was not changed.")
        return

    if new_status == "Claimed" and order["printing_status"] != "Completed":
        print("\nThis order cannot be marked Claimed because its printing "
              "status is not Completed yet.")
        return

    order["claim_status"] = new_status
    if new_status == "Claimed":
        order["date_claimed"] = datetime.now().strftime(DATE_FORMAT)
    else:
        order["date_claimed"] = None
    if save_data(data):
        print(f"\nClaim status of order {order['order_number']} is now "
              f"{new_status}.")


def view_completed_by_claim_status(data):
    """8. View completed orders by claim status"""
    show_title("View Completed Orders by Claim Status")
    status = ask_choice("Claim status:", CLAIM_STATUSES)
    matches = [
        o for o in data["orders"]
        if o["printing_status"] == "Completed" and o["claim_status"] == status
    ]
    print_orders(matches, f"--- Completed Orders: {status} ---")


def customer_claim_summary(data):
    """9. Customer claim summary: each customer name appears only once, with
    the number of completed orders and whether they are claimed or not.
    Orders that are not completed yet are not counted, because there is
    nothing to claim yet."""
    customers = {}
    for order in data["orders"]:
        if order["printing_status"] != "Completed":
            continue
        key = order["customer_name"].lower()
        entry = customers.setdefault(
            key, {"name": order["customer_name"], "completed": 0, "claimed": 0})
        entry["completed"] += 1
        if order["claim_status"] == "Claimed":
            entry["claimed"] += 1

    rows = []
    for entry in sorted(customers.values(), key=lambda e: e["name"].lower()):
        unclaimed = entry["completed"] - entry["claimed"]
        status = "Claimed" if unclaimed == 0 else "Unclaimed"
        rows.append([entry["name"], entry["completed"], entry["claimed"],
                     unclaimed, status])

    print_table("--- Customer Claim Summary ---", SUMMARY_COLUMNS, rows,
                "customer")
    print("Only completed orders are counted.")


# ---------------------------------------------------------------------------
# Login and main menu
# ---------------------------------------------------------------------------
def login():
    """Ask for the admin username and password.
    Returns False after too many wrong attempts."""
    print("=" * 60)
    print(" Printing Order and Claim Status System")
    print(" GoldPrint, Carmen, Cagayan de Oro City")
    print("=" * 60)

    for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            print("\nLogin successful.")
            return True
        remaining = MAX_LOGIN_ATTEMPTS - attempt
        if remaining > 0:
            print(f"Wrong username or password. {remaining} attempt(s) left.\n")

    print("\nToo many wrong attempts. The program will now close.")
    return False


def show_menu():
    print()
    print("=" * 60)
    print(" MAIN MENU")
    print("=" * 60)
    print("  1. Add order")
    print("  2. View all orders")
    print("  3. View orders by printing status")
    print("  4. Update order information")
    print("  5. Delete order")
    print("  6. Update printing status")
    print("  7. Update claim status")
    print("  8. View completed orders by claim status")
    print("  9. Customer claim summary")
    print(" 10. Exit")
    print("=" * 60)


def main():
    if not login():
        return

    data = load_data()
    backup_data()

    actions = {
        "1": add_order,
        "2": view_all_orders,
        "3": view_orders_by_printing_status,
        "4": update_order_information,
        "5": delete_order,
        "6": update_printing_status,
        "7": update_claim_status,
        "8": view_completed_by_claim_status,
        "9": customer_claim_summary,
    }

    while True:
        show_menu()
        choice = input("Enter your choice (1-10): ").strip()

        if choice == "10":
            print("\nThank you. The program will now close.")
            break

        action = actions.get(choice)
        if action is None:
            print("Invalid choice. Please enter a number from 1 to 10.")
            continue

        try:
            action(data)
        except GoBack:
            print("\nBack to the main menu.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\nThe program was closed.")