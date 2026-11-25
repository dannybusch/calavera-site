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
