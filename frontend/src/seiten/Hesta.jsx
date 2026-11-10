// Modul «HESTA»: Monatsrapport für die Beherbergungsstatistik des BFS (Ankünfte und
// Übernachtungen je Nationalität, alphabetisch), Ablage der Rapporte und die monatlichen
// Mails des BFS mit den Zugangsdaten. Die Erfassung beim BFS erfolgt von Hand.
import { useCallback, useEffect, useState } from "react";
import { ClipboardPaste, FileText, Save } from "lucide-react";
import { api } from "../api.js";

const MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const zeit = (iso) => (iso ? new Date(iso).toLocaleString("de-CH", { dateStyle: "medium", timeStyle: "short" }) : "–");

export default function Hesta() {
  const [faellig, setFaellig] = useState(null);
  const [wahl, setWahl] = useState(null); // { jahr, monat }
  const [vorschau, setVorschau] = useState(null);
  const [ablage, setAblage] = useState([]);
  const [mails, setMails] = useState([]);
  const [fehler, setFehler] = useState(null);
  const [meldung, setMeldung] = useState(null);
  const [laeuft, setLaeuft] = useState(false);

  const allesLaden = useCallback(async () => {
    try {
      const [f, a, m] = await Promise.all([api.get("/hesta/faellig"), api.get("/hesta/meldungen"), api.get("/hesta/zugangsmails")]);
      setFaellig(f); setAblage(a); setMails(m);
      setWahl((w) => w ?? { jahr: f.jahr, monat: f.monat });
    } catch (e) { setFehler(e.message); }
  }, []);
  useEffect(() => { allesLaden(); }, [allesLaden]);

  useEffect(() => {
    if (!wahl) return;
    setVorschau(null);
    api.get(`/hesta/vorschau?jahr=${wahl.jahr}&monat=${wahl.monat}`).then(setVorschau).catch((e) => setFehler(e.message));
  }, [wahl]);

  const gespeichert = wahl && ablage.find((m) => m.jahr === wahl.jahr && m.monat === wahl.monat);
  const ablegen = async () => {
    setLaeuft(true); setFehler(null); setMeldung(null);
    try {
      await api.post("/hesta/meldungen", { jahr: wahl.jahr, monat: wahl.monat });
      setMeldung(`Rapport ${MONATE[wahl.monat - 1]} ${wahl.jahr} erstellt und abgelegt.`);
      await allesLaden();
    } catch (e) { setFehler(e.message); } finally { setLaeuft(false); }
  };
  const gemeldet = async (m) => {
    setLaeuft(true); setFehler(null);
    try { await api.post(`/hesta/meldungen/${m.id}/als-eingereicht-markieren`); await allesLaden(); }
    catch (e) { setFehler(e.message); } finally { setLaeuft(false); }
  };

  const jahre = [];
  for (let j = new Date().getFullYear() + 1; j >= new Date().getFullYear() - 3; j--) jahre.push(j);

  return (
    <div className="seite hesta">
      <header className="kopf"><h1>HESTA</h1></header>
      {faellig?.faellig && (
        <p className="meldung warnung">Fällig: Meldung <strong>{faellig.name}</strong> an das BFS (Anfang des Folgemonats).
          {faellig.status === "entwurf" ? " Der Rapport ist abgelegt – nach der Erfassung beim BFS als gemeldet markieren." : ""}</p>
      )}
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
      {meldung && <p className="meldung ok" role="status">{meldung}</p>}

      <div className="hesta-raster">
        <section className="karte auswertung-karte">
          <div className="abschnitt-kopf">
            <h2>Monatsrapport</h2>
            {wahl && (
              <span className="aktionen">
                <label className="kompakt">Monat
                  <select value={wahl.monat} onChange={(e) => setWahl({ ...wahl, monat: Number(e.target.value) })}>
                    {MONATE.map((n, i) => <option key={n} value={i + 1}>{n}</option>)}
                  </select>
                </label>
                <select aria-label="Jahr" value={wahl.jahr} onChange={(e) => setWahl({ ...wahl, jahr: Number(e.target.value) })}>
                  {jahre.map((j) => <option key={j} value={j}>{j}</option>)}
                </select>
              </span>
            )}
          </div>
          <p className="hinweis">Ankünfte und Übernachtungen je <strong>Nationalität</strong> (des Hauptgastes, für alle Personen inkl. Kinder),
            alphabetisch. Ankunft im Monat der Anreise; jede Nacht zählt zum Monat ihres Datums. Grundlage sind die Aufenthalte.</p>
          {!vorschau ? <p className="leer">Wird geladen …</p> : (
            <>
              <div className="tabelle-rahmen">
                <table className="auswertung">
                  <thead><tr><th>Nationalität</th><th className="zahl">Ankünfte</th><th className="zahl">Übernachtungen</th></tr></thead>
                  <tbody>
                    {vorschau.positionen.length === 0 && <tr><td colSpan={3} className="leer klein">Keine Aufenthalte in diesem Monat.</td></tr>}
                    {vorschau.positionen.map((p) => (
                      <tr key={p.land}><th scope="row">{p.name} <span className="leise klein">{p.land}</span></th>
                        <td className="zahl">{p.anzahl_personen}</td><td className="zahl">{p.anzahl_uebernachtungen}</td></tr>
                    ))}
                  </tbody>
                  <tfoot><tr><th scope="row">Total</th><td className="zahl">{vorschau.total_personen}</td><td className="zahl">{vorschau.total_uebernachtungen}</td></tr></tfoot>
                </table>
              </div>
              <div className="aktionen">
                {gespeichert?.status === "eingereicht"
                  ? <p className="hinweis">Für diesen Monat ist der Rapport abgelegt und als gemeldet markiert.</p>
                  : <button className="knopf haupt" disabled={laeuft} onClick={ablegen}><Save size={18} aria-hidden="true" />
                    {gespeichert ? "Rapport neu erstellen und ablegen" : "Rapport erstellen und ablegen"}</button>}
                <a className="knopf neben" href={`/hesta/pdf?jahr=${wahl.jahr}&monat=${wahl.monat}`} target="_blank" rel="noreferrer">
                  <FileText size={18} aria-hidden="true" />PDF-Vorschau</a>
              </div>
            </>
          )}
        </section>

        <section className="karte auswertung-karte">
          <h2>Ablage</h2>
          {ablage.length === 0 ? <p className="leer klein">Noch keine Rapporte abgelegt.</p> : (
            <table className="auswertung klein">
              <thead><tr><th>Monat</th><th className="zahl">Ank.</th><th className="zahl">Übern.</th><th>Status</th><th><span className="sr-only">Aktionen</span></th></tr></thead>
              <tbody>
                {ablage.map((m) => (
                  <tr key={m.id}>
                    <th scope="row"><button className="link" onClick={() => setWahl({ jahr: m.jahr, monat: m.monat })}>{MONATE[m.monat - 1]} {m.jahr}</button></th>
                    <td className="zahl">{m.total_personen}</td><td className="zahl">{m.total_uebernachtungen}</td>
                    <td>{m.status === "eingereicht"
                      ? <span className="marke-status ton-ok" title={zeit(m.eingereicht_am)}>gemeldet</span>
                      : <span className="marke-status ton-offen" title={`erstellt ${zeit(m.generiert_am)}`}>abgelegt</span>}</td>
                    <td className="zeilen-aktionen">
                      <a className="link" href={`/hesta/meldungen/${m.id}/pdf`} target="_blank" rel="noreferrer">PDF</a>
                      {m.status !== "eingereicht" && <button className="link" disabled={laeuft} onClick={() => gemeldet(m)}>als gemeldet markieren</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <Zugangsmails mails={mails} onGeaendert={allesLaden} />
    </div>
  );
}

function Zugangsmails({ mails, onGeaendert }) {
  const [einfuegen, setEinfuegen] = useState(false);
  const [text, setText] = useState("");
  const [fehler, setFehler] = useState(null);
  const [laeuft, setLaeuft] = useState(false);
  const [neueste, ...aeltere] = mails;
  const speichern = async (e) => {
    e.preventDefault(); setFehler(null); setLaeuft(true);
    try { await api.post("/hesta/zugangsmails", { text }); setText(""); setEinfuegen(false); onGeaendert(); }
    catch (err) { setFehler(err.message); } finally { setLaeuft(false); }
  };
  const loeschen = async (id) => {
    try { await api.delete(`/hesta/zugangsmails/${id}`); onGeaendert(); } catch (err) { setFehler(err.message); }
  };
  return (
    <section className="karte auswertung-karte">
      <div className="abschnitt-kopf">
        <h2>Zugangsdaten des BFS</h2>
        {!einfuegen && <button className="knopf neben" onClick={() => setEinfuegen(true)}><ClipboardPaste size={18} aria-hidden="true" />Mail einfügen</button>}
      </div>
      <p className="meldung warnung klein">Das Tool hat noch keine Anmeldung: Wer die Adresse kennt, sieht diese Mails samt Zugangsdaten.
        Bitte erst echte Zugangsdaten einfügen, wenn der Zugriff geschützt ist.</p>
      <p className="hinweis">Das BFS schickt jeden Monat neue Zugangsdaten. Sobald das Postfach angebunden ist, landen Mails von
        @bfs.admin.ch automatisch hier (nicht bei den Reservationen). Bis dahin die Mail kopieren und mit «Mail einfügen» ablegen.</p>
      {einfuegen && (
        <form className="bearbeiten-form" onSubmit={speichern}>
          <label>Mailtext (mit Von/Betreff/Datum, falls vorhanden)
            <textarea rows="8" required value={text} onChange={(e) => setText(e.target.value)} /></label>
          {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
          <div className="aktionen">
            <button className="knopf haupt" type="submit" disabled={laeuft || !text.trim()}>Ablegen</button>
            <button className="knopf leise" type="button" onClick={() => setEinfuegen(false)}>Abbrechen</button>
          </div>
        </form>
      )}
      {!neueste ? <p className="leer klein">Noch keine Mail des BFS.</p> : (
        <article className="bfs-mail">
          <header><strong>{neueste.betreff}</strong><span className="leise klein"> · {zeit(neueste.datum)} · {neueste.von}</span></header>
          <pre>{neueste.text}</pre>
          <button className="link klein" onClick={() => loeschen(neueste.id)}>Mail entfernen</button>
        </article>
      )}
      {aeltere.length > 0 && (
        <details className="je-nacht">
          <summary>Frühere Mails ({aeltere.length})</summary>
          {aeltere.map((m) => (
            <article key={m.id} className="bfs-mail">
              <header><strong>{m.betreff}</strong><span className="leise klein"> · {zeit(m.datum)}</span></header>
              <pre>{m.text}</pre>
              <button className="link klein" onClick={() => loeschen(m.id)}>Mail entfernen</button>
            </article>
          ))}
        </details>
      )}
    </section>
  );
}
