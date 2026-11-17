"""
functions.py - Business logic for PesoWise Student Budget Tracker (no Tkinter code in here).

Keeping validation and calculations separate from the GUI makes the code
easier to read, easier to test, and easier to explain during the defense.
"""
import calendar
import csv
import math
from collections import defaultdict
from datetime import date, datetime

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
CURRENCY = "₱"
MAX_AMOUNT = 10_000_000
MAX_DESCRIPTION = 60

EXPENSE_CATEGORIES = ["Food", "Transport", "School Supplies", "Tuition & Fees",
                      "Load & Data", "Rent & Dorm", "Bills", "Shopping",
                      "Health", "Entertainment", "Other"]
INCOME_CATEGORIES = ["Allowance", "Part-time Job", "Scholarship", "Freelance",
                     "Gift", "Other Income"]

# Category names used by the older (general) version -> new student names.
# database.init_db() uses this so old records keep working.
CATEGORY_RENAMES = {"School": "School Supplies", "Salary": "Part-time Job",
                    "Business": "Freelance"}

# Dictionary: transaction type -> list of allowed categories
CATEGORIES = {"Expense": EXPENSE_CATEGORIES, "Income": INCOME_CATEGORIES}


# ----------------------------------------------------------------------
# Formatting helpers
# ----------------------------------------------------------------------
def format_money(value):
    """Return a peso string such as ₱1,250.50 (negatives become -₱1,250.50)."""
    sign = "-" if value < 0 else ""
    return f"{sign}{CURRENCY}{abs(value):,.2f}"


def format_money_short(value):
    """Peso string without centavos, for small spaces such as ₱1,250."""
    return f"{CURRENCY}{value:,.0f}"


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------
def parse_amount(text):
    """
    Convert user text to a positive float.
    Returns (value, error_message). Exactly one of them is None.
    Accepts inputs like "1500", "1,500.50" or "₱1,500".
    """
    cleaned = text.replace(",", "").replace(CURRENCY, "").strip()
    if cleaned == "":
        return None, "Amount is required."
    try:
        value = float(cleaned)
    except ValueError:
        return None, "Amount must be a number (example: 1500 or 1,500.50)."
    if not math.isfinite(value) or value <= 0:
        return None, "Amount must be greater than 0."
    if value > MAX_AMOUNT:
        return None, f"Amount cannot exceed {format_money(MAX_AMOUNT)}."
    return round(value, 2), None


def validate_transaction(date_text, ttype, category, amount_text, description):
    """
    Validate every field of a transaction.
    Returns (record_dict, []) when valid, or (None, [list of error strings]).
    """
    errors = []
    date_text = date_text.strip()
    description = " ".join(description.split())      # trim + collapse spaces

    # --- Date ---
    if date_text == "":
        errors.append("Date is required.")
    else:
        try:
            parsed = datetime.strptime(date_text, "%Y-%m-%d")
            if not 2000 <= parsed.year <= 2100:
                errors.append("Year must be between 2000 and 2100.")
        except ValueError:
            errors.append("Date must be a real date in YYYY-MM-DD format "
                          "(example: 2026-11-17).")

    # --- Type and category ---
    if ttype not in CATEGORIES:
        errors.append("Please choose Income or Expense.")
    if category == "":
        errors.append("Please select a category.")
    elif ttype in CATEGORIES and category not in CATEGORIES[ttype]:
        errors.append(f"'{category}' is not a valid {ttype} category.")

    # --- Amount ---
    amount, amount_error = parse_amount(amount_text)
    if amount_error:
        errors.append(amount_error)

    # --- Description ---
    if description == "":
        errors.append("Description is required.")
    elif len(description) > MAX_DESCRIPTION:
        errors.append(f"Description is too long (max {MAX_DESCRIPTION} characters).")

    if errors:
        return None, errors
    return {"date": date_text, "type": ttype, "category": category,
            "description": description, "amount": amount}, []


