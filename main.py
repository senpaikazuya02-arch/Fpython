import sqlite3
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk, messagebox, filedialog

import database as db
from functions import (CATEGORIES, EXPENSE_CATEGORIES, INCOME_CATEGORIES,
                       available_months, budget_status, build_report_text,
                       compute_summary, daily_allowance, daily_totals, export_csv,
                       format_money, format_money_short, month_matrix, parse_amount,
                       sample_data, shift_month, spending_by_category,
                       validate_transaction)

FONT = "Segoe UI"

BG = "#e9f0f3"            #
CARD = "#fbfdfd"         
BORDER = "#d0dde3"        
TRACK = "#dce7ec"       
ROW_HOVER = "#eef5f7"    

TEXT = "#1f3a47"        
MUTED = "#5d7683"       

SIDEBAR = "#1f3f4d"
SIDEBAR_HOVER = "#2a5163"
SIDEBAR_ACTIVE = "#33647a"
SIDEBAR_SUB = "#bdd2da"
ACCENT = "#7fd1bb"      

HERO = "#27607a"          
HERO_CHIP = "#357189"
HERO_SUB = "#cfe3ea"

PRIMARY = "#2b6f8e"
PRIMARY_HOVER = "#225a74"
GREEN = "#2f7d6d"
GREEN_HOVER = "#256456"
RED = "#a8484e"
RED_HOVER = "#8e3a40"
AMBER = "#a8671a"
NEUTRAL_BG = "#cfdde3"
NEUTRAL_HOVER = "#bccfd7"
LIGHT_BG = "#e6f0f3"      
CHIP_BG = "#dfeaee"      
CAL_SELECTED_BG = "#dcebf1"  
TODAY_BORDER = "#4fa98f"      

# Soft text colors used on the dark blue balance card
LEVEL_ON_DARK = {"good": "#a6e3d0", "warn": "#f2d49a", "bad": "#f6b9bc", "neutral": HERO_SUB}
LEVEL_COLORS = {"ok": GREEN, "near": AMBER, "over": RED}
PILL_COLORS = {"ok": ("#d6ece5", GREEN), "near": ("#f5e7cd", AMBER), "over": ("#f1d7d9", RED)}
TOAST_COLORS = {"success": GREEN, "warn": AMBER, "danger": RED}

# Every category gets its own muted color for its round icon and chart bar.
CATEGORY_COLORS = {
    "Food": "#c9894a", "Transport": "#5b8fb9", "School Supplies": "#7a8fc4",
    "Tuition & Fees": "#6a7db0", "Load & Data": "#4fa3a5", "Rent & Dorm": "#8a7fb0",
    "Bills": "#b5806a", "Shopping": "#c27a97", "Health": "#5fa88a",
    "Entertainment": "#b08c3f", "Other": "#78909c",
    "Allowance": "#3f9a84", "Part-time Job": "#4a8fbf", "Scholarship": "#6aa56a",
    "Freelance": "#5a9cae", "Gift": "#c0857b", "Other Income": "#78909c"}

WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

PAGE_INFO = {"home": ("Home", "Your money at a glance"),
             "transactions": ("Transactions", "Everything you earned and spent"),
             "calendar": ("Calendar", "See your spending day by day"),
             "budgets": ("Budgets", "Set limits so you do not overspend"),
             "reports": ("Reports", "A written summary of all your records")}

SORT_OPTIONS = {
    "Newest first": (lambda r: (r["date"], r["id"]), True),
    "Oldest first": (lambda r: (r["date"], r["id"]), False),
    "Highest amount": (lambda r: r["amount"], True),
    "Lowest amount": (lambda r: r["amount"], False)}

MAX_LIST_ROWS = 300       # keep the transaction list fast

def pretty_date(text):
    """'2026-11-17' -> 'Today' / 'Yesterday' / 'Nov 17, 2026'."""
    try:
        day = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return text
    delta = (date.today() - day).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    return f"{day:%b} {day.day}, {day.year}"


def bind_tree(widget, sequence, callback):
    """Bind an event on a widget and on everything inside it."""
    widget.bind(sequence, callback, add="+")
    for child in widget.winfo_children():
        bind_tree(child, sequence, callback)


def paint_tree(widget, color):
    """Change the background of a widget and everything inside it."""
    if not getattr(widget, "keep_bg", False) and widget.winfo_class() in ("Frame", "Label", "Canvas"):
        widget.configure(bg=color)
    for child in widget.winfo_children():
        paint_tree(child, color)


def clear_children(widget):
    for child in widget.winfo_children():
        child.destroy()

class FlatButton(tk.Label):
    """A big, flat, colored button (a Label that reacts to the mouse).
    Used instead of tk.Button because tk.Button ignores colors on macOS."""
    KINDS = {"primary": (PRIMARY, PRIMARY_HOVER, "white"),
             "success": (GREEN, GREEN_HOVER, "white"),
             "danger": (RED, RED_HOVER, "white"),
             "neutral": (NEUTRAL_BG, NEUTRAL_HOVER, TEXT),
             "light": (LIGHT_BG, "white", SIDEBAR)}

    def __init__(self, parent, text, command, kind="primary", size="normal"):
        bg, hover, fg = self.KINDS[kind]
        fonts = {"big": ((FONT, 11, "bold"), 22, 12),
                 "normal": ((FONT, 10, "bold"), 18, 9),
                 "small": ((FONT, 9, "bold"), 11, 5)}
        font, padx, pady = fonts[size]
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font,
                         padx=padx, pady=pady, cursor="hand2")
        self.base_color, self.hover_color, self.command = bg, hover, command
        self.bind("<Enter>", lambda event: self.configure(bg=self.hover_color))
        self.bind("<Leave>", lambda event: self.configure(bg=self.base_color))
        self.bind("<Button-1>", lambda event: self.command())


class ChipGroup(tk.Frame):
    """A grid of clickable chips. Exactly one chip is selected (stored in `variable`)."""

    def __init__(self, parent, items, variable, columns=4, bg=CARD, on_change=None):
        super().__init__(parent, bg=bg)
        self.variable = variable
        self.columns = columns
        self.on_change = on_change
        self.chips = {}
        self.set_items(items)

    def set_items(self, items):
        clear_children(self)
        self.chips = {}
        for index, item in enumerate(items):
            chip = tk.Label(self, text=item, padx=10, pady=8, cursor="hand2", font=(FONT, 10))
            chip.grid(row=index // self.columns, column=index % self.columns,
                      sticky="ew", padx=3, pady=3)
            chip.bind("<Button-1>", lambda event, value=item: self.select(value))
            self.chips[item] = chip
        for column in range(self.columns):
            self.columnconfigure(column, weight=1, uniform="chip")
        self.paint()

    def select(self, value):
        self.variable.set(value)
        self.paint()
        if self.on_change:
            self.on_change()

    def paint(self):
        for item, chip in self.chips.items():
            if item == self.variable.get():
                chip.configure(bg=PRIMARY, fg="white", font=(FONT, 10, "bold"))
            else:
                chip.configure(bg=CHIP_BG, fg=TEXT, font=(FONT, 10))


class RoundBar(tk.Canvas):
    """A progress bar with rounded ends."""

    def __init__(self, parent, bg=CARD, height=12):
        super().__init__(parent, bg=bg, height=height, highlightthickness=0)
        self.bar_height = height
        self.percent = 0.0
        self.color = GREEN
        self.bind("<Configure>", lambda event: self.redraw())

    def set(self, percent, color):
        self.percent = max(0.0, min(percent, 100.0))
        self.color = color
        self.redraw()

    def redraw(self):
        self.delete("all")
        width = self.winfo_width()
        if width < 20:
            return
        pad = self.bar_height // 2
        y = self.bar_height / 2
        thickness = self.bar_height - 2
        self.create_line(pad, y, width - pad, y, width=thickness, capstyle="round", fill=TRACK)
        if self.percent > 0:
            end = pad + (width - 2 * pad) * self.percent / 100
            self.create_line(pad, y, max(end, pad + 1), y, width=thickness,
                             capstyle="round", fill=self.color)


