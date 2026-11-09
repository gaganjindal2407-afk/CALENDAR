"""
Timeless Calendar - An endless desktop calendar with dynamic yearly repeats,
leap-year (Feb 29) handling, reminder schedules, and theme switching.
"""

import os
import sys
import json
import uuid
import calendar
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Optional plyer support for native desktop notifications
try:
    from plyer import notification as plyer_notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


# ==========================================
# CONFIGURATION & THEMES
# ==========================================

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_DIR, "events.json")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")

CATEGORIES = {
    "Anniversary": "#E91E63",  # Vibrant Pink
    "Birthday":    "#9C27B0",  # Purple
    "Holiday":     "#2E7D32",  # Forest Green
    "Personal":    "#0288D1",  # Deep Sky Blue
    "Other":       "#EF6C00",  # Dark Orange
}

THEMES = {
    "light": {
        "bg": "#F5F6F8",
        "card_bg": "#FFFFFF",
        "header_bg": "#EAECEF",
        "fg": "#212529",
        "muted_fg": "#6C757D",
        "border": "#D0D5DD",
        "selected": "#D6E4FF",
        "today_highlight": "#E3F2FD",
        "today_fg": "#0D47A1",
        "button_bg": "#FFFFFF",
        "button_fg": "#212529",
        "accent": "#1976D2",
    },
    "dark": {
        "bg": "#121418",
        "card_bg": "#1E222B",
        "header_bg": "#181B22",
        "fg": "#E0E6ED",
        "muted_fg": "#8B949E",
        "border": "#2E3440",
        "selected": "#2D3748",
        "today_highlight": "#203354",
        "today_fg": "#64B5F6",
        "button_bg": "#252B36",
        "button_fg": "#E0E6ED",
        "accent": "#42A5F5",
    }
}


