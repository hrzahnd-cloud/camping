/*
 * Erfundene Testdaten für die Nebensaison: ab morgen bis Mitte Dezember –
 * nur für die Testumgebung. Zum Ausprobieren von Anreise, Check-in, Abreise
 * und «nicht angereist» im Alltag.
 *
 * Erzeugt über die normale API (wie die Oberfläche):
 *  - einige Gäste, die schon da sind (Aufenthalt erfasst) und in den
 *    nächsten Tagen abreisen;
 *  - akzeptierte Reservationen mit Anreise ab morgen bis 15. Dezember,
 *    Nebensaison-Belegung (ca. 6–16 Plätze, am Wochenende mehr), dazu
 *    einzelne Wintercamper mit langem Aufenthalt, Zwärgli und Spycher;
 *  - je Reservation die Belege (Antwort mit Anzahlung, gutgeschriebene
 *    Zahlung – teils in Euro bezahlt, teils TWINT –, Bestätigung), Stammgäste
 *    ohne Anzahlung;
 *  - kurzfristige Anfragen, die noch auf die Anzahlung warten, und offene
 *    Anfragen in verschiedenen Stadien.
 *
 * Vorher werden frühere Test-Anfragen mit Datum im November/Dezember 2026
 * entfernt (nur Adressen @example.com/.org/.net; Juli 2027 bleibt).
 *
 * Alle Gäste sind erfunden, alle Adressen enden auf example.com/.org/.net.
 *
 *   node scripts/testdaten_nebensaison.js http://127.0.0.1:8000            # erzeugen
 *   node scripts/testdaten_nebensaison.js http://127.0.0.1:8000 --loeschen # entfernen
 *
 * Im Browser (Konsole der Testseite): Datei einfügen, dann
 *   await nebensaisonErzeugen("")   bzw.   await nebensaisonLoeschen("")
 */

const NS_TESTDOMAIN = /@example\.(com|org|net)$/i;
const NS_ENDE = "2026-12-15";