class ScrollFrame(tk.Frame):
    """A frame whose content scrolls vertically. Put widgets into `.inner`."""

    def __init__(self, parent, bg=BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, yscrollincrement=20)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda event: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(
            self.window, width=event.width))

    def scroll(self, event):
        if event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        elif event.delta:
            step = -1 if event.delta > 0 else 1
        else:
            return
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(step * 2, "units")


class NavItem(tk.Frame):
    """One entry of the sidebar menu."""

    def __init__(self, parent, text, command):
        super().__init__(parent, bg=SIDEBAR, cursor="hand2")
        self.active = False
        self.indicator = tk.Frame(self, bg=SIDEBAR, width=4)
        self.indicator.pack(side="left", fill="y")
        self.label = tk.Label(self, text=text, bg=SIDEBAR, fg=SIDEBAR_SUB, anchor="w",
                              font=(FONT, 11), padx=18, pady=12)
        self.label.pack(side="left", fill="x", expand=True)
        for widget in (self, self.label):
            widget.bind("<Button-1>", lambda event: command())
            widget.bind("<Enter>", lambda event: self.paint(True))
            widget.bind("<Leave>", lambda event: self.paint(False))

    def set_active(self, active):
        self.active = active
        self.paint(False)

    def paint(self, hover):
        if self.active:
            bg, fg, font = SIDEBAR_ACTIVE, "white", (FONT, 11, "bold")
        else:
            bg, fg, font = (SIDEBAR_HOVER if hover else SIDEBAR), SIDEBAR_SUB, (FONT, 11)
        self.configure(bg=bg)
        self.label.configure(bg=bg, fg=fg, font=font)
        self.indicator.configure(bg=ACCENT if self.active else bg)

class PopupBase(tk.Toplevel):
    """Shared behaviour for the pop-up forms: centered, modal, Esc closes."""

    def __init__(self, app, title, parent=None):
        super().__init__(parent or app.root)
        self.app = app
        self.withdraw()                      # hide until the layout is ready
        self.title(title)
        self.configure(bg=CARD, padx=28, pady=22)
        self.resizable(False, False)
        self.transient(parent or app.root)
        self.error_var = tk.StringVar()
        self.bind("<Escape>", lambda event: self.destroy())

    def label(self, text):
        tk.Label(self, text=text, bg=CARD, fg=MUTED, font=(FONT, 10, "bold"),
                 anchor="w").pack(fill="x", pady=(14, 5))

    def finish(self, focus_widget, buttons):
        """Show the pop-up in the middle of the main window and make it modal."""
        if buttons is not None:               # forms with Save/Cancel show errors above them
            tk.Label(self, textvariable=self.error_var, bg=CARD, fg=RED, justify="left",
                     anchor="w", wraplength=400, font=(FONT, 10)
                     ).pack(fill="x", pady=(12, 0), before=buttons)
        self.update_idletasks()
        root = self.master
        x = root.winfo_rootx() + (root.winfo_width() - self.winfo_reqwidth()) // 2
        y = root.winfo_rooty() + (root.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.wait_visibility()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        focus_widget.focus_set()

    def show_errors(self, errors):
        self.error_var.set("\n".join(f"\u2022 {error}" for error in errors))


class TransactionDialog(PopupBase):
    """Add a new transaction, or edit/delete an existing one."""

    def __init__(self, app, record=None, default_date=None):
        super().__init__(app, "Edit Transaction" if record else "Add Transaction")
        self.record = record
        today = default_date or date.today().strftime("%Y-%m-%d")
        self.type_var = tk.StringVar(value=record["type"] if record else "Expense")
        self.category_var = tk.StringVar(value=record["category"] if record else "")
        self.amount_var = tk.StringVar(value=f"{record['amount']:.2f}" if record else "")
        self.date_var = tk.StringVar(value=record["date"] if record else today)
        self.desc_var = tk.StringVar(value=record["description"] if record else "")

        tk.Label(self, text="Edit transaction" if record else "New transaction",
                 bg=CARD, fg=TEXT, font=(FONT, 16, "bold"), anchor="w").pack(fill="x")

        toggle = tk.Frame(self, bg=CARD)
        toggle.pack(fill="x", pady=(14, 0))
        toggle.columnconfigure(0, weight=1, uniform="toggle")
        toggle.columnconfigure(1, weight=1, uniform="toggle")
        self.type_buttons = {}
        for column, choice in enumerate(("Expense", "Income")):
            button = tk.Label(toggle, text=choice, pady=11, cursor="hand2", font=(FONT, 11, "bold"))
            button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 4, 0))
            button.bind("<Button-1>", lambda event, value=choice: self.set_type(value))
            self.type_buttons[choice] = button

        self.label("Amount")
        amount_row = tk.Frame(self, bg=CARD)
        amount_row.pack(fill="x")
        tk.Label(amount_row, text="\u20b1", bg=CARD, fg=TEXT,
                 font=(FONT, 20, "bold")).pack(side="left", padx=(0, 8))
        self.amount_entry = ttk.Entry(amount_row, textvariable=self.amount_var,
                                      style="Big.TEntry", width=18)
        self.amount_entry.pack(side="left", fill="x", expand=True)

        self.label("Category")
        self.chips = ChipGroup(self, CATEGORIES[self.type_var.get()], self.category_var, columns=3)
        self.chips.pack(fill="x")

        self.label("Date (YYYY-MM-DD)")
        date_row = tk.Frame(self, bg=CARD)
        date_row.pack(fill="x")
        ttk.Entry(date_row, textvariable=self.date_var, width=14).pack(side="left")
        FlatButton(date_row, "Calendar", self.pick_date, "primary", "small"
                   ).pack(side="left", padx=(10, 6))
        FlatButton(date_row, "Today", lambda: self.set_date(0), "neutral", "small"
                   ).pack(side="left", padx=(0, 6))
        FlatButton(date_row, "Yesterday", lambda: self.set_date(1), "neutral", "small"
                   ).pack(side="left")

        self.label("Description")
        desc_entry = ttk.Entry(self, textvariable=self.desc_var)
        desc_entry.pack(fill="x")
        buttons = tk.Frame(self, bg=CARD)
        buttons.pack(fill="x", pady=(20, 0))
        if record:
            FlatButton(buttons, "Delete", self.delete, "danger").pack(side="left")
        FlatButton(buttons, "Save", self.save, "success", "big").pack(side="right")
        FlatButton(buttons, "Cancel", self.destroy, "neutral", "big").pack(side="right", padx=10)

        for entry in (self.amount_entry, desc_entry):
            entry.bind("<Return>", lambda event: self.save())
        self.paint_type()
        self.finish(self.amount_entry, buttons)

    def set_type(self, value):
        self.type_var.set(value)
        if self.category_var.get() not in CATEGORIES[value]:
            self.category_var.set("")
        self.chips.set_items(CATEGORIES[value])
        self.paint_type()

    def paint_type(self):
        colors = {"Expense": RED, "Income": GREEN}
        for choice, button in self.type_buttons.items():
            if choice == self.type_var.get():
                button.configure(bg=colors[choice], fg="white")
            else:
                button.configure(bg=CHIP_BG, fg=TEXT)

    def pick_date(self):
        DatePicker(self.app, self, self.date_var.get(), self.date_var.set)

    def set_date(self, days_ago):
        day = date.today().toordinal() - days_ago
        self.date_var.set(date.fromordinal(day).strftime("%Y-%m-%d"))

    def save(self):
        record, errors = validate_transaction(self.date_var.get(), self.type_var.get(),
                                              self.category_var.get(), self.amount_var.get(),
                                              self.desc_var.get())
        if errors:
            self.show_errors(errors)
            return
        tx_id = self.record["id"] if self.record else None
        if self.app.commit_transaction(record, tx_id, self):
            self.destroy()

    def delete(self):
        if self.app.remove_transaction(self.record, self):
            self.destroy()


