"""Localization utilities for Spanish translation."""

DAYS = {
    "Monday": "lunes",
    "Tuesday": "martes",
    "Wednesday": "miércoles",
    "Thursday": "jueves",
    "Friday": "viernes",
    "Saturday": "sábado",
    "Sunday": "domingo",
}

DAYS_SHORT = {
    "Mon": "lun",
    "Tue": "mar",
    "Wed": "mié",
    "Thu": "jue",
    "Fri": "vie",
    "Sat": "sáb",
    "Sun": "dom",
}

MONTHS = {
    "January": "enero",
    "February": "febrero",
    "March": "marzo",
    "April": "abril",
    "May": "mayo",
    "June": "junio",
    "July": "julio",
    "August": "agosto",
    "September": "septiembre",
    "October": "octubre",
    "November": "noviembre",
    "December": "diciembre",
}

MONTHS_SHORT = {
    "Jan": "ene",
    "Feb": "feb",
    "Mar": "mar",
    "Apr": "abr",
    "May": "may",
    "Jun": "jun",
    "Jul": "jul",
    "Aug": "ago",
    "Sep": "sep",
    "Oct": "oct",
    "Nov": "nov",
    "Dec": "dic",
}

RELATIVE = {
    "today": "hoy",
    "tonight": "esta noche",
    "tomorrow": "mañana",
    "Today": "Hoy",
    "Tonight": "Esta noche",
    "Tomorrow": "Mañana",
}

OUTCOME = {
    "win": "victoria",
    "loss": "derrota",
    "tie": "empate",
    "defeated": "venció a",
    "lost to": "perdió contra",
    "tied": "empató con",
    "in overtime": "en la prórroga",
    "OT": "PR",
}

def translate_date(date_str: str) -> str:
    """Translates day and month names in a formatted date string."""
    result = date_str
    # Replace full names first, then short names
    for eng, esp in DAYS.items():
        result = result.replace(eng, esp.capitalize() if eng in date_str.split(",")[0] else esp)
    for eng, esp in MONTHS.items():
        result = result.replace(eng, esp)
    for eng, esp in DAYS_SHORT.items():
        result = result.replace(eng, esp)
    for eng, esp in MONTHS_SHORT.items():
        result = result.replace(eng, esp)
    return result

def t(key: str, default: str | None = None) -> str:
    """Translate a single term."""
    return RELATIVE.get(key, OUTCOME.get(key, default or key))
