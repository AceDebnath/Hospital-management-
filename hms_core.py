import sqlite3
import datetime
import sys
import os

# Configuration Constants
DB_FILENAME = "hospital_system.db"
DEFAULT_PAGE_SIZE = 20


class DatabaseManager:
    """Handles direct interactions with the SQLite database."""

    def __init__(self, db_name=DB_FILENAME):
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self.connect()
        self.initialize_schema()

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()
            # Ensure foreign key support
            self.cursor.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error as e:
            print(f"CRITICAL ERROR: Could not connect to database. {e}")
            sys.exit(1)

    def initialize_schema(self):
        # Patients
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                age INTEGER CHECK(age > 0),
                gender TEXT CHECK(gender IN ('M', 'F', 'O')),
                contact_number TEXT,
                address TEXT,
                blood_group TEXT,
                medical_history TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Staff
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS staff (
                staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('Doctor', 'Nurse', 'Admin', 'Pharmacist')),
                specialization TEXT,
                shift_timing TEXT,
                contact_number TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        """
        )

        # Inventory
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                quantity INTEGER DEFAULT 0 CHECK(quantity >= 0),
                price_per_unit REAL NOT NULL,
                expiry_date DATE,
                reorder_level INTEGER DEFAULT 10
            )
        """
        )

        # Appointments
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                doctor_id INTEGER NOT NULL,
                scheduled_time DATETIME NOT NULL,
                status TEXT DEFAULT 'Scheduled' CHECK(status IN ('Scheduled', 'Completed', 'Cancelled')),
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
                FOREIGN KEY (doctor_id) REFERENCES staff(staff_id)
            )
        """
        )

        # Bills
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bills (
                bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                items_summary TEXT NOT NULL,
                total_amount REAL NOT NULL CHECK(total_amount >= 0),
                payment_status TEXT DEFAULT 'Pending',
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
            )
        """
        )

        self.conn.commit()

    def execute_query(self, query, params=()):
        try:
            cur = self.cursor.execute(query, params)
            self.conn.commit()
            return cur
        except sqlite3.IntegrityError as e:
            print(f"Data Integrity Error: {e}")
            return None
        except sqlite3.Error as e:
            print(f"Database Error: {e}")
            return None

    def fetch_all(self, query, params=()):
        cur = self.cursor.execute(query, params)
        return cur.fetchall()

    def fetch_one(self, query, params=()):
        cur = self.cursor.execute(query, params)
        return cur.fetchone()

    def close(self):
        if self.conn:
            self.conn.close()