class DatePicker(PopupBase):
    """A small month calendar. Click a day to fill in the date."""

    def __init__(self, app, parent, initial, on_pick):
        super().__init__(app, "Pick a date", parent)
        self.parent_dialog = parent
        self.on_pick = on_pick
        try:
            start = datetime.strptime(initial.strip(), "%Y-%m-%d").date()
        except ValueError:
            start = date.today()
        self.selected = start
        self.year, self.month = start.year, start.month
        self.title_var = tk.StringVar()

        nav = tk.Frame(self, bg=CARD)
        nav.pack(fill="x")
        FlatButton(nav, "<", lambda: self.shift(-1), "neutral", "small").pack(side="left")
        FlatButton(nav, ">", lambda: self.shift(1), "neutral", "small").pack(side="right")
        tk.Label(nav, textvariable=self.title_var, bg=CARD, fg=TEXT,
                 font=(FONT, 13, "bold")).pack(side="left", expand=True)
        self.days = tk.Frame(self, bg=CARD)
        self.days.pack(pady=(12, 0))
        FlatButton(self, "Today", self.pick_today, "neutral").pack(fill="x", pady=(14, 0))
        self.draw()
        self.finish(self, None)

    def shift(self, delta):
        self.year, self.month = shift_month(self.year, self.month, delta)
        self.draw()

    def draw(self):
        self.title_var.set(f"{date(self.year, self.month, 1):%B %Y}")
        clear_children(self.days)
        for column, name in enumerate(WEEKDAYS):
            tk.Label(self.days, text=name, bg=CARD, fg=MUTED, width=5,
                     font=(FONT, 9, "bold")).grid(row=0, column=column, pady=(0, 4))
        today = date.today()
        for row, week in enumerate(month_matrix(self.year, self.month), start=1):
            for column, day in enumerate(week):
                if day == 0:
                    continue
                current = date(self.year, self.month, day)
                if current == self.selected:
                    bg, fg, font = PRIMARY, "white", (FONT, 10, "bold")
                elif current == today:
                    bg, fg, font = CAL_SELECTED_BG, PRIMARY, (FONT, 10, "bold")
                else:
                    bg, fg, font = CARD, TEXT, (FONT, 10)
                cell = tk.Label(self.days, text=str(day), bg=bg, fg=fg, font=font, width=5,
                                pady=7, cursor="hand2")
                cell.grid(row=row, column=column, padx=1, pady=1)
                cell.bind("<Button-1>", lambda event, value=current: self.choose(value))

    def choose(self, day):
        self.on_pick(day.strftime("%Y-%m-%d"))
        self.destroy()

    def pick_today(self):
        self.choose(date.today())

    def destroy(self):
        parent = self.parent_dialog
        super().destroy()
        try:
            parent.grab_set()              
        except tk.TclError:
            pass


