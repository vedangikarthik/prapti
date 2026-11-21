"""Build a small .ics calendar file for a scheme deadline (with reminders)."""
from __future__ import annotations

from datetime import date, datetime, timezone


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_ics(scheme: dict) -> str | None:
    if not scheme.get("deadline"):
        return None
    d = date.fromisoformat(scheme["deadline"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    title = _escape(f"Last date: {scheme['name_en']}")
    desc = _escape(f"Apply on {scheme.get('source_name', '')}: {scheme.get('source_url', '')}\n"
                   f"{scheme.get('deadline_note', '')}\nFrom Arhata. Never pay anyone to apply for you.")
    alarms = "".join(
        f"BEGIN:VALARM\r\nACTION:DISPLAY\r\nDESCRIPTION:{title}\r\nTRIGGER:-P{n}D\r\nEND:VALARM\r\n"
        for n in (14, 7, 3, 1)
    )
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Arhata//Claim what's yours//EN\r\nCALSCALE:GREGORIAN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{scheme['id']}-{d.isoformat()}@arhata\r\n"
        f"DTSTAMP:{stamp}\r\n"
        f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}\r\n"
        f"SUMMARY:{title}\r\n"
        f"DESCRIPTION:{desc}\r\n"
        f"URL:{scheme.get('source_url', '')}\r\n"
        f"{alarms}"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
