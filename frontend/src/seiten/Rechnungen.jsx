// Modul «Rechnungen»: Rechnungen aus den Aufenthalten – offen, bezahlt, storniert.
// Erstellt werden sie im Aufenthalt bei der Abreise; hier: Übersicht, PDF, Zahlung, Storno.
import { useCallback, useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { api } from "../api.js";
import { datumKurz, datumVoll, heuteIso } from "../format.js";
import { Bestaetigung, Schublade } from "./Belegung.jsx";

export const ZAHLUNGSARTEN = { bar: "Bar", twint: "TWINT", karte: "Karte", ueberweisung: "Überweisung" };
const REGISTER = [
  { code: "offen", name: "Offen" },
  { code: "bezahlt", name: "Bezahlt" },
  { code: "storniert", name: "Storniert" },
];
const STATUS_TON = { offen: "offen", bezahlt: "ok", storniert: "aus" };
const STATUS_NAME = { offen: "offen", bezahlt: "bezahlt", storniert: "storniert" };
export const chf = (x) => `CHF ${Number(x).toFixed(2)}`;

export default function Rechnungen() {
  const [register, setRegister] = useState("offen");
  const [liste, setListe] = useState(null);
  const [fehler, setFehler] = useState(null);
  const [offen, setOffen] = useState(null);

  const laden = useCallback(() => {
    setFehler(null);
    api.get("/rechnungen/liste").then(setListe).catch((e) => setFehler(e.message));
  }, []);
  useEffect(laden, [laden]);
  useEffect(() => {
    const zu = (e) => { if (e.key === "Escape") setOffen(null); };
    window.addEventListener("keydown", zu);
    return () => window.removeEventListener("keydown", zu);
  }, []);

  const anzahl = Object.fromEntries(REGISTER.map((r) => [r.code, (liste || []).filter((x) => x.status === r.code).length]));
  const sichtbar = (liste || []).filter((x) => x.status === register);
  const summeOffen = (liste || []).filter((x) => x.status === "offen").reduce((s, x) => s + Number(x.restbetrag), 0);

  return (
    <div className="seite">
      <header className="kopf">
        <h1>Rechnungen</h1>
        {summeOffen > 0 && <p className="kopf-zahl">Offen: <strong>{chf(summeOffen)}</strong></p>}
      </header>
      <p className="hinweis">Rechnungen entstehen im Aufenthalt bei der Abreise («Aufenthalte» › Gast › «Rechnung erstellen»).</p>
      <div className="ablagen" role="tablist" aria-label="Rechnungen">
        {REGISTER.map((r) => (
          <button key={r.code} role="tab" aria-selected={register === r.code} onClick={() => setRegister(r.code)}>
            {r.name} <span className="zahl">{anzahl[r.code] ?? 0}</span>
          </button>
        ))}
      </div>
      {fehler && <p className="meldung fehler">{fehler}</p>}
      {!fehler && !liste && <p className="leer">Wird geladen …</p>}
      {liste && sichtbar.length === 0 && <p className="leer">Keine Rechnungen {register === "offen" ? "offen" : `mit Status «${STATUS_NAME[register]}»`}.</p>}
      {sichtbar.length > 0 && (
        <div className="tabelle-rahmen">
          <table className="rechnungsliste">
            <thead><tr><th>Nummer</th><th>Datum</th><th>Gast</th><th>Aufenthalt</th><th className="zahl">Total</th>
              <th className="zahl">{register === "offen" ? "Offen" : "Anzahlung"}</th><th>Zahlung</th></tr></thead>
            <tbody>
              {sichtbar.map((r) => (
                <tr key={r.id} onClick={() => setOffen(r.id)} tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") setOffen(r.id); }}>
                  <td className="nummer">{r.nummer}</td>
                  <td>{datumVoll(r.datum)}</td>
                  <td><strong>{r.gast_name}</strong></td>
                  <td className="leise">{datumKurz(r.von)} – {datumKurz(r.bis)}</td>
                  <td className="zahl">{chf(r.gesamtbetrag)}</td>
                  <td className="zahl">{register === "offen" ? <strong>{chf(r.restbetrag)}</strong> : Number(r.anzahlung) ? chf(r.anzahlung) : "–"}</td>
                  <td>{r.status === "bezahlt" ? `${ZAHLUNGSARTEN[r.zahlungsart] ?? "mit Anzahlung"}, ${datumKurz(r.bezahlt_am)}` : <span className={`marke-status ton-${STATUS_TON[r.status]}`}>{STATUS_NAME[r.status]}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {offen && (
        <Schublade breit titel="Rechnung" onSchliessen={() => setOffen(null)}>
          <RechnungPanel id={offen} onGeaendert={laden} />
        </Schublade>
      )}
    </div>
  );
}

export function RechnungPanel({ id, onGeaendert, mitAufenthaltLink = true }) {
  const [r, setR] = useState(null);
  const [fehler, setFehler] = useState(null);
  const [laeuft, setLaeuft] = useState(false);
  const [storno, setStorno] = useState(false);
  const laden = useCallback(() => { api.get(`/rechnungen/details/${id}`).then(setR).catch((e) => setFehler(e.message)); }, [id]);
  useEffect(laden, [laden]);
  const ausfuehren = async (fn) => {
    setLaeuft(true); setFehler(null);
    try { setR(await fn()); onGeaendert?.(); } catch (e) { setFehler(e.message); } finally { setLaeuft(false); setStorno(false); }
  };
  if (fehler && !r) return <p className="meldung fehler">{fehler}</p>;
  if (!r) return <p className="leer">Wird geladen …</p>;
  return (
    <div className="panel rechnung-panel">
      <h2>Rechnung {r.nummer}</h2>
      <p>
        <span className={`marke-status ton-${STATUS_TON[r.status]}`}>{STATUS_NAME[r.status]}</span>
        <span className="leise"> {datumVoll(r.datum)} · {r.gast_name} · Aufenthalt {datumKurz(r.von)} – {datumKurz(r.bis)}</span>
        {r.reservationsnummer && <span className="nummer"> Reservation {r.reservationsnummer}</span>}
      </p>
      <div className="tabelle-rahmen">
        <table className="leistungen">
          <thead><tr><th>Leistung</th><th className="zahl">Menge</th><th className="zahl">Preis</th><th className="zahl">MWST</th><th className="zahl">Betrag</th></tr></thead>
          <tbody>
            {r.positionen.map((p, i) => (
              <tr key={i} className={Number(p.betrag) < 0 ? "abzug" : ""}>
                <td>{p.bezeichnung}</td><td className="zahl">{p.menge}</td><td className="zahl">{Number(p.einzelpreis).toFixed(2)}</td>
                <td className="zahl leise">{Number(p.mwstsatz_prozent) ? `${p.mwstsatz_prozent} %` : "–"}</td><td className="zahl">{Number(p.betrag).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="total-box">
        <dl>
          <div className="summe"><dt>Total</dt><dd>{chf(r.gesamtbetrag)}</dd></div>
          {Number(r.anzahlung) > 0 && <div><dt>Anzahlung erhalten</dt><dd>– {chf(r.anzahlung)}</dd></div>}
          {Number(r.anzahlung) > 0 && <div className="summe"><dt>Restbetrag</dt><dd>{chf(r.restbetrag)}</dd></div>}
        </dl>
        <p className="hinweis klein">Endpreise; darin MWST {chf(r.mwst_betrag_total)}. Kurtaxe und Beherbergungsabgabe ohne MWST.</p>
        {r.status === "bezahlt" && <p className="meldung ok">Bezahlt am {datumVoll(r.bezahlt_am)}{r.zahlungsart ? `, ${ZAHLUNGSARTEN[r.zahlungsart]}` : " (mit der Anzahlung)"}.</p>}
        {r.status === "storniert" && <p className="meldung warnung">Storniert. Die Nummer bleibt vergeben; der Aufenthalt ist wieder änderbar.</p>}
      </div>
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
      <div className="aktionen">
        <a className="knopf neben" href={`/rechnungen/${r.id}/pdf`} target="_blank" rel="noreferrer"><FileText size={18} aria-hidden="true" />PDF öffnen</a>
        {mitAufenthaltLink && <a className="knopf leise" href={`#/aufenthalte?id=${r.buchung_id}`}>Zum Aufenthalt</a>}
      </div>
      {r.status === "offen" && <ZahlungErfassen laeuft={laeuft} betrag={r.restbetrag}
        onBezahlt={(w) => ausfuehren(() => api.post(`/rechnungen/${r.id}/bezahlt`, w))} />}
      {r.status !== "storniert" && (
        <Bestaetigung offen={storno} onOeffnen={() => setStorno(true)} onAbbrechen={() => setStorno(false)} knopf="Rechnung stornieren"
          frage={`Rechnung ${r.nummer} stornieren? Die Nummer bleibt vergeben, eine erfasste Zahlung wird ebenfalls storniert. Danach lässt sich der Aufenthalt ändern und neu abrechnen.`}
          laeuft={laeuft} onJa={() => ausfuehren(() => api.post(`/rechnungen/${r.id}/stornieren`))} />
      )}
    </div>
  );
}

export function ZahlungErfassen({ betrag, laeuft, onBezahlt, titel = "Zahlung erfassen", mitOffen = false, onOffen }) {
  const [arten, setArten] = useState(["bar", "twint"]);
  const [datum, setDatum] = useState(heuteIso());
  useEffect(() => { api.get("/rechnungen/einstellungen").then((e) => setArten(e.zahlungsarten)).catch(() => {}); }, []);
  return (
    <section className="zahlung-erfassen">
      <h3>{titel}{betrag !== undefined ? ` – ${chf(betrag)}` : ""}</h3>
      <div className="aktionen">
        {arten.filter((a) => a !== "ueberweisung").map((a) => (
          <button key={a} className="knopf haupt" disabled={laeuft} onClick={() => onBezahlt({ zahlungsart: a, datum })}>{ZAHLUNGSARTEN[a]}</button>
        ))}
        {!mitOffen && arten.includes("ueberweisung") && (
          <button className="knopf neben" disabled={laeuft} onClick={() => onBezahlt({ zahlungsart: "ueberweisung", datum })}>Überweisung eingegangen</button>
        )}
        {mitOffen && <button className="knopf neben" disabled={laeuft} onClick={onOffen}>Offen – Gast überweist</button>}
        {!mitOffen && <label className="kompakt">am<input type="date" value={datum} max={heuteIso()} onChange={(e) => setDatum(e.target.value)} /></label>}
      </div>
    </section>
  );
}
