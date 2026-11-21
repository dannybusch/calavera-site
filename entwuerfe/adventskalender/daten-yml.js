/* Adventskalender – Daten aus advent/adventskalender2026.yml laden (nur für Entwurf A).
   Braucht js-yaml (static/js/js-yaml.min.js) und einen kleinen Webserver, weil Browser
   Dateien nicht per file:// nachladen. Im Projektordner:
       python -m http.server 8001
   dann http://localhost:8001/entwuerfe/adventskalender/a-tueren.html

   Simulation:  ?heute=7  (welcher Dezembertag ist)   ?offen=7  (Tür 7 gleich öffnen)
   Ohne ?heute: im Dezember des Kalenderjahres der echte Tag, sonst der 7.
   Leere Felder werden als Platzhalter angezeigt (gepunktet unterstrichen). */
(function () {
  var QUELLE = "../../advent/adventskalender2026.yml";
  var WT = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
  var DIENSTE = { youtube_music: "YouTube Music", bandcamp: "Bandcamp", spotify: "Spotify", apple_music: "Apple Music",
                  tidal: "Tidal", soundcloud: "SoundCloud", deezer: "Deezer" };

  function leer(v) { return v === undefined || v === null || String(v).trim() === ""; }
  // Feld mit Platzhalter-Kennung: {wert, ph}
  function feld(v, ersatz) { return leer(v) ? { wert: ersatz, ph: true } : { wert: String(v).trim(), ph: false }; }

  function aufbereiten(d) {
    var p = new URLSearchParams(location.search), jahr = d.jahr || 2026, jetzt = new Date();
    var heute = p.get("heute") ? parseInt(p.get("heute"), 10)
              : (jetzt.getFullYear() === jahr && jetzt.getMonth() === 11 ? jetzt.getDate() : 7);
    var tueren = [];
    for (var t = 1; t <= 24; t++) {
      var e = (d.tueren || []).filter(function (x) { return x && x.tag === t; })[0] || {};
      var links = [];
      Object.keys(e.links || {}).forEach(function (k) {
        var url = e.links[k];
        if (k === "andere" && Array.isArray(url)) {
          url.forEach(function (a) { if (a && !leer(a.url)) links.push({ dienst: a.name || "Link", url: a.url }); });
        } else if (!leer(url)) {
          links.push({ dienst: DIENSTE[k] || k, url: url });
        }
      });
      var kz = ("0" + t).slice(-2);
      tueren.push({
        tag: t,
        wochentag: WT[new Date(jahr, 11, t).getDay()],
        datum: kz + ".12.",
        song: feld(e.song, "Song " + kz + " folgt"),
        kuenstler: feld(e.kuenstler, "Künstler:in"),
        erschienen: leer(e.erschienen) ? "" : String(e.erschienen),
        person: feld(e.person, "Name folgt"),
        rolle: feld(e.rolle, "DJ / Team"),
        text: feld(e.text, "Hier steht bald, warum dieser Song – ein paar Sätze von der Person selbst."),
        links: links,
        status: t < heute ? "offen" : (t === heute ? "heute" : "zu")
      });
    }
    return {
      jahr: jahr, heute: heute, offen: parseInt(p.get("offen") || "0", 10),
      titel: feld(d.titel, "24 Türen. 24 Lieblingssongs."),
      kicker: feld(d.kicker, "Calavera · Advent " + jahr),
      einleitung: feld(d.einleitung, "Einleitung folgt."),
      oeffnet_um: d.oeffnet_um || "00:00",
      tueren: tueren,
      // Reihenfolge im Raster: klassisch durcheinander, aber fest
      mischung: [17, 3, 22, 9, 1, 14, 6, 20, 11, 24, 4, 15, 8, 19, 2, 12, 23, 7, 16, 10, 5, 21, 13, 18]
    };
  }

  window.adventLaden = function () {
    return fetch(QUELLE, { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.text(); })
      .then(function (txt) { return aufbereiten(jsyaml.load(txt) || {}); });
  };

  window.ADVENT_ICON = function (key) {
    if (key === "play") return '<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5z"/></svg>';
    return '<svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>';
  };
})();
