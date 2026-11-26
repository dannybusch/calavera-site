/* Adventskalender (/adventskalender/) – nur auf dieser Seite.
   Enthält keine Daten: Die geöffneten Türen stehen fertig im HTML (<article id="tuer-N">), dieses Script
   zeigt sie nur im Fenster. Was noch kommt, weiß die Seite nicht – der Build schreibt es gar nicht hinein.
   Kein Speichern im Browser; Deep-Links über #tuer-N. */
(function () {
  "use strict";
  // Mitwirkende bei jedem Besuch neu mischen (Reihenfolge verrät nichts über die Türen)
  var mit = document.querySelector(".adv-mit ul");
  if (mit) {
    var li = Array.prototype.slice.call(mit.children);
    for (var i = li.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), x = li[i]; li[i] = li[j]; li[j] = x; }
    li.forEach(function (el) { mit.appendChild(el); });
  }
  // Ratespiel „Wann ist der Song erschienen?“ – im HTML steht nur ein Prüfwert (FNV-1a von Salz + Jahr), nicht das Jahr.
  // Tipps merkt sich die Seite nur, solange sie offen ist (kein Speichern im Browser).
  function fnv(t) {
    var h = 0x811c9dc5, b = new TextEncoder().encode(t);
    for (var i = 0; i < b.length; i++) { h ^= b[i]; h = Math.imul(h, 0x01000193) >>> 0; }
    return ("0000000" + h.toString(16)).slice(-8);
  }
  var tipps = {};
  function aufloesen(box, gewaehlt) {
    var richtig = null, salz = box.dataset.salz, h = box.dataset.h;
    box.querySelectorAll(".ab-j").forEach(function (b) {
      b.disabled = true;
      if (fnv(salz + b.dataset.j) === h) { richtig = b.dataset.j; b.classList.add("is-richtig"); }
      if (b.dataset.j === gewaehlt) b.classList.add("is-gewaehlt");
    });
    box.classList.add("is-geraten");
    box.querySelector(".ab-raten-aufl").textContent = gewaehlt === richtig
      ? "Richtig – " + richtig + "."
      : "Leider nein – erschienen " + richtig + ".";
    var art = box.closest(".adv-tuer"), j = art && art.querySelector(".ab-jahr");
    if (j) j.textContent = " · " + richtig;
  }
  function ratenWiederherstellen(root) {
    (root || document).querySelectorAll(".adv-tuer").forEach(function (a) {
      var t = a.dataset.tuer, box = a.querySelector(".ab-raten");
      if (box && tipps[t] && !box.classList.contains("is-geraten")) aufloesen(box, tipps[t]);
    });
  }
  // Konfetti bei richtigem Tipp: ein paar Schnipsel in Rot, Gold und Creme, ohne Bibliothek (Web Animations).
  // Hängt im Fenster (<dialog> liegt ganz oben – außerhalb wäre es verdeckt). Bei reduzierter Bewegung: keins.
  function konfetti(von) {
    if (!von.animate || (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches)) return;
    var buehne = von.closest("dialog") || document.body, r = von.getBoundingClientRect();
    var farben = ["#b3122e", "#cb5e71", "#d4a64a", "#e8c872", "#d1cabf"];
    for (var i = 0; i < 46; i++) {
      var k = document.createElement("span"), w = 5 + Math.random() * 5, winkel = Math.random() * Math.PI * 2;
      var weit = 60 + Math.random() * 140, dx = Math.cos(winkel) * weit, dy = Math.sin(winkel) * weit * .7 - 60;
      k.setAttribute("aria-hidden", "true");
      k.style.cssText = "position:fixed;z-index:10;pointer-events:none;left:" + (r.left + r.width / 2) + "px;top:" +
        (r.top + r.height / 2) + "px;width:" + w + "px;height:" + (w * (Math.random() < .5 ? .45 : 1)) + "px;background:" +
        farben[i % farben.length] + ";border-radius:" + (Math.random() < .3 ? "50%" : "1px");
      buehne.appendChild(k);
      var dreh = (Math.random() * 720 - 360) + "deg";
      k.animate([
        { transform: "translate(-50%,-50%) rotate(0)", opacity: 1 },
        { transform: "translate(calc(-50% + " + dx + "px), calc(-50% + " + dy + "px)) rotate(" + dreh + ")", opacity: 1, offset: .45 },
        { transform: "translate(calc(-50% + " + dx * 1.15 + "px), calc(-50% + " + (dy + 160) + "px)) rotate(" + dreh + ")", opacity: 0 }
      ], { duration: 1300 + Math.random() * 700, easing: "cubic-bezier(.2,.7,.4,1)" }).onfinish = (function (el) {
        return function () { el.remove(); };
      })(k);
    }
  }

  document.addEventListener("click", function (e) {
    var b = e.target.closest(".ab-j");
    if (!b || b.disabled) return;
    var art = b.closest(".adv-tuer");
    tipps[art.dataset.tuer] = b.dataset.j;
    aufloesen(b.closest(".ab-raten"), b.dataset.j);
    if (b.classList.contains("is-richtig")) konfetti(b);
    var orig = document.getElementById("tuer-" + art.dataset.tuer);   // auch die Liste unter dem Raster auflösen
    if (orig && orig !== art) ratenWiederherstellen(orig.parentNode);
  });

  var grid = document.querySelector(".adv-grid"), dlg = document.querySelector(".adv-dlg");
  if (!grid || !dlg || typeof dlg.showModal !== "function") return;   // ohne <dialog>: Liste + Anker reichen
  var inhalt = dlg.querySelector(".adv-dlg-inhalt"), toast = document.querySelector(".adv-toast");
  var artikel = Array.prototype.slice.call(document.querySelectorAll(".adv-tuer"))
    .sort(function (a, b) { return a.dataset.tuer - b.dataset.tuer; });
  var nrn = artikel.map(function (a) { return +a.dataset.tuer; }), aktuell = 0, tt;
  var still = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  function zeige(n, ohneHash) {
    var a = document.getElementById("tuer-" + n);
    if (!a) return;
    aktuell = n;
    inhalt.innerHTML = "";
    var kopie = a.cloneNode(true);
    kopie.removeAttribute("id");                                  // die Anker-ID bleibt beim Original
    var h = kopie.querySelector("[id]"); if (h) { h.id = "dlg-song"; kopie.setAttribute("aria-labelledby", "dlg-song"); }
    inhalt.appendChild(kopie);
    ratenWiederherstellen(inhalt);
    dlg.setAttribute("aria-labelledby", "dlg-song");
    var i = nrn.indexOf(n);
    dlg.querySelector('[data-schritt="-1"]').disabled = i <= 0;
    dlg.querySelector('[data-schritt="1"]').disabled = i >= nrn.length - 1;
    var tuer = grid.querySelector('.door[data-tuer="' + n + '"]');
    if (tuer) tuer.classList.add("is-auf");
    if (!ohneHash && history.replaceState) history.replaceState(null, "", "#tuer-" + n);
    if (!dlg.open) dlg.showModal();
    dlg.scrollTop = 0;
  }

  grid.addEventListener("click", function (e) {
    var d = e.target.closest(".door");
    if (!d) return;
    if (d.classList.contains("is-zu")) {
      toast.textContent = d.dataset.ab ? "Noch zu – diese Tür öffnet am " + d.dataset.ab : "Diese Tür folgt in Kürze";
      toast.classList.add("zeigen"); clearTimeout(tt);
      tt = setTimeout(function () { toast.classList.remove("zeigen"); }, 2600);
      return;
    }
    e.preventDefault();
    var n = +d.dataset.tuer;
    if (d.classList.contains("is-heute") && !d.classList.contains("is-auf") && !still) {
      d.classList.add("is-auf");                                  // erst schwenkt die Tür nach außen auf, dann der Inhalt
      setTimeout(function () { zeige(n); }, 900);
      return;
    }
    zeige(n);
  });

  dlg.addEventListener("click", function (e) {
    var s = e.target.closest("[data-schritt]");
    if (s) { var i = nrn.indexOf(aktuell) + (+s.dataset.schritt); if (nrn[i]) zeige(nrn[i]); return; }
    if (e.target === dlg || e.target.closest("[data-zu]")) dlg.close();
  });
  dlg.addEventListener("close", function () {
    if (history.replaceState && /^#tuer-/.test(location.hash)) history.replaceState(null, "", location.pathname + location.search);
  });
  document.addEventListener("keydown", function (e) {
    if (!dlg.open) return;
    if (e.key === "ArrowLeft") dlg.querySelector('[data-schritt="-1"]').click();
    if (e.key === "ArrowRight") dlg.querySelector('[data-schritt="1"]').click();
  });

  // Deep-Link: /adventskalender/#tuer-7 öffnet Tür 7 direkt
  var m = /^#tuer-(\d+)$/.exec(location.hash);
  if (m && nrn.indexOf(+m[1]) >= 0) zeige(+m[1], true);
})();
