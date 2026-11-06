/*
 * Erfundene Testdaten für Juli 2027 (Hochsaison) – nur für die Testumgebung.
 *
 * Erzeugt über die normale API (wie die Oberfläche):
 *  - akzeptierte Reservationen, bis an die 50 Stellplätze (Zelt/Wohnwagen/Camper)
 *    mit Mitte Juli mehreren Nächten ab 45 und einzelnen ausgebuchten Nächten,
 *    dazu Zwärgli und Spycher;
 *  - je Reservation die «Belege»: Antwort mit Anzahlung, gutgeschriebene Zahlung
 *    (teils in Euro bezahlt, also krumme CHF-Beträge, teils TWINT), Bestätigung;
 *    einzelne Stammgäste ohne Anzahlung, einzelne mit freier Antwort vorab;
 *  - offene Anfragen in verschiedenen Stadien, einige Absagen/Stornos;
 *  - einige Reservationen um heute, um Check-in und «nicht angereist» zu testen.
 *
 * Alle Gäste sind erfunden, alle Adressen enden auf example.com/.org/.net
 * (reservierte Domains). Damit lassen sich die Testdaten wieder entfernen:
 *
 *   node scripts/testdaten_juli2027.js http://127.0.0.1:8000            # erzeugen
 *   node scripts/testdaten_juli2027.js http://127.0.0.1:8000 --loeschen # entfernen
 *
 * Im Browser (Konsole der Testseite): Datei einfügen, dann
 *   await testdatenErzeugen("")   bzw.   await testdatenLoeschen("")
 */

const TESTDOMAIN = /@example\.(com|org|net)$/i;

