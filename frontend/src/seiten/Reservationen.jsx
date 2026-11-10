import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CalendarX, ClipboardPaste, Copy, Mail, MessageSquare, Plus, Search } from "lucide-react";
import { api } from "../api.js";
import { TypMarke } from "../typen.jsx";
import { HoheBelegung } from "./Belegung.jsx";
import {
  QUELLEN, SPRACHEN, STATUS, TYPEN, datumKurz, datumVoll, fehlendText, naechte, personen, personenLang, statusName, zeitraum,
} from "../format.js";

const ABLAGEN = [
  { code: "offen", name: "Zu bearbeiten", status: ["neu", "unvollstaendig", "geprueft_vollstaendig"] },
  { code: "laufend", name: "Warten auf Gast", status: ["in_abklaerung", "erstantwort_gesendet", "zahlung_ausstehend"] },
  { code: "akzeptiert", name: "Akzeptiert", status: ["bezahlt_akzeptiert", "angereist"] },
  { code: "erledigt", name: "Abgelehnt / storniert", status: ["abgelehnt", "storniert", "nicht_erschienen"] },
  { code: "alle", name: "Alle", status: null },
];

const AKZEPTIEREN = "akzeptieren";
const ERST = "erstantwort_zahlungsinfo";
const BESTAETIGUNG = "bestaetigung_definitiv";
const ZAHLUNGSARTEN = { bankueberweisung: "Banküberweisung", twint: "TWINT", bar: "Bar", kreditkarte: "Kreditkarte" };
const chf = (x) => `CHF ${Number(x).toLocaleString("de-CH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Nächste sinnvolle Schritte je Status (Konzept 10.2–10.5)
const SCHRITTE = {
  neu: [],
  unvollstaendig: [["abgelehnt", "Ablehnen", "leise"]],
  // AKZEPTIEREN öffnet das Formular mit dem gutgeschriebenen Betrag
  geprueft_vollstaendig: [["erstantwort_gesendet", "Schon beantwortet", "neben"], [AKZEPTIEREN, "Ohne Anzahlung akzeptieren", "leise"], ["abgelehnt", "Ablehnen", "leise"]],
  in_abklaerung: [["erstantwort_gesendet", "Anzahlung schon angefordert", "neben"], [AKZEPTIEREN, "Ohne Anzahlung akzeptieren", "leise"], ["abgelehnt", "Ablehnen", "leise"]],
  erstantwort_gesendet: [["zahlung_ausstehend", "Wartet auf Zahlung", "neben"], [AKZEPTIEREN, "Zahlung erhalten, akzeptieren", "haupt"], ["abgelehnt", "Ablehnen", "leise"]],
  zahlung_ausstehend: [[AKZEPTIEREN, "Zahlung erhalten, akzeptieren", "haupt"], ["storniert", "Stornieren", "leise"]],
  bezahlt_akzeptiert: [["storniert", "Stornieren", "leise"]],
  angereist: [],
  nicht_erschienen: [["bezahlt_akzeptiert", "Zurück auf «Akzeptiert»", "neben"]],
  abgelehnt: [["neu", "Wieder öffnen", "neben"]],
  storniert: [["neu", "Wieder öffnen", "neben"]],
};

// wie _STATUS_NUR_VOLLSTAENDIG im Backend
const NUR_VOLLSTAENDIG = new Set(["erstantwort_gesendet", "zahlung_ausstehend", "bezahlt_akzeptiert", AKZEPTIEREN]);

const LEER = {
  quelle: "manuell", sprache: "de", gast_name: "", gast_email: "", gast_telefon: "",
  gewuenscht_von: "", gewuenscht_bis: "", stellplatz_typ: "", anzahl_erwachsene: 2, anzahl_kinder: 0, anzahl_kleinkinder: 0,
  bemerkung: "", rohtext: "",
};

export function StatusMarke({ status }) {
  return <span className={`marke-status ton-${STATUS[status]?.ton ?? "info"}`}>{statusName(status)}</span>;
}

export default function Reservationen() {
  const [anfragen, setAnfragen] = useState(null);
  // #/reservationen?id=… (z.B. aus der Belegung): Anfrage direkt öffnen
  const startId = new URLSearchParams(window.location.hash.split("?")[1] || "").get("id");
  const [ablage, setAblage] = useState(startId ? "alle" : "offen");
  const [suche, setSuche] = useState("");
  const [auswahl, setAuswahl] = useState(startId); // id | "neu" | "text" | null
  const [fehler, setFehler] = useState(null);

  const laden = useCallback(() => {
    api.get("/reservationsanfragen").then(setAnfragen).catch((e) => setFehler(e.message));
  }, []);
  useEffect(laden, [laden]);

  const inAblage = (ablageCode, x) => {
    const a = ABLAGEN.find((y) => y.code === ablageCode);
    return !a.status || a.status.includes(x.status) || (ablageCode === "offen" && x.neue_mails > 0);
  };
  const anzahl = useMemo(() => Object.fromEntries(ABLAGEN.map((a) => [
    a.code, (anfragen || []).filter((x) => inAblage(a.code, x)).length,
  ])), [anfragen]); // eslint-disable-line react-hooks/exhaustive-deps

  const liste = useMemo(() => {
    const s = suche.trim().toLowerCase();
    // mit Suchbegriff: in allen Ablagen suchen (z.B. Gast nennt am Telefon die Nummer)
    return (anfragen || [])
      .filter((a) => s || inAblage(ablage, a))
      .filter((a) => !s || `${a.nummer ?? ""} ${a.gast_name} ${a.gast_email}`.toLowerCase().includes(s));
  }, [anfragen, ablage, suche]); // eslint-disable-line react-hooks/exhaustive-deps

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
            <input type="search" placeholder="Name, E-Mail oder Nummer suchen" value={suche} onChange={(e) => setSuche(e.target.value)} />
          </label>
          {anfragen === null && <p className="leer">Wird geladen …</p>}
          {suche.trim() && <p className="hinweis">Suche in allen Ablagen.</p>}
          {anfragen && liste.length === 0 && suche.trim() && <p className="leer">Keine Anfrage gefunden.</p>}
          {anfragen && liste.length === 0 && !suche.trim() && (
            <p className="leer">Keine Anfragen in dieser Ablage. Neue Anfragen aus dem Postfach oder per Telefon erscheinen unter «Zu bearbeiten».</p>
          )}
          <ul className="anfrageliste">
            {liste.map((a) => (
              <li key={a.id}>
                <button className="anfrage" aria-current={auswahl === a.id ? "true" : undefined} onClick={() => setAuswahl(a.id)}>
                  <span className="zeile1">
                    <strong>{a.gast_name}{a.nummer && <span className="nummer">{a.nummer}</span>}</strong>
                    <span className="marken">
                      {a.neue_mails > 0 && <span className="marke-neu">{a.neue_mails === 1 ? "Neue Mail" : `${a.neue_mails} neue Mails`}</span>}
                      <StatusMarke status={a.status} />
                    </span>
                  </span>
                  <span className="zeile2">
                    {zeitraum(a.gewuenscht_von, a.gewuenscht_bis)}
                    <span className="trenner" aria-hidden="true" /><TypMarke code={a.stellplatz_typ} />
                    <span className="trenner" aria-hidden="true" />{personen(a.anzahl_erwachsene, a.anzahl_kinder, a.anzahl_kleinkinder)}
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

const FREI = "freie_antwort";
const AUSGEBUCHT = "absage_ausgebucht";

const ANTWORT_TITEL = { [ERST]: "Antwort mit Anzahlung", [FREI]: "Freie Antwort", [BESTAETIGUNG]: "Bestätigung", [AUSGEBUCHT]: "Absage: ausgebucht" };

function Antwort({ anfrage, typ, onGesendet, onAbbrechen }) {
  const frei = typ === FREI;
  const sofort = typ !== ERST; // ohne Eingaben: Text gleich erstellen
  const [eingabe, setEingabe] = useState({ sprache: anfrage.sprache || "de", betrag: "", zahlungsfrist: "" });
  const [entwurf, setEntwurf] = useState(null);
  const [fehler, setFehler] = useState(null);
  const [kopiert, setKopiert] = useState(null);
  const [laeuft, setLaeuft] = useState(false);
  const textfeld = useRef(null);
  const cursor = useRef(null);

  const basis = useRef(null); // erstellter Text und Einfügestelle, um den eigenen Text zu erkennen

  const vorbereiten = useCallback(async (werte, eigenerText = "") => {
    setFehler(null); setLaeuft(true);
    try {
      const e = await api.post(`/reservationsanfragen/${anfrage.id}/antwort/vorbereiten`, sofort
        ? { typ, sprache: werte.sprache }
        : { sprache: werte.sprache, betrag: werte.betrag, zahlungsfrist: werte.zahlungsfrist || null });
      if (frei && e.einfuege_position != null) {
        // Platz für den eigenen Text zwischen Anrede und Gruss
        const p = e.einfuege_position;
        basis.current = { vor: e.text.slice(0, p), nach: e.text.slice(p) };
        e.text = `${basis.current.vor}${eigenerText || "\n\n"}${basis.current.nach}`;
        cursor.current = eigenerText ? p + eigenerText.replace(/\s+$/, "").length : p;
      }
      setEntwurf(e);
    } catch (err) { setFehler(err.message); } finally { setLaeuft(false); }
  }, [anfrage.id, frei, sofort, typ]);

  // Freie Antwort und Bestätigung: Text sofort erstellen
  useEffect(() => { if (sofort) vorbereiten({ sprache: anfrage.sprache || "de" }); }, [sofort, vorbereiten, anfrage.sprache]);

  useEffect(() => {
    if (entwurf && cursor.current != null && textfeld.current) {
      textfeld.current.focus();
      textfeld.current.setSelectionRange(cursor.current, cursor.current);
      cursor.current = null;
    }
  }, [entwurf]);

  const spracheWechseln = (sprache) => {
    const werte = { ...eingabe, sprache };
    setEingabe(werte);
    if (!sofort) return;
    if (!frei) { vorbereiten(werte); return; }
    // Bereits geschriebenen Text zwischen Anrede und Gruss übernehmen
    let eigenerText = "";
    const b = basis.current;
    if (entwurf && b && entwurf.text.startsWith(b.vor) && entwurf.text.endsWith(b.nach)) {
      eigenerText = entwurf.text.slice(b.vor.length, entwurf.text.length - b.nach.length);
    }
    vorbereiten(werte, eigenerText.trim() ? eigenerText : "");
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
        betrag: typ === ERST ? eingabe.betrag : null,
      }));
    } catch (err) { setFehler(err.message); } finally { setLaeuft(false); }
  };

  const neuerStatus = typ === BESTAETIGUNG ? null
    : typ === AUSGEBUCHT ? "Abgelehnt"
    : frei ? (["erstantwort_gesendet", "zahlung_ausstehend", "bezahlt_akzeptiert"].includes(anfrage.status) ? null : "In Abklärung")
      : "Antwort gesendet";

  return (
    <div className="formular">
      <h2>{ANTWORT_TITEL[typ]} an {anfrage.gast_name}{anfrage.nummer && <span className="nummer"> · {anfrage.nummer}</span>}</h2>
      {typ === BESTAETIGUNG && (
        <p className="hinweis">
          Bestätigt dem Gast, dass die Reservation definitiv gebucht ist
          {anfrage.anzahlung_erhalten ? `, mit Dank für die Anzahlung von ${chf(anfrage.anzahlung_erhalten)}` : ""}.
        </p>
      )}
      {typ === AUSGEBUCHT && (
        <p className="hinweis">
          Absage mit den ausgebuchten Nächten des gewünschten Zeitraums und, falls in Sicht, dem nächsten freien Zeitraum
          gleicher Länge. Nach dem Versand gilt die Anfrage als «abgelehnt».
        </p>
      )}
      {frei && (
        <p className="hinweis">
          Für Fragen des Gastes, ohne Aufforderung zur Anzahlung: Anrede, Ihr Text und die Signatur. Beim Wechsel der
          Sprache werden Anrede, Gruss und Betreff angepasst, Ihr Text bleibt.
        </p>
      )}
      <form className="felder" onSubmit={(e) => { e.preventDefault(); vorbereiten(eingabe); }}>
        <label>Sprache
          <select value={eingabe.sprache} onChange={(e) => spracheWechseln(e.target.value)}>
            {Object.entries(SPRACHEN).map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
        </label>
        {typ === ERST && (
          <>
            <label>Anzahlung in CHF
              <input required type="number" min="0.05" step="0.05" inputMode="decimal" value={eingabe.betrag}
                onChange={(e) => setEingabe({ ...eingabe, betrag: e.target.value })} />
            </label>
            <label>Zahlungsfrist (optional)
              <input type="date" value={eingabe.zahlungsfrist} onChange={(e) => setEingabe({ ...eingabe, zahlungsfrist: e.target.value })} />
            </label>
          </>
        )}
        {(!sofort || !entwurf) && (
          <div className="aktionen breit">
            {typ === ERST && <button className="knopf haupt" type="submit" disabled={laeuft}>{entwurf ? "Text neu erstellen" : "Text erstellen"}</button>}
            <button className="knopf leise" type="button" onClick={onAbbrechen}>Abbrechen</button>
          </div>
        )}
      </form>
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}

      {entwurf && (
        <>
          {entwurf.warnungen.map((w) => <p key={w} className="meldung warnung">{w}. Unter Einstellungen › Betriebsangaben ergänzen.</p>)}
          <p className="hinweis">
            {frei ? "Ihre Antwort zwischen Anrede und Gruss schreiben." : "Prüfen und bei Bedarf anpassen."} Danach den Text in
            Ihr Mailprogramm übernehmen, an {entwurf.empfaenger} senden und hier als gesendet markieren.
          </p>
          <div className="feld"><label htmlFor="antwort-an">An</label><input id="antwort-an" readOnly value={entwurf.empfaenger} /></div>
          <div className="feld"><label htmlFor="antwort-betreff">Betreff</label>
            <input id="antwort-betreff" value={entwurf.betreff} onChange={(e) => setEntwurf({ ...entwurf, betreff: e.target.value })} /></div>
          <div className="feld"><label htmlFor="antwort-text">Text</label>
            <textarea id="antwort-text" ref={textfeld} rows={frei ? 14 : 22} value={entwurf.text}
              onChange={(e) => setEntwurf({ ...entwurf, text: e.target.value })} /></div>
          <div className="aktionen">
            <button className="knopf neben" type="button" onClick={() => kopieren("betreff", entwurf.betreff)}><Copy size={16} aria-hidden="true" />{kopiert === "betreff" ? "Betreff kopiert" : "Betreff kopieren"}</button>
            <button className="knopf neben" type="button" onClick={() => kopieren("text", entwurf.text)}><Copy size={16} aria-hidden="true" />{kopiert === "text" ? "Text kopiert" : "Text kopieren"}</button>
            <a className="knopf neben" href={mailto}><Mail size={16} aria-hidden="true" />Im Mailprogramm öffnen</a>
          </div>
          <div className="aktionen">
            <button className="knopf haupt" type="button" disabled={laeuft} onClick={gesendet}>Als gesendet markieren</button>
            {sofort && <button className="knopf leise" type="button" onClick={onAbbrechen}>{typ === BESTAETIGUNG ? "Später" : "Abbrechen"}</button>}
          </div>
          <p className="hinweis">
            «Als gesendet markieren» speichert den Text im Mailverlauf der Anfrage
            {neuerStatus ? ` und setzt den Status auf «${neuerStatus}».` : ". Der Status bleibt unverändert."}
          </p>
        </>
      )}
    </div>
  );
}

function Akzeptieren({ anfrage, onAkzeptiert, onAbbrechen }) {
  const mitAnzahlung = ["erstantwort_gesendet", "zahlung_ausstehend"].includes(anfrage.status);
  const heute = new Date().toLocaleDateString("sv-SE");
  const [werte, setWerte] = useState({
    betrag: mitAnzahlung && anfrage.anzahlung_verlangt ? anfrage.anzahlung_verlangt : "",
    zahlungsart: "bankueberweisung", eingegangen_am: heute,
  });
  const [fehler, setFehler] = useState(null);
  const [laeuft, setLaeuft] = useState(false);
  const betrag = Number(werte.betrag) || 0;

  const absenden = async (e) => {
    e.preventDefault(); setFehler(null); setLaeuft(true);
    try {
      onAkzeptiert(await api.post(`/reservationsanfragen/${anfrage.id}/zahlung-bestaetigen`, betrag > 0
        ? { betrag: werte.betrag, zahlungsart: werte.zahlungsart, eingegangen_am: werte.eingegangen_am || null }
        : {}));
    } catch (err) { setFehler(err.message); } finally { setLaeuft(false); }
  };

  return (
    <form className="formular" onSubmit={absenden}>
      <h2>Reservation akzeptieren{anfrage.nummer && <span className="nummer"> · {anfrage.nummer}</span>}</h2>
      <p className="hinweis">
        {anfrage.gast_name}, {zeitraum(anfrage.gewuenscht_von, anfrage.gewuenscht_bis)}.
        {anfrage.anzahlung_verlangt ? ` Verlangt wurden ${chf(anfrage.anzahlung_verlangt)}.` : ""}
      </p>
      <p id="akz-betrag-hinweis" className="hinweis">
        Erfassen Sie den Betrag, der auf dem Konto gutgeschrieben wurde, z.B. nach Umrechnung einer Zahlung in Euro.
        Leer lassen, wenn ohne Anzahlung akzeptiert wird (z.B. Stammgäste).
      </p>
      <div className="felder">
        <div className="feld">
          <label htmlFor="akz-betrag">Gutgeschriebene Anzahlung in CHF</label>
          <input id="akz-betrag" type="number" min="0" step="0.01" inputMode="decimal" value={werte.betrag}
            aria-describedby="akz-betrag-hinweis" onChange={(e) => setWerte({ ...werte, betrag: e.target.value })} />
        </div>
        {betrag > 0 && (
          <>
            <label>Zahlungsart
              <select value={werte.zahlungsart} onChange={(e) => setWerte({ ...werte, zahlungsart: e.target.value })}>
                {Object.entries(ZAHLUNGSARTEN).map(([c, n]) => <option key={c} value={c}>{n}</option>)}
              </select>
            </label>
            <label>Eingegangen am
              <input type="date" value={werte.eingegangen_am} max={heute} onChange={(e) => setWerte({ ...werte, eingegangen_am: e.target.value })} />
            </label>
          </>
        )}
      </div>
      {anfrage.hohe_belegung?.length > 0 && <HoheBelegung liste={anfrage.hohe_belegung} />}
      {betrag > 0 && anfrage.anzahlung_verlangt && Math.abs(betrag - Number(anfrage.anzahlung_verlangt)) >= 0.005 && (
        <p className="betrag-hinweis">
          {chf(Math.abs(betrag - Number(anfrage.anzahlung_verlangt)))} {betrag < Number(anfrage.anzahlung_verlangt) ? "weniger" : "mehr"} als
          verlangt. Für die Rechnung gilt der gutgeschriebene Betrag.
        </p>
      )}
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
      <div className="aktionen">
        <button className="knopf haupt" type="submit" disabled={laeuft}>
          {betrag > 0 ? `${chf(betrag)} erhalten, akzeptieren` : "Ohne Anzahlung akzeptieren"}
        </button>
        <button className="knopf leise" type="button" onClick={onAbbrechen}>Abbrechen</button>
      </div>
      <p className="hinweis">Danach wird die Bestätigung an den Gast vorbereitet («definitiv gebucht»).</p>
    </form>
  );
}

function Verlauf({ mails, offen }) {
  const zeit = (iso) => new Date(iso).toLocaleString("de-CH", { dateStyle: "medium", timeStyle: "short" });
  return (
    <details className="rohtext verlauf" open={offen}>
      <summary>Mailverlauf ({mails.length})</summary>
      <ol className="verlauf-liste">
        {mails.map((m) => (
          <li key={m.id} className={`mail ${m.richtung}`}>
            <p className="mail-kopf">
              <span className="richtung">{m.richtung === "eingang" ? "Vom Gast" : "Antwort an den Gast"}</span>
              {!m.gelesen && <span className="marke-neu">neu</span>}
              {m.weitergeleitet && <span className="zusatz">weitergeleitet</span>}
              {m.quelle === "tool" && <span className="zusatz">im Tool vorbereitet</span>}
              <time dateTime={m.datum}>{zeit(m.datum)}</time>
            </p>
            <p className="mail-betreff">{m.betreff || "(ohne Betreff)"}<span>{m.richtung === "eingang" ? `von ${m.von}` : `an ${m.an ?? ""}`}</span></p>
            <pre>{m.text}</pre>
          </li>
        ))}
      </ol>
    </details>
  );
}

function Detail({ id, onGeaendert }) {
  const [anfrage, setAnfrage] = useState(null);
  const [bearbeiten, setBearbeiten] = useState(false);
  const [antworten, setAntworten] = useState(null); // null | Vorlagentyp
  const [akzeptieren, setAkzeptieren] = useState(false);
  const [mails, setMails] = useState([]);
  const [fehler, setFehler] = useState(null);
  const [laeuft, setLaeuft] = useState(false);

  const mailsLaden = useCallback(() => {
    api.get(`/reservationsanfragen/${id}/mails`).then(setMails).catch(() => {});
  }, [id]);
  useEffect(() => {
    api.get(`/reservationsanfragen/${id}`).then((a) => {
      setAnfrage(a);
      // neue Mails des Gastes gelten als gelesen, sobald die Anfrage geöffnet ist
      // (im Verlauf bleiben sie in dieser Ansicht als «neu» markiert)
      if (a.neue_mails > 0) api.post(`/reservationsanfragen/${id}/mails/gelesen`).then(onGeaendert).catch(() => {});
    }).catch((e) => setFehler(e.message));
    mailsLaden();
  }, [id, mailsLaden]); // eslint-disable-line react-hooks/exhaustive-deps

  const statusSetzen = async (status) => {
    setLaeuft(true); setFehler(null);
    try {
      setAnfrage(await api.post(`/reservationsanfragen/${id}/status`, { status }));
      onGeaendert();
    } catch (e) { setFehler(e.message); } finally { setLaeuft(false); }
  };

  if (fehler && !anfrage) return <p className="meldung fehler">{fehler}</p>;
  if (!anfrage) return <p className="leer">Wird geladen …</p>;
  if (akzeptieren) {
    return (
      <Akzeptieren
        anfrage={anfrage}
        onAkzeptiert={(a) => { setAnfrage(a); setAkzeptieren(false); onGeaendert(); setAntworten(BESTAETIGUNG); }}
        onAbbrechen={() => setAkzeptieren(false)}
      />
    );
  }
  if (antworten) {
    return (
      <Antwort
        anfrage={anfrage}
        typ={antworten}
        onGesendet={(a) => { setAnfrage(a); setAntworten(null); mailsLaden(); onGeaendert(); }}
        onAbbrechen={() => setAntworten(null)}
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
        {anfrage.nummer && <span className="nummer">Nr. {anfrage.nummer}</span>}
        <StatusMarke status={anfrage.status} />
      </header>
      {anfrage.hohe_belegung?.length > 0 && <HoheBelegung liste={anfrage.hohe_belegung} />}
      {anfrage.ausgebucht?.zeitraeume?.length > 0 && <Ausgebucht info={anfrage.ausgebucht} onAbsage={() => setAntworten(AUSGEBUCHT)} />}
      {anfrage.status === "angereist" && (
        <p className="meldung ok">Angereist – der Aufenthalt ist in der <a href={`#/belegung?tag=${anfrage.gewuenscht_von}&eintrag=${anfrage.id}`}>Belegung</a> erfasst.</p>
      )}
      {!anfrage.vollstaendig && (
        <p className="meldung warnung">Es fehlt: {fehlendText(anfrage.fehlende_angaben)}. Ergänzen Sie die Angaben über «Bearbeiten».</p>
      )}
      <dl className="angaben">
        <dt>Zeitraum</dt>
        <dd>{anfrage.gewuenscht_von ? `${datumVoll(anfrage.gewuenscht_von)} bis ${datumVoll(anfrage.gewuenscht_bis)}` : "fehlt"}{n ? ` (${n} ${n === 1 ? "Nacht" : "Nächte"})` : ""}</dd>
        <dt>Stellplatz</dt><dd><TypMarke code={anfrage.stellplatz_typ} /></dd>
        <dt>Personen</dt><dd>{personenLang(anfrage.anzahl_erwachsene, anfrage.anzahl_kinder, anfrage.anzahl_kleinkinder)}</dd>
        <dt>E-Mail</dt><dd><a href={`mailto:${anfrage.gast_email}`}>{anfrage.gast_email}</a></dd>
        <dt>Telefon</dt><dd>{anfrage.gast_telefon || "–"}</dd>
        <dt>Sprache</dt><dd>{SPRACHEN[anfrage.sprache] ?? anfrage.sprache}</dd>
        <dt>Eingang</dt><dd>{new Date(anfrage.eingangs_datum).toLocaleString("de-CH", { dateStyle: "medium", timeStyle: "short" })}, {QUELLEN[anfrage.quelle] ?? anfrage.quelle}</dd>
        <dt>Newsletter</dt><dd>{anfrage.newsletter_einwilligung ? "eingewilligt" : "nein"}</dd>
        {(anfrage.anzahlung_verlangt || anfrage.anzahlung_erhalten || anfrage.status === "bezahlt_akzeptiert") && (
          <>
            <dt>Anzahlung</dt>
            <dd>
              {anfrage.anzahlung_erhalten
                ? `${chf(anfrage.anzahlung_erhalten)} erhalten${anfrage.anzahlung_eingegangen_am ? ` am ${datumVoll(anfrage.anzahlung_eingegangen_am)}` : ""}${anfrage.anzahlung_zahlungsart ? ` (${ZAHLUNGSARTEN[anfrage.anzahlung_zahlungsart] ?? anfrage.anzahlung_zahlungsart})` : ""}`
                : anfrage.status === "bezahlt_akzeptiert" ? "keine (ohne Anzahlung akzeptiert)" : "noch nicht eingegangen"}
              {anfrage.anzahlung_verlangt ? `, verlangt ${chf(anfrage.anzahlung_verlangt)}` : ""}
            </dd>
          </>
        )}
        {anfrage.bemerkung && (<><dt>Bemerkung</dt><dd className="mehrzeilig">{anfrage.bemerkung}</dd></>)}
      </dl>

      <div className="aktionen">
        {anfrage.vollstaendig && ["geprueft_vollstaendig", "in_abklaerung", "erstantwort_gesendet", "zahlung_ausstehend"].includes(anfrage.status) && (
          <button className={`knopf ${["geprueft_vollstaendig", "in_abklaerung"].includes(anfrage.status) ? "haupt" : "neben"}`}
            onClick={() => setAntworten(ERST)}>
            <Mail size={18} aria-hidden="true" />Antwort mit Anzahlung
          </button>
        )}
        {anfrage.status === "bezahlt_akzeptiert" && (
          <button className="knopf neben" onClick={() => setAntworten(BESTAETIGUNG)}>
            <Mail size={18} aria-hidden="true" />Bestätigung vorbereiten
          </button>
        )}
        {!["abgelehnt", "storniert"].includes(anfrage.status) && (
          <button className="knopf neben" onClick={() => setAntworten(FREI)}>
            <MessageSquare size={18} aria-hidden="true" />Freie Antwort
          </button>
        )}
        {(SCHRITTE[anfrage.status] || []).filter(([status]) => anfrage.vollstaendig || !NUR_VOLLSTAENDIG.has(status)).map(([status, text, art]) => (
          <button key={status} className={`knopf ${art}`} disabled={laeuft}
            onClick={() => (status === AKZEPTIEREN ? setAkzeptieren(true) : statusSetzen(status))}>{text}</button>
        ))}
        <button className="knopf neben" onClick={() => setBearbeiten(true)}>Bearbeiten</button>
      </div>
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}

      {mails.length > 0 && <Verlauf mails={mails} offen={anfrage.neue_mails > 0} />}
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
      anzahl_kleinkinder: Number(werte.anzahl_kleinkinder || 0),
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
        <label>Erwachsene (ab 16)<input type="number" min="0" value={werte.anzahl_erwachsene} onChange={setze("anzahl_erwachsene")} /></label>
        <label>Kinder (6–15)<input type="number" min="0" value={werte.anzahl_kinder} onChange={setze("anzahl_kinder")} /></label>
        <label>Kleinkinder (0–5)<input type="number" min="0" value={werte.anzahl_kleinkinder ?? 0} onChange={setze("anzahl_kleinkinder")} /></label>
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

function Ausgebucht({ info, onAbsage }) {
  const alle = info.naechte_voll === info.naechte;
  const zeitraeume = info.zeitraeume.map((z) => `${datumKurz(z.von)} – ${datumKurz(z.bis)}`).join(", ");
  return (
    <div className="meldung fehler ausgebucht">
      <p>
        <strong>{alle ? "Ausgebucht" : `${info.naechte_voll} von ${info.naechte} Nächten ausgebucht`}</strong>: {zeitraeume}.
        {info.wieder_frei ? ` Nächster freier Zeitraum mit ${info.naechte} ${info.naechte === 1 ? "Nacht" : "Nächten"}: ${datumKurz(info.wieder_frei.von)} – ${datumKurz(info.wieder_frei.bis)}.` : " In den nächsten Wochen ist kein gleich langer Zeitraum frei."}
      </p>
      <button className="knopf neben" onClick={onAbsage}><CalendarX size={18} aria-hidden="true" />Absage: ausgebucht</button>
    </div>
  );
}
