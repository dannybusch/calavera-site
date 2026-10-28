// Reel-Bibliothek für alle Vorlagen.
// Die Daten kommen aus reels.py als window.DATA (daten.js). Jede Vorlage setzt
//   window.REEL = { beats: <Länge in Schlägen, Vielfaches von 4>, render(b, t) { … } }
// reels.py ruft render(b, t) für jedes (Unter-)Bild auf: b = Schlag (Kommazahl), t = Sekunden.
const Reel = (() => {
  const D = window.DATA || {};
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const ease = {
    linear: x => x,
    out: x => 1 - Math.pow(1 - x, 3),
    in: x => x * x * x,
    inOut: x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2,
    snap: x => 1 - Math.pow(1 - x, 5),
  };
  // Keyframes über Schläge: [[schlag, wert, ease], …] – Wert: Zahl oder Array
  function track(keys, b) {
    if (b <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) {
      const [b1, v1, e = "inOut"] = keys[i], [b0, v0] = keys[i - 1];
      if (b <= b1) {
        const p = ease[e](clamp((b - b0) / Math.max(1e-6, b1 - b0)));
        return Array.isArray(v0) ? v0.map((x, k) => x + (v1[k] - x) * p) : v0 + (v1 - v0) * p;
      }
    }
    return keys[keys.length - 1][1];
  }
  const prog = (b, at, dur, e = "snap") => ease[e](clamp((b - at) / dur));
  const pulse = (b, decay = 7) => b < 0 ? 0 : Math.exp(-(b - Math.floor(b)) * decay);
  // Lautstärke der Bässe aus der Musik (0..1, ein Wert pro Videobild) – ohne Musik 0
  const energy = t => { const e = D.energie || []; return e.length ? e[Math.min(e.length - 1, Math.max(0, Math.round(t * 30)))] : 0; };
  // Pumpen im Takt: Schlag-Puls, mit Musik zusätzlich von den Bässen getragen
  const pump = (b, t) => clamp(Math.max(pulse(b), energy(t) * .9));
  const set = (el, css) => Object.assign(el.style, css);
  const $ = id => document.getElementById(id);
  function letters(el) {
    const txt = el.textContent; el.textContent = "";
    [...txt].forEach(ch => { const s = document.createElement("span"); s.className = "ch"; s.textContent = ch === " " ? " " : ch; el.appendChild(s); });
    return [...el.querySelectorAll(".ch")];
  }
  // Schriftgröße so wählen, dass der Text in maxW passt (zwischen minPx und maxPx)
  function fit(el, maxW, maxPx, minPx = 40) {
    let px = maxPx; el.style.fontSize = px + "px";
    while (px > minPx && el.getBoundingClientRect().width > maxW) { px -= 4; el.style.fontSize = px + "px"; }
    return px;
  }
  // Text auf höchstens zwei ausgewogene Zeilen verteilen
  function zweiZeilen(txt) {
    const w = txt.split(/\s+/); if (w.length < 2) return [txt];
    let best = [txt], score = 1e9;
    for (let i = 1; i < w.length; i++) { const a = w.slice(0, i).join(" "), c = w.slice(i).join(" "); const s = Math.max(a.length, c.length); if (s < score) { score = s; best = [a, c]; } }
    return best;
  }
  // Text-Block mit eingepasster Größe (ein- oder zweizeilig) bauen
  function textBlock(parent, cls, txt, { maxW = 960, maxPx = 200, minPx = 60, zweizeilig = "auto" } = {}) {
    const box = document.createElement("div"); box.className = cls; parent.appendChild(box);
    const one = document.createElement("span"); one.className = "fit"; one.textContent = txt; box.appendChild(one);
    let px = fit(one, maxW, maxPx, minPx);
    if ((zweizeilig === true || (zweizeilig === "auto" && px < maxPx * .62)) && txt.includes(" ")) {
      box.textContent = "";
      const lines = zweiZeilen(txt).map(l => { const s = document.createElement("span"); s.className = "fit"; s.textContent = l; box.appendChild(s); box.appendChild(document.createElement("br")); return s; });
      px = Math.min(...lines.map(s => fit(s, maxW, maxPx, minPx)));
      lines.forEach(s => s.style.fontSize = px + "px");
    }
    return box;
  }
  // Atmosphäre: nebel | konfetti | schnee | funken | sterne (feste Zufallswerte → jedes Rendern gleich)
  function atmo(parent, typ, { dichte = 1, vorn = false } = {}) {
    let s = 7 + (vorn ? 13 : 0); const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
    const el = document.createElement("div"); parent.appendChild(el);
    if (typ === "nebel") { el.className = "nebel"; el.innerHTML = vorn ? '<span class="n2"></span><span class="n3"></span>' : '<span class="n1"></span><span class="n2"></span><span class="n3"></span>'; el.style.setProperty("--nh", vorn ? "760px" : "1300px"); if (!vorn) el.style.opacity = .55; return el; }
    el.className = "teilchen " + typ;
    const n = Math.round({ konfetti: 26, schnee: 40, funken: 16, sterne: 14 }[typ] * dichte);
    const farben = ["#e23a5b", "#f3c766", "#ff6fb5", "#5ec8ff", "#9ef08a"];
    for (let i = 0; i < n; i++) {
      const p = document.createElement("i"), x = (i + rnd()) / n * 100;
      if (typ === "konfetti") { const d = 6 + rnd() * 5; p.style.cssText = `--x:${x}%;--w:${26 + rnd() * 22}px;--c:${farben[i % 5]};--d:${d}s;--dl:${-rnd() * d}s;--dx:${-80 + rnd() * 160}px;--r:${360 + rnd() * 540}deg;--f:${.3 + rnd() * .4}s`; }
      if (typ === "schnee") { const d = 8 + rnd() * 8; p.style.cssText = `--x:${x}%;--w:${5 + rnd() * 12}px;--o:${.5 + rnd() * .45};--d:${d}s;--dl:${-rnd() * d}s;--dx:${-60 + rnd() * 120}px;--r:0deg;--f:${2.5 + rnd() * 2}s`; }
      if (typ === "funken") { const d = 7 + rnd() * 6; p.style.cssText = `--x:${x}%;--w:${5 + rnd() * 6}px;--d:${d}s;--dl:${-rnd() * d}s;--dx:${-120 + rnd() * 240}px;--f:${.4 + rnd() * .6}s`; }
      if (typ === "sterne") { const d = 3.5 + rnd() * 4; p.style.cssText = `--x:${x}%;--y:${8 + rnd() * 84}%;--w:${18 + rnd() * 26}px;--d:${d}s;--dl:${-rnd() * 8}s`; }
      el.appendChild(p);
    }
    return el;
  }
  // Doppelblitz ab Schlag `at` (gewitter) – höchstens 2 Blitze in 4 s
  const blitz = (b, at, stark = .75) => { const d = b - at; return d < 0 ? 0 : Math.exp(-d * 14) * stark + (d > .18 ? Math.exp(-(d - .18) * 16) * stark * .5 : 0); };

  // Schlusstafel: Datum, Titel, Zeile mit DJ, Ort/Zeit – passt sich der Textlänge an
  function ende(parent, top, { datumPx = 240, titelPx = 130 } = {}) {
    const box = document.createElement("div"); box.className = "ende"; box.style.top = top + "px"; parent.appendChild(box);
    const datum = textBlock(box, "display ende-datum", D.datum, { maxPx: datumPx, zweizeilig: false });
    const titel = textBlock(box, "display ende-titel", D.titel, { maxPx: titelPx, minPx: 64 });
    const by = document.createElement("p"); by.className = "ende-by"; by.textContent = D.byline ? (D.byline_mit ? "mit " + D.byline : D.byline) : ""; box.appendChild(by);
    const ort = document.createElement("p"); ort.className = "mono ende-ort"; ort.textContent = D.infozeile; box.appendChild(ort);
    return { box, datum, titel, by, ort };
  }
  function endeZeigen(e, b, at, pmp) {
    set(e.box, { display: b >= at - .05 ? "block" : "none" });
    const p1 = prog(b, at, .22), p2 = prog(b, at + 1, .25), p3 = prog(b, at + 2, .35, "out"), p4 = prog(b, at + 2.5, .35, "out");
    set(e.datum, { opacity: p1, transform: `scale(${(1 + (1 - p1) * .55) * (1 + (b >= at ? pmp * .04 : 0))})` });
    set(e.titel, { opacity: p2, transform: `translateY(${(1 - p2) * 70}px)` });
    set(e.by, { opacity: p3 });
    set(e.ort, { opacity: p4, letterSpacing: (.3 - .14 * p4) + "em" });
  }
  // Flyer-Element (Seitenverhältnis aus den Daten)
  function flyer(parent, src = D.flyer) { const img = document.createElement("img"); img.className = "flyer"; img.src = src; img.alt = ""; parent.appendChild(img); return img; }

  if (D.hilfslinien) document.addEventListener("DOMContentLoaded", () => document.querySelector(".stage")?.classList.add("hilfslinien"));
  return { D, clamp, ease, track, prog, pulse, energy, pump, set, $, letters, fit, zweiZeilen, textBlock, atmo, blitz, ende, endeZeigen, flyer };
})();
