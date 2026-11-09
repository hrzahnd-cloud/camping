// Modul «Auswertungen»: Einnahmen & MWST (nach Zahlungseingang), Übernachtungen & Taxen
// (nach Nacht, Kontrolle zu Feratel), Saison-Zusammenstellung für die Buchhaltung (Excel/PDF).
import { useEffect, useMemo, useState } from "react";
import { FileSpreadsheet, FileText } from "lucide-react";
import { api } from "../api.js";
import { datumVoll } from "../format.js";

const REGISTER = [
  { code: "einnahmen", name: "Einnahmen & MWST" },
  { code: "uebernachtungen", name: "Übernachtungen & Taxen" },
  { code: "saison", name: "Saison (Buchhaltung)" },
];
const zahl = (x) => Number(x || 0).toLocaleString("de-CH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const ganz = (x) => Number(x || 0).toLocaleString("de-CH");
const TYP = { zeltwiese: "Zelt", wohnwagen: "Wohnwagen", camper: "Camper", zwaergli: "Zwärgli", spycher: "Spycher" };

function Veraenderung({ jetzt, vorher }) {
  const a = Number(jetzt || 0), b = Number(vorher || 0);
  if (!b && !a) return <span className="leise">–</span>;
  if (!b) return <span className="leise">neu</span>;
  const p = Math.round(((a - b) / b) * 100);
  return <span className={p >= 0 ? "plus" : "minus"}>{p > 0 ? "+" : ""}{p} %</span>;
}

function Balken({ wert, max, vergleich }) {
  const w = max ? Math.max(0, (Number(wert) / max) * 100) : 0;
  const v = max && vergleich !== undefined ? Math.max(0, (Number(vergleich) / max) * 100) : null;
  return (
    <span className="balken" aria-hidden="true">
      <span className="jetzt" style={{ width: `${w}%` }} />
      {v !== null && <span className="vorher" style={{ width: `${v}%` }} />}
    </span>
  );
}

export default function Auswertungen() {
  const [jahre, setJahre] = useState(null);
  const [jahr, setJahr] = useState(null);
  const [vergleich, setVergleich] = useState("");
  const [register, setRegister] = useState("einnahmen");
  const [daten, setDaten] = useState(null);
  const [fehler, setFehler] = useState(null);

  useEffect(() => {
    api.get("/auswertungen/jahre").then((j) => {
      setJahre(j);
      const aktuell = j.includes(new Date().getFullYear()) ? new Date().getFullYear() : j[j.length - 1];
      setJahr(aktuell); setVergleich(String(aktuell - 1));
    }).catch((e) => setFehler(e.message));
  }, []);

  useEffect(() => {
    if (!jahr) return;
    setDaten(null); setFehler(null);
    const v = vergleich ? `&vergleich=${vergleich}` : "";
    const pfad = register === "saison" ? `/auswertungen/saison?jahr=${jahr}` : `/auswertungen/${register}?jahr=${jahr}${v}`;
    // Daten mit ihrem Register merken: nie eine Ansicht mit den Daten eines anderen Registers zeichnen
    api.get(pfad).then((d) => setDaten({ register, d })).catch((e) => setFehler(e.message));
  }, [jahr, vergleich, register]);

  const vergleichsJahre = useMemo(() => {
    if (!jahr) return [];
    const liste = new Set([...(jahre || []), jahr - 1, jahr - 2]);
    return [...liste].filter((j) => j !== jahr).sort((a, b) => b - a);
  }, [jahre, jahr]);

  return (
    <div className="seite auswertungen">
      <header className="kopf">
        <h1>Auswertungen</h1>
        {jahr && (
          <div className="aktionen">
            <label className="kompakt">Jahr
              <select value={jahr} onChange={(e) => { const j = Number(e.target.value); setJahr(j); setVergleich(String(j - 1)); }}>
                {(jahre || []).map((j) => <option key={j} value={j}>{j}</option>)}
              </select>
            </label>
            {register !== "saison" && (
              <label className="kompakt">Vergleich
                <select value={vergleich} onChange={(e) => setVergleich(e.target.value)}>
                  <option value="">ohne</option>
                  {vergleichsJahre.map((j) => <option key={j} value={j}>{j}</option>)}
                </select>
              </label>
            )}
          </div>
        )}
      </header>
      <div className="ablagen" role="tablist" aria-label="Auswertung">
        {REGISTER.map((r) => (
          <button key={r.code} role="tab" aria-selected={register === r.code} onClick={() => setRegister(r.code)}>{r.name}</button>
        ))}
      </div>
      {fehler && <p className="meldung fehler">{fehler}</p>}
      {!fehler && daten?.register !== register && <p className="leer">Wird geladen …</p>}
      {daten?.register === register && register === "einnahmen" && <Einnahmen d={daten.d} vergleich={vergleich} />}
      {daten?.register === register && register === "uebernachtungen" && <Uebernachtungen d={daten.d} vergleich={vergleich} />}
      {daten?.register === register && register === "saison" && <Saison s={daten.d} />}
    </div>
  );
}

function Einnahmen({ d, vergleich }) {
  const a = d.aktuell, v = d.vergleich;
  const vm = Object.fromEntries((v?.monate || []).map((m) => [m.monat, m]));
  const zeilen = a.monate.filter((m) => Number(m.einnahmen) || Number(vm[m.monat]?.einnahmen));
  const max = Math.max(1, ...a.monate.map((m) => Number(m.einnahmen)), ...(v?.monate || []).map((m) => Number(m.einnahmen)));
  return (
    <section className="karte auswertung-karte">
      <p className="hinweis">Nach <strong>Zahlungseingang</strong> (vereinnahmtes Entgelt): Anzahlungen und Schlusszahlungen im Monat, in dem das Geld
        eingegangen ist. Eine Zahlung wird im Verhältnis ihres Rechnungstotals aufgeteilt in MWST-pflichtigen Umsatz und durchlaufende Taxen.
        «Vorläufig» sind Anzahlungen ohne Rechnung (noch nicht abgereist oder nicht erschienen), ganz als Beherbergung gerechnet.</p>
      {zeilen.length === 0 ? <p className="leer">Keine Zahlungseingänge {a.jahr}{vergleich ? ` oder ${vergleich}` : ""}.</p> : (
        <div className="tabelle-rahmen">
          <table className="auswertung">
            <thead><tr><th>Monat</th><th className="zahl">Einnahmen {a.jahr}</th>{v && <th className="zahl">{v.jahr}</th>}{v && <th className="zahl">±</th>}
              <th className="balken-spalte"><span className="sr-only">Vergleich</span></th>
              <th className="zahl">Taxen</th><th className="zahl">MWST-pflichtig</th><th className="zahl">MWST</th><th className="zahl">vorläufig</th></tr></thead>
            <tbody>
              {zeilen.map((m) => (
                <tr key={m.monat}>
                  <th scope="row">{m.name}</th>
                  <td className="zahl">{zahl(m.einnahmen)}</td>
                  {v && <td className="zahl leise">{zahl(vm[m.monat]?.einnahmen)}</td>}
                  {v && <td className="zahl"><Veraenderung jetzt={m.einnahmen} vorher={vm[m.monat]?.einnahmen} /></td>}
                  <td className="balken-spalte"><Balken wert={m.einnahmen} max={max} vergleich={v ? vm[m.monat]?.einnahmen ?? 0 : undefined} /></td>
                  <td className="zahl">{zahl(m.taxen)}</td>
                  <td className="zahl">{zahl(m.umsatz_mwst_pflichtig)}</td>
                  <td className="zahl">{zahl(m.mwst)}</td>
                  <td className="zahl leise">{Number(m.vorlaeufig) ? zahl(m.vorlaeufig) : "–"}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row">Total</th><td className="zahl">{zahl(a.total.einnahmen)}</td>
                {v && <td className="zahl leise">{zahl(v.total.einnahmen)}</td>}
                {v && <td className="zahl"><Veraenderung jetzt={a.total.einnahmen} vorher={v.total.einnahmen} /></td>}
                <td /><td className="zahl">{zahl(a.total.taxen)}</td><td className="zahl">{zahl(a.total.umsatz_mwst_pflichtig)}</td>
                <td className="zahl">{zahl(a.total.mwst)}</td><td className="zahl leise">{Number(a.total.vorlaeufig) ? zahl(a.total.vorlaeufig) : "–"}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
      <div className="kennzahlen">
        {a.total.saetze.map((s) => (
          <div key={s.satz}><span>MWST {s.satz} % auf {zahl(s.brutto)}</span><strong>CHF {zahl(s.mwst)}</strong></div>
        ))}
        {Object.entries(a.total.zahlungsarten).map(([k, b]) => <div key={k}><span>{k}</span><strong>CHF {zahl(b)}</strong></div>)}
      </div>
    </section>
  );
}

function Uebernachtungen({ d, vergleich }) {
  const a = d.aktuell, v = d.vergleich;
  const vm = Object.fromEntries((v?.monate || []).map((m) => [m.monat, m]));
  const zeilen = a.monate.filter((m) => m.personennaechte || vm[m.monat]?.personennaechte);
  const plaetze = [...new Set(a.monate.flatMap((m) => Object.keys(m.plaetze)))];
  const max = Math.max(1, ...a.monate.map((m) => m.personennaechte), ...(v?.monate || []).map((m) => m.personennaechte));
  return (
    <section className="karte auswertung-karte">
      <p className="hinweis">Nach <strong>Nacht</strong> aus den Aufenthalten (eingecheckt und abgereist) – als Kontrolle zur Abrechnung über Feratel.
        Kurtaxe nur für kurtaxepflichtige Erwachsene, Beherbergungsabgabe für alle Erwachsenen.</p>
      {zeilen.length === 0 ? <p className="leer">Keine Übernachtungen {a.jahr}{vergleich ? ` oder ${vergleich}` : ""}.</p> : (
        <div className="tabelle-rahmen">
          <table className="auswertung">
            <thead><tr><th>Monat</th><th className="zahl">Ankünfte</th><th className="zahl">Personennächte</th>{v && <th className="zahl">{v.jahr}</th>}{v && <th className="zahl">±</th>}
              <th className="balken-spalte"><span className="sr-only">Vergleich</span></th>
              <th className="zahl">Erw.</th><th className="zahl">davon KT</th><th className="zahl">Kinder</th><th className="zahl">Kleink.</th>
              <th className="zahl">Kurtaxe</th><th className="zahl">Beherb.-Abgabe</th>{v && <th className="zahl">Taxen {v.jahr}</th>}
              {plaetze.map((p) => <th key={p} className="zahl">Nächte {TYP[p] ?? p}</th>)}</tr></thead>
            <tbody>
              {zeilen.map((m) => (
                <tr key={m.monat}>
                  <th scope="row">{m.name}</th><td className="zahl">{ganz(m.ankuenfte)}</td><td className="zahl">{ganz(m.personennaechte)}</td>
                  {v && <td className="zahl leise">{ganz(vm[m.monat]?.personennaechte)}</td>}
                  {v && <td className="zahl"><Veraenderung jetzt={m.personennaechte} vorher={vm[m.monat]?.personennaechte} /></td>}
                  <td className="balken-spalte"><Balken wert={m.personennaechte} max={max} vergleich={v ? vm[m.monat]?.personennaechte ?? 0 : undefined} /></td>
                  <td className="zahl">{ganz(m.erwachsene)}</td><td className="zahl leise">{ganz(m.erwachsene_kurtaxe)}</td>
                  <td className="zahl">{ganz(m.kinder)}</td><td className="zahl">{ganz(m.kleinkinder)}</td>
                  <td className="zahl">{zahl(m.kurtaxe)}</td><td className="zahl">{zahl(m.beherbergungsabgabe)}</td>
                  {v && <td className="zahl leise">{zahl(vm[m.monat]?.taxen)}</td>}
                  {plaetze.map((p) => <td key={p} className="zahl">{ganz(m.plaetze[p] || 0)}</td>)}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row">Total</th><td className="zahl">{ganz(a.total.ankuenfte)}</td><td className="zahl">{ganz(a.total.personennaechte)}</td>
                {v && <td className="zahl leise">{ganz(v.total.personennaechte)}</td>}
                {v && <td className="zahl"><Veraenderung jetzt={a.total.personennaechte} vorher={v.total.personennaechte} /></td>}
                <td /><td className="zahl">{ganz(a.total.erwachsene)}</td><td className="zahl leise">{ganz(a.total.erwachsene_kurtaxe)}</td>
                <td className="zahl">{ganz(a.total.kinder)}</td><td className="zahl">{ganz(a.total.kleinkinder)}</td>
                <td className="zahl">{zahl(a.total.kurtaxe)}</td><td className="zahl">{zahl(a.total.beherbergungsabgabe)}</td>
                {v && <td className="zahl leise">{zahl(v.total.taxen)}</td>}
                {plaetze.map((p) => <td key={p} className="zahl">{ganz(a.total.plaetze[p] || 0)}</td>)}
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </section>
  );
}

function Saison({ s }) {
  const r = s.rechnungen;
  return (
    <section className="karte auswertung-karte">
      <div className="abschnitt-kopf">
        <p className="hinweis">Zusammenstellung {s.jahr} für die Buchhaltung: Rechnungen nach Rechnungsdatum (ohne stornierte), MWST auf den
          Rechnungstotalen; Einnahmen nach Zahlungseingang.</p>
        <span className="aktionen">
          <a className="knopf neben" href={`/auswertungen/saison/${s.jahr}.xlsx`}><FileSpreadsheet size={18} aria-hidden="true" />Excel</a>
          <a className="knopf neben" href={`/auswertungen/saison/${s.jahr}.pdf`} target="_blank" rel="noreferrer"><FileText size={18} aria-hidden="true" />PDF</a>
        </span>
      </div>
      <div className="kennzahlen gross">
        <div><span>Rechnungen{r.von ? ` (${r.von} – ${r.bis})` : ""}</span><strong>{r.anzahl}</strong>{r.storniert > 0 && <em>{r.storniert} storniert, nicht gezählt</em>}</div>
        <div><span>Total Rechnungen</span><strong>CHF {zahl(r.total)}</strong><em>inkl. MWST und Taxen</em></div>
        <div><span>Einnahmen (Zahlungseingang)</span><strong>CHF {zahl(s.einnahmen.einnahmen)}</strong></div>
        <div><span>Taxen</span><strong>CHF {zahl(s.taxen_total)}</strong><em>durchlaufend</em></div>
      </div>
      <div className="saison-raster-auswertung">
        <div>
          <h3>MWST auf den Rechnungstotalen</h3>
          <table className="auswertung klein"><thead><tr><th>Satz</th><th className="zahl">Brutto</th><th className="zahl">MWST</th><th className="zahl">Netto</th></tr></thead>
            <tbody>{s.mwst_auf_rechnungen.map((m) => <tr key={m.satz}><th scope="row">{m.satz} %</th><td className="zahl">{zahl(m.brutto)}</td><td className="zahl">{zahl(m.mwst)}</td><td className="zahl">{zahl(m.netto)}</td></tr>)}</tbody></table>
          <h3>Taxen</h3>
          <table className="auswertung klein"><tbody>{s.taxen.map((t) => <tr key={t.bezeichnung}><th scope="row">{t.bezeichnung}</th><td className="zahl">{zahl(t.betrag)}</td></tr>)}</tbody></table>
          <h3>Einnahmen je Zahlungsart</h3>
          <table className="auswertung klein"><tbody>{Object.entries(s.einnahmen.zahlungsarten).map(([k, b]) => <tr key={k}><th scope="row">{k}</th><td className="zahl">{zahl(b)}</td></tr>)}
            <tr><th scope="row">MWST (vereinnahmt)</th><td className="zahl">{zahl(s.einnahmen.mwst)}</td></tr></tbody></table>
        </div>
        <div>
          <h3>Umsatz je Leistung</h3>
          {s.leistungen.length === 0 ? <p className="leer klein">Noch keine Rechnungen.</p> : (
            <table className="auswertung klein"><thead><tr><th>Leistung</th><th className="zahl">Menge</th><th className="zahl">Betrag</th></tr></thead>
              <tbody>{s.leistungen.map((l) => <tr key={l.bezeichnung}><th scope="row">{l.bezeichnung}</th><td className="zahl">{l.menge}</td><td className="zahl">{zahl(l.betrag)}</td></tr>)}</tbody></table>
          )}
          {(s.offene_rechnungen.length > 0 || s.anzahlungen_ohne_rechnung.length > 0) && (
            <>
              <h3>Offen bzw. noch nicht abgerechnet</h3>
              <table className="auswertung klein"><tbody>
                {s.offene_rechnungen.map((o) => <tr key={o.nummer}><th scope="row">Rechnung {o.nummer} · {o.gast}</th><td className="zahl">{zahl(o.restbetrag)}</td></tr>)}
              </tbody></table>
              {s.anzahlungen_ohne_rechnung.length > 0 && (
                <details className="je-nacht">
                  <summary>{s.anzahlungen_ohne_rechnung.length} Anzahlungen ohne Rechnung · CHF {zahl(s.anzahlungen_ohne_rechnung.reduce((x, a) => x + Number(a.betrag), 0))}</summary>
                  <table className="auswertung klein"><tbody>
                    {s.anzahlungen_ohne_rechnung.map((a, i) => <tr key={i}><th scope="row">{datumVoll(a.datum)} · {a.gast}{a.reservation ? ` (${a.reservation})` : ""}</th><td className="zahl">{zahl(a.betrag)}</td></tr>)}
                  </tbody></table>
                </details>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
