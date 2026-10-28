import { useCallback, useEffect, useMemo, useState } from "react";
import { ClipboardPaste, Copy, Mail, Plus, Search } from "lucide-react";
import { api } from "../api.js";
import {
  QUELLEN, SPRACHEN, STATUS, TYPEN, datumVoll, fehlendText, naechte, personen, statusName, typName, zeitraum,
} from "../format.js";

const ABLAGEN = [
  { code: "offen", name: "Zu bearbeiten", status: ["neu", "unvollstaendig", "geprueft_vollstaendig"] },
  { code: "laufend", name: "Warten auf Gast", status: ["erstantwort_gesendet", "zahlung_ausstehend"] },
  { code: "akzeptiert", name: "Akzeptiert", status: ["bezahlt_akzeptiert"] },
  { code: "erledigt", name: "Abgelehnt / storniert", status: ["abgelehnt", "storniert"] },
  { code: "alle", name: "Alle", status: null },
];

// Nächste sinnvolle Schritte je Status (Konzept 10.2–10.5)
const SCHRITTE = {
  neu: [],
  unvollstaendig: [["abgelehnt", "Ablehnen", "leise"]],
  geprueft_vollstaendig: [["erstantwort_gesendet", "Schon beantwortet", "neben"], ["abgelehnt", "Ablehnen", "leise"]],
  erstantwort_gesendet: [["zahlung_ausstehend", "Wartet auf Zahlung", "neben"], ["bezahlt_akzeptiert", "Zahlung erhalten, akzeptieren", "haupt"], ["abgelehnt", "Ablehnen", "leise"]],
  zahlung_ausstehend: [["bezahlt_akzeptiert", "Zahlung erhalten, akzeptieren", "haupt"], ["storniert", "Stornieren", "leise"]],
  bezahlt_akzeptiert: [["storniert", "Stornieren", "leise"]],
  abgelehnt: [["neu", "Wieder öffnen", "neben"]],
  storniert: [["neu", "Wieder öffnen", "neben"]],
};

const LEER = {
  quelle: "manuell", sprache: "de", gast_name: "", gast_email: "", gast_telefon: "",
  gewuenscht_von: "", gewuenscht_bis: "", stellplatz_typ: "", anzahl_erwachsene: 2, anzahl_kinder: 0,
  bemerkung: "", rohtext: "",
};

export function StatusMarke({ status }) {
  return <span className={`marke-status ton-${STATUS[status]?.ton ?? "info"}`}>{statusName(status)}</span>;
}