class PatientManager:
    """Manages patient operations: registration, search, listing."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def register_patient(self):
        print("\n--- PATIENT REGISTRATION ---")
        name = input("Enter Full Name: ").strip()
        if not name:
            print("Error: Name is required.")
            return

        try:
            age = int(input("Enter Age: "))
            if age <= 0:
                raise ValueError
        except ValueError:
            print("Error: Age must be a positive integer.")
            return

        gender = input("Enter Gender (M/F/O): ").strip().upper()
        if gender not in ["M", "F", "O"]:
            print("Error: Invalid Gender.")
            return

        contact = input("Enter Contact Number: ").strip()
        address = input("Enter Address: ").strip()
        blood_group = input("Enter Blood Group: ").strip()
        history = input("Initial Medical History (Optional): ").strip()

        query = (
            "INSERT INTO patients (full_name, age, gender, contact_number, address, blood_group, medical_history)"
            " VALUES (?,?,?,?,?,?,?)"
        )
        if self.db.execute_query(query, (name, age, gender, contact, address, blood_group, history)):
            pid = self.db.cursor.lastrowid
            print(f"SUCCESS: Patient registered. Assigned Unique ID: {pid}")

    def view_patients(self):
        print("\n--- PATIENT DIRECTORY ---")
        patients = self.db.fetch_all(
            "SELECT patient_id, full_name, age, gender, contact_number FROM patients"
        )

        print(f"{'ID':<5} {'Name':<25} {'Age':<5} {'Sex':<5} {'Contact':<15}")
        print("-" * 60)
        for p in patients:
            print(f"{p[0]:<5} {p[1]:<25} {p[2]:<5} {p[3]:<5} {p[4]:<15}")

    def search_patient(self):
        search_term = input("Enter Patient ID or Name to search: ").strip()
        # Try numeric search first
        try:
            pid = int(search_term)
            results = self.db.fetch_all("SELECT * FROM patients WHERE patient_id = ?", (pid,))
        except ValueError:
            results = self.db.fetch_all(
                "SELECT * FROM patients WHERE full_name LIKE ?", (f"%{search_term}%",)
            )

        if not results:
            print("No records found matching that criteria.")
            return

        for p in results:
            print("\n--- PATIENT RECORD ---")
            print(f"ID: {p[0]}")
            print(f"Name: {p[1]}, Age: {p[2]}, Gender: {p[3]}")
            print(f"Contact: {p[4]}")
            print(f"Address: {p[5]}")
            print(f"Blood Group: {p[6]}")
            print(f"Medical History: {p[7]}")
            print(f"Registered: {p[8]}")


class StaffManager:
    """Handles Human Resources: Doctors, Nurses, Admin."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def add_staff(self):
        print("\n--- ADD STAFF MEMBER ---")
        name = input("Enter Staff Name: ").strip()
        print("Roles: Doctor, Nurse, Admin, Pharmacist")
        role = input("Enter Role: ").strip().capitalize()

        valid_roles = ["Doctor", "Nurse", "Admin", "Pharmacist"]
        if role not in valid_roles:
            print("Error: Invalid Role.")
            return

        spec = ""
        if role == "Doctor":
            spec = input("Enter Specialization (e.g., Cardiology): ").strip()

        contact = input("Enter Contact Number: ").strip()
        shift = input("Enter Shift Timings (e.g., 9AM-5PM): ").strip()

        query = (
            "INSERT INTO staff (full_name, role, specialization, contact_number, shift_timing)"
            " VALUES (?,?,?,?,?)"
        )
        if self.db.execute_query(query, (name, role, spec, contact, shift)):
            print(f"Staff member '{name}' added successfully as {role}.")

    def view_staff(self, role_filter=None):
        base_query = "SELECT staff_id, full_name, role, specialization, shift_timing FROM staff"
        if role_filter:
            query = base_query + " WHERE role = ?"
            params = (role_filter,)
        else:
            query = base_query
            params = ()

        staff_list = self.db.fetch_all(query, params)
        print(f"\n--- STAFF DIRECTORY ({role_filter if role_filter else 'ALL'}) ---")
        print(f"{'ID':<5} {'Name':<20} {'Role':<10} {'Specialization':<15} {'Shift':<10}")
        print("-" * 65)
        for s in staff_list:
            spec = s[3] if s[3] else "N/A"
            print(f"{s[0]:<5} {s[1]:<20} {s[2]:<10} {spec:<15} {s[4]:<10}")


