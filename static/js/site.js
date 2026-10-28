/* Calavera Bremen – kleines Script für die statische Seite
 *
 *  1. Menü-Button auf dem Handy
 *  2. Programm: vergangene Termine ausblenden, den nächsten groß hervorheben
 *     (der Build macht das schon – hier wird es nachgezogen, falls der letzte
 *     Build ein paar Stunden alt ist)
 *  3. Teilen-Knopf auf Veranstaltungsseiten
 *  4. Kellerfunk: liest die config.yml von live.calavera.club und zeigt, ob gerade
 *     gesendet wird – mit derselben Logik wie live.calavera.club (site.live: auto|an|aus,
 *     Sendungen ohne end laufen 6 Stunden). Auf jeder Seite: schmales Band oben, wenn live
 *     (oder dezent mit Countdown, wenn eine Sendung in weniger als 60 Minuten beginnt).
 *  Startseite: die Veranstaltung des Tages übernimmt ab ein paar Stunden vor Beginn den Claim.
 *
 *  Testen:  ?now=2026-10-23T23:00  tut so, als wäre es diese Bremer Uhrzeit (die Uhr läuft von dort weiter).
 */
(function () {
  "use strict";

  var TZ = "Europe/Berlin";
  var WD = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

  /* ---------- Zeit ---------- */
  function tzOffset(ms) {
    var parts = new Intl.DateTimeFormat("en-US", {
      timeZone: TZ, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit"
    }).formatToParts(new Date(ms));
    var p = {};
    parts.forEach(function (x) { p[x.type] = x.value; });
    return Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour % 24, +p.minute, +p.second) - Math.floor(ms / 1000) * 1000;
  }
  /* "2026-10-23 22:00" als Bremer Ortszeit → Date */
  function bremen(value) {
    if (value instanceof Date) {           // js-yaml liest Zeitstempel mit Sekunden als UTC – als Ortszeit deuten
      value = value.toISOString().slice(0, 16).replace("T", " ");
    }
    var m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2})[:.](\d{2})/.exec(String(value || "").trim());
    if (!m) return null;
    var guess = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
    var t = guess - tzOffset(guess);
    t = guess - tzOffset(t);               // zweiter Durchgang für Sommer-/Winterzeit-Wechsel
    return new Date(t);
  }
  function bremenParts(d) {
    var parts = new Intl.DateTimeFormat("de-DE", {
      timeZone: TZ, weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23"
    }).formatToParts(d);
    var p = {};
    parts.forEach(function (x) { p[x.type] = x.value; });
    return p;
  }
  function dayKey(d) { var p = bremenParts(d); return p.day + "." + p.month; }
  function fmtShort(d) {           // "Sa 31.10. · 22:00"
    var p = bremenParts(d);
    return p.weekday.replace(".", "") + " " + p.day + "." + p.month + ". · " + p.hour + ":" + p.minute;
  }
  function fmtTime(d) { var p = bremenParts(d); return p.hour + ":" + p.minute; }

  var nowParam = new URLSearchParams(location.search).get("now");
  var fixedNow = nowParam ? bremen(nowParam) : null;
  var loadedAt = Date.now();
  function now() { return fixedNow ? new Date(fixedNow.getTime() + Date.now() - loadedAt) : new Date(); }
  function countdown(ms) {         // 2:14:05 bzw. 42:10
    var s = Math.max(0, Math.floor(ms / 1000)), h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
    var mm = (h ? String(m).padStart(2, "0") : String(m)) + ":" + String(sec).padStart(2, "0");
    return h ? h + ":" + mm : mm;
  }

  /* ---------- 1. Menü ---------- */
  var toggle = document.querySelector(".menu-toggle");
  var nav = document.getElementById("hauptmenue");
  if (toggle && nav) {
    var label = toggle.querySelector(".menu-label");
    function setMenu(open) {
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      nav.classList.toggle("is-open", open);
      if (label) label.textContent = open ? "Schließen" : "Menü";
    }
    toggle.addEventListener("click", function () { setMenu(toggle.getAttribute("aria-expanded") !== "true"); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") { setMenu(false); toggle.focus(); }
    });
    nav.addEventListener("click", function (e) { if (e.target.closest("a")) setMenu(false); });
  }

  /* ---------- 2. Programm ---------- */
  function relLabel(start, end, n) {
    if (start <= n && n < end) return "Läuft gerade";
    if (dayKey(start) === dayKey(n)) return "Heute";
    if (dayKey(start) === dayKey(new Date(n.getTime() + 864e5))) return "Morgen";
    return "Als Nächstes";
  }
  /* Startseiten-Übernahme: Veranstaltung, die in weniger als X Stunden beginnt oder gerade läuft,
     ersetzt den Claim (Vorlagen im <template>, siehe index.html). Im Programm darunter wird dann
     keine Kachel mehr extra groß gezeigt – das wäre doppelt. */
  var heroEl = document.querySelector(".hero");
  var tkVorlagen = Array.prototype.slice.call(document.querySelectorAll("template.takeover-vorlage"));
  var tkAktiv = null;
  function tkWahl() {
    var n = now();
    return tkVorlagen.filter(function (t) {
      var st = new Date(t.getAttribute("data-start")), en = new Date(t.getAttribute("data-end"));
      return st.getTime() - (parseFloat(t.getAttribute("data-stunden")) || 6) * 36e5 <= n && n < en;
    })[0] || null;
  }
  function tkZeigen() {
    var t = tkWahl();
    if (t === (tkAktiv && tkAktiv.vorlage)) return;
    if (tkAktiv) { tkAktiv.el.remove(); tkAktiv = null; }
    heroEl.classList.toggle("is-takeover", !!t);
    if (!t) return;
    var el = t.content.querySelector(".tile").cloneNode(true);
    heroEl.querySelector(".hero-claim").appendChild(el);
    tkAktiv = { vorlage: t, el: el, start: new Date(t.getAttribute("data-start")), end: new Date(t.getAttribute("data-end")),
                lab: el.querySelector("[data-label]"), count: el.querySelector("[data-count]") };
    var d = tkAktiv.count && tkAktiv.count.getAttribute("data-doors");
    tkAktiv.doors = d ? new Date(d) : null;
  }
  function tkTick() {
    tkZeigen();
    if (!tkAktiv) return;
    var n = now(), a = tkAktiv, live = a.start <= n && n < a.end;
    if (a.lab) a.lab.textContent = live ? "Läuft gerade" : relLabel(a.start, a.end, n) + " · " + fmtTime(a.start);
    if (a.count) {
      a.count.classList.toggle("is-live", live);
      a.count.innerHTML = live ? '<span class="tc-dot" aria-hidden="true"></span>Jetzt geöffnet · bis ' + fmtTime(a.end) + " Uhr"
        : a.doors && n < a.doors ? "Einlass in <b>" + countdown(a.doors - n) + "</b>"
        : "Beginn in <b>" + countdown(a.start - n) + "</b>";
    }
  }
  if (heroEl && tkVorlagen.length) { tkTick(); setInterval(tkTick, 1000); }

  document.querySelectorAll(".program-grid").forEach(function (grid) {
    var n = now();
    var tiles = Array.prototype.slice.call(grid.querySelectorAll(".tile"));
    var left = tiles.filter(function (t) {
      var end = new Date(t.getAttribute("data-end"));
      if (end <= n) { t.remove(); return false; }
      t.classList.remove("is-next");
      return true;
    });
    left.forEach(function (t) {     // Stream-Kennzeichen leuchtet, solange der Abend läuft
      var c = t.querySelector(".chip--stream");
      if (c) c.classList.toggle("is-live", new Date(t.getAttribute("data-start")) <= n);
    });
    if (left.length && heroEl && heroEl.classList.contains("is-takeover")) {
      /* Übernahme aktiv: kein zweites großes Bild im Programm */
    } else if (left.length) {
      var first = left[0];
      first.classList.add("is-next");
      var start = new Date(first.getAttribute("data-start"));
      var lab = first.querySelector("[data-label]");
      var rel = relLabel(start, new Date(first.getAttribute("data-end")), n);
      if (lab) lab.textContent = rel === "Als Nächstes" ? rel + " · " + fmtShort(start).split(" · ")[0].replace(/\.$/, ".") : rel + " · " + fmtTime(start);
    } else {
      grid.hidden = true;
      var empty = grid.parentNode.querySelector(".program-empty");
      if (empty) empty.hidden = false;
    }
  });
  /* Veranstaltungsseite: vorbei? Weitere Termine aufräumen */
  var ev = document.querySelector(".event[data-end]");
  if (ev && new Date(ev.getAttribute("data-end")) <= now()) {
    var note = ev.querySelector(".past-note");
    if (note) note.hidden = false;
    document.body.classList.add("is-past");
  }
  /* Stream-Karte (Abende mit "stream:"): vorher Hinweis, während der Veranstaltung "Jetzt live", danach weg */
  var evs = document.querySelector(".ev-stream[data-start]");
  if (evs) {
    var evsStart = new Date(evs.getAttribute("data-start"));
    var evsEnd = new Date(evs.getAttribute("data-end"));
    var evsStatus = evs.querySelector("[data-evs-status]");
    var evsCta = evs.querySelector("[data-evs-cta]");
    var updateStream = function () {
      var n = now();
      if (n >= evsEnd) { evs.hidden = true; return; }
      var live = n >= evsStart;
      evs.hidden = false;
      evs.classList.toggle("is-live", live);
      if (evsStatus) evsStatus.textContent = live ? "Jetzt live" : "Auch im Stream";
      if (evsCta) evsCta.textContent = live ? "Jetzt reinhören" : "Zum Stream";
    };
    updateStream();
    setInterval(updateStream, 30000);
  }
  document.querySelectorAll(".more-item[data-end]").forEach(function (a) {
    if (new Date(a.getAttribute("data-end")) <= now()) a.parentNode.remove();
  });
  /* Gruppen unter "Weitere Termine" nachziehen: Breite anpassen, leere Gruppen ausblenden,
     und "Außerdem im Programm" nicht als einzige Überschrift stehen lassen */
  var groups = Array.prototype.slice.call(document.querySelectorAll(".more-group"));
  groups.forEach(function (g) {
    var n = g.querySelectorAll(".more-item").length;
    if (!n) { g.remove(); return; }
    g.style.setProperty("--n", n);
  });
  if (groups.length && !document.querySelector(".more-group--reihe")) {
    document.querySelectorAll(".more-group .more-group-title").forEach(function (h) { h.remove(); });
  }
  var moreSection = document.querySelector("section.more");
  if (moreSection && !moreSection.querySelector(".more-item")) moreSection.remove();

  /* ---------- 3. Teilen ---------- */
  document.querySelectorAll("[data-share]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var data = { title: btn.getAttribute("data-title"), url: btn.getAttribute("data-url") };
      var lab = btn.querySelector("[data-share-label]");
      if (navigator.share) {
        navigator.share(data).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(data.url).then(function () {
          if (lab) { lab.textContent = "Link kopiert"; setTimeout(function () { lab.textContent = "Teilen"; }, 2400); }
        });
      } else {
        window.prompt("Link zum Teilen:", data.url);
      }
    });
  });

  /* ---------- Effekte nur animieren, wenn sie zu sehen sind ----------
   * Jede Kachel bzw. Veranstaltungsseite mit Effekten (.has-fx) bekommt .fx-paused, solange keine ihrer
   * Effekt-Ebenen (.fx) im Bild ist – und alle, solange der Tab im Hintergrund liegt. */
  var fxOwners = document.querySelectorAll(".has-fx");
  if (fxOwners.length && "IntersectionObserver" in window) {
    var fxVisible = new Map();                      // Effekt-Ebene → gerade im Bild?
    var fxUpdate = function (owner) {
      var on = !document.hidden && Array.prototype.some.call(owner.querySelectorAll(".fx"), function (l) { return fxVisible.get(l); });
      owner.classList.toggle("fx-paused", !on);
    };
    var fxObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { fxVisible.set(e.target, e.isIntersecting); });
      entries.forEach(function (e) { var o = e.target.closest(".has-fx"); if (o) fxUpdate(o); });
    }, { rootMargin: "150px 0px" });                 // kurz vor dem Hereinscrollen schon starten
    fxOwners.forEach(function (o) { o.querySelectorAll(".fx").forEach(function (l) { fxObserver.observe(l); }); });
    document.addEventListener("visibilitychange", function () { fxOwners.forEach(fxUpdate); });
  }

  /* ---------- Interne Seiten: Kopieren-Knöpfe + Zeichenzähler ---------- */
  var copyText = function (el) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(el.value);
    el.focus(); el.select();                         // Rückfall für http:// (lokal)
    try { document.execCommand("copy"); } catch (e) {}
    return Promise.resolve();
  };
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    var label = btn.textContent;
    btn.addEventListener("click", function () {
      var el = document.getElementById(btn.getAttribute("data-copy"));
      if (!el) return;
      copyText(el).then(function () {
        btn.textContent = "✓ Kopiert";
        btn.classList.add("is-done");
        setTimeout(function () { btn.textContent = label; btn.classList.remove("is-done"); }, 2000);
      });
    });
  });
  document.querySelectorAll("[data-count][data-limit]").forEach(function (c) {
    var el = document.getElementById(c.getAttribute("data-count"));
    var limit = parseInt(c.getAttribute("data-limit"), 10);
    // Instagram zählt Zeichen wie JavaScript (Emojis = 2), daher hier nachzählen
    if (el && el.value.length > limit) {
      c.classList.add("is-over");
      c.textContent = el.value.length + " Zeichen – " + (el.value.length - limit) + " zu viel (max. " + limit + ")";
    }
  });

  /* ---------- No-Cookie-Banner ----------
   * Erscheint nur, wenn jemand von außen kommt (Link, Suche, direkt eingetippt) – nicht bei
   * jedem Klick innerhalb der Seite. Gespeichert wird dafür nichts: kein Cookie, kein localStorage.
   * Verschwindet, wenn der rote Balken abgelaufen ist (hält an, solange Maus oder Fokus darauf ist).
   */
  /* Zum Testen: #nocookie (oder ?nocookie) an eine beliebige Adresse hängen, z. B.
   *   https://www.calavera.club/#nocookie
   *   https://www.calavera.club/programm/#nocookie
   * Funktioniert auch auf einer schon offenen Seite: #nocookie in die Adresszeile tippen, Enter. */
  var nc = document.getElementById("nocookie");
  if (nc) {
    var ncTimer = nc.querySelector(".nc-timer");
    var ncHideTimeout = null;
    var forced = function () {
      return location.hash.toLowerCase() === "#nocookie" || new URLSearchParams(location.search).has("nocookie");
    };
    var closeNc = function () {
      if (nc.hidden || nc.classList.contains("is-leaving")) return;
      nc.classList.add("is-leaving");
      ncHideTimeout = setTimeout(function () { nc.hidden = true; nc.classList.remove("is-leaving", "is-running"); }, 500);
    };
    var showNc = function (delay) {
      clearTimeout(ncHideTimeout);
      nc.classList.remove("is-running", "is-leaving");
      void ncTimer.offsetWidth;                       // Balken-Animation von vorn starten
      setTimeout(function () {
        nc.classList.add("is-entering");
        nc.hidden = false;
        requestAnimationFrame(function () {
          requestAnimationFrame(function () { nc.classList.remove("is-entering"); nc.classList.add("is-running"); });
        });
      }, delay);
    };
    ncTimer.addEventListener("animationend", closeNc);
    nc.querySelectorAll("[data-nc-close]").forEach(function (b) { b.addEventListener("click", closeNc); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !nc.hidden) closeNc(); });
    window.addEventListener("hashchange", function () { if (forced()) showNc(0); });

    var fromOutside = true;
    try { fromOutside = !document.referrer || new URL(document.referrer).host !== location.host; } catch (e) {}
    if (fromOutside || forced()) showNc(1200);
  }

  /* ---------- 4. Kellerfunk ---------- */
  var card = document.querySelector(".kf-card[data-config]");
  var band = document.querySelector(".onair-band[data-config]");
  var src = card || band;
  if (!src) return;
  var base = (src.getAttribute("data-url") || "https://live.calavera.club").replace(/\/+$/, "") + "/";
  var hours = parseFloat(src.getAttribute("data-hours")) || 6;
  var refresh = Math.max(20, parseInt(src.getAttribute("data-refresh"), 10) || 60) * 1000;
  card = card || document.createElement("div");     // ohne Karte (alle Seiten außer Start): nur das Band
  var el = {
    status: card.querySelector(".kf-status-text"),
    show: card.querySelector(".kf-show"),
    text: card.querySelector(".kf-text"),
    vis: card.querySelector(".kf-visual"),
    img: card.querySelector(".kf-visual img"),
    cta: card.querySelector(".kf-cta")
  };
  var defaults = { text: el.text ? el.text.textContent : "", cta: el.cta ? el.cta.innerHTML : "" };

  function resolve(url) {
    if (!url) return "";
    try { return new URL(url, base).href; } catch (e) { return ""; }
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function evaluate(cfg) {
    var n = now();
    var shows = (cfg && Array.isArray(cfg.shows) ? cfg.shows : []).map(function (s) {
      var start = bremen(s && s.start);
      if (!start) return null;
      var end = bremen(s.end) || new Date(start.getTime() + hours * 36e5);
      return { title: s.title || "Kellerfunk", djs: [].concat(s.djs || []).filter(Boolean), start: start, end: end,
               visual: resolve(s.visual || s.flyer || ""), description: s.description || "" };
    }).filter(Boolean).sort(function (a, b) { return a.start - b.start; });

    var mode = String(cfg && cfg.site && cfg.site.live != null ? cfg.site.live : "auto").toLowerCase();
    var running = shows.filter(function (s) { return s.start <= n && n < s.end; })[0] || null;
    var next = shows.filter(function (s) { return s.start > n; })[0] || null;
    var live;
    if (mode === "an" || mode === "on" || mode === "true" || mode === "ja") { live = true; running = running || next || shows[shows.length - 1] || null; }
    else if (mode === "aus" || mode === "off" || mode === "false" || mode === "nein") { live = false; running = null; }
    else { live = !!running; }
    return { live: live, show: live ? running : next };
  }

  /* Band oben auf jeder Seite: live → rot; beginnt in < 60 Minuten → dezent mit Countdown.
     Wegklicken gilt für diese Sendung, bis der Tab geschlossen wird (sessionStorage). */
  var bandEl = band && {
    status: band.querySelector(".ob-status"), show: band.querySelector(".ob-show"), go: band.querySelector(".ob-go"),
    close: band.querySelector(".ob-close")
  };
  var bandKey = "";
  function bandZu(key) { try { return sessionStorage.getItem("onair-zu") === key; } catch (e) { return false; } }
  if (bandEl && bandEl.close) bandEl.close.addEventListener("click", function () {
    try { sessionStorage.setItem("onair-zu", bandKey); } catch (e) {}
    band.hidden = true;
  });
  function renderBand(state) {
    if (!band) return;
    var show = state.show, n = now();
    var bald = !state.live && show && show.start - n > 0 && show.start - n <= 36e5;
    var mode = state.live && show ? "live" : bald ? "bald" : "";
    bandKey = mode ? mode + ":" + show.start.getTime() : "";
    if (!mode || bandZu(bandKey)) { band.hidden = true; return; }
    band.classList.toggle("is-live", mode === "live");
    band.classList.toggle("is-soon", mode === "bald");
    var who = show.djs.length ? " · " + show.djs.join(" & ") : "";
    bandEl.status.textContent = mode === "live" ? "Live im Kellerfunk" : "Kellerfunk";
    bandEl.show.textContent = (mode === "live" ? "" : "Gleich auf Sendung: ") + show.title + who;
    bandEl.go.innerHTML = mode === "live" ? 'Reinhören <span aria-hidden="true">↗</span>' : "in " + countdown(show.start - n);
    band.hidden = false;
  }

  function render(state) {
    renderBand(state);
    if (!el.show) return;                             // keine Kellerfunk-Karte auf dieser Seite
    var show = state.show;
    card.classList.toggle("is-live", state.live);
    if (el.status) el.status.textContent = state.live ? "Jetzt live" : (show ? "Off Air" : "Kellerfunk");
    if (show) {
      var who = show.djs.length ? " mit " + esc(show.djs.join(" & ")) : "";
      el.show.innerHTML = state.live
        ? "Gerade auf Sendung: <strong>" + esc(show.title) + "</strong>" + who
        : "Nächste Sendung: <strong>" + esc(show.title) + "</strong><br>" + esc(fmtShort(show.start)) + " Uhr" + who;
      el.show.hidden = false;
    } else {
      el.show.hidden = true;
    }
    if (el.text) el.text.textContent = defaults.text;
    if (state.live && show && show.visual) {   // Visual nur live – sonst steht das Kellerfunk-Logo in der Mitte
      if (el.img.getAttribute("src") !== show.visual) {
        el.img.src = show.visual;
        el.img.alt = "Visual zur Sendung " + show.title;
      }
      el.vis.hidden = false;
      card.classList.add("has-visual");
    } else {
      el.vis.hidden = true;
      card.classList.remove("has-visual");
    }
    if (el.cta) el.cta.innerHTML = state.live ? 'Jetzt reinhören <span aria-hidden="true">↗</span>' : defaults.cta;
  }
  if (el.img) el.img.addEventListener("error", function () { el.vis.hidden = true; card.classList.remove("has-visual"); });
  /* Logo nicht ladbar → stattdessen wieder den Schriftzug zeigen */
  var logo = card.querySelector(".kf-logo img");
  if (logo) {
    var noLogo = function () { card.classList.add("no-logo"); };
    if (logo.complete && logo.naturalWidth === 0) noLogo();
    logo.addEventListener("error", noLogo);
  }

  var lastCfg = null;
  function load() {
    if (!window.jsyaml) return;  // js-yaml fehlt → statischer Inhalt bleibt
    fetch(src.getAttribute("data-config"), { cache: "no-store", credentials: "omit" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (txt) { lastCfg = window.jsyaml.load(txt) || {}; render(evaluate(lastCfg)); })
      .catch(function () { if (lastCfg) render(evaluate(lastCfg)); /* sonst bleibt der statische Inhalt */ });
  }
  function start() {
    load(); setInterval(load, refresh);
    // Countdown im Band sekundengenau (und pünktlich auf "live" umschalten)
    if (band) setInterval(function () { if (lastCfg && (band.classList.contains("is-soon") || band.hidden)) renderBand(evaluate(lastCfg)); }, 1000);
  }
  if (window.jsyaml) start(); else window.addEventListener("load", start);
})();