function nsZufall(seed) { // mulberry32
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const NS_NAMEN = {
  de: { v: ["Anna", "Lukas", "Mia", "Jonas", "Lea", "Noah", "Laura", "Elias", "Sarah", "Tim", "Nina", "Felix", "Julia", "Urs", "Sophie", "Simon", "Lena", "Beat", "Eva", "Reto", "Ruedi", "Monika"],
    n: ["Brunner", "Keller", "Huber", "Meier", "Schmid", "Graf", "Frei", "Baumann", "Wyss", "Zürcher", "Kunz", "Roth", "Steiner", "Lehmann", "Moser", "Bühler", "Gerber", "Hofer", "Sutter", "Vogel", "Aebi", "Imhof"] },
  fr: { v: ["Camille", "Louis", "Chloé", "Hugo", "Manon", "Lucas", "Léa", "Théo", "Inès", "Jules"],
    n: ["Martin", "Bernard", "Dubois", "Moreau", "Laurent", "Girard", "Rochat", "Favre", "Perret", "Meylan"] },
  it: { v: ["Giulia", "Marco", "Sofia", "Luca", "Chiara", "Matteo"],
    n: ["Rossi", "Bianchi", "Ferrari", "Romano", "Bernasconi", "Galli"] },
  en: { v: ["Emma", "James", "Daan", "Sanne", "Sven", "Femke", "Oliver", "Jens"],
    n: ["Smith", "Taylor", "de Vries", "Jansen", "Bakker", "Visser", "Peeters", "Hansen"] },
};
const NS_LAND = { de: ["CH", "CH", "CH", "DE", "DE", "AT"], fr: ["CH", "FR", "FR", "BE"], it: ["CH", "IT"], en: ["NL", "NL", "GB", "DK", "BE"] };
const NS_DOMAINS = ["example.com", "example.org", "example.net"];
const NS_FRAGEN = ["Ist der Platz im Winter geöffnet und gibt es Strom?", "Sind Hunde erlaubt?", "Gibt es warme Duschen im Winter?",
  "Können wir ein paar Tage früher abreisen, falls Schnee kommt?", "Hat es Gasflaschen zu kaufen?", "Wie weit ist das nächste Skigebiet?"];
const NS_FREIE_ANTWORT = "Vielen Dank für Ihre Frage. Gerne bestätigen wir: das ist bei uns möglich. Melden Sie sich bei Fragen jederzeit.";
const NS_KURS_EUR_CHF = 0.935;

const nsIso = (d) => d.toISOString().slice(0, 10);
const nsPlus = (d, n) => { const x = new Date(d); x.setUTCDate(x.getUTCDate() + n); return x; };
const nsTag = (s) => new Date(`${s}T00:00:00Z`);
const nsNaechte = (a, b) => Math.round((nsTag(b) - nsTag(a)) / 86400000);

function nsApi(basis) {
  const aufruf = async (methode, pfad, daten) => {
    const r = await fetch(basis + pfad, { method: methode, headers: daten ? { "Content-Type": "application/json" } : undefined,
      body: daten ? JSON.stringify(daten) : undefined });
    if (!r.ok) throw new Error(`${methode} ${pfad}: ${r.status} ${await r.text()}`);
    return r.status === 204 ? null : r.json();
  };
  return { get: (p) => aufruf("GET", p), post: (p, d) => aufruf("POST", p, d), del: (p) => aufruf("DELETE", p) };
}

/** Plant die Daten (ohne API), deterministisch je Stichtag. */
function nsPlanen(heute) {
  const r = nsZufall(2611);
  const wahl = (liste) => liste[Math.floor(r() * liste.length)];
  const sprache = () => { const x = r(); return x < 0.65 ? "de" : x < 0.8 ? "fr" : x < 0.86 ? "it" : "en"; };
  let nr = 0;
  const gast = () => {
    const sp = sprache(), i = nr++;
    const v = wahl(NS_NAMEN[sp].v), n = wahl(NS_NAMEN[sp].n);
    const mail = `${v}.${n}${i}`.toLowerCase().normalize("NFD").replace(/[^a-z0-9.]/g, "");
    return { sprache: sp, vorname: v, nachname: n, name: `${v} ${n}`, land: wahl(NS_LAND[sp]),
      email: `${mail}@${wahl(NS_DOMAINS)}`, telefon: `079 555 ${String(10 + (i % 90)).padStart(2, "0")} ${String(10 + ((i * 7) % 90)).padStart(2, "0")}` };
  };
  const h = nsTag(nsIso(heute));
  const morgen = nsPlus(h, 1), ende = nsTag(NS_ENDE);
  const eingangVor = (von, minTage = 3) => { // Eingang zwischen 1. Okt. und spätestens gestern, vor der Anreise
    const start = nsTag("2026-10-01").getTime();
    const bis = Math.min(nsPlus(h, -1).getTime(), nsPlus(von, -minTage).getTime());
    const d = new Date(start + r() * Math.max(0, bis - start));
    d.setUTCHours(7 + Math.floor(r() * 12), Math.floor(r() * 60));
    return d.toISOString();
  };
  const typ = () => wahl(["zeltwiese", "wohnwagen", "wohnwagen", "wohnwagen", "camper", "camper", "camper", "camper"]);
  const personen = () => ({ e: wahl([1, 2, 2, 2, 2, 3, 4]), k: wahl([0, 0, 0, 0, 1, 2]) });

  const plan = [];
  const belegt = {};
  const belegen = (von, bis) => { for (let d = nsTag(von); d < nsTag(bis); d = nsPlus(d, 1)) belegt[nsIso(d)] = (belegt[nsIso(d)] || 0) + 1; };

  // 1) schon da: Aufenthalt erfasst, Abreise in den nächsten Tagen
  [[-3, 4], [-2, 3], [-2, 5], [-1, 2], [-1, 4], [-4, 6]].forEach(([ab, bisTag]) => {
    const von = nsPlus(h, ab), bis = nsPlus(h, bisTag);
    const t = typ();
    plan.push({ ...gast(), ...personen(), von: nsIso(von), bis: nsIso(bis), typ: t, ziel: "eingecheckt",
      eingang: eingangVor(von, 5), platz: String(3 + plan.length * 4) });
    belegen(nsIso(von), nsIso(bis));
  });
  // 2) Wintercamper: lange Aufenthalte, oft Stammgäste
  [[1, 21], [2, 30], [5, 14], [9, 26], [17, 18]].forEach(([ab, n]) => {
    const von = nsPlus(h, ab);
    if (von > ende) return;
    plan.push({ ...gast(), e: 2, k: 0, von: nsIso(von), bis: nsIso(nsPlus(von, n)), typ: wahl(["wohnwagen", "camper"]),
      ziel: "akzeptiert", eingang: eingangVor(von, 10), stammgast: r() < 0.6 });
    belegen(nsIso(von), nsIso(nsPlus(von, n)));
  });
  // 3) Stellplätze auffüllen: Nebensaison, Wochenende mehr
  const ziel = (d) => {
    const wt = d.getUTCDay(); // 5 = Fr, 6 = Sa
    const basis = d < nsTag("2026-12-01") ? 10 : 7;
    return basis + (wt === 5 || wt === 6 ? 5 : 0) + Math.round((r() - 0.5) * 3);
  };
  for (let d = morgen; d <= ende; d = nsPlus(d, 1)) {
    let neu = 0;
    while ((belegt[nsIso(d)] || 0) < ziel(d) && neu < 7) {
      const wt = d.getUTCDay();
      const n = wt === 5 ? wahl([2, 2, 3]) : wt === 6 ? wahl([1, 1, 2]) : wahl([1, 2, 2, 3, 3, 4, 5, 7]);
      const bis = nsPlus(d, n);
      plan.push({ ...gast(), ...personen(), von: nsIso(d), bis: nsIso(bis), typ: typ(), ziel: "akzeptiert", eingang: eingangVor(d) });
      belegen(nsIso(d), nsIso(bis));
      neu++;
    }
  }
  // 4) Zwärgli (4) und Spycher (3): vor allem Wochenenden
  for (let d = morgen; d <= ende; d = nsPlus(d, 1)) {
    const wt = d.getUTCDay();
    const anzahl = wt === 5 ? 2 + Math.floor(r() * 3) : wt === 2 || wt === 3 ? (r() < 0.4 ? 1 : 0) : 0;
    for (let j = 0; j < anzahl; j++) {
      const n = wt === 5 ? 2 : wahl([2, 3]);
      plan.push({ ...gast(), e: 2, k: wahl([0, 0, 1, 2]), von: nsIso(d), bis: nsIso(nsPlus(d, n)),
        typ: j % 2 ? "spycher" : "zwaergli", ziel: "akzeptiert", eingang: eingangVor(d) });
    }
  }
  // 5) kurzfristig, Anzahlung noch ausstehend (zählt noch nicht zur Belegung)
  [[1, 2], [2, 3], [3, 2], [6, 4]].forEach(([ab, n]) => {
    const von = nsPlus(h, ab);
    plan.push({ ...gast(), ...personen(), von: nsIso(von), bis: nsIso(nsPlus(von, n)), typ: typ(), ziel: "erstantwort_gesendet",
      eingang: nsIso(nsPlus(h, -1 - (ab % 2))) + "T09:30:00Z" });
  });
  // 6) offene Anfragen, Absagen, Stornos
  const offen = ["neu", "neu", "neu", "neu", "unvollstaendig", "unvollstaendig", "in_abklaerung", "in_abklaerung",
    "erstantwort_gesendet", "erstantwort_gesendet", "erstantwort_gesendet", "abgelehnt", "storniert", "storniert"];
  offen.forEach((z, j) => {
    const von = nsPlus(h, 2 + Math.floor(r() * (nsNaechte(nsIso(h), NS_ENDE) - 3)));
    const eingang = z === "neu" ? (j < 2 ? nsIso(h) + `T0${7 + j}:15:00Z` : eingangVor(von, 2)) : eingangVor(von);
    plan.push({ ...gast(), ...personen(), von: nsIso(von), bis: nsIso(nsPlus(von, wahl([2, 3, 4, 7]))), typ: typ(), ziel: z, eingang });
  });

  for (const p of plan) {
    p.frage = p.frage ?? (r() < 0.15 || p.ziel === "in_abklaerung" ? wahl(NS_FRAGEN) : null);
    p.stammgast = p.stammgast ?? (["akzeptiert", "eingecheckt"].includes(p.ziel) && r() < 0.15);
    const lang = nsNaechte(p.von, p.bis);
    p.anzahlung = ["zwaergli", "spycher"].includes(p.typ) ? (lang > 3 ? 150 : 100) : (lang > 3 ? 100 : 50);
    p.euro = ["de", "fr", "en"].includes(p.sprache) && p.land !== "CH" && r() < 0.6;
    p.twint = !p.euro && r() < 0.3;
    p.quelle = r() < 0.7 ? "homepage_formular" : "email";
  }
  return plan;
}

async function nsAltesEntfernen(a, log) {
  const alle = (await a.get("/reservationsanfragen")).filter((x) => NS_TESTDOMAIN.test(x.gast_email || "")
    && x.gewuenscht_von && x.gewuenscht_von < "2027-01-01");
  for (const x of alle) {
    const d = await a.get(`/reservationsanfragen/${x.id}`);
    if (d.buchung_id) await a.del(`/aufenthalte/${d.buchung_id}`);
    await a.del(`/reservationsanfragen/${x.id}`);
  }
  log(`${alle.length} frühere Test-Anfragen (Nov./Dez. 2026) entfernt.`);
  return alle.length;
}

async function nebensaisonErzeugen(basis = "", { log = console.log, heute = new Date() } = {}) {
  const a = nsApi(basis);
  await nsAltesEntfernen(a, log);
  const plan = nsPlanen(heute);
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
      const text = typ === "freie_antwort" ? e.text.slice(0, e.einfuege_position) + NS_FREIE_ANTWORT + "\n\n" + e.text.slice(e.einfuege_position) : e.text;
      return a.post(`${url}/antwort/gesendet`, { vorlage_id: e.vorlage_id, betreff: e.betreff, text, betrag: extra.betrag ?? null });
    };
    const akzeptiert = ["akzeptiert", "eingecheckt", "storniert"].includes(p.ziel);
    if (["neu", "unvollstaendig"].includes(p.ziel)) { /* noch nicht beantwortet */ }
    else if (p.ziel === "abgelehnt") {
      await senden("freie_antwort");
      await a.post(`${url}/status`, { status: "abgelehnt" });
    } else {
      if (p.frage) await senden("freie_antwort");
      if (p.ziel !== "in_abklaerung") {
        if (p.stammgast && akzeptiert) {
          await a.post(`${url}/zahlung-bestaetigen`, {});
        } else {
          await senden("erstantwort_zahlungsinfo", { betrag: String(p.anzahlung) });
          if (akzeptiert) {
            const betrag = p.euro ? (p.anzahlung * NS_KURS_EUR_CHF).toFixed(2) : String(p.anzahlung);
            const ein = new Date(Math.min(heute.getTime() - 86400000, new Date(p.eingang).getTime() + (2 + n % 5) * 86400000));
            await a.post(`${url}/zahlung-bestaetigen`, { betrag, zahlungsart: p.twint ? "twint" : "bankueberweisung",
              eingegangen_am: ein.toISOString().slice(0, 10) });
          }
        }
        if (akzeptiert) await senden("bestaetigung_definitiv");
        if (p.ziel === "storniert") await a.post(`${url}/status`, { status: "storniert" });
        if (p.ziel === "eingecheckt") {
          await a.post("/aufenthalte", { reservationsanfrage_id: anfrage.id, vorname: p.vorname, nachname: p.nachname,
            nationalitaet: p.land, land: p.land, stellplatz_typ: p.typ, platz: p.platz, von: p.von, bis: p.bis,
            anzahl_erwachsene: p.e, anzahl_kinder: p.k });
        }
      }
    }
    zaehler[p.ziel] = (zaehler[p.ziel] || 0) + 1;
    if (++n % 25 === 0) log(`… ${n} von ${plan.length}`);
  }
  log("Fertig:", JSON.stringify(zaehler));
  return zaehler;
}

async function nebensaisonLoeschen(basis = "", { log = console.log } = {}) {
  return nsAltesEntfernen(nsApi(basis), log);
}

if (typeof module !== "undefined" && require.main === module) {
  const [basis, schalter] = process.argv.slice(2);
  if (!basis) { console.error("Aufruf: node scripts/testdaten_nebensaison.js <basis-url> [--loeschen]"); process.exit(2); }
  (schalter === "--loeschen" ? nebensaisonLoeschen(basis) : nebensaisonErzeugen(basis))
    .catch((e) => { console.error(e.message); process.exit(1); });
}
if (typeof module !== "undefined") module.exports = { nsPlanen, nebensaisonErzeugen, nebensaisonLoeschen };