# ----------------------------------------------------------------------
# Data processing / calculations
# ----------------------------------------------------------------------
def compute_summary(rows):
    """
    Totals for a list of transaction dictionaries.
    Returns a dictionary with income, expenses, balance, savings_rate,
    status (text) and level ("good", "warn", "bad", "neutral") for coloring.
    """
    income = 0.0
    expenses = 0.0
    for row in rows:                                  # loop + conditional
        if row["type"] == "Income":
            income += row["amount"]
        else:
            expenses += row["amount"]

    balance = income - expenses
    savings_rate = (balance / income * 100) if income > 0 else 0.0

    if not rows:
        status, level = "No data yet", "neutral"
    elif balance < 0:
        status, level = "Overspending - you spent more than your allowance and income", "bad"
    elif savings_rate >= 20:
        status, level = "Great job - you saved 20% or more of your money", "good"
    elif balance > 0:
        status, level = "On track - you still have money left", "good"
    else:
        status, level = "Break-even - nothing left over this period", "warn"

    return {"income": income, "expenses": expenses, "balance": balance,
            "savings_rate": savings_rate, "status": status, "level": level}


def days_left_in_month(today=None):
    """Days remaining in the month, counting today."""
    today = today or date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return last_day - today.day + 1


def daily_allowance(balance, today=None):
    """How much a student can spend per day until the month ends (never below 0)."""
    return max(balance, 0.0) / days_left_in_month(today)


def spending_by_category(rows):
    """Dictionary {category: total expense}, sorted from highest to lowest."""
    totals = defaultdict(float)
    for row in rows:
        if row["type"] == "Expense":
            totals[row["category"]] += row["amount"]
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))


def monthly_totals(rows):
    """Dictionary {'YYYY-MM': {'Income': x, 'Expense': y}} sorted by month."""
    months = defaultdict(lambda: {"Income": 0.0, "Expense": 0.0})
    for row in rows:
        months[row["date"][:7]][row["type"]] += row["amount"]
    return dict(sorted(months.items()))


def available_months(rows):
    """Unique 'YYYY-MM' values (newest first); always includes the current month."""
    months = {row["date"][:7] for row in rows}
    months.add(date.today().strftime("%Y-%m"))
    return sorted(months, reverse=True)


def month_matrix(year, month):
    """Weeks of a month for a calendar grid (Sunday first). 0 = day outside the month."""
    return calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)


