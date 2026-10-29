/* Calavera Bremen – Seiteneffekte: wirken global auf jeder Seite (config.yml → seiteneffekte:).
 * Jeder Eintrag kann ein Zeitfenster haben (start/end, Bremer Zeit); der Browser schaltet ihn pünktlich
 * ein und wieder aus – auch wenn der letzte Build älter ist. Testen: ?now=2026-10-31T20:00
 *
 *   spinne – im Eck hängt ein Netz; scrollt man nach oben, seilt sich die Spinne ab und klettert wieder hoch
 *   logo   – das offene Auge im Calavera-Totenkopf folgt der Maus (bzw. dem Finger) und zwinkert ab und zu;
 *            wer eine Weile nichts tut, sieht den Kopf sich neigen
 *   rip    – Gedenken: schmales, dunkles Band ganz oben (R.I.P. · Name · Lebensdaten · Satz · Link),
 *            dahinter ganz ruhig vorbeiziehende Sterne; mehrere Einträge erscheinen nebeneinander
 */
(function () {
  "use strict";
  var datenEl = document.getElementById("seiteneffekte-daten");
  if (!datenEl) return;
  var liste = [];
  try { liste = JSON.parse(datenEl.textContent) || []; } catch (e) { return; }
  var jetzt = function () { return window.calaveraJetzt ? window.calaveraJetzt() : new Date(); };
  var ruhig = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var rnd = function (a, b) { return a + Math.random() * (b - a); };

  /* ---------- spinne ---------- */
  function spinne() {
    var netz = '<svg class="se-netz" viewBox="0 0 150 150" aria-hidden="true" focusable="false">';
    var mx = 150, my = 0, winkel = [], i, k;
    for (i = 0; i <= 6; i++) winkel.push(Math.PI / 2 + i * (Math.PI / 2) / 6);
    winkel.forEach(function (w) { netz += '<line x1="150" y1="0" x2="' + (mx + Math.cos(w) * 160).toFixed(1) + '" y2="' + (my + Math.sin(w) * 160).toFixed(1) + '"/>'; });
    [26, 50, 76, 102, 128].forEach(function (r) {
      var d = "";
      for (k = 0; k < winkel.length - 1; k++) {
        var a = winkel[k], b = winkel[k + 1], m = (a + b) / 2;
        var x1 = mx + Math.cos(a) * r, y1 = my + Math.sin(a) * r, x2 = mx + Math.cos(b) * r, y2 = my + Math.sin(b) * r;
        var cx = mx + Math.cos(m) * r * .86, cy = my + Math.sin(m) * r * .86;          // durchhängende Fäden
        d += (k ? "" : "M" + x1.toFixed(1) + " " + y1.toFixed(1)) + " Q" + cx.toFixed(1) + " " + cy.toFixed(1) + " " + x2.toFixed(1) + " " + y2.toFixed(1);
      }
      netz += '<path d="' + d + '"/>';
    });
    netz += "</svg>";
    var tier = '<svg viewBox="-22 -22 44 44" aria-hidden="true" focusable="false"><g class="se-beine">' +
      '<path d="M-4 -2C-10 -10-15 -11-19 -6M-5 1C-12 -3-17 -2-20 2M-5 4C-12 4-16 8-18 13M-4 6C-9 10-11 15-12 19"/>' +
      '<path d="M4 -2C10 -10 15 -11 19 -6M5 1C12 -3 17 -2 20 2M5 4C12 4 16 8 18 13M4 6C9 10 11 15 12 19"/></g>' +
      '<ellipse class="se-leib" cx="0" cy="6" rx="6.5" ry="8"/><circle class="se-leib" cx="0" cy="-5" r="4.2"/>' +
      '<circle class="se-auge" cx="-1.6" cy="-6.2" r="1"/><circle class="se-auge" cx="1.6" cy="-6.2" r="1"/></svg>';
    var el = document.createElement("div");
    el.className = "se-spinne";
    el.setAttribute("aria-hidden", "true");
    el.innerHTML = netz + '<div class="se-anker"><span class="se-faden"></span><span class="se-tier" title="Huch!">' + tier + "</span></div>";
    document.body.appendChild(el);
    var anker = el.querySelector(".se-anker"), tierEl = el.querySelector(".se-tier");
    var RUHE = 44, unterwegs = false, zuletztY = window.scrollY, hoch = 0, timer = null;
    function laenge(px, dauer, kurve) {
      anker.style.setProperty("--len", px + "px");
      anker.style.setProperty("--dauer", dauer + "s");
      anker.style.setProperty("--kurve", kurve);
      el.classList.toggle("se-krabbelt", true);
      clearTimeout(timer);
      timer = setTimeout(function () { el.classList.remove("se-krabbelt"); }, dauer * 1000);
    }
    function abseilen() {
      if (unterwegs || ruhig) return;
      unterwegs = true;
      laenge(Math.round(rnd(150, Math.min(300, window.innerHeight * .45))), .9, "cubic-bezier(.3, 1.35, .45, 1)");   // fällt, federt nach
      setTimeout(function () {
        laenge(RUHE, rnd(2.4, 3.2), "cubic-bezier(.45, 0, .55, 1)");                                                // klettert wieder hoch
        setTimeout(function () { unterwegs = false; }, 3300);
      }, rnd(1400, 2400));
    }
    anker.style.setProperty("--len", RUHE + "px");
    window.addEventListener("scroll", function () {
      var y = window.scrollY;
      hoch = y < zuletztY ? hoch + (zuletztY - y) : 0;
      zuletztY = y;
      if (hoch > 70) { hoch = 0; abseilen(); }
    }, { passive: true });
    tierEl.addEventListener("pointerenter", function () {      // erschreckt: schnell nach oben, dann langsam zurück
      if (ruhig) return;
      unterwegs = true;
      laenge(8, .35, "ease-out");
      setTimeout(function () { laenge(RUHE, 1.8, "ease-in-out"); setTimeout(function () { unterwegs = false; }, 1900); }, 1200);
    });
    var intro = setTimeout(abseilen, 2600);                     // einmal zur Begrüßung
    return function () { clearTimeout(intro); clearTimeout(timer); el.remove(); };
  }

  /* ---------- logo ---------- */
  function logo() {
    var brand = document.querySelector(".site-header .brand");
    if (!brand) return function () {};
    var el = document.createElement("span");
    el.className = "se-logo";
    el.setAttribute("aria-hidden", "true");
    el.innerHTML = '<span class="se-auge"><span class="se-pupille"></span><span class="se-lid"></span></span>';
    brand.appendChild(el);
    brand.classList.add("se-logo-lebt");
    var auge = el.querySelector(".se-auge"), pupille = el.querySelector(".se-pupille"), lid = el.querySelector(".se-lid");
    var ziel = null, laeuft = true, ruheSeit = Date.now(), idleTimer;
    function schauen(x, y) { ziel = { x: x, y: y }; ruheSeit = Date.now(); brand.classList.remove("se-neigt"); }
    function zeichnen() {
      if (!laeuft) return;
      if (ziel) {
        var r = auge.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        var dx = ziel.x - cx, dy = ziel.y - cy, d = Math.sqrt(dx * dx + dy * dy) || 1, s = Math.min(1, d / 260);
        pupille.style.transform = "translate(" + (dx / d * s * 27).toFixed(1) + "%, " + (dy / d * s * 22).toFixed(1) + "%)";
      }
      requestAnimationFrame(zeichnen);
    }
    var maus = function (e) { schauen(e.clientX, e.clientY); };
    var tipp = function (e) { var t = e.touches && e.touches[0]; if (t) schauen(t.clientX, t.clientY); };
    document.addEventListener("pointermove", maus, { passive: true });
    document.addEventListener("touchstart", tipp, { passive: true });
    requestAnimationFrame(zeichnen);
    // zwinkern in unregelmäßigen Abständen; nach 9 s ohne Bewegung neigt sich der Kopf kurz
    function zwinkern() {
      if (!laeuft) return;
      if (!ruhig) { lid.classList.remove("zu"); void lid.offsetWidth; lid.classList.add("zu"); }
      idleTimer = setTimeout(zwinkern, rnd(3500, 8500));
    }
    idleTimer = setTimeout(zwinkern, rnd(1500, 3000));
    var neigen = setInterval(function () {
      if (!ruhig && Date.now() - ruheSeit > 9000 && !brand.classList.contains("se-neigt")) {
        brand.classList.add("se-neigt");
        ziel = { x: window.innerWidth * rnd(.2, .9), y: window.innerHeight * rnd(.4, 1) };   // schaut sich um
        setTimeout(function () { brand.classList.remove("se-neigt"); ruheSeit = Date.now(); }, 2600);
      }
    }, 1000);
    return function () {
      laeuft = false; clearTimeout(idleTimer); clearInterval(neigen);
      document.removeEventListener("pointermove", maus); document.removeEventListener("touchstart", tipp);
      brand.classList.remove("se-logo-lebt", "se-neigt"); el.remove();
    };
  }

  /* ---------- rip: Gedenken ---------- */
  function rip(eintraege) {
    var text = function (t) { var s = document.createElement("span"); s.textContent = t; return s; };
    var band = document.createElement("aside");
    band.className = "se-rip";
    band.setAttribute("aria-label", "In Erinnerung");
    var innen = document.createElement("div"); innen.className = "se-rip-innen wrap"; band.appendChild(innen);
    var zeile = document.createElement("div"); zeile.className = "se-rip-zeile"; innen.appendChild(zeile);
    eintraege.forEach(function (e) {
      var p = document.createElement(e.link ? "a" : "span");
      p.className = "se-rip-person";
      if (e.link) { p.href = e.link; p.rel = "noopener"; }
      var marke = text("R.I.P."); marke.className = "se-rip-marke"; marke.setAttribute("aria-hidden", "true"); p.appendChild(marke);
      var name = text(e.person); name.className = "se-rip-name"; p.appendChild(name);
      if (e.daten) { var d = text(e.daten); d.className = "se-rip-daten"; p.appendChild(d); }
      if (e.text) { var t = text(e.text); t.className = "se-rip-text"; p.appendChild(t); }
      if (e.link) { var l = text("↗"); l.className = "se-rip-pfeil"; l.setAttribute("aria-hidden", "true"); p.appendChild(l); }
      zeile.appendChild(p);
    });
    var knopf = document.createElement("button");
    knopf.className = "ob-close"; knopf.type = "button"; knopf.setAttribute("aria-label", "Hinweis ausblenden");
    knopf.innerHTML = '<svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>';
    innen.appendChild(knopf);
    // Wegklicken gilt nur für die gerade offene Seite – gespeichert wird nichts (kein Cookie, kein Storage)
    var kopf = document.querySelector(".site-header");
    if (kopf) kopf.parentNode.insertBefore(band, kopf);
    knopf.addEventListener("click", function () { band.remove(); });
    var sterne = null;
    if (eintraege.some(function (e) { return e.sterne !== false; })) {
      sterne = document.createElement("div");
      sterne.className = "se-sterne"; sterne.setAttribute("aria-hidden", "true");
      var html = "";
      for (var i = 0; i < 70; i++) {
        var dauer = rnd(9, 22);
        html += '<i style="--w:' + rnd(0, 360).toFixed(0) + 'deg;--d:' + dauer.toFixed(1) + 's;--dl:' + (-rnd(0, dauer)).toFixed(1) + 's;--g:' + rnd(1, 2.6).toFixed(1) + 'px"></i>';
      }
      sterne.innerHTML = html;
      document.body.appendChild(sterne);
    }
    return function () { band.remove(); if (sterne) sterne.remove(); };
  }

  // Effekte bekommen ihre gerade aktiven Einträge (wichtig für rip: wen, Daten, Text); ändert sich die
  // Auswahl (z. B. ein zweiter Eintrag beginnt), wird der Effekt neu aufgebaut
  var EFFEKTE = { spinne: spinne, logo: logo, rip: rip };
  var aktiv = {};      // name → { schluessel, weg: Aufräum-Funktion }
  function pruefen() {
    var n = jetzt(), soll = {};
    liste.forEach(function (e) {
      var an = (!e.start || n >= new Date(e.start)) && (!e.end || n < new Date(e.end));
      if (an && EFFEKTE[e.name]) (soll[e.name] = soll[e.name] || []).push(e);
    });
    Object.keys(EFFEKTE).forEach(function (name) {
      var schluessel = soll[name] ? JSON.stringify(soll[name]) : "";
      if (aktiv[name] && aktiv[name].schluessel !== schluessel) { aktiv[name].weg(); delete aktiv[name]; }
      if (schluessel && !aktiv[name]) aktiv[name] = { schluessel: schluessel, weg: EFFEKTE[name](soll[name]) };
    });
  }
  pruefen();
  setInterval(pruefen, 20000);
})();