export default function Reservationen() {
  const [anfragen, setAnfragen] = useState(null);
  const [ablage, setAblage] = useState("offen");
  const [suche, setSuche] = useState("");
  const [auswahl, setAuswahl] = useState(null); // id | "neu" | "text" | null
  const [fehler, setFehler] = useState(null);

  const laden = useCallback(() => {
    api.get("/reservationsanfragen").then(setAnfragen).catch((e) => setFehler(e.message));
  }, []);
  useEffect(laden, [laden]);

  const anzahl = useMemo(() => Object.fromEntries(ABLAGEN.map((a) => [
    a.code, (anfragen || []).filter((x) => !a.status || a.status.includes(x.status)).length,
  ])), [anfragen]);

  const liste = useMemo(() => {
    const filter = ABLAGEN.find((a) => a.code === ablage).status;
    const s = suche.trim().toLowerCase();
    return (anfragen || [])
      .filter((a) => !filter || filter.includes(a.status))
      .filter((a) => !s || `${a.gast_name} ${a.gast_email}`.toLowerCase().includes(s));
  }, [anfragen, ablage, suche]);

  const nachSpeichern = (anfrage) => { laden(); setAuswahl(anfrage.id); };

  return (
    <div className="seite">
      <header className="kopf">
        <h1>Reservationen</h1>
        <div className="aktionen">
          <button className="knopf neben" onClick={() => setAuswahl("text")}><ClipboardPaste size={18} aria-hidden="true" />Mailtext einfügen</button>
          <button className="knopf haupt" onClick={() => setAuswahl("neu")}><Plus size={18} aria-hidden="true" />Anfrage erfassen</button>
        </div>
      </header>
      {fehler && <p className="meldung fehler">{fehler}</p>}

      <div className="ablagen" role="tablist" aria-label="Ablage">
        {ABLAGEN.map((a) => (
          <button key={a.code} role="tab" aria-selected={ablage === a.code} onClick={() => setAblage(a.code)}>
            {a.name} <span className="zahl">{anzahl[a.code] ?? 0}</span>
          </button>
        ))}
      </div>

      <div className="zweiteilig">
        <section className="postfach" aria-label="Anfragen">
          <label className="suchfeld">
            <Search size={16} aria-hidden="true" />
            <input type="search" placeholder="Name oder E-Mail suchen" value={suche} onChange={(e) => setSuche(e.target.value)} />
          </label>
          {anfragen === null && <p className="leer">Wird geladen …</p>}
          {anfragen && liste.length === 0 && (
            <p className="leer">Keine Anfragen in dieser Ablage. Neue Anfragen aus dem Postfach oder per Telefon erscheinen unter «Zu bearbeiten».</p>
          )}
          <ul className="anfrageliste">
            {liste.map((a) => (
              <li key={a.id}>
                <button className="anfrage" aria-current={auswahl === a.id ? "true" : undefined} onClick={() => setAuswahl(a.id)}>
                  <span className="zeile1"><strong>{a.gast_name}</strong><StatusMarke status={a.status} /></span>
                  <span className="zeile2">
                    {zeitraum(a.gewuenscht_von, a.gewuenscht_bis)}
                    <span className="trenner" aria-hidden="true" />{typName(a.stellplatz_typ)}
                    <span className="trenner" aria-hidden="true" />{personen(a.anzahl_erwachsene, a.anzahl_kinder)}
                  </span>
                  {!a.vollstaendig && <span className="zeile3">Es fehlt: {fehlendText(a.fehlende_angaben)}</span>}
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="detail" aria-label="Details">
          {auswahl === null && <p className="leer">Wählen Sie eine Anfrage aus der Liste aus.</p>}
          {auswahl === "neu" && <Formular key="neu" anfrage={LEER} neu onGespeichert={nachSpeichern} onAbbrechen={() => setAuswahl(null)} />}
          {auswahl === "text" && <Mailtext onGespeichert={(a) => { setAblage("offen"); nachSpeichern(a); }} onAbbrechen={() => setAuswahl(null)} />}
          {auswahl && auswahl !== "neu" && auswahl !== "text" && <Detail key={auswahl} id={auswahl} onGeaendert={laden} />}
        </section>
      </div>
    </div>
  );
}

function Mailtext({ onGespeichert, onAbbrechen }) {
  const [text, setText] = useState("");
  const [fehler, setFehler] = useState(null);
  const [laeuft, setLaeuft] = useState(false);

  const uebernehmen = async (e) => {
    e.preventDefault();
    setLaeuft(true); setFehler(null);
    try { onGespeichert(await api.post("/reservationsanfragen/mail-import/text", { text })); }
    catch (err) { setFehler(err.message); } finally { setLaeuft(false); }
  };

  return (
    <form className="formular" onSubmit={uebernehmen}>
      <h2>Mailtext einfügen</h2>
      <p className="hinweis">
        Kopieren Sie den Text der Reservationsmail (z.B. vom Homepage-Formular) aus Ihrem Mailprogramm und fügen Sie ihn hier ein.
        Name, Kontakt, Zeitraum, Stellplatz und Personen werden erkannt. Prüfen Sie die Angaben danach und ergänzen Sie, was fehlt.
      </p>
      <div className="feld"><label htmlFor="mailtext">Text der Mail</label>
        <textarea id="mailtext" rows="14" required minLength={10} value={text} onChange={(e) => setText(e.target.value)} /></div>
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
      <div className="aktionen">
        <button className="knopf haupt" type="submit" disabled={laeuft || text.trim().length < 10}>Anfrage übernehmen</button>
        <button className="knopf leise" type="button" onClick={onAbbrechen}>Abbrechen</button>
      </div>
    </form>
  );
}

function Antwort({ anfrage, onGesendet, onAbbrechen }) {
  const [eingabe, setEingabe] = useState({ sprache: anfrage.sprache || "de", betrag: "", zahlungsfrist: "" });
  const [entwurf, setEntwurf] = useState(null);
  const [fehler, setFehler] = useState(null);
  const [kopiert, setKopiert] = useState(null);
  const [laeuft, setLaeuft] = useState(false);

  const erstellen = async (e) => {
    e.preventDefault(); setFehler(null); setLaeuft(true);
    try {
      setEntwurf(await api.post(`/reservationsanfragen/${anfrage.id}/antwort/vorbereiten`, {
        sprache: eingabe.sprache, betrag: eingabe.betrag, zahlungsfrist: eingabe.zahlungsfrist || null,
      }));
    } catch (err) { setFehler(err.message); } finally { setLaeuft(false); }
  };

  const kopieren = async (was, inhalt) => {
    try { await navigator.clipboard.writeText(inhalt); setKopiert(was); setTimeout(() => setKopiert(null), 2500); }
    catch { setFehler("Kopieren nicht möglich. Bitte den Text markieren und mit Ctrl+C kopieren."); }
  };

  const mailto = entwurf
    ? `mailto:${encodeURIComponent(entwurf.empfaenger)}?subject=${encodeURIComponent(entwurf.betreff)}&body=${encodeURIComponent(entwurf.text)}`
    : "";

  const gesendet = async () => {
    setFehler(null); setLaeuft(true);
    try {
      onGesendet(await api.post(`/reservationsanfragen/${anfrage.id}/antwort/gesendet`, {
        vorlage_id: entwurf.vorlage_id, betreff: entwurf.betreff, text: entwurf.text,
      }));
    } catch (err) { setFehler(err.message); } finally { setLaeuft(false); }
  };

  return (
    <div className="formular">
      <h2>Antwort an {anfrage.gast_name}</h2>
      <form className="felder" onSubmit={erstellen}>
        <label>Sprache
          <select value={eingabe.sprache} onChange={(e) => setEingabe({ ...eingabe, sprache: e.target.value })}>
            {Object.entries(SPRACHEN).map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
        </label>
        <label>Anzahlung in CHF
          <input required type="number" min="0.05" step="0.05" inputMode="decimal" value={eingabe.betrag}
            onChange={(e) => setEingabe({ ...eingabe, betrag: e.target.value })} />
        </label>
        <label>Zahlungsfrist (optional)
          <input type="date" value={eingabe.zahlungsfrist} onChange={(e) => setEingabe({ ...eingabe, zahlungsfrist: e.target.value })} />
        </label>
        <div className="aktionen breit">
          <button className="knopf haupt" type="submit" disabled={laeuft}>{entwurf ? "Text neu erstellen" : "Text erstellen"}</button>
          <button className="knopf leise" type="button" onClick={onAbbrechen}>Abbrechen</button>
        </div>
      </form>
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}

      {entwurf && (
        <>
          {entwurf.warnungen.map((w) => <p key={w} className="meldung warnung">{w}. Unter Einstellungen › Betriebsangaben ergänzen.</p>)}
          <p className="hinweis">
            Prüfen und bei Bedarf anpassen. Danach den Text in Ihr Mailprogramm übernehmen, an {entwurf.empfaenger} senden
            und hier als gesendet markieren.
          </p>
          <div className="feld"><label htmlFor="antwort-an">An</label><input id="antwort-an" readOnly value={entwurf.empfaenger} /></div>
          <div className="feld"><label htmlFor="antwort-betreff">Betreff</label>
            <input id="antwort-betreff" value={entwurf.betreff} onChange={(e) => setEntwurf({ ...entwurf, betreff: e.target.value })} /></div>
          <div className="feld"><label htmlFor="antwort-text">Text</label>
            <textarea id="antwort-text" rows="22" value={entwurf.text} onChange={(e) => setEntwurf({ ...entwurf, text: e.target.value })} /></div>
          <div className="aktionen">
            <button className="knopf neben" type="button" onClick={() => kopieren("betreff", entwurf.betreff)}><Copy size={16} aria-hidden="true" />{kopiert === "betreff" ? "Betreff kopiert" : "Betreff kopieren"}</button>
            <button className="knopf neben" type="button" onClick={() => kopieren("text", entwurf.text)}><Copy size={16} aria-hidden="true" />{kopiert === "text" ? "Text kopiert" : "Text kopieren"}</button>
            <a className="knopf neben" href={mailto}><Mail size={16} aria-hidden="true" />Im Mailprogramm öffnen</a>
          </div>
          <div className="aktionen">
            <button className="knopf haupt" type="button" disabled={laeuft} onClick={gesendet}>Als gesendet markieren</button>
          </div>
          <p className="hinweis">«Als gesendet markieren» speichert den Text im Protokoll der Anfrage und setzt den Status auf «Antwort gesendet».</p>
        </>
      )}
    </div>
  );
}

function Detail({ id, onGeaendert }) {
  const [anfrage, setAnfrage] = useState(null);
  const [bearbeiten, setBearbeiten] = useState(false);
  const [antworten, setAntworten] = useState(false);
  const [mails, setMails] = useState([]);
  const [fehler, setFehler] = useState(null);
  const [laeuft, setLaeuft] = useState(false);

  const mailsLaden = useCallback(() => {
    api.get(`/reservationsanfragen/${id}/mails`).then(setMails).catch(() => {});
  }, [id]);
  useEffect(() => {
    api.get(`/reservationsanfragen/${id}`).then(setAnfrage).catch((e) => setFehler(e.message));
    mailsLaden();
  }, [id, mailsLaden]);

  const statusSetzen = async (status) => {
    setLaeuft(true); setFehler(null);
    try {
      setAnfrage(await api.post(`/reservationsanfragen/${id}/status`, { status }));
      onGeaendert();
    } catch (e) { setFehler(e.message); } finally { setLaeuft(false); }
  };

  if (fehler && !anfrage) return <p className="meldung fehler">{fehler}</p>;
  if (!anfrage) return <p className="leer">Wird geladen …</p>;
  if (antworten) {
    return (
      <Antwort
        anfrage={anfrage}
        onGesendet={(a) => { setAnfrage(a); setAntworten(false); mailsLaden(); onGeaendert(); }}
        onAbbrechen={() => setAntworten(false)}
      />
    );
  }
  if (bearbeiten) {
    return (
      <Formular
        anfrage={anfrage}
        onGespeichert={(a) => { setAnfrage(a); setBearbeiten(false); onGeaendert(); }}
        onAbbrechen={() => setBearbeiten(false)}
      />
    );
  }

  const n = naechte(anfrage.gewuenscht_von, anfrage.gewuenscht_bis);
  return (
    <article className="karte-detail">
      <header>
        <h2>{anfrage.gast_name}</h2>
        <StatusMarke status={anfrage.status} />
      </header>
      {!anfrage.vollstaendig && (
        <p className="meldung warnung">Es fehlt: {fehlendText(anfrage.fehlende_angaben)}. Ergänzen Sie die Angaben über «Bearbeiten».</p>
      )}
      <dl className="angaben">
        <dt>Zeitraum</dt>
        <dd>{anfrage.gewuenscht_von ? `${datumVoll(anfrage.gewuenscht_von)} bis ${datumVoll(anfrage.gewuenscht_bis)}` : "fehlt"}{n ? ` (${n} ${n === 1 ? "Nacht" : "Nächte"})` : ""}</dd>
        <dt>Stellplatz</dt><dd>{typName(anfrage.stellplatz_typ)}</dd>
        <dt>Personen</dt><dd>{anfrage.anzahl_erwachsene} Erwachsene, {anfrage.anzahl_kinder} Kinder</dd>
        <dt>E-Mail</dt><dd><a href={`mailto:${anfrage.gast_email}`}>{anfrage.gast_email}</a></dd>
        <dt>Telefon</dt><dd>{anfrage.gast_telefon || "–"}</dd>
        <dt>Sprache</dt><dd>{SPRACHEN[anfrage.sprache] ?? anfrage.sprache}</dd>
        <dt>Eingang</dt><dd>{new Date(anfrage.eingangs_datum).toLocaleString("de-CH", { dateStyle: "medium", timeStyle: "short" })}, {QUELLEN[anfrage.quelle] ?? anfrage.quelle}</dd>
        <dt>Newsletter</dt><dd>{anfrage.newsletter_einwilligung ? "eingewilligt" : "nein"}</dd>
        {anfrage.bemerkung && (<><dt>Bemerkung</dt><dd className="mehrzeilig">{anfrage.bemerkung}</dd></>)}
      </dl>

      <div className="aktionen">
        {anfrage.vollstaendig && ["geprueft_vollstaendig", "erstantwort_gesendet", "zahlung_ausstehend"].includes(anfrage.status) && (
          <button className={`knopf ${anfrage.status === "geprueft_vollstaendig" ? "haupt" : "neben"}`} onClick={() => setAntworten(true)}>
            <Mail size={18} aria-hidden="true" />{mails.length ? "Weitere Antwort vorbereiten" : "Antwort vorbereiten"}
          </button>
        )}
        {(SCHRITTE[anfrage.status] || []).map(([status, text, art]) => (
          <button key={status} className={`knopf ${art}`} disabled={laeuft} onClick={() => statusSetzen(status)}>{text}</button>
        ))}
        <button className="knopf neben" onClick={() => setBearbeiten(true)}>Bearbeiten</button>
      </div>
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}

      {mails.length > 0 && (
        <details className="rohtext">
          <summary>Gesendete Antworten ({mails.length})</summary>
          {mails.map((m) => (
            <div key={m.id} className="mail">
              <p className="mail-betreff">{new Date(m.gesendet_am).toLocaleString("de-CH", { dateStyle: "medium", timeStyle: "short" })}: {m.betreff_final}</p>
              <pre>{m.koerper_final}</pre>
            </div>
          ))}
        </details>
      )}
      {anfrage.rohtext && (
        <details className="rohtext">
          <summary>Originalnachricht anzeigen</summary>
          <pre>{anfrage.rohtext}</pre>
        </details>
      )}
    </article>
  );
}

function Formular({ anfrage, neu = false, onGespeichert, onAbbrechen }) {
  const [werte, setWerte] = useState(() => ({ ...LEER, ...Object.fromEntries(Object.entries(anfrage).map(([k, v]) => [k, v ?? ""])) }));
  const [fehler, setFehler] = useState(null);
  const [laeuft, setLaeuft] = useState(false);
  const setze = (feld) => (e) => setWerte({ ...werte, [feld]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const speichern = async (e) => {
    e.preventDefault();
    setLaeuft(true); setFehler(null);
    const leerZuNull = (v) => (v === "" ? null : v);
    const daten = {
      sprache: werte.sprache,
      gast_name: werte.gast_name.trim(),
      gast_email: werte.gast_email.trim(),
      gast_telefon: leerZuNull(werte.gast_telefon),
      gewuenscht_von: leerZuNull(werte.gewuenscht_von),
      gewuenscht_bis: leerZuNull(werte.gewuenscht_bis),
      stellplatz_typ: leerZuNull(werte.stellplatz_typ),
      anzahl_erwachsene: Number(werte.anzahl_erwachsene || 0),
      anzahl_kinder: Number(werte.anzahl_kinder || 0),
      bemerkung: leerZuNull(werte.bemerkung),
      newsletter_einwilligung: Boolean(werte.newsletter_einwilligung),
    };
    try {
      const ergebnis = neu
        ? await api.post("/reservationsanfragen", {
          ...daten, quelle: werte.quelle, eingangs_datum: new Date().toISOString(), rohtext: leerZuNull(werte.rohtext),
        })
        : await api.patch(`/reservationsanfragen/${anfrage.id}`, daten);
      onGespeichert(ergebnis);
    } catch (err) { setFehler(err.message); } finally { setLaeuft(false); }
  };

  return (
    <form className="formular" onSubmit={speichern}>
      <h2>{neu ? "Anfrage erfassen" : "Anfrage bearbeiten"}</h2>
      <p className="hinweis">Felder ohne Angabe dürfen leer bleiben. Die Anfrage erscheint dann unter «Zu bearbeiten» mit dem Hinweis, was fehlt.</p>
      <div className="felder">
        <label className="breit">Name<input required value={werte.gast_name} onChange={setze("gast_name")} autoComplete="off" /></label>
        <label>E-Mail<input required type="email" value={werte.gast_email} onChange={setze("gast_email")} autoComplete="off" /></label>
        <label>Telefon<input value={werte.gast_telefon} onChange={setze("gast_telefon")} autoComplete="off" /></label>
        <label>Anreise<input type="date" value={werte.gewuenscht_von} onChange={setze("gewuenscht_von")} /></label>
        <label>Abreise<input type="date" value={werte.gewuenscht_bis} onChange={setze("gewuenscht_bis")} /></label>
        <label>Stellplatz
          <select value={werte.stellplatz_typ} onChange={setze("stellplatz_typ")}>
            <option value="">noch offen</option>
            {TYPEN.map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}
          </select>
        </label>
        <label>Sprache
          <select value={werte.sprache} onChange={setze("sprache")}>
            {Object.entries(SPRACHEN).map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
        </label>
        <label>Erwachsene<input type="number" min="0" value={werte.anzahl_erwachsene} onChange={setze("anzahl_erwachsene")} /></label>
        <label>Kinder<input type="number" min="0" value={werte.anzahl_kinder} onChange={setze("anzahl_kinder")} /></label>
        {neu && (
          <label>Eingang über
            <select value={werte.quelle} onChange={setze("quelle")}>
              {Object.entries(QUELLEN).map(([c, n]) => <option key={c} value={c}>{n}</option>)}
            </select>
          </label>
        )}
        <div className="feld breit"><label htmlFor="anfrage-bemerkung">Bemerkung</label><textarea id="anfrage-bemerkung" rows="3" value={werte.bemerkung} onChange={setze("bemerkung")} /></div>
        {neu && (
          <div className="feld breit"><label htmlFor="anfrage-rohtext">Originalnachricht (optional, z.B. Mailtext einfügen)</label>
            <textarea id="anfrage-rohtext" rows="5" value={werte.rohtext} onChange={setze("rohtext")} /></div>
        )}
        <label className="kontrolle breit">
          <input type="checkbox" checked={Boolean(werte.newsletter_einwilligung)} onChange={setze("newsletter_einwilligung")} />
          Gast hat ausdrücklich in den Newsletter eingewilligt
        </label>
      </div>
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
      <div className="aktionen">
        <button className="knopf haupt" type="submit" disabled={laeuft}>{neu ? "Anfrage speichern" : "Änderungen speichern"}</button>
        <button className="knopf leise" type="button" onClick={onAbbrechen}>Abbrechen</button>
      </div>
    </form>
  );
}
