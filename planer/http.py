"""Höflicher Abruf: eigener User-Agent, Pause je Host, robots.txt, optionaler Datei-Cache.

Alle Plugins holen ihre Seiten nur hierüber. Tests ersetzen das Objekt durch eine Attrappe
mit derselben Methode `text(url)`.
"""
from __future__ import annotations

import hashlib
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlsplit

import requests

USER_AGENT = "Calavera-Planungskalender/1.0 (+https://www.calavera.club)"


class AbrufFehler(Exception):
    pass


class Http:
    def __init__(self, pause: float = 1.0, cache_ordner: Path | None = None,
                 cache_minuten: float = 0, timeout: float = 25) -> None:
        self.pause = pause
        self.cache_ordner = cache_ordner
        self.cache_minuten = cache_minuten
        self.timeout = timeout
        self.sitzung = requests.Session()
        self.sitzung.headers["User-Agent"] = USER_AGENT
        self.sitzung.headers["Accept-Language"] = "de-DE,de;q=0.9"
        self._letzter: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.abrufe = 0

    # --- robots.txt --------------------------------------------------------------------------
    def _erlaubt(self, url: str) -> bool:
        teile = urlsplit(url)
        host = f"{teile.scheme}://{teile.netloc}"
        if teile.netloc.endswith("docs.google.com"):
            return True  # Google-Export-Links sind keine Crawl-Ziele im Sinne von robots.txt
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.sitzung.get(host + "/robots.txt", timeout=self.timeout)
                if r.status_code >= 400:
                    rp = None  # keine robots.txt → alles erlaubt
                else:
                    rp.parse(r.text.splitlines())
            except requests.RequestException:
                rp = None
            self._robots[host] = rp
        rp = self._robots[host]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    # --- Cache --------------------------------------------------------------------------------
    def _cache_datei(self, url: str) -> Path | None:
        if not self.cache_ordner or self.cache_minuten <= 0:
            return None
        return self.cache_ordner / (hashlib.sha1(url.encode()).hexdigest() + ".txt")

    # --- Abruf --------------------------------------------------------------------------------
    def text(self, url: str) -> str:
        datei = self._cache_datei(url)
        if datei and datei.exists() and time.time() - datei.stat().st_mtime < self.cache_minuten * 60:
            return datei.read_text(encoding="utf-8")

        if not self._erlaubt(url):
            raise AbrufFehler(f"robots.txt verbietet {url}")

        host = urlsplit(url).netloc
        warten = self._letzter.get(host, 0) + self.pause - time.time()
        if warten > 0:
            time.sleep(warten)
        try:
            r = self.sitzung.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            raise AbrufFehler(f"{url}: {e}") from e
        finally:
            self._letzter[host] = time.time()
        self.abrufe += 1
        if r.status_code >= 400:
            raise AbrufFehler(f"{url}: HTTP {r.status_code}")
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding or "utf-8"
        text = r.text
        if datei:
            datei.parent.mkdir(parents=True, exist_ok=True)
            datei.write_text(text, encoding="utf-8")
        return text