class InventoryManager:
    """Manages Medical Supply Chain: stock, reorder alerts."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def add_item(self):
        print("\n--- ADD INVENTORY ITEM ---")
        name = input("Item Name: ").strip()
        category = input("Category (Medicine/Equipment): ").strip()
        try:
            qty = int(input("Initial Quantity: "))
            price = float(input("Price per Unit: "))
            reorder = int(input("Reorder Level Alert (Default 10): ") or 10)
        except ValueError:
            print("Error: Invalid numeric input.")
            return

        query = (
            "INSERT INTO inventory (item_name, category, quantity, price_per_unit, reorder_level)"
            " VALUES (?,?,?,?,?)"
        )
        if self.db.execute_query(query, (name, category, qty, price, reorder)):
            print(f"Item '{name}' added to inventory.")
        else:
            print("Error: Item likely already exists (Name must be unique).")

    def update_stock(self):
        item_name = input("Enter Item Name to Update: ").strip()
        item = self.db.fetch_one("SELECT item_id, quantity FROM inventory WHERE item_name = ?", (item_name,))

        if not item:
            print("Item not found.")
            return

        item_id, quantity = item[0], item[1]
        print(f"Current Stock: {quantity}")
        try:
            change = int(input("Enter quantity to ADD (use negative for removal): "))
            new_qty = quantity + change
            if new_qty < 0:
                print("Error: Resulting stock cannot be negative.")
                return

            self.db.execute_query("UPDATE inventory SET quantity = ? WHERE item_id = ?", (new_qty, item_id))
            print("Stock updated successfully.")
        except ValueError:
            print("Invalid input.")

    def check_low_stock(self):
        print("\n--- LOW STOCK ALERTS ---")
        query = "SELECT item_name, quantity, reorder_level FROM inventory WHERE quantity <= reorder_level"
        items = self.db.fetch_all(query)

        if not items:
            print("All stock levels are healthy.")
            return

        print(f"{'Item':<20} {'Current':<10} {'Minimum':<10}")
        print("-" * 40)
        for name, qty, reorder in items:
            marker = "(!)" if qty <= reorder else ""
            print(f"{name:<20} {qty:<10} {reorder:<10} {marker}")


class OperationsManager:
    """Integrates Patient, Staff, Inventory for appointments and billing."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def schedule_appointment(self):
        print("\n--- SCHEDULE APPOINTMENT ---")
        try:
            pid = int(input("Enter Patient ID: "))
            if not self.db.fetch_one("SELECT 1 FROM patients WHERE patient_id = ?", (pid,)):
                print("Error: Patient ID not found.")
                return

            print("\nAvailable Doctors:")
            docs = self.db.fetch_all("SELECT staff_id, full_name, specialization FROM staff WHERE role = 'Doctor'")
            for d in docs:
                print(f"ID: {d[0]} | Dr. {d[1]} ({d[2] if d[2] else 'General'})")

            did = int(input("Enter Doctor ID: "))
            doc_check = self.db.fetch_one("SELECT 1 FROM staff WHERE staff_id = ? AND role = 'Doctor'", (did,))
            if not doc_check:
                print("Error: Invalid Doctor ID.")
                return

            date_str = input("Enter Date (YYYY-MM-DD HH:MM): ")
            notes = input("Reason for Visit: ")

            query = (
                "INSERT INTO appointments (patient_id, doctor_id, scheduled_time, notes)"
                " VALUES (?,?,?,?)"
            )
            if self.db.execute_query(query, (pid, did, date_str, notes)):
                print("Appointment confirmed.")

        except ValueError:
            print("Invalid numeric input.")

    def generate_bill(self):
        print("\n--- GENERATE INVOICE ---")
        try:
            pid = int(input("Enter Patient ID: "))
            patient = self.db.fetch_one("SELECT full_name FROM patients WHERE patient_id = ?", (pid,))
            if not patient:
                print("Patient not found.")
                return

            print(f"Invoicing for: {patient[0]}")

            bill_items = []
            total_amount = 0.0

            if input("Add Consultation Fee? (y/n): ").lower() == 'y':
                fee = float(input("Enter Fee Amount: "))
                bill_items.append(f"Consultation: ${fee:.2f}")
                total_amount += fee

            inv = InventoryManager(self.db)
            while True:
                if input("Add Medicine/Item? (y/n): ").lower() != 'y':
                    break

                item_name = input("Enter Item Name: ")
                stock_data = self.db.fetch_one(
                    "SELECT item_id, price_per_unit, quantity FROM inventory WHERE item_name = ?", (item_name,)
                )

                if not stock_data:
                    print("Item not found in inventory.")
                    continue

                iid, price, available = stock_data
                print(f"Price: ${price}/unit | Available: {available}")

                req_qty = int(input("Quantity: "))
                if req_qty > available:
                    print(f"Error: Insufficient stock. Only {available} available.")
                    continue

                new_qty = available - req_qty
                self.db.execute_query("UPDATE inventory SET quantity = ? WHERE item_id = ?", (new_qty, iid))

                cost = price * req_qty
                bill_items.append(f"{item_name} x{req_qty}: ${cost:.2f}")
                total_amount += cost
                print(f"Added {item_name} to bill and updated inventory.")

            items_str = "; ".join(bill_items)
            self.db.execute_query(
                "INSERT INTO bills (patient_id, items_summary, total_amount, payment_status) VALUES (?,?,?, 'Unpaid')",
                (pid, items_str, total_amount),
            )

            print("\n" + "=" * 40)
            print(f"INVOICE GENERATED FOR {patient[0]}")
            print("=" * 40)
            for item in bill_items:
                print(f"* {item}")
            print("-" * 40)
            print(f"TOTAL PAYABLE: ${total_amount:.2f}")
            print("=" * 40)

        except ValueError:
            print("Invalid input error. Transaction aborted.")

            