class BudgetDialog(PopupBase):
    """Set, change or remove the monthly limit of one expense category."""

    def __init__(self, app, category=None, limit=None):
        super().__init__(app, "Edit Budget" if category else "Set a Budget")
        self.category_var = tk.StringVar(value=category or "")
        self.limit_var = tk.StringVar(value=f"{limit:.2f}" if limit else "")

        tk.Label(self, text="Monthly budget", bg=CARD, fg=TEXT,
                 font=(FONT, 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(self, text="Pick a category and the most you want to spend on it each month.",
                 bg=CARD, fg=MUTED, font=(FONT, 10), anchor="w", wraplength=400,
                 justify="left").pack(fill="x", pady=(4, 0))

        self.label("Category")
        ChipGroup(self, EXPENSE_CATEGORIES, self.category_var, columns=3).pack(fill="x")

        self.label("Monthly limit")
        limit_row = tk.Frame(self, bg=CARD)
        limit_row.pack(fill="x")
        tk.Label(limit_row, text="\u20b1", bg=CARD, fg=TEXT,
                 font=(FONT, 20, "bold")).pack(side="left", padx=(0, 8))
        self.limit_entry = ttk.Entry(limit_row, textvariable=self.limit_var,
                                     style="Big.TEntry", width=18)
        self.limit_entry.pack(side="left", fill="x", expand=True)
        self.limit_entry.bind("<Return>", lambda event: self.save())

        buttons = tk.Frame(self, bg=CARD)
        buttons.pack(fill="x", pady=(20, 0))
        if category:
            FlatButton(buttons, "Remove", self.remove, "danger").pack(side="left")
        FlatButton(buttons, "Save", self.save, "success", "big").pack(side="right")
        FlatButton(buttons, "Cancel", self.destroy, "neutral", "big").pack(side="right", padx=10)
        self.finish(self.limit_entry, buttons)

    def save(self):
        category = self.category_var.get()
        errors = []
        if category not in EXPENSE_CATEGORIES:
            errors.append("Please pick an expense category.")
        limit, error = parse_amount(self.limit_var.get())
        if error:
            errors.append(error.replace("Amount", "Limit"))
        if errors:
            self.show_errors(errors)
            return
        if self.app.save_budget(category, limit, self):
            self.destroy()

    def remove(self):
        if self.app.remove_budget(self.category_var.get(), self):
            self.destroy()

class BudgetApp:
    """The whole application. Each method does one clear job."""

    def __init__(self, root):
        self.root = root
        self.all_rows = []               # every transaction (list of dictionaries)
        self.chart_data = {}
        self.pages = {}
        self.nav_items = {}
        self.toast_job = None
        today = date.today()
        self.cal_year, self.cal_month = today.year, today.month     # month shown in Calendar
        self.selected_day = today.strftime("%Y-%m-%d")              # day picked in Calendar

        root.title("PesoWise - Student Budget Tracker")
        root.geometry("1180x760")
        root.minsize(1020, 680)
        root.configure(bg=BG)

        self.create_variables()
        self.apply_styles()
        self.build_layout()
        self.bind_shortcuts()
        self.refresh_all()
        self.show_page("home")

    def create_variables(self):
        """Tkinter variables linked to widgets."""
        today = date.today()
        self.title_var = tk.StringVar()
        self.subtitle_var = tk.StringVar()
        # home
        self.dash_month_var = tk.StringVar(value=today.strftime("%Y-%m"))
        self.income_var = tk.StringVar()
        self.expense_var = tk.StringVar()
        self.balance_var = tk.StringVar()
        self.rate_var = tk.StringVar()
        self.daily_var = tk.StringVar()
        self.daily_hint_var = tk.StringVar()
        self.dash_status_var = tk.StringVar()
        # transactions
        self.search_var = tk.StringVar()
        self.filter_type_var = tk.StringVar(value="All")
        self.filter_cat_var = tk.StringVar(value="All")
        self.filter_month_var = tk.StringVar(value="All")
        self.sort_var = tk.StringVar(value="Newest first")
        self.count_var = tk.StringVar()
        # calendar
        self.cal_title_var = tk.StringVar()
        self.cal_month_var = tk.StringVar()
        self.day_title_var = tk.StringVar()
        self.day_summary_var = tk.StringVar()
        # budgets
        self.budget_headline_var = tk.StringVar()
        self.budget_summary_var = tk.StringVar()

    def apply_styles(self):
        """Look of the few ttk widgets we still use (entries, dropdowns, scrollbars)."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=(FONT, 10))
        style.configure("TEntry", fieldbackground="white", foreground=TEXT, padding=7,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        style.map("TEntry", bordercolor=[("focus", PRIMARY)],
                  lightcolor=[("focus", PRIMARY)], darkcolor=[("focus", PRIMARY)])
        style.configure("Big.TEntry", font=(FONT, 18, "bold"), padding=8)
        style.configure("TCombobox", fieldbackground="white", background=NEUTRAL_BG,
                        foreground=TEXT, arrowcolor=TEXT, padding=6,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        style.map("TCombobox", fieldbackground=[("readonly", "white")],
                  foreground=[("readonly", TEXT)],
                  selectbackground=[("readonly", "white")],
                  selectforeground=[("readonly", TEXT)],
                  bordercolor=[("focus", PRIMARY)])
        style.configure("Vertical.TScrollbar", background="#b7cbd3", troughcolor=BG,
                        bordercolor=BG, arrowcolor=TEXT, relief="flat")
        self.root.option_add("*TCombobox*Listbox.background", "white")
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", PRIMARY)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "white")
        self.root.option_add("*TCombobox*Listbox.font", (FONT, 10))

    def bind_shortcuts(self):
        self.root.bind("<F5>", lambda event: self.refresh_all())
        self.root.bind("<Control-n>", lambda event: self.open_transaction_dialog())
        self.root.bind("<Control-e>", lambda event: self.export_transactions())
        self.root.bind_all("<MouseWheel>", self.on_mousewheel)
        self.root.bind_all("<Button-4>", self.on_mousewheel)      # Linux scroll up
        self.root.bind_all("<Button-5>", self.on_mousewheel)      # Linux scroll down

    def on_mousewheel(self, event):
        """Scroll the ScrollFrame that is under the mouse pointer."""
        try:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            return
        while widget is not None:
            if isinstance(widget, ScrollFrame):
                widget.scroll(event)
                return
            widget = widget.master

    def build_layout(self):
        self.build_sidebar()
        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        topbar = tk.Frame(self.main, bg=BG, padx=26, pady=18)
        topbar.pack(fill="x")
        titles = tk.Frame(topbar, bg=BG)
        titles.pack(side="left")
        tk.Label(titles, textvariable=self.title_var, bg=BG, fg=TEXT,
                 font=(FONT, 22, "bold"), anchor="w").pack(anchor="w")
        tk.Label(titles, textvariable=self.subtitle_var, bg=BG, fg=MUTED,
                 font=(FONT, 10), anchor="w").pack(anchor="w")
        today = date.today()
        tk.Label(topbar, text=f"{today:%A, %B} {today.day}, {today.year}", bg=BG, fg=MUTED,
                 font=(FONT, 10)).pack(side="right", anchor="n")

        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True)
        self.build_home_page()
        self.build_transactions_page()
        self.build_calendar_page()
        self.build_budgets_page()
        self.build_reports_page()

        self.toast_label = tk.Label(self.main, text="", fg="white", padx=20, pady=11,
                                    font=(FONT, 10, "bold"))

    def build_sidebar(self):
        sidebar = tk.Frame(self.root, bg=SIDEBAR, width=232)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        logo = tk.Frame(sidebar, bg=SIDEBAR, padx=22, pady=24)
        logo.pack(fill="x")
        tk.Label(logo, text="PesoWise", bg=SIDEBAR, fg="white",
                 font=(FONT, 21, "bold")).pack(anchor="w")
        tk.Label(logo, text="Student Budget Tracker", bg=SIDEBAR, fg=SIDEBAR_SUB,
                 font=(FONT, 9)).pack(anchor="w")

        FlatButton(sidebar, "+   Add Transaction", self.open_transaction_dialog,
                   "light", "big").pack(fill="x", padx=18, pady=(0, 20))

        for key, text in (("home", "Home"), ("transactions", "Transactions"),
                          ("calendar", "Calendar"), ("budgets", "Budgets"),
                          ("reports", "Reports")):
            item = NavItem(sidebar, text, lambda page=key: self.show_page(page))
            item.pack(fill="x")
            self.nav_items[key] = item

        bottom = tk.Frame(sidebar, bg=SIDEBAR, padx=22, pady=18)
        bottom.pack(side="bottom", fill="x")
        for text, command in (("Export to CSV", self.export_transactions),
                              ("Load sample data", self.load_sample_data),
                              ("Delete all data", self.delete_all_data),
                              ("About", self.show_about)):
            link = tk.Label(bottom, text=text, bg=SIDEBAR, fg=SIDEBAR_SUB, anchor="w",
                            font=(FONT, 10), cursor="hand2")
            link.pack(fill="x", pady=4)
            link.bind("<Button-1>", lambda event, action=command: action())
            link.bind("<Enter>", lambda event, label=link: label.configure(fg="white"))
            link.bind("<Leave>", lambda event, label=link: label.configure(fg=SIDEBAR_SUB))

    def show_page(self, key):
        for page in self.pages.values():
            page.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        for name, item in self.nav_items.items():
            item.set_active(name == key)
        self.title_var.set(PAGE_INFO[key][0])
        self.subtitle_var.set(PAGE_INFO[key][1])

    def make_card(self, parent, title=None, action_text=None, action=None):
        """A white card with an optional title and a small link on the right."""
        card = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=BORDER, padx=20, pady=16)
        if title:
            header = tk.Frame(card, bg=CARD)
            header.pack(fill="x", pady=(0, 10))
            tk.Label(header, text=title, bg=CARD, fg=TEXT,
                     font=(FONT, 12, "bold")).pack(side="left")
            if action_text:
                link = tk.Label(header, text=action_text, bg=CARD, fg=PRIMARY,
                                font=(FONT, 10, "bold"), cursor="hand2")
                link.pack(side="right")
                link.bind("<Button-1>", lambda event: action())
        return card

    def make_icon(self, parent, category, bg, size=42):
        """Round colored icon showing the first letter of the category."""
        canvas = tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0)
        color = CATEGORY_COLORS.get(category, "#78909c")
        canvas.create_oval(2, 2, size - 2, size - 2, fill=color, outline="")
        canvas.create_text(size / 2, size / 2, text=category[:1].upper(), fill="white",
                           font=(FONT, int(size / 3.2), "bold"))
        return canvas

    def make_hoverable(self, line, base=CARD, hover=ROW_HOVER):
        """Highlight a list row while the mouse is over it."""
        def on_enter(event):
            paint_tree(line, hover)

        def on_leave(event):
            try:
                x, y = line.winfo_pointerxy()
                under = line.winfo_containing(x, y)
            except (KeyError, tk.TclError):
                under = None
            if under is not None and (str(under) == str(line)
                                      or str(under).startswith(str(line) + ".")):
                return                        # still inside the row
            paint_tree(line, base)
        bind_tree(line, "<Enter>", on_enter)
        bind_tree(line, "<Leave>", on_leave)

    def build_tx_row(self, parent, row):
        """One transaction as a list row: icon, description, category/date, amount."""
        income = row["type"] == "Income"
        line = tk.Frame(parent, bg=CARD, cursor="hand2")
        line.pack(fill="x")
        body = tk.Frame(line, bg=CARD, padx=6, pady=10)
        body.pack(fill="x")
        self.make_icon(body, row["category"], CARD).pack(side="left")
        texts = tk.Frame(body, bg=CARD)
        texts.pack(side="left", padx=14, fill="x", expand=True)
        tk.Label(texts, text=row["description"], bg=CARD, fg=TEXT, anchor="w",
                 font=(FONT, 11, "bold")).pack(fill="x")
        tk.Label(texts, text=f"{row['category']}   \u2022   {pretty_date(row['date'])}",
                 bg=CARD, fg=MUTED, anchor="w", font=(FONT, 9)).pack(fill="x")
        sign = "+" if income else "-"
        tk.Label(body, text=f"{sign}{format_money(row['amount'])}", bg=CARD,
                 fg=GREEN if income else RED, font=(FONT, 12, "bold")).pack(side="right")
        divider = tk.Frame(line, bg=BORDER, height=1)
        divider.keep_bg = True
        divider.pack(fill="x")
        self.make_hoverable(line)
        bind_tree(line, "<Button-1>", lambda event, record=row: self.open_transaction_dialog(record))
        return line

    def empty_state(self, parent, message, bg=CARD):
        tk.Label(parent, text=message, bg=bg, fg=MUTED, font=(FONT, 11),
                 justify="center", pady=30).pack(fill="x")

    def notify(self, message, kind="success", milliseconds=2800):
        """Show a small message at the bottom of the window for a few seconds."""
        if self.toast_job is not None:
            self.root.after_cancel(self.toast_job)
        self.toast_label.configure(text=message, bg=TOAST_COLORS[kind])
        self.toast_label.place(relx=0.5, rely=1.0, y=-24, anchor="s")
        self.toast_label.lift()
        self.toast_job = self.root.after(milliseconds, self.hide_toast)

    def hide_toast(self):
        self.toast_label.place_forget()
        self.toast_job = None

    def build_home_page(self):
        page = ScrollFrame(self.content, bg=BG)
        self.pages["home"] = page
        body = tk.Frame(page.inner, bg=BG)
        body.pack(fill="x", padx=26, pady=(0, 20))

        top = tk.Frame(body, bg=BG)
        top.pack(fill="x", pady=(0, 12))
        tk.Label(top, text="Showing", bg=BG, fg=MUTED, font=(FONT, 10)).pack(side="left")
        self.dash_month_combo = ttk.Combobox(top, textvariable=self.dash_month_var,
                                             state="readonly", width=12)
        self.dash_month_combo.pack(side="left", padx=8)
        self.dash_month_combo.bind("<<ComboboxSelected>>", lambda event: self.refresh_home())

        # --- balance card + two small cards ---
        grid = tk.Frame(body, bg=BG)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=3, uniform="top")
        grid.columnconfigure(1, weight=2, uniform="top")

        hero = tk.Frame(grid, bg=HERO, padx=28, pady=24)
        hero.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        tk.Label(hero, text="Your balance", bg=HERO, fg=HERO_SUB, font=(FONT, 11)).pack(anchor="w")
        self.hero_amount = tk.Label(hero, textvariable=self.balance_var, bg=HERO, fg="white",
                                    font=(FONT, 32, "bold"))
        self.hero_amount.pack(anchor="w")
        self.hero_status = tk.Label(hero, textvariable=self.dash_status_var, bg=HERO,
                                    fg=HERO_SUB, font=(FONT, 10, "bold"), wraplength=430,
                                    justify="left")
        self.hero_status.pack(anchor="w", pady=(2, 18))
        chips = tk.Frame(hero, bg=HERO)
        chips.pack(fill="x")
        for title, variable in (("Money in", self.income_var), ("Money out", self.expense_var)):
            box = tk.Frame(chips, bg=HERO_CHIP, padx=18, pady=10)
            box.pack(side="left", padx=(0, 12))
            tk.Label(box, text=title, bg=HERO_CHIP, fg=HERO_SUB, font=(FONT, 9)).pack(anchor="w")
            tk.Label(box, textvariable=variable, bg=HERO_CHIP, fg="white",
                     font=(FONT, 13, "bold")).pack(anchor="w")

        side = tk.Frame(grid, bg=BG)
        side.grid(row=0, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)
        side.rowconfigure(0, weight=1)
        side.rowconfigure(1, weight=1)
        self.stat_card(side, "Safe to spend per day", self.daily_var, self.daily_hint_var,
                       AMBER).grid(row=0, column=0, sticky="nsew", pady=(0, 7))
        savings_hint = tk.StringVar(value="of the money you received")
        self.stat_card(side, "Savings rate", self.rate_var, savings_hint,
                       GREEN).grid(row=1, column=0, sticky="nsew", pady=(7, 0))

        middle = tk.Frame(body, bg=BG)
        middle.pack(fill="x", pady=14)
        middle.columnconfigure(0, weight=3, uniform="mid")
        middle.columnconfigure(1, weight=2, uniform="mid")

        chart_card = self.make_card(middle, "Where your money went")
        chart_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.chart_canvas = tk.Canvas(chart_card, bg=CARD, height=232, highlightthickness=0)
        self.chart_canvas.pack(fill="both", expand=True)
        self.chart_canvas.bind("<Configure>", lambda event: self.draw_category_chart())

        budget_card = self.make_card(middle, "Budget progress", "Manage",
                                     lambda: self.show_page("budgets"))
        budget_card.grid(row=0, column=1, sticky="nsew")
        self.budget_panel = tk.Frame(budget_card, bg=CARD)
        self.budget_panel.pack(fill="both", expand=True)

        recent_card = self.make_card(body, "Recent transactions", "See all",
                                     lambda: self.show_page("transactions"))
        recent_card.pack(fill="x")
        self.recent_box = tk.Frame(recent_card, bg=CARD)
        self.recent_box.pack(fill="x")

    def stat_card(self, parent, title, value_var, hint_var, color):
        card = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=BORDER, padx=20, pady=14)
        tk.Label(card, text=title, bg=CARD, fg=MUTED, font=(FONT, 10)).pack(anchor="w")
        tk.Label(card, textvariable=value_var, bg=CARD, fg=color,
                 font=(FONT, 22, "bold")).pack(anchor="w")
        tk.Label(card, textvariable=hint_var, bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        return card

    def refresh_home(self):
        period = self.dash_month_var.get()
        if period == "All time":
            rows = self.all_rows
        else:
            rows = [row for row in self.all_rows if row["date"].startswith(period)]

        summary = compute_summary(rows)
        self.income_var.set(format_money(summary["income"]))
        self.expense_var.set(format_money(summary["expenses"]))
        self.balance_var.set(format_money(summary["balance"]))
        self.rate_var.set(f"{summary['savings_rate']:.1f}%")
        self.dash_status_var.set(summary["status"])
        self.hero_status.configure(fg=LEVEL_ON_DARK[summary["level"]])
        self.hero_amount.configure(fg="white" if summary["balance"] >= 0 else LEVEL_ON_DARK["bad"])

        # The daily limit only makes sense for the current month.
        if period == date.today().strftime("%Y-%m"):
            self.daily_var.set(format_money(daily_allowance(summary["balance"])))
            self.daily_hint_var.set("until the end of this month")
        else:
            self.daily_var.set("n/a")
            self.daily_hint_var.set("choose this month to see it")

        self.chart_data = spending_by_category(rows)
        self.draw_category_chart()
        self.refresh_budget_panel()

        clear_children(self.recent_box)
        if self.all_rows:
            for row in self.all_rows[:5]:
                self.build_tx_row(self.recent_box, row)
        else:
            self.empty_state(self.recent_box, "No transactions yet.\n"
                             "Press  + Add Transaction  to record your first one.")

    def draw_category_chart(self):
        """Horizontal bars with rounded ends, drawn on a Canvas."""
        canvas = self.chart_canvas
        canvas.delete("all")
        width = canvas.winfo_width()
        if width < 50:
            width = 480
        if not self.chart_data:
            canvas.create_text(width / 2, 110, fill=MUTED, font=(FONT, 11),
                               text="No expenses for this period yet.")
            return
        items = list(self.chart_data.items())[:6]
        total = sum(self.chart_data.values())
        biggest = items[0][1]
        label_width, right_width, row_height = 118, 160, 36
        start = label_width + 6
        bar_space = max(width - label_width - right_width, 60)
        for index, (category, amount) in enumerate(items):
            y = 20 + index * row_height
            canvas.create_text(4, y, anchor="w", text=category, fill=TEXT, font=(FONT, 10))
            canvas.create_line(start, y, start + bar_space, y, width=12,
                               capstyle="round", fill=TRACK)
            length = max(bar_space * amount / biggest, 2)
            canvas.create_line(start, y, start + length, y, width=12, capstyle="round",
                               fill=CATEGORY_COLORS.get(category, PRIMARY))
            canvas.create_text(start + bar_space + 14, y, anchor="w", fill=MUTED,
                               font=(FONT, 9),
                               text=f"{format_money(amount)}   {amount / total * 100:.0f}%")

    def current_month_spending(self):
        month = date.today().strftime("%Y-%m")
        rows = [row for row in self.all_rows if row["date"].startswith(month)]
        return spending_by_category(rows)

    def get_budgets(self):
        try:
            return db.get_budgets()
        except sqlite3.Error as error:
            messagebox.showerror("Database Error", str(error))
            return {}

    def refresh_budget_panel(self):
        clear_children(self.budget_panel)
        budgets = self.get_budgets()
        if not budgets:
            self.empty_state(self.budget_panel, "No budgets yet.\nOpen Budgets to set a\n"
                             "monthly limit per category.")
            return
        spent = self.current_month_spending()
        results = []
        for category, limit in budgets.items():
            used = spent.get(category, 0.0)
            percent, level, label = budget_status(used, limit)
            results.append((percent, level, category, used, limit))
        results.sort(reverse=True)                      # most used first
        for percent, level, category, used, limit in results[:5]:
            line = tk.Frame(self.budget_panel, bg=CARD)
            line.pack(fill="x", pady=(0, 10))
            top = tk.Frame(line, bg=CARD)
            top.pack(fill="x")
            tk.Label(top, text=category, bg=CARD, fg=TEXT, font=(FONT, 10, "bold")).pack(side="left")
            tk.Label(top, text=f"{format_money(used)} / {format_money(limit)}", bg=CARD,
                     fg=MUTED, font=(FONT, 9)).pack(side="right")
            bar = RoundBar(line, CARD, height=12)
            bar.pack(fill="x", pady=(4, 0))
            bar.set(percent, LEVEL_COLORS[level])

    def build_transactions_page(self):
        page = tk.Frame(self.content, bg=BG, padx=26)
        self.pages["transactions"] = page

        # --- row 1: search, type chips, add ---
        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x")
        search = ttk.Entry(bar, textvariable=self.search_var, width=30)
        search.pack(side="left", padx=(0, 14))
        self.type_chips = ChipGroup(bar, ["All", "Expense", "Income"], self.filter_type_var,
                                    columns=3, bg=BG, on_change=self.refresh_transactions)
        self.type_chips.pack(side="left")
        FlatButton(bar, "+ Add", self.open_transaction_dialog, "success").pack(side="right")

        # --- row 2: dropdown filters ---
        filters = tk.Frame(page, bg=BG)
        filters.pack(fill="x", pady=(10, 8))
        tk.Label(filters, text="Category", bg=BG, fg=MUTED, font=(FONT, 10)).pack(side="left")
        cat_filter = ttk.Combobox(filters, textvariable=self.filter_cat_var, state="readonly",
                                  values=["All"] + EXPENSE_CATEGORIES + INCOME_CATEGORIES, width=15)
        cat_filter.pack(side="left", padx=(6, 14))
        tk.Label(filters, text="Month", bg=BG, fg=MUTED, font=(FONT, 10)).pack(side="left")
        self.month_filter = ttk.Combobox(filters, textvariable=self.filter_month_var,
                                         state="readonly", values=["All"], width=10)
        self.month_filter.pack(side="left", padx=(6, 14))
        tk.Label(filters, text="Sort", bg=BG, fg=MUTED, font=(FONT, 10)).pack(side="left")
        sort_filter = ttk.Combobox(filters, textvariable=self.sort_var, state="readonly",
                                   values=list(SORT_OPTIONS), width=14)
        sort_filter.pack(side="left", padx=(6, 14))
        FlatButton(filters, "Reset", self.reset_filters, "neutral", "small").pack(side="left")

        tk.Label(page, textvariable=self.count_var, bg=BG, fg=MUTED, anchor="w",
                 font=(FONT, 10)).pack(fill="x", pady=(0, 6))

        card = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=BORDER, padx=10, pady=6)
        card.pack(fill="both", expand=True, pady=(0, 20))
        self.tx_scroll = ScrollFrame(card, bg=CARD)
        self.tx_scroll.pack(fill="both", expand=True)

        # live filtering (set up last so every widget already exists)
        self.search_var.trace_add("write", lambda *args: self.refresh_transactions())
        for combo in (cat_filter, self.month_filter, sort_filter):
            combo.bind("<<ComboboxSelected>>", lambda event: self.refresh_transactions())

    def reset_filters(self):
        self.filter_type_var.set("All")
        self.filter_cat_var.set("All")
        self.filter_month_var.set("All")
        self.sort_var.set("Newest first")
        self.search_var.set("")
        self.type_chips.paint()
        self.refresh_transactions()

    def refresh_transactions(self):
        ttype = self.filter_type_var.get()
        category = self.filter_cat_var.get()
        month = self.filter_month_var.get()
        try:
            rows = db.get_transactions(
                ttype=None if ttype == "All" else ttype,
                category=None if category == "All" else category,
                month=None if month == "All" else month,
                keyword=self.search_var.get().strip() or None)
        except sqlite3.Error as error:
            messagebox.showerror("Database Error", str(error))
            return

        sort_key, descending = SORT_OPTIONS[self.sort_var.get()]
        rows.sort(key=sort_key, reverse=descending)

        inner = self.tx_scroll.inner
        clear_children(inner)
        if not rows:
            self.empty_state(inner, "No transactions match.\nTry another filter or add a new one.")
        for row in rows[:MAX_LIST_ROWS]:
            self.build_tx_row(inner, row)

        summary = compute_summary(rows)
        shown = min(len(rows), MAX_LIST_ROWS)
        self.count_var.set(f"{shown} of {len(self.all_rows)} transactions   \u2022   "
                           f"In {format_money(summary['income'])}   "
                           f"Out {format_money(summary['expenses'])}   "
                           f"Net {format_money(summary['balance'])}")

    def build_calendar_page(self):
        page = tk.Frame(self.content, bg=BG, padx=26)
        self.pages["calendar"] = page
        page.columnconfigure(0, weight=3, uniform="cal")
        page.columnconfigure(1, weight=2, uniform="cal")
        page.rowconfigure(0, weight=1)

        # --- left: month grid ---
        left = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=BORDER, padx=16, pady=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14), pady=(0, 20))
        nav = tk.Frame(left, bg=CARD)
        nav.pack(fill="x", pady=(0, 10))
        FlatButton(nav, "<", lambda: self.change_month(-1), "neutral").pack(side="left")
        FlatButton(nav, ">", lambda: self.change_month(1), "neutral").pack(side="left", padx=(6, 0))
        tk.Label(nav, textvariable=self.cal_title_var, bg=CARD, fg=TEXT,
                 font=(FONT, 15, "bold")).pack(side="left", padx=16)
        FlatButton(nav, "Today", self.go_today, "primary").pack(side="right")
        self.cal_grid = tk.Frame(left, bg=CARD)
        self.cal_grid.pack(fill="both", expand=True)
        tk.Label(left, textvariable=self.cal_month_var, bg=CARD, fg=MUTED, anchor="w",
                 font=(FONT, 10)).pack(fill="x", pady=(8, 0))

        # --- right: the selected day ---
        right = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER,
                         highlightcolor=BORDER, padx=18, pady=14)
        right.grid(row=0, column=1, sticky="nsew", pady=(0, 20))
        tk.Label(right, textvariable=self.day_title_var, bg=CARD, fg=TEXT, anchor="w",
                 font=(FONT, 13, "bold")).pack(fill="x")
        tk.Label(right, textvariable=self.day_summary_var, bg=CARD, fg=MUTED, anchor="w",
                 font=(FONT, 10)).pack(fill="x", pady=(2, 10))
        FlatButton(right, "+ Add on this day",
                   lambda: self.open_transaction_dialog(None, self.selected_day),
                   "success").pack(fill="x", pady=(0, 10))
        self.day_scroll = ScrollFrame(right, bg=CARD)
        self.day_scroll.pack(fill="both", expand=True)

    def change_month(self, delta):
        self.cal_year, self.cal_month = shift_month(self.cal_year, self.cal_month, delta)
        today = date.today()
        if (self.cal_year, self.cal_month) == (today.year, today.month):
            self.selected_day = today.strftime("%Y-%m-%d")
        else:
            self.selected_day = f"{self.cal_year:04d}-{self.cal_month:02d}-01"
        self.refresh_calendar()

    def go_today(self):
        today = date.today()
        self.cal_year, self.cal_month = today.year, today.month
        self.selected_day = today.strftime("%Y-%m-%d")
        self.refresh_calendar()

    def select_day(self, day_text):
        self.selected_day = day_text
        self.refresh_calendar()

    def refresh_calendar(self):
        year, month = self.cal_year, self.cal_month
        self.cal_title_var.set(f"{date(year, month, 1):%B %Y}")
        prefix = f"{year:04d}-{month:02d}"
        month_rows = [row for row in self.all_rows if row["date"].startswith(prefix)]
        totals = daily_totals(month_rows)

        grid = self.cal_grid
        clear_children(grid)
        weeks = month_matrix(year, month)
        for column in range(7):
            grid.columnconfigure(column, weight=1, uniform="day")
            tk.Label(grid, text=WEEKDAYS[column], bg=CARD, fg=MUTED,
                     font=(FONT, 9, "bold")).grid(row=0, column=column, pady=(0, 4))
        for row_number in range(1, 7):
            grid.rowconfigure(row_number, weight=1 if row_number <= len(weeks) else 0)
        for row_number, week in enumerate(weeks, start=1):
            for column, day in enumerate(week):
                if day:
                    day_text = f"{prefix}-{day:02d}"
                    self.build_day_cell(grid, row_number, column, day, day_text,
                                        totals.get(day_text))

        summary = compute_summary(month_rows)
        self.cal_month_var.set(f"This month   \u2022   In {format_money(summary['income'])}   "
                               f"Out {format_money(summary['expenses'])}   "
                               f"Net {format_money(summary['balance'])}")
        self.refresh_day_panel()

    def build_day_cell(self, grid, row_number, column, day, day_text, totals):
        """One day of the month: the number plus money in / money out."""
        is_today = day_text == date.today().strftime("%Y-%m-%d")
        selected = day_text == self.selected_day
        bg = CAL_SELECTED_BG if selected else CARD
        border = PRIMARY if selected else (TODAY_BORDER if is_today else BORDER)
        thickness = 2 if (selected or is_today) else 1
        cell = tk.Frame(grid, bg=bg, highlightthickness=thickness, highlightbackground=border,
                        highlightcolor=border, padx=6, pady=4, cursor="hand2")
        cell.grid(row=row_number, column=column, sticky="nsew", padx=2, pady=2)
        tk.Label(cell, text=str(day), bg=bg, fg=PRIMARY if is_today else TEXT, anchor="w",
                 font=(FONT, 10, "bold")).pack(fill="x")
        income = totals["Income"] if totals else 0
        expense = totals["Expense"] if totals else 0
        tk.Label(cell, text=f"+{format_money_short(income)}" if income else " ", bg=bg,
                 fg=GREEN, anchor="w", font=(FONT, 8)).pack(fill="x")
        tk.Label(cell, text=f"-{format_money_short(expense)}" if expense else " ", bg=bg,
                 fg=RED, anchor="w", font=(FONT, 8)).pack(fill="x")
        bind_tree(cell, "<Button-1>", lambda event, value=day_text: self.select_day(value))

    def refresh_day_panel(self):
        day = datetime.strptime(self.selected_day, "%Y-%m-%d").date()
        self.day_title_var.set(f"{day:%A, %B} {day.day}, {day.year}")
        rows = [row for row in self.all_rows if row["date"] == self.selected_day]
        inner = self.day_scroll.inner
        clear_children(inner)
        if rows:
            summary = compute_summary(rows)
            self.day_summary_var.set(f"In {format_money(summary['income'])}   \u2022   "
                                     f"Out {format_money(summary['expenses'])}")
            for row in rows:
                self.build_tx_row(inner, row)
        else:
            self.day_summary_var.set("Nothing recorded")
            self.empty_state(inner, "No transactions on this day.\nUse the green button to add one.")

    def build_budgets_page(self):
        page = tk.Frame(self.content, bg=BG, padx=26)
        self.pages["budgets"] = page

        summary = tk.Frame(page, bg=HERO, padx=26, pady=20)
        summary.pack(fill="x")
        head = tk.Frame(summary, bg=HERO)
        head.pack(fill="x")
        tk.Label(head, text=f"{date.today():%B %Y} budgets", bg=HERO, fg=HERO_SUB,
                 font=(FONT, 11)).pack(side="left")
        FlatButton(head, "+ Set a Budget", self.open_budget_dialog, "light").pack(side="right")
        tk.Label(summary, textvariable=self.budget_headline_var, bg=HERO, fg="white",
                 font=(FONT, 22, "bold"), anchor="w").pack(fill="x", pady=(4, 8))
        self.budget_total_bar = RoundBar(summary, HERO, height=14)
        self.budget_total_bar.pack(fill="x")
        tk.Label(summary, textvariable=self.budget_summary_var, bg=HERO, fg=HERO_SUB,
                 font=(FONT, 10), anchor="w").pack(fill="x", pady=(8, 0))

        tk.Label(page, text="Tap a budget to edit it", bg=BG, fg=MUTED, anchor="w",
                 font=(FONT, 10)).pack(fill="x", pady=(14, 6))
        self.budget_scroll = ScrollFrame(page, bg=BG)
        self.budget_scroll.pack(fill="both", expand=True, pady=(0, 20))

    def refresh_budgets(self):
        budgets = self.get_budgets()
        spent = self.current_month_spending()
        inner = self.budget_scroll.inner
        clear_children(inner)

        total_limit = total_spent = 0.0
        for category, limit in budgets.items():
            used = spent.get(category, 0.0)
            percent, level, label = budget_status(used, limit)
            total_limit += limit
            total_spent += used
            self.build_budget_card(inner, category, limit, used, percent, level, label)

        if budgets:
            left = total_limit - total_spent
            if left >= 0:
                self.budget_headline_var.set(f"{format_money(left)} left to spend")
            else:
                self.budget_headline_var.set(f"Over by {format_money(-left)}")
            self.budget_summary_var.set(f"Budgeted {format_money(total_limit)}   \u2022   "
                                        f"Spent {format_money(total_spent)}")
            percent, level, label = budget_status(total_spent, total_limit)
            self.budget_total_bar.set(percent, {"ok": "#7fd1bb", "near": "#f2d49a",
                                                "over": "#f6b9bc"}[level])
        else:
            self.budget_headline_var.set("No budgets yet")
            self.budget_summary_var.set("Press + Set a Budget to add your first limit.")
            self.budget_total_bar.set(0, "#7fd1bb")
            self.empty_state(inner, "Budgets help you stay inside your allowance.\n"
                             "Try Food or Load & Data first.", bg=BG)

    def build_budget_card(self, parent, category, limit, used, percent, level, label):
        card = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=BORDER, padx=20, pady=14, cursor="hand2")
        card.pack(fill="x", pady=5, padx=(0, 8))
        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x")
        self.make_icon(top, category, CARD).pack(side="left")
        names = tk.Frame(top, bg=CARD)
        names.pack(side="left", padx=14)
        tk.Label(names, text=category, bg=CARD, fg=TEXT, anchor="w",
                 font=(FONT, 12, "bold")).pack(fill="x")
        tk.Label(names, text=f"{format_money(used)} of {format_money(limit)} spent", bg=CARD,
                 fg=MUTED, anchor="w", font=(FONT, 9)).pack(fill="x")
        pill_bg, pill_fg = PILL_COLORS[level]
        pill = tk.Label(top, text=f"{label}  {percent:.0f}%", bg=pill_bg, fg=pill_fg,
                        padx=12, pady=4, font=(FONT, 9, "bold"))
        pill.keep_bg = True
        pill.pack(side="right")
        bar = RoundBar(card, CARD, height=14)
        bar.pack(fill="x", pady=(12, 4))
        bar.set(percent, LEVEL_COLORS[level])
        remaining = limit - used
        text = f"{format_money(remaining)} left" if remaining >= 0 else f"Over by {format_money(-remaining)}"
        tk.Label(card, text=text, bg=CARD, fg=RED if remaining < 0 else MUTED, anchor="w",
                 font=(FONT, 9)).pack(fill="x")
        bind_tree(card, "<Button-1>",
                  lambda event, name=category, amount=limit: self.open_budget_dialog(name, amount))

    def build_reports_page(self):
        page = tk.Frame(self.content, bg=BG, padx=26)
        self.pages["reports"] = page
        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", pady=(0, 10))
        FlatButton(bar, "Save Report", self.save_report, "primary").pack(side="left")
        FlatButton(bar, "Export CSV", self.export_transactions, "neutral").pack(side="left", padx=10)
        FlatButton(bar, "Refresh", self.refresh_all, "neutral").pack(side="left")

        card = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=BORDER)
        card.pack(fill="both", expand=True, pady=(0, 20))
        self.report_text = tk.Text(card, wrap="none", font=("Courier New", 10), bg=CARD, fg=TEXT,
                                   padx=18, pady=14, state="disabled", relief="flat", bd=0)
        y_scroll = ttk.Scrollbar(card, orient="vertical", command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=y_scroll.set)
        self.report_text.pack(side="left", fill="both", expand=True)
        y_scroll.pack(side="right", fill="y")

    def refresh_report(self):
        self.report_text.config(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", build_report_text(self.all_rows))
        self.report_text.config(state="disabled")

    def refresh_month_options(self):
        months = available_months(self.all_rows)
        self.dash_month_combo["values"] = ["All time"] + months
        if self.dash_month_var.get() not in ["All time"] + months:
            self.dash_month_var.set(months[0])
        self.month_filter["values"] = ["All"] + months
        if self.filter_month_var.get() not in ["All"] + months:
            self.filter_month_var.set("All")

    def refresh_all(self):
        try:
            self.all_rows = db.get_transactions()
        except sqlite3.Error as error:
            messagebox.showerror("Database Error", f"Could not load data.\n\n{error}")
            self.all_rows = []
        self.refresh_month_options()
        self.refresh_home()
        self.refresh_transactions()
        self.refresh_calendar()
        self.refresh_budgets()
        self.refresh_report()

    def open_transaction_dialog(self, record=None, default_date=None):
        TransactionDialog(self, record, default_date)

    def open_budget_dialog(self, category=None, limit=None):
        BudgetDialog(self, category, limit)

    def commit_transaction(self, record, tx_id, parent):
        """Save a new transaction (tx_id None) or update an existing one. True on success."""
        try:
            if tx_id is None:
                if db.is_duplicate(record) and not messagebox.askyesno(
                        "Possible Duplicate",
                        "A transaction with the same date, type, category, description "
                        "and amount already exists.\n\nAdd it anyway?", parent=parent):
                    return False
                db.add_transaction(record)
                message = f"Added: {record['description']} ({format_money(record['amount'])})"
            else:
                if db.is_duplicate(record, ignore_id=tx_id):
                    messagebox.showwarning("Duplicate", "Another transaction with exactly the "
                                           "same details already exists.", parent=parent)
                    return False
                if not db.update_transaction(tx_id, record):
                    messagebox.showerror("Not Found", "That record no longer exists.",
                                         parent=parent)
                    return False
                message = "Transaction updated"
        except sqlite3.Error as error:
            messagebox.showerror("Database Error", f"Could not save the record.\n\n{error}",
                                 parent=parent)
            return False
        self.refresh_all()
        alert = self.budget_alert(record)
        if alert:
            self.notify(alert[0], alert[1], 5000)
        else:
            self.notify(message)
        return True

    def remove_transaction(self, record, parent):
        question = (f"Delete this transaction?\n\n{record['date']}  |  {record['type']}  |  "
                    f"{record['description']}  |  {format_money(record['amount'])}\n\n"
                    "This cannot be undone.")
        if not messagebox.askyesno("Confirm Delete", question, icon="warning", parent=parent):
            return False
        try:
            db.delete_transaction(record["id"])
        except sqlite3.Error as error:
            messagebox.showerror("Database Error", f"Could not delete the record.\n\n{error}",
                                 parent=parent)
            return False
        self.refresh_all()
        self.notify("Transaction deleted")
        return True

    def budget_alert(self, record):
        """Return (message, kind) when an expense pushes a category near/over its budget."""
        if record["type"] != "Expense":
            return None
        try:
            limit = db.get_budgets().get(record["category"])
            if limit is None:
                return None
            rows = db.get_transactions(ttype="Expense", category=record["category"],
                                       month=record["date"][:7])
        except sqlite3.Error:
            return None
        spent = sum(row["amount"] for row in rows)
        percent, level, label = budget_status(spent, limit)
        if level == "over":
            return (f"Over budget: {record['category']} is at {percent:.0f}% "
                    f"({format_money(spent)} of {format_money(limit)})", "danger")
        if level == "near":
            return (f"Heads up: {record['category']} is at {percent:.0f}% of its budget", "warn")
        return None

    def save_budget(self, category, limit, parent):
        try:
            db.set_budget(category, limit)
        except sqlite3.Error as error:
            messagebox.showerror("Database Error", str(error), parent=parent)
            return False
        self.refresh_all()
        self.notify(f"Budget saved: {category} {format_money(limit)} per month")
        return True

    def remove_budget(self, category, parent):
        if not category:
            return False
        if not messagebox.askyesno("Confirm", f"Remove the budget for {category}?", parent=parent):
            return False
        try:
            removed = db.remove_budget(category)
        except sqlite3.Error as error:
            messagebox.showerror("Database Error", str(error), parent=parent)
            return False
        if not removed:
            messagebox.showinfo("Not Found", f"There is no budget for {category}.", parent=parent)
            return False
        self.refresh_all()
        self.notify(f"Budget removed: {category}")
        return True

    def export_transactions(self):
        if not self.all_rows:
            messagebox.showinfo("Nothing to Export", "There are no transactions yet.")
            return
        path = filedialog.asksaveasfilename(
            title="Export transactions", defaultextension=".csv",
            initialfile=f"transactions_{date.today():%Y%m%d}.csv",
            filetypes=[("CSV file", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            export_csv(path, self.all_rows)
        except OSError as error:
            messagebox.showerror("Export Failed", f"Could not write the file.\n\n{error}")
            return
        self.notify(f"Exported {len(self.all_rows)} transactions")

    def save_report(self):
        path = filedialog.asksaveasfilename(
            title="Save report", defaultextension=".txt",
            initialfile=f"report_{date.today():%Y%m%d}.txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(build_report_text(self.all_rows))
        except OSError as error:
            messagebox.showerror("Save Failed", f"Could not write the file.\n\n{error}")
            return
        self.notify("Report saved")

    def load_sample_data(self):
        if not messagebox.askyesno("Load Sample Data",
                                   "Add about 45 sample student transactions and starter budgets "
                                   "for demonstration?\n\nYour existing data will be kept."):
            return
        added = skipped = 0
        try:
            for record in sample_data():
                if db.is_duplicate(record):
                    skipped += 1
                else:
                    db.add_transaction(record)
                    added += 1
            if not db.get_budgets():
                for category, limit in (("Food", 2500), ("Transport", 800),
                                        ("Load & Data", 350), ("Entertainment", 400),
                                        ("School Supplies", 1000)):
                    db.set_budget(category, limit)
        except sqlite3.Error as error:
            messagebox.showerror("Database Error", str(error))
            return
        self.refresh_all()
        self.notify(f"Sample data loaded: {added} added, {skipped} skipped")

    def delete_all_data(self):
        if not messagebox.askyesno("Delete All Data",
                                   "This permanently deletes ALL transactions and budgets.\n\n"
                                   "Are you absolutely sure?", icon="warning"):
            return
        try:
            db.clear_all()
        except sqlite3.Error as error:
            messagebox.showerror("Database Error", str(error))
            return
        self.refresh_all()
        self.notify("All data deleted", "warn")

    def show_about(self):
        messagebox.showinfo("About PesoWise",
                            "PesoWise - Student Budget Tracker\n"
                            "Version 2.0\n\n"
                            "Python Tkinter Final Project\n"
                            "Storage: SQLite (pesowise.db)\n\n"
                            "Shortcuts:  Ctrl+N add transaction,  Ctrl+E export CSV,  "
                            "F5 refresh,  Esc close a pop-up.\n\n"
                            "Track your allowance, income and school expenses, set monthly "
                            "category budgets, see how much you can safely spend per day, "
                            "and view reports.")


def main():
    db.init_db()
    root = tk.Tk()
    BudgetApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()