function zufall(seed) { // mulberry32, damit jeder Lauf dieselben Daten ergibt
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const NAMEN = {
  de: { v: ["Anna", "Lukas", "Mia", "Jonas", "Lea", "Noah", "Laura", "Elias", "Sarah", "Tim", "Nina", "Felix", "Julia", "David", "Sophie", "Simon", "Lena", "Marco", "Eva", "Reto"],
    n: ["Brunner", "Keller", "Huber", "Meier", "Schmid", "Graf", "Frei", "Baumann", "Wyss", "Zürcher", "Kunz", "Roth", "Steiner", "Lehmann", "Moser", "Bühler", "Gerber", "Hofer", "Sutter", "Vogel"] },
  fr: { v: ["Camille", "Louis", "Chloé", "Hugo", "Manon", "Lucas", "Léa", "Théo", "Inès", "Jules"],
    n: ["Martin", "Bernard", "Dubois", "Moreau", "Laurent", "Girard", "Rochat", "Favre", "Perret", "Meylan"] },
  it: { v: ["Giulia", "Marco", "Sofia", "Luca", "Chiara", "Matteo", "Elena", "Andrea"],
    n: ["Rossi", "Bianchi", "Ferrari", "Romano", "Colombo", "Bernasconi", "Galli", "Fontana"] },
  en: { v: ["Emma", "James", "Olivia", "Daan", "Sanne", "Liam", "Ruth", "Sven", "Femke", "Oliver"],
    n: ["Smith", "Taylor", "de Vries", "Jansen", "Bakker", "Walker", "Visser", "Hughes", "Peeters", "Evans"] },
};
const DOMAINS = ["example.com", "example.org", "example.net"];
const FRAGEN = ["Sind Hunde erlaubt?", "Was kosten die Duschen?", "Gibt es eine ÖV-Verbindung in der Nähe?", "Können wir einen Platz mit Seesicht haben?",
  "Hat es einen Laden auf dem Platz?", "Dürfen wir ein zweites Zelt mitbringen?"];
const FREIE_ANTWORT = "Vielen Dank für Ihre Frage. Gerne bestätigen wir: das ist bei uns möglich. Melden Sie sich bei Fragen jederzeit.";

const iso = (d) => d.toISOString().slice(0, 10);
const plus = (d, n) => { const x = new Date(d); x.setUTCDate(x.getUTCDate() + n); return x; };
const tag = (s) => new Date(`${s}T00:00:00Z`);

function api(basis) {
  const aufruf = async (methode, pfad, daten) => {
    const r = await fetch(basis + pfad, { method: methode, headers: daten ? { "Content-Type": "application/json" } : undefined,
      body: daten ? JSON.stringify(daten) : undefined });
    if (!r.ok) throw new Error(`${methode} ${pfad}: ${r.status} ${await r.text()}`);
    return r.status === 204 ? null : r.json();
  };
  return { get: (p) => aufruf("GET", p), post: (p, d) => aufruf("POST", p, d), del: (p) => aufruf("DELETE", p) };
}

/** Plant die Reservationen (ohne API), deterministisch. */
function planen(heute) {
  const r = zufall(2027);
  const wahl = (liste) => liste[Math.floor(r() * liste.length)];
  const sprache = () => { const x = r(); return x < 0.6 ? "de" : x < 0.75 ? "fr" : x < 0.82 ? "it" : "en"; };
  const gast = (i) => {
    const sp = sprache();
    const v = wahl(NAMEN[sp].v), n = wahl(NAMEN[sp].n);
    const mail = `${v}.${n}${i}`.toLowerCase().normalize("NFD").replace(/[^a-z0-9.]/g, "");
    return { sprache: sp, name: `${v} ${n}`, email: `${mail}@${wahl(DOMAINS)}`, telefon: `079 555 ${String(10 + (i % 90)).padStart(2, "0")} ${String(10 + ((i * 7) % 90)).padStart(2, "0")}` };
  };
  const eingang = () => { // Eingang zwischen 1. Sept. 2026 und gestern
    const start = tag("2026-09-01").getTime(), ende = plus(heute, -1).getTime();
    const d = new Date(start + r() * (ende - start));
    d.setUTCHours(7 + Math.floor(r() * 13), Math.floor(r() * 60));
    return d.toISOString();
  };

  // Ziel-Belegung der Stellplätze je Nacht: Anfang Juli ~30, Mitte Juli 45–50, Ende ~36
  const ziel = (d) => {
    const t = (d - tag("2027-07-01")) / 86400000; // 0..30
    if (t < 0) return 22;
    const kurve = 31 + 18 * Math.sin(Math.PI * Math.min(1, Math.max(0, (t - 2) / 27)));
    return Math.min(50, Math.round(kurve + (r() - 0.5) * 3));
  };
  const plan = [];
  const belegt = {}; // Stellplätze je Nacht
  const naechte = (von, n) => Array.from({ length: n }, (_, i) => iso(plus(von, i)));
  let i = 0;
  for (let d = tag("2027-06-27"); d <= tag("2027-07-31"); d = plus(d, 1)) {
    while ((belegt[iso(d)] || 0) < ziel(d)) {
      const n = wahl([2, 2, 3, 3, 4, 5, 5, 6, 7, 7, 8, 10, 14]);
      const nachtListe = naechte(d, n);
      if (nachtListe.some((x) => (belegt[x] || 0) >= 50)) break;
      nachtListe.forEach((x) => { belegt[x] = (belegt[x] || 0) + 1; });
      const typ = wahl(["zeltwiese", "zeltwiese", "wohnwagen", "wohnwagen", "wohnwagen", "camper", "camper", "camper"]);
      plan.push({ ...gast(i++), von: iso(d), bis: iso(plus(d, n)), typ, ziel: "akzeptiert", eingang: eingang(),
        e: wahl([1, 2, 2, 2, 2, 3, 4]), k: wahl([0, 0, 0, 1, 2, 2, 3]) });
    }
  }
  // Zwärgli (4) und Spycher (3): separat
  for (const [typ, anzahl] of [["zwaergli", 4], ["spycher", 3]]) {
    for (let platz = 0; platz < anzahl; platz++) {
      let d = plus(tag("2027-07-01"), Math.floor(r() * 3));
      while (d < tag("2027-07-29")) {
        const n = wahl([2, 3, 3, 4, 7]);
        if (r() < 0.85) plan.push({ ...gast(i++), von: iso(d), bis: iso(plus(d, n)), typ, ziel: "akzeptiert", eingang: eingang(), e: 2, k: wahl([0, 1, 2]) });
        d = plus(d, n + Math.floor(r() * 2));
      }
    }
  }
  // offene Anfragen und Absagen für Juli
  const offen = ["neu", "neu", "neu", "unvollstaendig", "unvollstaendig", "in_abklaerung", "in_abklaerung", "in_abklaerung",
    "erstantwort_gesendet", "erstantwort_gesendet", "erstantwort_gesendet", "erstantwort_gesendet", "erstantwort_gesendet",
    "abgelehnt", "abgelehnt", "storniert", "storniert", "storniert"];
  for (let j = 0; j < 30; j++) {
    const d = plus(tag("2027-07-01"), Math.floor(r() * 28));
    plan.push({ ...gast(i++), von: iso(d), bis: iso(plus(d, wahl([2, 3, 4, 5, 7]))), typ: wahl(["zeltwiese", "wohnwagen", "camper", "camper"]),
      ziel: offen[j % offen.length], eingang: eingang(), e: wahl([1, 2, 2, 3]), k: wahl([0, 0, 1, 2]) });
  }
  // um heute: Check-in und «nicht angereist» ausprobieren
  const h = tag(iso(heute));
  [[-2, 4], [-1, 3], [-1, 2], [0, 3], [0, 5], [0, 2], [1, 3]].forEach(([ab, n]) => {
    plan.push({ ...gast(i++), von: iso(plus(h, ab)), bis: iso(plus(h, ab + n)), typ: wahl(["zeltwiese", "wohnwagen", "camper"]),
      ziel: "akzeptiert", eingang: iso(plus(h, -20)) + "T10:00:00Z", e: 2, k: wahl([0, 1]), nebensaison: true });
  });

  // Ausprägungen der Belege
  for (const p of plan) {
    p.frage = r() < 0.2 ? wahl(FRAGEN) : null;
    p.stammgast = p.ziel === "akzeptiert" && r() < 0.1;
    const lang = (tag(p.bis) - tag(p.von)) / 86400000;
    p.anzahlung = ["zwaergli", "spycher"].includes(p.typ) ? (lang > 3 ? 150 : 100) : (lang > 3 ? 100 : 50);
    p.euro = r() < 0.25;
    p.twint = !p.euro && r() < 0.2;
    p.bestaetigt = r() < 0.85;
    p.quelle = r() < 0.7 ? "homepage_formular" : "email";
  }
  return plan;
}

const KURS_EUR_CHF = 0.935;

async function testdatenErzeugen(basis = "", { log = console.log, heute = new Date() } = {}) {
  const a = api(basis);
  const plan = planen(heute);
  log(`${plan.length} Anfragen werden erzeugt …`);
  const zaehler = {};
  let n = 0;
  for (const p of plan) {
    const anfrage = await a.post("/reservationsanfragen", {
      quelle: p.quelle, eingangs_datum: p.eingang, sprache: p.sprache, gast_name: p.name, gast_email: p.email,
      gast_telefon: p.telefon, gewuenscht_von: p.von, gewuenscht_bis: p.bis,
      stellplatz_typ: p.ziel === "unvollstaendig" ? null : p.typ, anzahl_erwachsene: p.e, anzahl_kinder: p.k,
      bemerkung: p.frage, newsletter_einwilligung: false,
    });
    const url = `/reservationsanfragen/${anfrage.id}`;
    const senden = async (typ, extra = {}) => {
      const e = await a.post(`${url}/antwort/vorbereiten`, { typ, sprache: p.sprache, ...extra });
      const text = typ === "freie_antwort" ? e.text.slice(0, e.einfuege_position) + FREIE_ANTWORT + "\n\n" + e.text.slice(e.einfuege_position) : e.text;
      return a.post(`${url}/antwort/gesendet`, { vorlage_id: e.vorlage_id, betreff: e.betreff, text, betrag: extra.betrag ?? null });
    };
    if (["neu", "unvollstaendig"].includes(p.ziel)) { /* nichts beantwortet */ }
    else if (p.ziel === "abgelehnt") {
      await senden("freie_antwort");
      await a.post(`${url}/status`, { status: "abgelehnt" });
    } else {
      if (p.frage || p.ziel === "in_abklaerung") await senden("freie_antwort");
      if (p.ziel !== "in_abklaerung") {
        if (p.stammgast) {
          await a.post(`${url}/zahlung-bestaetigen`, {});
        } else {
          await senden("erstantwort_zahlungsinfo", { betrag: String(p.anzahlung) });
          if (["akzeptiert", "storniert"].includes(p.ziel)) {
            const betrag = p.euro ? (p.anzahlung * KURS_EUR_CHF).toFixed(2) : String(p.anzahlung);
            const eingang = new Date(Math.min(Date.now() - 86400000, new Date(p.eingang).getTime() + (3 + n % 9) * 86400000));
            await a.post(`${url}/zahlung-bestaetigen`, { betrag, zahlungsart: p.twint ? "twint" : "bankueberweisung",
              eingegangen_am: eingang.toISOString().slice(0, 10) });
          }
        }
        if (["akzeptiert", "storniert"].includes(p.ziel) && (p.bestaetigt || p.nebensaison)) await senden("bestaetigung_definitiv");
        if (p.ziel === "storniert") await a.post(`${url}/status`, { status: "storniert" });
      }
    }
    zaehler[p.ziel] = (zaehler[p.ziel] || 0) + 1;
    if (++n % 25 === 0) log(`… ${n} von ${plan.length}`);
  }
  log("Fertig:", JSON.stringify(zaehler));
  return zaehler;
}

async function testdatenLoeschen(basis = "", { log = console.log } = {}) {
  const a = api(basis);
  const anfragen = (await a.get("/reservationsanfragen")).filter((x) => TESTDOMAIN.test(x.gast_email));
  let n = 0;
  for (const x of anfragen) {
    const d = await a.get(`/reservationsanfragen/${x.id}`);
    if (d.buchung_id) await a.del(`/aufenthalte/${d.buchung_id}`);
    await a.del(`/reservationsanfragen/${x.id}`);
    n++;
  }
  log(`${n} Test-Anfragen gelöscht (Adressen @example.com/.org/.net).`);
  return n;
}

if (typeof module !== "undefined" && require.main === module) {
  const [basis, schalter] = process.argv.slice(2);
  if (!basis) { console.error("Aufruf: node scripts/testdaten_juli2027.js <basis-url> [--loeschen]"); process.exit(2); }
  (schalter === "--loeschen" ? testdatenLoeschen(basis) : testdatenErzeugen(basis))
    .catch((e) => { console.error(e.message); process.exit(1); });
}
if (typeof module !== "undefined") module.exports = { planen, testdatenErzeugen, testdatenLoeschen };