def get_ordinal(n: int) -> str:
    """Return ordinal representation of an integer (e.g., 1st, 2nd, 3rd, 4th)."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# ==========================================
# DATA & SETTINGS STORAGE
# ==========================================

class EventManager:
    """Handles storage, querying, and on-the-fly recurrence computation."""

    def __init__(self, data_path=DATA_FILE, settings_path=SETTINGS_FILE):
        self.data_path = data_path
        self.settings_path = settings_path
        self.events = []
        self.settings = {
            "theme": "light",
            "feb29_rule": "Feb 28"  # Options: 'Feb 28' or 'Mar 1'
        }
        self.load_settings()
        self.load_events()

    def load_settings(self):
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    self.settings.update(json.load(f))
            except Exception:
                pass

    def save_settings(self):
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_events(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    self.events = json.load(f)
            except Exception:
                self.events = []
        else:
            self.events = []

    def save_events(self):
        try:
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(self.events, f, indent=2)
        except Exception as e:
            print(f"Error saving events: {e}")

    def add_event(self, event_data: dict):
        if "id" not in event_data:
            event_data["id"] = str(uuid.uuid4())
        self.events.append(event_data)
        self.save_events()

    def update_event(self, updated_data: dict):
        for idx, ev in enumerate(self.events):
            if ev["id"] == updated_data["id"]:
                self.events[idx] = updated_data
                self.save_events()
                return True
        return False

    def delete_event(self, event_id: str):
        self.events = [ev for ev in self.events if ev["id"] != event_id]
        self.save_events()

    def get_event_by_id(self, event_id: str):
        for ev in self.events:
            if ev["id"] == event_id:
                return ev
        return None

    def resolve_occurrence_date(self, event: dict, target_year: int):
        """
        Calculates occurrence date for an event in `target_year`.
        Returns date object or None if the event should not occur.
        """
        orig_y, orig_m, orig_d = map(int, event["start_date"].split("-"))
        repeat = event.get("repeat_yearly", False)

        if not repeat:
            if orig_y == target_year:
                return date(orig_y, orig_m, orig_d)
            return None

        # Do not show yearly repeated events prior to their inception year
        if target_year < orig_y:
            return None

        # Handle February 29th events
        if orig_m == 2 and orig_d == 29:
            if calendar.isleap(target_year):
                return date(target_year, 2, 29)
            else:
                rule = self.settings.get("feb29_rule", "Feb 28")
                return date(target_year, 3, 1) if rule == "Mar 1" else date(target_year, 2, 28)

        # Standard anniversary/birthday
        try:
            return date(target_year, orig_m, orig_d)
        except ValueError:
            return None

    def format_event_title(self, event: dict, target_year: int) -> str:
        """Formats the title with milestone counts (e.g., '5th Anniversary', 'Turns 30')."""
        orig_y, _, _ = map(int, event["start_date"].split("-"))
        title = event.get("title", "Untitled")
        category = event.get("category", "Other")
        repeat = event.get("repeat_yearly", False)

        if not repeat or target_year <= orig_y:
            return title

        diff = target_year - orig_y
        if category == "Birthday":
            return f"{title} (Turns {diff})"
        elif category == "Anniversary":
            if "anniversary" in title.lower():
                return f"{title} ({get_ordinal(diff)})"
            return f"{title} ({get_ordinal(diff)} Anniversary)"
        else:
            return f"{title} ({get_ordinal(diff)} Year)"

    def get_events_for_date(self, query_date: date):
        """Finds all events and milestone copies occurring on a specific date."""
        results = []
        for ev in self.events:
            occ_date = self.resolve_occurrence_date(ev, query_date.year)
            if occ_date == query_date:
                display_title = self.format_event_title(ev, query_date.year)
                results.append({
                    "event": ev,
                    "display_title": display_title,
                    "date": query_date
                })
        return results

    def get_events_for_month(self, year: int, month: int):
        """Returns a dict mapping day (int) to list of event items."""
        events_by_day = {}
        for ev in self.events:
            occ_date = self.resolve_occurrence_date(ev, year)
            if occ_date and occ_date.month == month:
                day = occ_date.day
                if day not in events_by_day:
                    events_by_day[day] = []
                events_by_day[day].append({
                    "event": ev,
                    "display_title": self.format_event_title(ev, year),
                    "date": occ_date
                })
        return events_by_day

    def get_upcoming(self, base_date: date, days_ahead: int = 30):
        """Returns all events and reminders occurring in [base_date, base_date + days_ahead]."""
        end_date = base_date + timedelta(days=days_ahead)
        years_to_check = {base_date.year, end_date.year}
        upcoming_items = []

        for ev in self.events:
            for y in years_to_check:
                occ_date = self.resolve_occurrence_date(ev, y)
                if not occ_date:
                    continue

                display_title = self.format_event_title(ev, y)

                # Event day itself
                if base_date <= occ_date <= end_date:
                    upcoming_items.append({
                        "type": "event",
                        "date": occ_date,
                        "days_left": (occ_date - base_date).days,
                        "title": display_title,
                        "category": ev.get("category", "Other"),
                        "time": ev.get("time", ""),
                        "event": ev
                    })

                # Check reminder offsets
                for days_before in ev.get("reminders", []):
                    rem_date = occ_date - timedelta(days=days_before)
                    if base_date <= rem_date <= end_date:
                        desc = "Today" if days_before == 0 else f"{days_before}d before"
                        upcoming_items.append({
                            "type": "reminder",
                            "date": rem_date,
                            "days_left": (rem_date - base_date).days,
                            "title": f"Reminder ({desc}): {display_title}",
                            "category": ev.get("category", "Other"),
                            "time": ev.get("time", ""),
                            "event": ev
                        })

        upcoming_items.sort(key=lambda x: (x["date"], x["time"] or "00:00", x["type"]))
        return upcoming_items


# ==========================================
# EVENT DIALOG (ADD & EDIT)
# ==========================================

class EventDialog(tk.Toplevel):
    def __init__(self, parent, event_manager: EventManager, initial_date: date, event_to_edit=None):
        super().__init__(parent)
        self.parent = parent
        self.mgr = event_manager
        self.event_to_edit = event_to_edit
        self.initial_date = initial_date
        self.result = False

        self.title("Edit Event" if event_to_edit else "Add Event")
        self.geometry("450x600")
        self.minsize(420, 560)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.theme = THEMES[self.mgr.settings.get("theme", "light")]
        self.configure(bg=self.theme["bg"])

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        main_frame = tk.Frame(self, bg=self.theme["bg"], padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        # Title
        tk.Label(main_frame, text="Event Title:", font=("Arial", 10, "bold"),
                 bg=self.theme["bg"], fg=self.theme["fg"]).pack(anchor="w", pady=(0, 2))
        self.title_entry = tk.Entry(main_frame, font=("Arial", 11), relief="solid", bd=1)
        self.title_entry.pack(fill="x", pady=(0, 10))

        # Category
        tk.Label(main_frame, text="Category:", font=("Arial", 10, "bold"),
                 bg=self.theme["bg"], fg=self.theme["fg"]).pack(anchor="w", pady=(0, 2))
        self.cat_var = tk.StringVar(value="Personal")
        self.cat_combo = ttk.Combobox(main_frame, textvariable=self.cat_var,
                                      values=list(CATEGORIES.keys()), state="readonly")
        self.cat_combo.pack(fill="x", pady=(0, 10))
        self.cat_combo.bind("<<ComboboxSelected>>", self._on_category_changed)

        # Date Pickers
        tk.Label(main_frame, text="Original Date (YYYY-MM-DD):", font=("Arial", 10, "bold"),
                 bg=self.theme["bg"], fg=self.theme["fg"]).pack(anchor="w", pady=(0, 2))
        date_row = tk.Frame(main_frame, bg=self.theme["bg"])
        date_row.pack(fill="x", pady=(0, 10))

        self.year_var = tk.StringVar(value=str(self.initial_date.year))
        self.month_var = tk.StringVar(value=str(self.initial_date.month))
        self.day_var = tk.StringVar(value=str(self.initial_date.day))

        tk.Label(date_row, text="Y:", bg=self.theme["bg"], fg=self.theme["muted_fg"]).pack(side="left")
        self.year_spin = tk.Spinbox(date_row, from_=1, to=9999, textvariable=self.year_var, width=6)
        self.year_spin.pack(side="left", padx=(2, 10))

        tk.Label(date_row, text="M:", bg=self.theme["bg"], fg=self.theme["muted_fg"]).pack(side="left")
        self.month_spin = tk.Spinbox(date_row, from_=1, to=12, textvariable=self.month_var, width=4)
        self.month_spin.pack(side="left", padx=(2, 10))

        tk.Label(date_row, text="D:", bg=self.theme["bg"], fg=self.theme["muted_fg"]).pack(side="left")
        self.day_spin = tk.Spinbox(date_row, from_=1, to=31, textvariable=self.day_var, width=4)
        self.day_spin.pack(side="left", padx=(2, 0))

        # Time (Optional)
        tk.Label(main_frame, text="Time (Optional, HH:MM 24-hr):", font=("Arial", 10, "bold"),
                 bg=self.theme["bg"], fg=self.theme["fg"]).pack(anchor="w", pady=(0, 2))
        self.time_entry = tk.Entry(main_frame, font=("Arial", 10), relief="solid", bd=1)
        self.time_entry.pack(fill="x", pady=(0, 10))

        # Yearly Repeat Checkbox
        self.repeat_var = tk.BooleanVar(value=False)
        self.repeat_check = tk.Checkbutton(
            main_frame, text="Repeat every year", variable=self.repeat_var,
            font=("Arial", 10, "bold"), bg=self.theme["bg"], fg=self.theme["fg"],
            selectcolor=self.theme["card_bg"], activebackground=self.theme["bg"]
        )
        self.repeat_check.pack(anchor="w", pady=(0, 10))

        # Reminders
        rem_frame = tk.LabelFrame(main_frame, text="Reminders", font=("Arial", 10, "bold"),
                                  bg=self.theme["bg"], fg=self.theme["fg"], padx=10, pady=8)
        rem_frame.pack(fill="x", pady=(0, 10))

        self.rem_0_var = tk.BooleanVar(value=True)   # On day
        self.rem_1_var = tk.BooleanVar(value=False)  # 1 day before
        self.rem_7_var = tk.BooleanVar(value=False)  # 1 week before
        self.rem_30_var = tk.BooleanVar(value=False) # 1 month (30 days) before

        tk.Checkbutton(rem_frame, text="On the day", variable=self.rem_0_var,
                       bg=self.theme["bg"], fg=self.theme["fg"], selectcolor=self.theme["card_bg"]).grid(row=0, column=0, sticky="w")
        tk.Checkbutton(rem_frame, text="1 day before", variable=self.rem_1_var,
                       bg=self.theme["bg"], fg=self.theme["fg"], selectcolor=self.theme["card_bg"]).grid(row=0, column=1, sticky="w")
        tk.Checkbutton(rem_frame, text="1 week before", variable=self.rem_7_var,
                       bg=self.theme["bg"], fg=self.theme["fg"], selectcolor=self.theme["card_bg"]).grid(row=1, column=0, sticky="w")
        tk.Checkbutton(rem_frame, text="1 month before (30d)", variable=self.rem_30_var,
                       bg=self.theme["bg"], fg=self.theme["fg"], selectcolor=self.theme["card_bg"]).grid(row=1, column=1, sticky="w")

        custom_row = tk.Frame(rem_frame, bg=self.theme["bg"])
        custom_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))
        tk.Label(custom_row, text="Custom (days before):", bg=self.theme["bg"],
                 fg=self.theme["muted_fg"], font=("Arial", 9)).pack(side="left")
        self.custom_rem_entry = tk.Entry(custom_row, width=8, relief="solid", bd=1)
        self.custom_rem_entry.pack(side="left", padx=5)

        # Notes
        tk.Label(main_frame, text="Notes:", font=("Arial", 10, "bold"),
                 bg=self.theme["bg"], fg=self.theme["fg"]).pack(anchor="w", pady=(0, 2))
        self.notes_text = tk.Text(main_frame, height=4, font=("Arial", 10), relief="solid", bd=1)
        self.notes_text.pack(fill="both", expand=True, pady=(0, 15))

        # Buttons
        btn_bar = tk.Frame(main_frame, bg=self.theme["bg"])
        btn_bar.pack(fill="x")

        tk.Button(btn_bar, text="Cancel", command=self.destroy,
                  bg=self.theme["button_bg"], fg=self.theme["button_fg"],
                  relief="groove", padx=15).pack(side="right", padx=(5, 0))
        tk.Button(btn_bar, text="Save Event", command=self._save_event,
                  bg=self.theme["accent"], fg="#FFFFFF", font=("Arial", 10, "bold"),
                  relief="flat", padx=15).pack(side="right")

    def _on_category_changed(self, event=None):
        cat = self.cat_var.get()
        if cat in ["Anniversary", "Birthday"]:
            self.repeat_var.set(True)

    def _load_data(self):
        if self.event_to_edit:
            ev = self.event_to_edit
            self.title_entry.insert(0, ev.get("title", ""))
            self.cat_var.set(ev.get("category", "Personal"))

            y, m, d = ev["start_date"].split("-")
            self.year_var.set(str(int(y)))
            self.month_var.set(str(int(m)))
            self.day_var.set(str(int(d)))

            self.time_entry.insert(0, ev.get("time") or "")
            self.repeat_var.set(ev.get("repeat_yearly", False))
            self.notes_text.insert("1.0", ev.get("notes", ""))

            reminders = ev.get("reminders", [])
            self.rem_0_var.set(0 in reminders)
            self.rem_1_var.set(1 in reminders)
            self.rem_7_var.set(7 in reminders)
            self.rem_30_var.set(30 in reminders)

            custom_rems = [str(r) for r in reminders if r not in [0, 1, 7, 30]]
            if custom_rems:
                self.custom_rem_entry.insert(0, ", ".join(custom_rems))
        else:
            self._on_category_changed()

    def _save_event(self):
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Validation Error", "Please provide an event title.", parent=self)
            return

        try:
            y = int(self.year_var.get())
            m = int(self.month_var.get())
            d = int(self.day_var.get())
            if not (1 <= y <= 9999):
                raise ValueError("Year must be 1 to 9999.")
            # Verify date existence
            date(y, m, d)
        except ValueError as err:
            messagebox.showerror("Invalid Date", f"The date selected is invalid: {err}", parent=self)
            return

        time_val = self.time_entry.get().strip()
        if time_val:
            try:
                datetime.strptime(time_val, "%H:%M")
            except ValueError:
                messagebox.showerror("Invalid Time", "Time must be in HH:MM format (e.g. 14:30).", parent=self)
                return
        else:
            time_val = None

        reminders = []
        if self.rem_0_var.get(): reminders.append(0)
        if self.rem_1_var.get(): reminders.append(1)
        if self.rem_7_var.get(): reminders.append(7)
        if self.rem_30_var.get(): reminders.append(30)

        custom_str = self.custom_rem_entry.get().strip()
        if custom_str:
            for piece in custom_str.split(","):
                piece = piece.strip()
                if piece.isdigit():
                    reminders.append(int(piece))

        reminders = sorted(list(set(reminders)))

        event_payload = {
            "id": self.event_to_edit["id"] if self.event_to_edit else str(uuid.uuid4()),
            "title": title,
            "start_date": f"{y:04d}-{m:02d}-{d:02d}",
            "time": time_val,
            "notes": self.notes_text.get("1.0", "end-1c").strip(),
            "category": self.cat_var.get(),
            "repeat_yearly": self.repeat_var.get(),
            "reminders": reminders
        }

        if self.event_to_edit:
            self.mgr.update_event(event_payload)
        else:
            self.mgr.add_event(event_payload)

        self.result = True
        self.destroy()


# ==========================================
# JUMP TO DATE & SETTINGS DIALOGS
# ==========================================

class JumpDateDialog(tk.Toplevel):
    def __init__(self, parent, current_year: int, current_month: int, theme):
        super().__init__(parent)
        self.title("Jump to Date")
        self.geometry("300x180")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.theme = theme
        self.configure(bg=theme["bg"])
        self.selected_target = None

        tk.Label(self, text="Select Month & Year (1 - 9999):", font=("Arial", 10, "bold"),
                 bg=theme["bg"], fg=theme["fg"]).pack(pady=(15, 10))

        row = tk.Frame(self, bg=theme["bg"])
        row.pack(pady=5)

        self.month_var = tk.StringVar(value=calendar.month_name[current_month])
        self.month_combo = ttk.Combobox(row, textvariable=self.month_var,
                                        values=[calendar.month_name[i] for i in range(1, 13)],
                                        width=12, state="readonly")
        self.month_combo.pack(side="left", padx=5)

        self.year_var = tk.StringVar(value=str(current_year))
        self.year_spin = tk.Spinbox(row, from_=1, to=9999, textvariable=self.year_var, width=6)
        self.year_spin.pack(side="left", padx=5)

        btn_row = tk.Frame(self, bg=theme["bg"])
        btn_row.pack(pady=(15, 0))

        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=theme["button_bg"], fg=theme["button_fg"]).pack(side="right", padx=5)
        tk.Button(btn_row, text="Jump", command=self._confirm,
                  bg=theme["accent"], fg="#FFFFFF", font=("Arial", 9, "bold")).pack(side="right", padx=5)

    def _confirm(self):
        try:
            y = int(self.year_var.get())
            if not (1 <= y <= 9999):
                raise ValueError()
            m = list(calendar.month_name).index(self.month_var.get())
            self.selected_target = (y, m)
            self.destroy()
        except Exception:
            messagebox.showerror("Error", "Year must be an integer between 1 and 9999.", parent=self)


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, event_manager: EventManager, theme):
        super().__init__(parent)
        self.mgr = event_manager
        self.theme = theme
        self.title("Calendar Settings")
        self.geometry("380x220")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(bg=theme["bg"])
        self.changed = False

        main_frame = tk.Frame(self, bg=theme["bg"], padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text="Leap Year Rules", font=("Arial", 11, "bold"),
                 bg=theme["bg"], fg=theme["fg"]).pack(anchor="w", pady=(0, 5))

        tk.Label(main_frame, text="For February 29 events in non-leap years, observe on:",
                 font=("Arial", 9), bg=theme["bg"], fg=theme["muted_fg"]).pack(anchor="w", pady=(0, 5))

        self.rule_var = tk.StringVar(value=self.mgr.settings.get("feb29_rule", "Feb 28"))

        tk.Radiobutton(main_frame, text="February 28 (Traditional / Default)",
                       variable=self.rule_var, value="Feb 28", bg=theme["bg"],
                       fg=theme["fg"], selectcolor=theme["card_bg"]).pack(anchor="w", pady=2)

        tk.Radiobutton(main_frame, text="March 1 (Day after Feb 28)",
                       variable=self.rule_var, value="Mar 1", bg=theme["bg"],
                       fg=theme["fg"], selectcolor=theme["card_bg"]).pack(anchor="w", pady=2)

        btn_row = tk.Frame(main_frame, bg=theme["bg"])
        btn_row.pack(fill="x", pady=(20, 0))

        tk.Button(btn_row, text="Save Settings", command=self._save,
                  bg=theme["accent"], fg="#FFFFFF", font=("Arial", 9, "bold")).pack(side="right")
        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=theme["button_bg"], fg=theme["button_fg"]).pack(side="right", padx=5)

    def _save(self):
        self.mgr.settings["feb29_rule"] = self.rule_var.get()
        self.mgr.save_settings()
        self.changed = True
        self.destroy()


# ==========================================
# MAIN APPLICATION WINDOW
# ==========================================

class TimelessCalendarApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Timeless Calendar")
        self.geometry("1100x720")
        self.minsize(900, 600)

        self.mgr = EventManager()
        self.today = date.today()
        self.current_year = self.today.year
        self.current_month = self.today.month
        self.selected_date = self.today

        self.theme_name = self.mgr.settings.get("theme", "light")
        self.theme = THEMES[self.theme_name]

        self.view_mode = "month"  # 'month' or 'year'
        self.cell_widgets = {}
        self.notified_today = set()

        self._configure_window()
        self._build_menu_and_header()
        self._build_main_layout()
        self._bind_shortcuts()

        self.render_calendar()
        self.refresh_side_panel()

        # Check today's reminders on startup
        self.after(500, self.check_startup_reminders)
        # Background checking every minute
        self.after(60000, self.periodic_reminder_check)

    def _configure_window(self):
        self.configure(bg=self.theme["bg"])

    def _bind_shortcuts(self):
        self.bind("<Left>", lambda e: self.prev_month())
        self.bind("<Right>", lambda e: self.next_month())
        self.bind("<t>", lambda e: self.go_to_today())
        self.bind("<T>", lambda e: self.go_to_today())
        self.bind("<j>", lambda e: self.show_jump_dialog())
        self.bind("<J>", lambda e: self.show_jump_dialog())
        self.bind("<n>", lambda e: self.open_add_event_dialog())
        self.bind("<N>", lambda e: self.open_add_event_dialog())
        self.bind("<y>", lambda e: self.toggle_year_view())
        self.bind("<Y>", lambda e: self.toggle_year_view())

    # ---------------- UI BUILDERS ----------------

    def _build_menu_and_header(self):
        top_bar = tk.Frame(self, bg=self.theme["header_bg"], height=56, padx=15, pady=8)
        top_bar.pack(fill="x", side="top")

        # Left Controls: Navigation
        nav_frame = tk.Frame(top_bar, bg=self.theme["header_bg"])
        nav_frame.pack(side="left")

        self.prev_btn = tk.Button(nav_frame, text="◀", font=("Arial", 11, "bold"),
                                  command=self.prev_month, relief="flat", padx=8,
                                  bg=self.theme["button_bg"], fg=self.theme["button_fg"])
        self.prev_btn.pack(side="left", padx=2)

        self.next_btn = tk.Button(nav_frame, text="▶", font=("Arial", 11, "bold"),
                                  command=self.next_month, relief="flat", padx=8,
                                  bg=self.theme["button_bg"], fg=self.theme["button_fg"])
        self.next_btn.pack(side="left", padx=2)

        self.header_title = tk.Label(nav_frame, text="", font=("Arial", 14, "bold"),
                                     bg=self.theme["header_bg"], fg=self.theme["fg"], padx=10)
        self.header_title.pack(side="left")

        # Quick Actions
        self.today_btn = tk.Button(nav_frame, text="Today", font=("Arial", 9, "bold"),
                                   command=self.go_to_today, relief="groove",
                                   bg=self.theme["button_bg"], fg=self.theme["button_fg"], padx=8)
        self.today_btn.pack(side="left", padx=4)

        self.jump_btn = tk.Button(nav_frame, text="Jump...", font=("Arial", 9),
                                  command=self.show_jump_dialog, relief="groove",
                                  bg=self.theme["button_bg"], fg=self.theme["button_fg"], padx=8)
        self.jump_btn.pack(side="left", padx=4)

        self.year_view_btn = tk.Button(nav_frame, text="Year View", font=("Arial", 9),
                                       command=self.toggle_year_view, relief="groove",
                                       bg=self.theme["button_bg"], fg=self.theme["button_fg"], padx=8)
        self.year_view_btn.pack(side="left", padx=4)

        # Right Controls: Utilities & Theme
        util_frame = tk.Frame(top_bar, bg=self.theme["header_bg"])
        util_frame.pack(side="right")

        self.theme_btn = tk.Button(util_frame, text="🌙 Dark" if self.theme_name == "light" else "☀️ Light",
                                   font=("Arial", 9), command=self.toggle_theme, relief="groove",
                                   bg=self.theme["button_bg"], fg=self.theme["button_fg"], padx=8)
        self.theme_btn.pack(side="right", padx=3)

        self.settings_btn = tk.Button(util_frame, text="⚙ Settings", font=("Arial", 9),
                                      command=self.show_settings_dialog, relief="groove",
                                      bg=self.theme["button_bg"], fg=self.theme["button_fg"], padx=8)
        self.settings_btn.pack(side="right", padx=3)

        self.backup_btn = tk.Menubutton(util_frame, text="Backup ▾", relief="groove",
                                        font=("Arial", 9), bg=self.theme["button_bg"],
                                        fg=self.theme["button_fg"], padx=8)
        self.backup_menu = tk.Menu(self.backup_btn, tearoff=0)
        self.backup_menu.add_command(label="Export Events JSON...", command=self.export_events)
        self.backup_menu.add_command(label="Import Events JSON...", command=self.import_events)
        self.backup_btn["menu"] = self.backup_menu
        self.backup_btn.pack(side="right", padx=3)

    def _build_main_layout(self):
        self.main_container = tk.Frame(self, bg=self.theme["bg"])
        self.main_container.pack(fill="both", expand=True, padx=12, pady=10)

        # Left: Calendar Grid Frame
        self.cal_frame = tk.Frame(self.main_container, bg=self.theme["bg"])
        self.cal_frame.pack(side="left", fill="both", expand=True)

        # Right: Side Panel (Selected Date + Upcoming Tabs)
        self.side_frame = tk.Frame(self.main_container, bg=self.theme["card_bg"],
                                   relief="solid", bd=1, width=320)
        self.side_frame.pack(side="right", fill="both", padx=(10, 0))
        self.side_frame.pack_propagate(False)

        self._build_side_panel()

    def _build_side_panel(self):
        # Clean custom notebook style
        self.notebook = ttk.Notebook(self.side_frame)
        self.notebook.pack(fill="both", expand=True)

        # Tab 1: Day Details
        self.tab_day = tk.Frame(self.notebook, bg=self.theme["card_bg"], padx=10, pady=10)
        self.notebook.add(self.tab_day, text="Day Events")

        self.day_header_lbl = tk.Label(self.tab_day, text="", font=("Arial", 11, "bold"),
                                       bg=self.theme["card_bg"], fg=self.theme["fg"])
        self.day_header_lbl.pack(anchor="w", pady=(0, 6))

        self.add_event_btn = tk.Button(self.tab_day, text="+ New Event for Day",
                                       command=self.open_add_event_dialog, bg=self.theme["accent"],
                                       fg="#FFFFFF", relief="flat", font=("Arial", 9, "bold"), pady=4)
        self.add_event_btn.pack(fill="x", pady=(0, 10))

        # Scrollable events list for selected day
        self.day_canvas = tk.Canvas(self.tab_day, bg=self.theme["card_bg"], highlightthickness=0)
        self.day_scroll = ttk.Scrollbar(self.tab_day, orient="vertical", command=self.day_canvas.yview)
        self.day_list_frame = tk.Frame(self.day_canvas, bg=self.theme["card_bg"])

        self.day_list_frame.bind("<Configure>", lambda e: self.day_canvas.configure(
            scrollregion=self.day_canvas.bbox("all")))
        self.day_canvas.create_window((0, 0), window=self.day_list_frame, anchor="nw", width=290)
        self.day_canvas.configure(yscrollcommand=self.day_scroll.set)

        self.day_canvas.pack(side="left", fill="both", expand=True)
        self.day_scroll.pack(side="right", fill="y")

        # Tab 2: Upcoming 30 Days
        self.tab_upcoming = tk.Frame(self.notebook, bg=self.theme["card_bg"], padx=10, pady=10)
        self.notebook.add(self.tab_upcoming, text="Upcoming (30d)")

        self.up_canvas = tk.Canvas(self.tab_upcoming, bg=self.theme["card_bg"], highlightthickness=0)
        self.up_scroll = ttk.Scrollbar(self.tab_upcoming, orient="vertical", command=self.up_canvas.yview)
        self.up_list_frame = tk.Frame(self.up_canvas, bg=self.theme["card_bg"])

        self.up_list_frame.bind("<Configure>", lambda e: self.up_canvas.configure(
            scrollregion=self.up_canvas.bbox("all")))
        self.up_canvas.create_window((0, 0), window=self.up_list_frame, anchor="nw", width=290)
        self.up_canvas.configure(yscrollcommand=self.up_scroll.set)

        self.up_canvas.pack(side="left", fill="both", expand=True)
        self.up_scroll.pack(side="right", fill="y")

    # ---------------- RENDER ENGINES ----------------

    def render_calendar(self):
        """Dispatches rendering according to view mode."""
        for widget in self.cal_frame.winfo_children():
            widget.destroy()

        if self.view_mode == "month":
            self._render_month_grid()
        else:
            self._render_year_grid()

    def _render_month_grid(self):
        self.header_title.config(text=f"{calendar.month_name[self.current_month]} {self.current_year}")

        # Weekday headers (Monday to Sunday)
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        headers_frame = tk.Frame(self.cal_frame, bg=self.theme["bg"])
        headers_frame.pack(fill="x", pady=(0, 4))
        for col, day_name in enumerate(weekdays):
            headers_frame.grid_columnconfigure(col, weight=1, uniform="cal_col")
            lbl = tk.Label(headers_frame, text=day_name, font=("Arial", 10, "bold"),
                           bg=self.theme["bg"], fg=self.theme["muted_fg"], pady=4)
            lbl.grid(row=0, column=col, sticky="nsew")

        # Days grid
        grid_container = tk.Frame(self.cal_frame, bg=self.theme["border"])
        grid_container.pack(fill="both", expand=True)

        for col in range(7):
            grid_container.grid_columnconfigure(col, weight=1, uniform="cal_col")
        for row in range(6):
            grid_container.grid_rowconfigure(row, weight=1, uniform="cal_row")

        month_events = self.mgr.get_events_for_month(self.current_year, self.current_month)
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(self.current_year, self.current_month)

        self.cell_widgets.clear()

        for row_idx, week in enumerate(month_days):
            for col_idx, day_num in enumerate(week):
                if day_num == 0:
                    # Inactive cell outside current month
                    empty_cell = tk.Frame(grid_container, bg=self.theme["bg"])
                    empty_cell.grid(row=row_idx, column=col_idx, sticky="nsew", padx=1, pady=1)
                    continue

                cell_date = date(self.current_year, self.current_month, day_num)
                is_today = (cell_date == self.today)
                is_selected = (cell_date == self.selected_date)

                bg_col = self.theme["card_bg"]
                if is_selected:
                    bg_col = self.theme["selected"]
                elif is_today:
                    bg_col = self.theme["today_highlight"]

                cell = tk.Frame(grid_container, bg=bg_col, relief="flat", cursor="hand2")
                cell.grid(row=row_idx, column=col_idx, sticky="nsew", padx=1, pady=1)

                # Day number label
                fg_col = self.theme["today_fg"] if is_today else self.theme["fg"]
                font_weight = "bold" if (is_today or is_selected) else "normal"
                lbl_day = tk.Label(cell, text=str(day_num), font=("Arial", 10, font_weight),
                                   bg=bg_col, fg=fg_col)
                lbl_day.pack(anchor="nw", padx=4, pady=2)

                # Event markers container
                markers_box = tk.Frame(cell, bg=bg_col)
                markers_box.pack(fill="both", expand=True, padx=4, pady=(0, 2))

                day_ev_list = month_events.get(day_num, [])
                for idx, ev_item in enumerate(day_ev_list[:3]):
                    cat = ev_item["event"].get("category", "Other")
                    dot_color = CATEGORIES.get(cat, "#888888")
                    pill = tk.Frame(markers_box, bg=dot_color, height=6)
                    pill.pack(fill="x", pady=1)

                if len(day_ev_list) > 3:
                    more_lbl = tk.Label(markers_box, text=f"+{len(day_ev_list) - 3} more",
                                        font=("Arial", 7), bg=bg_col, fg=self.theme["muted_fg"])
                    more_lbl.pack(anchor="e")

                # Bind click events
                for w in (cell, lbl_day, markers_box):
                    w.bind("<Button-1>", lambda e, d=cell_date: self.select_date(d))
                    w.bind("<Double-Button-1>", lambda e, d=cell_date: self.on_cell_double_click(d))

                self.cell_widgets[cell_date] = cell

    def _render_year_grid(self):
        """Displays a 3x4 grid of months for fast navigation."""
        self.header_title.config(text=f"Year {self.current_year}")

        year_frame = tk.Frame(self.cal_frame, bg=self.theme["bg"])
        year_frame.pack(fill="both", expand=True)

        for col in range(4):
            year_frame.grid_columnconfigure(col, weight=1, uniform="yr_col")
        for row in range(3):
            year_frame.grid_rowconfigure(row, weight=1, uniform="yr_row")

        for month_idx in range(1, 13):
            r = (month_idx - 1) // 4
            c = (month_idx - 1) % 4

            card = tk.Frame(year_frame, bg=self.theme["card_bg"], relief="solid", bd=1, cursor="hand2")
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")

            lbl_m = tk.Label(card, text=calendar.month_name[month_idx], font=("Arial", 11, "bold"),
                             bg=self.theme["card_bg"], fg=self.theme["fg"])
            lbl_m.pack(pady=(6, 2))

            # Mini preview: count of events in this month
            month_evs = self.mgr.get_events_for_month(self.current_year, month_idx)
            count = sum(len(items) for items in month_evs.values())
            lbl_count = tk.Label(card, text=f"{count} events" if count else "No events",
                                 font=("Arial", 9), bg=self.theme["card_bg"],
                                 fg=self.theme["muted_fg"] if count == 0 else self.theme["accent"])
            lbl_count.pack()

            # Click on card navigates into month view
            card.bind("<Button-1>", lambda e, m=month_idx: self.open_month_from_year(m))
            lbl_m.bind("<Button-1>", lambda e, m=month_idx: self.open_month_from_year(m))
            lbl_count.bind("<Button-1>", lambda e, m=month_idx: self.open_month_from_year(m))

    # ---------------- ACTIONS & NAVIGATION ----------------

    def select_date(self, new_date: date):
        self.selected_date = new_date
        self.render_calendar()
        self.refresh_side_panel()

    def on_cell_double_click(self, target_date: date):
        self.selected_date = target_date
        self.open_add_event_dialog()

    def prev_month(self):
        if self.view_mode == "year":
            if self.current_year > 1:
                self.current_year -= 1
                self.render_calendar()
            return

        if self.current_month == 1:
            if self.current_year > 1:
                self.current_year -= 1
                self.current_month = 12
        else:
            self.current_month -= 1
        self.render_calendar()

    def next_month(self):
        if self.view_mode == "year":
            if self.current_year < 9999:
                self.current_year += 1
                self.render_calendar()
            return

        if self.current_month == 12:
            if self.current_year < 9999:
                self.current_year += 1
                self.current_month = 1
        else:
            self.current_month += 1
        self.render_calendar()

    def go_to_today(self):
        self.today = date.today()
        self.current_year = self.today.year
        self.current_month = self.today.month
        self.selected_date = self.today
        self.view_mode = "month"
        self.year_view_btn.config(text="Year View")
        self.render_calendar()
        self.refresh_side_panel()

    def toggle_year_view(self):
        if self.view_mode == "month":
            self.view_mode = "year"
            self.year_view_btn.config(text="Month View")
        else:
            self.view_mode = "month"
            self.year_view_btn.config(text="Year View")
        self.render_calendar()

    def open_month_from_year(self, month: int):
        self.current_month = month
        self.view_mode = "month"
        self.year_view_btn.config(text="Year View")
        self.render_calendar()

    def show_jump_dialog(self):
        dlg = JumpDateDialog(self, self.current_year, self.current_month, self.theme)
        self.wait_window(dlg)
        if dlg.selected_target:
            self.current_year, self.current_month = dlg.selected_target
            self.selected_date = date(self.current_year, self.current_month, 1)
            self.view_mode = "month"
            self.year_view_btn.config(text="Year View")
            self.render_calendar()
            self.refresh_side_panel()

    def show_settings_dialog(self):
        dlg = SettingsDialog(self, self.mgr, self.theme)
        self.wait_window(dlg)
        if dlg.changed:
            self.render_calendar()
            self.refresh_side_panel()

    def open_add_event_dialog(self):
        dlg = EventDialog(self, self.mgr, initial_date=self.selected_date)
        self.wait_window(dlg)
        if dlg.result:
            self.render_calendar()
            self.refresh_side_panel()

    def open_edit_event_dialog(self, event_dict: dict):
        dlg = EventDialog(self, self.mgr, initial_date=self.selected_date, event_to_edit=event_dict)
        self.wait_window(dlg)
        if dlg.result:
            self.render_calendar()
            self.refresh_side_panel()

    def delete_event(self, event_id: str):
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this event?", parent=self):
            self.mgr.delete_event(event_id)
            self.render_calendar()
            self.refresh_side_panel()

    # ---------------- SIDE PANEL REFRESH ----------------

    def refresh_side_panel(self):
        # 1. Update Selected Day Tab
        date_str = self.selected_date.strftime("%A, %b %d, %Y")
        self.day_header_lbl.config(text=date_str)

        for widget in self.day_list_frame.winfo_children():
            widget.destroy()

        day_items = self.mgr.get_events_for_date(self.selected_date)
        if not day_items:
            empty_lbl = tk.Label(self.day_list_frame, text="No events on this day.",
                                 font=("Arial", 9, "italic"), bg=self.theme["card_bg"],
                                 fg=self.theme["muted_fg"], pady=20)
            empty_lbl.pack()
        else:
            for item in day_items:
                ev = item["event"]
                card = tk.Frame(self.day_list_frame, bg=self.theme["bg"], relief="solid", bd=1, padx=8, pady=6)
                card.pack(fill="x", pady=4)

                cat_color = CATEGORIES.get(ev.get("category"), "#888888")
                top_row = tk.Frame(card, bg=self.theme["bg"])
                top_row.pack(fill="x")

                cat_tag = tk.Label(top_row, text=ev.get("category", "Other"), font=("Arial", 7, "bold"),
                                   bg=cat_color, fg="#FFFFFF", padx=4, pady=1)
                cat_tag.pack(side="left")

                if ev.get("time"):
                    time_lbl = tk.Label(top_row, text=ev["time"], font=("Arial", 8, "bold"),
                                        bg=self.theme["bg"], fg=self.theme["fg"])
                    time_lbl.pack(side="left", padx=5)

                title_lbl = tk.Label(card, text=item["display_title"], font=("Arial", 10, "bold"),
                                     bg=self.theme["bg"], fg=self.theme["fg"], wraplength=250, justify="left")
                title_lbl.pack(anchor="w", pady=(3, 2))

                if ev.get("notes"):
                    notes_lbl = tk.Label(card, text=ev["notes"], font=("Arial", 8),
                                         bg=self.theme["bg"], fg=self.theme["muted_fg"], wraplength=250, justify="left")
                    notes_lbl.pack(anchor="w", pady=(0, 4))

                btn_row = tk.Frame(card, bg=self.theme["bg"])
                btn_row.pack(fill="x", pady=(2, 0))

                edit_btn = tk.Button(btn_row, text="Edit", font=("Arial", 8),
                                     command=lambda e=ev: self.open_edit_event_dialog(e),
                                     bg=self.theme["button_bg"], fg=self.theme["button_fg"], relief="groove")
                edit_btn.pack(side="right", padx=2)

                del_btn = tk.Button(btn_row, text="Delete", font=("Arial", 8),
                                    command=lambda eid=ev["id"]: self.delete_event(eid),
                                    bg=self.theme["button_bg"], fg="#D32F2F", relief="groove")
                del_btn.pack(side="right", padx=2)

        # 2. Update Upcoming (30 Days) Tab
        for widget in self.up_list_frame.winfo_children():
            widget.destroy()

        upcoming_items = self.mgr.get_upcoming(self.today, days_ahead=30)
        if not upcoming_items:
            empty_up = tk.Label(self.up_list_frame, text="No events in the next 30 days.",
                                font=("Arial", 9, "italic"), bg=self.theme["card_bg"],
                                fg=self.theme["muted_fg"], pady=20)
            empty_up.pack()
        else:
            for item in upcoming_items:
                card = tk.Frame(self.up_list_frame, bg=self.theme["bg"], relief="solid", bd=1, padx=6, pady=4)
                card.pack(fill="x", pady=3)

                days_left = item["days_left"]
                when_text = "Today" if days_left == 0 else ("Tomorrow" if days_left == 1 else f"In {days_left} days")
                badge_color = "#D32F2F" if days_left <= 1 else self.theme["accent"]

                header_r = tk.Frame(card, bg=self.theme["bg"])
                header_r.pack(fill="x")

                lbl_badge = tk.Label(header_r, text=when_text, font=("Arial", 7, "bold"),
                                     bg=badge_color, fg="#FFFFFF", padx=4)
                lbl_badge.pack(side="left")

                lbl_d = tk.Label(header_r, text=item["date"].strftime("%b %d"), font=("Arial", 8),
                                 bg=self.theme["bg"], fg=self.theme["muted_fg"])
                lbl_d.pack(side="left", padx=4)

                lbl_title = tk.Label(card, text=item["title"], font=("Arial", 9, "bold"),
                                     bg=self.theme["bg"], fg=self.theme["fg"], wraplength=250, justify="left")
                lbl_title.pack(anchor="w", pady=(2, 0))

    # ---------------- THEME & BACKUP ----------------

    def toggle_theme(self):
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.theme = THEMES[self.theme_name]
        self.mgr.settings["theme"] = self.theme_name
        self.mgr.save_settings()

        # Update root & controls
        self.configure(bg=self.theme["bg"])
        self.theme_btn.config(text="🌙 Dark" if self.theme_name == "light" else "☀️ Light")
        self.render_calendar()
        self.refresh_side_panel()

    def export_events(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
            initialfile="events_backup.json",
            title="Export Events"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.mgr.events, f, indent=2)
                messagebox.showinfo("Export Successful", f"Saved {len(self.mgr.events)} events to backup.", parent=self)
            except Exception as e:
                messagebox.showerror("Export Failed", f"Could not write file: {e}", parent=self)

    def import_events(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json")],
            title="Import Events Backup"
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    imported_data = json.load(f)
                if not isinstance(imported_data, list):
                    raise ValueError("JSON file must contain an array of events.")

                # Validate structure
                count = 0
                for item in imported_data:
                    if "title" in item and "start_date" in item:
                        if "id" not in item:
                            item["id"] = str(uuid.uuid4())
                        self.mgr.events.append(item)
                        count += 1
                self.mgr.save_events()
                self.render_calendar()
                self.refresh_side_panel()
                messagebox.showinfo("Import Complete", f"Successfully imported {count} events.", parent=self)
            except Exception as e:
                messagebox.showerror("Import Failed", f"Invalid events JSON file: {e}", parent=self)

    # ---------------- NOTIFICATIONS & REMINDERS ----------------

    def notify(self, title: str, message: str):
        """Dispatches notification via plyer if available; otherwise displays Tkinter popup."""
        if PLYER_AVAILABLE:
            try:
                plyer_notification.notify(
                    title=title,
                    message=message,
                    app_name="Timeless Calendar",
                    timeout=10
                )
                return
            except Exception:
                pass
        # Fallback dialog
        messagebox.showinfo(title, message, parent=self)

    def check_startup_reminders(self):
        """Displays a summary popup of events due today upon app launch."""
        today_events = self.mgr.get_events_for_date(self.today)
        if today_events:
            summary = "\n".join([f"• {item['display_title']} ({item['event'].get('time') or 'All day'})"
                                 for item in today_events])
            self.notify("Today's Agenda", f"You have {len(today_events)} event(s) today:\n\n{summary}")

    def periodic_reminder_check(self):
        """Checks every 60 seconds for timed events matching the current minute."""
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        today_events = self.mgr.get_events_for_date(now.date())

        for item in today_events:
            ev = item["event"]
            ev_time = ev.get("time")
            if ev_time == current_time_str:
                unique_key = f"{ev['id']}_{now.date()}_{ev_time}"
                if unique_key not in self.notified_today:
                    self.notified_today.add(unique_key)
                    self.notify("Event Reminder", f"{item['display_title']}\nTime: {ev_time}")

        # Schedule next iteration in 60 seconds
        self.after(60000, self.periodic_reminder_check)


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    app = TimelessCalendarApp()
    app.mainloop()