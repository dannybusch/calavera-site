/* Adventskalender – gemeinsame Platzhalter-Daten für die drei Entwürfe.
   ALLES HIER IST PLATZHALTER. Keine echten Songs, keine echten Personen.
   Später käme das z. B. aus advent/*.md (YAML-Kopf) über build.py.

   Simulation im Browser (nur für die Entwürfe):
     ?heute=7   → so tun, als wäre der 7. Dezember (Standard: 7)
     ?offen=7   → Türchen 7 beim Laden direkt öffnen
   Zustand (geöffnete Türen) nur im Speicher der Seite – kein localStorage. */
(function () {
  var p = new URLSearchParams(location.search);
  var heute = parseInt(p.get("heute") || "7", 10);
  var offen = parseInt(p.get("offen") || "0", 10);
  var wt = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

  // Welche Dienste es gibt, Reihenfolge = Reihenfolge der Knöpfe. Pro Tür nur die, die gepflegt sind.
  var DIENSTE = {
    ytmusic:  "YouTube Music",
    bandcamp: "Bandcamp",
    spotify:  "Spotify",
    apple:    "Apple Music",
    tidal:    "Tidal",
    soundcloud: "SoundCloud"
  };
  // Unterschiedlich viele Links pro Tür, damit man sieht, wie die Knöpfe sich verhalten
  var MUSTER = [
    ["ytmusic", "bandcamp", "spotify"],
    ["bandcamp", "ytmusic"],
    ["ytmusic", "spotify", "apple", "tidal"],
    ["soundcloud", "ytmusic"],
    ["ytmusic"]
  ];

  var tueren = [];
  for (var t = 1; t <= 24; t++) {
    var d = new Date(2026, 11, t);
    var links = MUSTER[t % MUSTER.length].map(function (k) {
      return { key: k, dienst: DIENSTE[k], url: "#platzhalter-" + k };
    });
    tueren.push({
      tag: t,
      wochentag: wt[d.getDay()],
      datum: ("0" + t).slice(-2) + ".12.",
      song: "Songtitel " + ("0" + t).slice(-2),
      kuenstler: "Künstler:in",
      jahr: "Jahr",
      person: "Name " + ("0" + t).slice(-2),
      rolle: "DJ / Team",
      text: "Platzhaltertext: Warum dieser Song? Ein paar Sätze von der Person selbst – " +
            "wo sie ihn zum ersten Mal gehört hat, was er im Calavera bedeutet, welche Nacht dazugehört. " +
            "Zwei bis vier Sätze, nicht mehr.",
      links: links,
      // Status relativ zum simulierten Tag
      status: t < heute ? "offen" : (t === heute ? "heute" : "zu")
    });
  }

  window.ADVENT = {
    heute: heute,
    offen: offen,
    tueren: tueren,
    // Reihenfolge im Raster: klassisch durcheinander (fest, nicht zufällig – sonst springt es bei jedem Laden)
    mischung: [17, 3, 22, 9, 1, 14, 6, 20, 11, 24, 4, 15, 8, 19, 2, 12, 23, 7, 16, 10, 5, 21, 13, 18]
  };

  // Kleine SVG-Symbole für die Dienste (eigene, schlichte Formen – keine Markenlogos)
  window.ADVENT_ICON = function (key) {
    var play = '<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5z"/></svg>';
    var ext = '<svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>';
    return key === "play" ? play : ext;
  };
})();
