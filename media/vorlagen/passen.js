// Passt das Bild an: Titel werden kleiner, bis sie in ihre Zeilen passen (data-zeilen),
// Flyer in Spalten werden schmaler (data-flyerspalte), und notfalls schrumpft alles (--s),
// bis kein Kasten mit data-passt überläuft (beginnend bei data-max am <html>, sonst 1). Danach: window.fertig = true (media.py macht das Foto).
window.warnungen = [];
(async () => {
  await document.fonts.ready;
  await Promise.all([...document.images].map(i => i.complete ? null : new Promise(r => { i.onload = i.onerror = r; })));
  const root = document.documentElement;
  const ueber = el => el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1;
  const texte = [...document.querySelectorAll("[data-zeilen]")];
  const kaesten = [...document.querySelectorAll("[data-passt]")];
  const spalten = [...document.querySelectorAll("[data-flyerspalte]")];

  function textePassen() {
    for (const el of texte) {
      el.style.fontSize = "";
      let fs = parseFloat(getComputedStyle(el).fontSize);
      const min = fs * .45, z = +el.dataset.zeilen;
      const lh = () => { const v = getComputedStyle(el).lineHeight; return v.endsWith("px") ? parseFloat(v) : fs * 1.2; };
      while (fs > min && (el.scrollWidth > el.clientWidth + 1 || el.offsetHeight > z * lh() + 2)) {
        fs -= 1;
        el.style.fontSize = fs + "px";
      }
    }
  }

  // data-max am <html>: darf bei wenigen Terminen auch größer werden (bis zu diesem Faktor)
  const max = parseFloat(root.dataset.max || "1");
  let ok = false;
  for (let s = max; s >= .58; s -= .02) {
    root.style.setProperty("--s", s.toFixed(3));
    spalten.forEach(sp => sp.style.removeProperty("--fb"));
    textePassen();
    for (const sp of spalten) {
      for (let fb = 100; ueber(sp) && fb > 50; fb -= 2) sp.style.setProperty("--fb", fb + "%");
    }
    if (!kaesten.some(ueber)) { ok = true; break; }
  }
  if (!ok) window.warnungen.push("passt nicht ganz aufs Bild – weniger Termine oder kürzere Titel?");
  textePassen();
  window.fertig = true;
})();
