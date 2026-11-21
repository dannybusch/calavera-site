"""Gemeinsame Datenklasse für alle Quellen und die Abend-Zuordnung."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")

# Bis zu dieser Uhrzeit zählt ein Beginn noch zum Abend davor (Sa 01:00 → Freitagabend).
ABEND_GRENZE = time(6, 0)

WOCHENTAG_KURZ = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


@dataclass
class Termin:
    quelle: str                    # Plugin-ID, z. B. "modernes"
    titel: str
    tag: date                      # Kalendertag laut Quelle
    beginn: datetime | None = None  # mit Zeitzone; None = Uhrzeit unbekannt
    ende: datetime | None = None
    ort: str = ""                  # "Modernes", "Polyester" – beim Dark-Kalender leer
    stadt: str = ""
    url: str | None = None
    kategorien: list[str] = field(default_factory=list)
    uid: str = ""                  # stabil je Quelle (Quellen-UID oder URL)
    hinweis: str = ""              # z. B. "= Modernes" beim Dark-Kalender
    artverwandt: bool = False

    @property
    def abend(self) -> date:
        """Der Abend, zu dem der Termin gehört: Beginn nach Mitternacht zählt zum Vortag."""
        if self.beginn is not None:
            b = self.beginn.astimezone(TZ)
            if b.time() < ABEND_GRENZE:
                return b.date() - timedelta(days=1)
            return b.date()
        return self.tag

    @property
    def uhrzeit(self) -> str:
        if self.beginn is None:
            return ""
        return self.beginn.astimezone(TZ).strftime("%H:%M")


def ist_fr_sa(d: date) -> bool:
    return d.weekday() in (4, 5)


def zu_datetime(tag: date, hh: int, mm: int) -> datetime:
    return datetime(tag.year, tag.month, tag.day, hh, mm, tzinfo=TZ)
