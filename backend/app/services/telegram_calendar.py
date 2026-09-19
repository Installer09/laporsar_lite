
from datetime import datetime, timedelta, timezone

MONTH_NAMES_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

MONTH_NAMES_SHORT = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
    7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"
}

WEEKDAYS_ID = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
WEEKDAYS_FULL = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

def get_wib_now() -> datetime:
    """Get current time in WIB (UTC+7)."""
    tz = timezone(timedelta(hours=7))
    return datetime.now(tz)

def generate_7_days(start_dt: datetime = None) -> list[tuple[str, str]]:
    """
    Generate 7 days starting from start_dt (or WIB now) going backwards.
    Returns list of tuples: (button_label, YYYY-MM-DD)
    """
    if not start_dt:
        start_dt = get_wib_now()
        
    wib_now = get_wib_now()
    results = []
    
    for i in range(7):
        dt = start_dt - timedelta(days=i)
        date_str = dt.strftime("%Y-%m-%d")
        
        # Check if it corresponds to today or yesterday relative to real WIB now
        diff_days = (wib_now.date() - dt.date()).days
        
        if diff_days == 0:
            label = f"Hari Ini ({dt.day} {MONTH_NAMES_SHORT[dt.month]})"
        elif diff_days == 1:
            label = f"Kemarin ({dt.day} {MONTH_NAMES_SHORT[dt.month]})"
        else:
            day_name = WEEKDAYS_ID[dt.weekday()]
            label = f"{day_name}, {dt.day} {MONTH_NAMES_SHORT[dt.month]}"
            
        results.append((label, date_str))
    return results

def create_calendar(start_date_str: str = None) -> list:
    """
    Create Telegram inline keyboard markup for a 7-day compact window.
    Layout: 4 buttons in row 1, 3 buttons in row 2, and navigation controls in row 3.
    """
    if start_date_str:
        try:
            # Parse only YYYY-MM-DD
            start_dt = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
        except Exception:
            start_dt = get_wib_now()
    else:
        start_dt = get_wib_now()
        
    days = generate_7_days(start_dt)
    markup = []
    
    # Row 1: First 4 days
    row1 = [{"text": label, "callback_data": f"calendar_date:{date_str}"} for label, date_str in days[:4]]
    # Row 2: Remaining 3 days
    row2 = [{"text": label, "callback_data": f"calendar_date:{date_str}"} for label, date_str in days[4:]]
    
    markup.append(row1)
    markup.append(row2)
    
    # Navigation controls
    latest_dt = start_dt
    oldest_dt = start_dt - timedelta(days=6)
    
    prev_week_start = oldest_dt - timedelta(days=1)
    next_week_start = latest_dt + timedelta(days=7)
    
    prev_str = prev_week_start.strftime("%Y-%m-%d")
    next_str = next_week_start.strftime("%Y-%m-%d")
    
    # Prevent scrolling to the future beyond today
    wib_now = get_wib_now()
    has_future = next_week_start.date() > wib_now.date()
    
    nav_row = [
        {"text": "⬅️ Minggu Lalu", "callback_data": f"calendar_week_prev:{prev_str}"},
        {"text": "❌ Batal", "callback_data": "calendar_cancel"}
    ]
    if not has_future:
        nav_row.append({"text": "Minggu Depan ➡️", "callback_data": f"calendar_week_next:{next_str}"})
    else:
        # If it hits today, we disable the future navigation button to keep it clean
        nav_row.append({"text": "⏹️", "callback_data": "calendar_ignore"})
        
    markup.append(nav_row)
    return markup