def shift_month(year, month, delta):
    """Move forward/backward by `delta` months. Returns (year, month)."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def daily_totals(rows):
    """Dictionary {'YYYY-MM-DD': {'Income': x, 'Expense': y}} for the calendar cells."""
    days = defaultdict(lambda: {"Income": 0.0, "Expense": 0.0})
    for row in rows:
        days[row["date"]][row["type"]] += row["amount"]
    return dict(days)


def budget_status(spent, limit):
    """Return (percent_used, level, label) where level is ok / near / over."""
    percent = (spent / limit * 100) if limit > 0 else 0.0
    if percent > 100:
        return percent, "over", "Over budget"
    if percent >= 80:
        return percent, "near", "Near limit"
    return percent, "ok", "On track"


# ----------------------------------------------------------------------
# Reports and export
# ----------------------------------------------------------------------
def build_report_text(rows, generated=None):
    """Create a plain-text financial report from a list of transactions."""
    generated = generated or datetime.now()
    summary = compute_summary(rows)
    by_category = spending_by_category(rows)
    months = monthly_totals(rows)
    line = "=" * 64
    out = ["PESOWISE - STUDENT BUDGET REPORT",
           f"Generated: {generated:%Y-%m-%d %H:%M}",
           line, "", "1. OVERVIEW", "-" * 64,
           f"Transactions recorded : {len(rows)}",
           f"Total income          : {format_money(summary['income'])}",
           f"Total expenses        : {format_money(summary['expenses'])}",
           f"Net balance           : {format_money(summary['balance'])}",
           f"Savings rate          : {summary['savings_rate']:.1f}%",
           f"Status                : {summary['status']}", ""]

    out += ["2. EXPENSE BREAKDOWN BY CATEGORY", "-" * 64]
    if by_category:
        for category, amount in by_category.items():
            share = amount / summary["expenses"] * 100
            bar = "█" * max(1, round(share / 100 * 24))
            out.append(f"{category:<16}{format_money(amount):>15}{share:>7.1f}%  {bar}")
    else:
        out.append("No expenses recorded.")
    out.append("")

    out += ["3. MONTHLY SUMMARY", "-" * 64,
            f"{'Month':<10}{'Income':>16}{'Expenses':>16}{'Net':>16}"]
    if months:
        for month, totals in months.items():
            net = totals["Income"] - totals["Expense"]
            out.append(f"{month:<10}{format_money(totals['Income']):>16}"
                       f"{format_money(totals['Expense']):>16}{format_money(net):>16}")
    else:
        out.append("No data.")
    out.append("")

    out += ["4. TOP 5 LARGEST EXPENSES", "-" * 64]
    expenses = sorted((r for r in rows if r["type"] == "Expense"),
                      key=lambda r: r["amount"], reverse=True)[:5]
    if expenses:
        for rank, row in enumerate(expenses, start=1):
            out.append(f"{rank}. {row['date']}  {row['description']:<26}"
                       f"{row['category']:<16}{format_money(row['amount']):>14}")
    else:
        out.append("No expenses recorded.")
    out.append("")

    out += ["5. INSIGHTS", "-" * 64]
    if by_category:
        top_category = next(iter(by_category))
        out.append(f"* Highest spending category: {top_category} "
                   f"({format_money(by_category[top_category])}).")
        count = sum(1 for r in rows if r["type"] == "Expense")
        out.append(f"* Average expense per transaction: "
                   f"{format_money(summary['expenses'] / count)}.")
    deficits = [m for m, t in months.items() if t["Expense"] > t["Income"]]
    if deficits:
        out.append(f"* Months with overspending: {', '.join(deficits)}.")
    elif months:
        out.append("* No month with overspending. Keep it up!")
    if not rows:
        out.append("* Add some transactions to see insights.")
    return "\n".join(out)


def export_csv(path, rows):
    """Write transactions to a CSV file. Raises OSError if the file cannot be written."""
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["ID", "Date", "Type", "Category", "Description", "Amount"])
        for row in rows:
            writer.writerow([row["id"], row["date"], row["type"], row["category"],
                             row["description"], f"{row['amount']:.2f}"])


# ----------------------------------------------------------------------
# Sample data (for demonstrations and screenshots)
# ----------------------------------------------------------------------
def sample_data(today=None):
    """Return realistic records for the last 3 months."""
    today = today or date.today()
    templates = [
        (1, "Income", "Allowance", "Monthly allowance", 5000),
        (10, "Income", "Part-time Job", "Tutoring pay", 2000),
        (15, "Income", "Scholarship", "Scholarship stipend", 1500),
        (2, "Expense", "Food", "Canteen lunches (week 1)", 650),
        (9, "Expense", "Food", "Canteen lunches (week 2)", 620),
        (16, "Expense", "Food", "Canteen lunches (week 3)", 600),
        (23, "Expense", "Food", "Milk tea with friends", 280),
        (3, "Expense", "Transport", "Jeepney and MRT fare", 450),
        (17, "Expense", "Transport", "Ride-hailing home", 320),
        (4, "Expense", "Load & Data", "Mobile data promo", 299),
        (6, "Expense", "School Supplies", "Printing and notebooks", 420),
        (12, "Expense", "School Supplies", "Project materials", 850),
        (5, "Expense", "Rent & Dorm", "Dorm rent share", 2500),
        (14, "Expense", "Entertainment", "Movie night", 350),
        (18, "Expense", "Health", "Vitamins", 260),
        (20, "Expense", "Shopping", "New shirt", 600),
    ]
    factors = [1.0, 0.92, 1.08]          # small variation per month
    records = []
    for back in range(3):
        year, month = today.year, today.month - back
        while month <= 0:
            month += 12
            year -= 1
        for day, ttype, category, description, amount in templates:
            if back == 0 and day > today.day:
                continue                    # no future dates this month
            value = amount if ttype == "Income" else round(amount * factors[back], 2)
            records.append({"date": f"{year:04d}-{month:02d}-{day:02d}",
                            "type": ttype, "category": category,
                            "description": description, "amount": value})
    return records