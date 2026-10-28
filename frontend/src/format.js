export const TYPEN = [
  { code: "zeltwiese", name: "Zelt" },
  { code: "wohnwagen", name: "Wohnwagen" },
  { code: "camper", name: "Camper" },
  { code: "zwaergli", name: "Zwärgli" },
  { code: "spycher", name: "Spycher" },
];
export const typName = (code) => TYPEN.find((t) => t.code === code)?.name ?? "ohne Typ";

export const STATUS = {
  neu: { name: "Neu", ton: "info" },
  unvollstaendig: { name: "Angaben fehlen", ton: "warnung" },
  geprueft_vollstaendig: { name: "Vollständig", ton: "info" },
  erstantwort_gesendet: { name: "Antwort gesendet", ton: "offen" },
  zahlung_ausstehend: { name: "Zahlung ausstehend", ton: "offen" },
  bezahlt_akzeptiert: { name: "Akzeptiert", ton: "ok" },
  abgelehnt: { name: "Abgelehnt", ton: "aus" },
  storniert: { name: "Storniert", ton: "aus" },
};
export const statusName = (s) => STATUS[s]?.name ?? s;

export const FEHLEND = {
  gast_email: "E-Mail-Adresse",
  zeitraum: "Zeitraum",
  zeitraum_ungueltig: "Abreise muss nach der Anreise liegen",
  stellplatz_typ: "Stellplatz-Typ",
  anzahl_erwachsene: "mindestens 1 erwachsene Person",
};
export const fehlendText = (liste) =>
  (liste || "").split(",").filter(Boolean).map((f) => FEHLEND[f] ?? f).join(", ");

export const SPRACHEN = { de: "Deutsch", fr: "Französisch", it: "Italienisch", en: "Englisch" };
export const QUELLEN = { email: "E-Mail", homepage_formular: "Homepage", manuell: "Manuell / Telefon" };

const tagMonat = new Intl.DateTimeFormat("de-CH", { day: "numeric", month: "short" });
const voll = new Intl.DateTimeFormat("de-CH", { day: "2-digit", month: "2-digit", year: "numeric" });
export const ausIso = (iso) => (iso ? new Date(`${iso}T00:00:00`) : null);
export const datumKurz = (iso) => (iso ? tagMonat.format(ausIso(iso)) : "–");
export const datumVoll = (iso) => (iso ? voll.format(ausIso(iso)) : "–");
// Jahr nur anzeigen, wenn es nicht das laufende ist (z.B. Anfragen für die nächste Saison)
const mitJahr = (iso) => (iso && Number(iso.slice(0, 4)) !== new Date().getFullYear() ? ` ${iso.slice(0, 4)}` : "");
export const zeitraum = (von, bis) => (von && bis ? `${datumKurz(von)} – ${datumKurz(bis)}${mitJahr(bis)}` : "Zeitraum fehlt");
export const naechte = (von, bis) => (von && bis ? Math.round((ausIso(bis) - ausIso(von)) / 86400000) : null);
export const personen = (e, k) => `${e ?? 0} E / ${k ?? 0} K`;

export const isoDatum = (d) => {
  const z = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
};
export const plusTage = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
