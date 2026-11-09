// Modul «Buchungen & Aufenthalte»: wer auf dem Platz ist, wer anreist, wer abgereist ist.
// Details je Aufenthalt: Gast, Zeitraum (ganz verlängern/verkürzen) und Leistungen
// mit eigenem Zeitraum (Abwesenheiten, Personen mit Zusatzzelt, Strom …) samt Taxen.
// Reservationen und Belegung funktionieren auch ohne dieses Modul.
import { useCallback, useEffect, useState } from "react";
import { LogIn, Plus } from "lucide-react";
import { api } from "../api.js";
import {
  STATUS, ausIso, datumKurz, datumVoll, heuteIso, isoDatum, naechte, personen, personenLang, plusTage, statusName,
} from "../format.js";
import { TypMarke, typStil } from "../typen.jsx";
import { ANDERES, Bestaetigung, CheckIn, LAENDER, Schublade } from "./Belegung.jsx";

const REGISTER = [
  { code: "platz", name: "Auf dem Platz" },
  { code: "anreisen", name: "Anreisen" },
  { code: "abgereist", name: "Abgereist" },
];
const VORSCHAU_TAGE = 7;
const ABGEREIST_TAGE = 60;
const TAG = new Intl.DateTimeFormat("de-CH", { weekday: "long", day: "numeric", month: "long" });
const chf = (x) => `CHF ${Number(x).toFixed(2)}`;
const hashParameter = () => new URLSearchParams(window.location.hash.split("?")[1] || "");
const anzahlText = (n, eins, mehr) => `${n} ${n === 1 ? eins : mehr}`;

export default function Aufenthalte({ module = [] }) {
  const heute = heuteIso();
  const preiseAktiv = module.some((m) => m.code === "artikel" && m.aktiv);
  const [register, setRegister] = useState("platz");
  const [daten, setDaten] = useState(null);
  const [fehler, setFehler] = useState(null);
  // Schublade: { art: "aufenthalt", id } | { art: "reservation", id } | { art: "checkin", eintrag? }
  const [schublade, setSchublade] = useState(hashParameter().get("id") ? { art: "aufenthalt", id: hashParameter().get("id") } : null);

  const laden = useCallback(async () => {
    setFehler(null);
    try {
      const bisVorschau = isoDatum(plusTage(new Date(), VORSCHAU_TAGE));
      const abgereistAb = isoDatum(plusTage(new Date(), -ABGEREIST_TAGE));
      const [platz, abgereist, bel, nicht] = await Promise.all([
        api.get("/aufenthalte?status=eingecheckt"),
        api.get(`/aufenthalte?status=ausgecheckt&von=${abgereistAb}`),
        api.get(`/belegung?von=${heute}&bis=${bisVorschau}&status=akzeptiert`),
        api.get("/belegung/nicht-angereist"),
      ]);
      const anreisen = bel.eintraege.filter((e) => e.art !== "aufenthalt" && e.status === "bezahlt_akzeptiert" && e.von >= heute);
      setDaten({ platz, abgereist, anreisen, nicht });
    } catch (e) { setFehler(e.message); }
  }, [heute]);
  useEffect(() => { laden(); }, [laden]);

  useEffect(() => {
    const uebernehmen = () => { const id = hashParameter().get("id"); if (id) setSchublade({ art: "aufenthalt", id }); };
    const zu = (e) => { if (e.key === "Escape") setSchublade(null); };
    window.addEventListener("hashchange", uebernehmen);
    window.addEventListener("keydown", zu);
    return () => { window.removeEventListener("hashchange", uebernehmen); window.removeEventListener("keydown", zu); };
  }, []);

  const anzahl = daten ? { platz: daten.platz.length, anreisen: daten.anreisen.length + daten.nicht.length, abgereist: daten.abgereist.length } : {};
  const oeffnen = (id) => setSchublade({ art: "aufenthalt", id });

  return (
    <div className="seite">
      <header className="kopf">
        <h1>Aufenthalte</h1>
        <div className="aktionen">
          <button className="knopf haupt" onClick={() => setSchublade({ art: "checkin" })}>
            <LogIn size={18} aria-hidden="true" />Check-in ohne Reservation
          </button>
        </div>
      </header>

      <div className="ablagen" role="tablist" aria-label="Aufenthalte">
        {REGISTER.map((r) => (
          <button key={r.code} role="tab" aria-selected={register === r.code} onClick={() => setRegister(r.code)}>
            {r.name} <span className="zahl">{anzahl[r.code] ?? 0}</span>
          </button>
        ))}
      </div>

      {fehler && <p className="meldung fehler">{fehler}</p>}
      {!fehler && !daten && <p className="leer">Wird geladen …</p>}
      {daten && register === "platz" && <PlatzListe liste={daten.platz} heute={heute} onOeffnen={oeffnen} />}
      {daten && register === "anreisen" && (
        <AnreiseListe liste={daten.anreisen} nicht={daten.nicht} heute={heute}
          onOeffnen={(id) => setSchublade({ art: "reservation", id })} />
      )}
      {daten && register === "abgereist" && (
        <>
          <p className="hinweis">Abreisen der letzten {ABGEREIST_TAGE} Tage, neueste zuerst.</p>
          <AufenthaltListe liste={daten.abgereist} heute={heute} onOeffnen={oeffnen} leer="Keine Abreisen in dieser Zeit." />
        </>
      )}

      {schublade && (
        <Schublade breit={schublade.art === "aufenthalt"} titel="Aufenthalt" onSchliessen={() => setSchublade(null)}>
          {schublade.art === "aufenthalt" && (
            <AufenthaltPanel id={schublade.id} heute={heute} preiseAktiv={preiseAktiv} onGeaendert={laden}
              onGeloescht={() => { laden(); setSchublade(null); }} />
          )}
          {schublade.art === "reservation" && (
            <ReservationPanel id={schublade.id} heute={heute}
              onCheckin={(a) => setSchublade({ art: "checkin", eintrag: a })} />
          )}
          {schublade.art === "checkin" && (
            <CheckIn eintrag={schublade.eintrag} heute={heute}
              onAbbrechen={() => setSchublade(schublade.eintrag ? { art: "reservation", id: schublade.eintrag.id } : null)}
              onEingecheckt={(a) => { laden(); setRegister("platz"); oeffnen(a.buchung_id); }} />
          )}
        </Schublade>
      )}
    </div>
  );
}

// --- Listen ----------------------------------------------------------------------

function PlatzListe({ liste, heute, onOeffnen }) {
  const faellig = liste.filter((a) => a.bis <= heute);
  const weitere = liste.filter((a) => a.bis > heute);
  return (
    <div className="aufenthalt-gruppen">
      {faellig.length > 0 && (
        <section>
          <h2 className="gruppe-titel">Abreise heute{faellig.some((a) => a.bis < heute) ? " oder überfällig" : ""}</h2>
          <AufenthaltListe liste={faellig} heute={heute} onOeffnen={onOeffnen} />
        </section>
      )}
      <section>
        {faellig.length > 0 && <h2 className="gruppe-titel">Bleiben länger</h2>}
        <AufenthaltListe liste={weitere} heute={heute} onOeffnen={onOeffnen}
          leer={faellig.length ? "Sonst niemand." : "Zurzeit ist niemand eingecheckt."} />
      </section>
    </div>
  );
}

function AufenthaltListe({ liste, heute, onOeffnen, leer = "Keine Einträge." }) {
  if (liste.length === 0) return <p className="leer">{leer}</p>;
  return (
    <ul className="aufenthalt-liste">
      {liste.map((a) => {
        const n = naechte(a.von, a.bis);
        const hinweis = a.status === "eingecheckt" && a.bis < heute ? ["ziegel", "Abreise überfällig"]
          : a.status === "eingecheckt" && a.bis === heute ? ["harz", "reist heute ab"] : null;
        return (
          <li key={a.buchung_id}>
            <button onClick={() => onOeffnen(a.buchung_id)} style={{ "--typ": typStil(a.stellplatz_typ).farbe }}>
              <span className="platznr">{a.platz || "–"}</span>
              <span className="haupt">
                <strong>{a.vorname} {a.nachname}</strong>
                <span className="leise">
                  <TypMarke code={a.stellplatz_typ} groesse={14} /> · {datumKurz(a.von)} – {datumKurz(a.bis)} ({anzahlText(n, "Nacht", "Nächte")})
                  · {personen(a.anzahl_erwachsene, a.anzahl_kinder, a.anzahl_kleinkinder)}
                </span>
              </span>
              <span className="rechts">
                {hinweis && <span className={`marke-status ton-${hinweis[0] === "ziegel" ? "warnung" : "offen"}`}>{hinweis[1]}</span>}
                {a.reservationsnummer && <span className="nummer">{a.reservationsnummer}</span>}
                {a.nationalitaet && <span className="land" title={LAENDER[a.nationalitaet] ?? a.nationalitaet}>{a.nationalitaet}</span>}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function AnreiseListe({ liste, nicht, heute, onOeffnen }) {
  const tage = [...new Set(liste.map((e) => e.von))].sort();
  return (
    <div className="aufenthalt-gruppen">
      {nicht.length > 0 && (
        <section className="nicht-angereist">
          <h2 className="gruppe-titel">Noch nicht angereist</h2>
          <p className="hinweis">Anreise ist vorbei, aber kein Check-in erfasst. Einchecken oder in der Belegung «Nicht angereist» wählen.</p>
          <ReservationListe liste={nicht.map((x) => ({ ...x, id: x.anfrage_id }))} heute={heute} onOeffnen={onOeffnen} />
        </section>
      )}
      {tage.length === 0 && <p className="leer">Keine akzeptierten Anreisen in den nächsten {VORSCHAU_TAGE} Tagen.</p>}
      {tage.map((t) => (
        <section key={t}>
          <h2 className="gruppe-titel">{t === heute ? "Heute" : t === isoDatum(plusTage(new Date(), 1)) ? "Morgen" : ""}
            <span className="leise"> {TAG.format(ausIso(t))}</span></h2>
          <ReservationListe liste={liste.filter((e) => e.von === t)} heute={heute} onOeffnen={onOeffnen} />
        </section>
      ))}
    </div>
  );
}

function ReservationListe({ liste, heute, onOeffnen }) {
  return (
    <ul className="aufenthalt-liste">
      {liste.map((e) => (
        <li key={e.id}>
          <button onClick={() => onOeffnen(e.id)} style={{ "--typ": typStil(e.stellplatz_typ).farbe }}>
            <span className="platznr leise">{datumKurz(e.von)}</span>
            <span className="haupt">
              <strong>{e.gast_name}</strong>
              <span className="leise">
                <TypMarke code={e.stellplatz_typ} groesse={14} /> · bis {datumKurz(e.bis)} · {personen(e.erwachsene, e.kinder)}
              </span>
            </span>
            <span className="rechts">
              {e.nummer && <span className="nummer">{e.nummer}</span>}
              {e.von <= heute && <span className="hinweis-aktion">einchecken →</span>}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

// --- Reservation vor dem Check-in --------------------------------------------------

function ReservationPanel({ id, heute, onCheckin }) {
  const [a, setA] = useState(null);
  const [fehler, setFehler] = useState(null);
  useEffect(() => { api.get(`/reservationsanfragen/${id}`).then(setA).catch((e) => setFehler(e.message)); }, [id]);
  if (fehler) return <p className="meldung fehler">{fehler}</p>;
  if (!a) return <p className="leer">Wird geladen …</p>;
  const moeglich = a.status === "bezahlt_akzeptiert" && a.gewuenscht_von <= heute;
  return (
    <div className="panel">
      <h2>{a.gast_name}</h2>
      <p><span className={`marke-status ton-${STATUS[a.status]?.ton ?? "info"}`}>{statusName(a.status)}</span>
        {a.nummer && <span className="nummer"> Nr. {a.nummer}</span>}</p>
      <dl className="angaben">
        <dt>Zeitraum</dt><dd>{datumVoll(a.gewuenscht_von)} bis {datumVoll(a.gewuenscht_bis)}</dd>
        <dt>Stellplatz</dt><dd><TypMarke code={a.stellplatz_typ} /></dd>
        <dt>Personen</dt><dd>{personenLang(a.anzahl_erwachsene, a.anzahl_kinder, a.anzahl_kleinkinder)}</dd>
        <dt>Kontakt</dt><dd>{[a.gast_email, a.gast_telefon].filter(Boolean).join(", ")}</dd>
        <dt>Anzahlung</dt><dd>{a.anzahlung_erhalten ? `${chf(a.anzahlung_erhalten)} erhalten` : "ohne Anzahlung"}</dd>
        {a.bemerkung && <><dt>Bemerkung</dt><dd className="mehrzeilig">{a.bemerkung}</dd></>}
      </dl>
      <div className="aktionen">
        {moeglich
          ? <button className="knopf haupt" onClick={() => onCheckin(a)}><LogIn size={18} aria-hidden="true" />Angereist – einchecken</button>
          : <p className="hinweis">Einchecken ist ab dem Anreisetag ({datumVoll(a.gewuenscht_von)}) möglich.</p>}
        <a className="knopf neben" href={`#/belegung?tag=${a.gewuenscht_von}&eintrag=${a.id}`}>In der Belegung</a>
        <a className="knopf neben" href={`#/reservationen?id=${a.id}`}>Reservation</a>
      </div>
    </div>
  );
}

// --- Aufenthalt: Gast, Zeitraum, Leistungen, Taxen ------------------------------------

function AufenthaltPanel({ id, heute, preiseAktiv, onGeaendert, onGeloescht }) {
  const [auf, setAuf] = useState(null);
  const [leist, setLeist] = useState(null);
  const [fehler, setFehler] = useState(null);
  const [laeuft, setLaeuft] = useState(false);
  const [bearbeiten, setBearbeiten] = useState(null); // "gast" | "zeitraum" | null
  const [bestaetigen, setBestaetigen] = useState(null);
  const [abreise, setAbreise] = useState(heute);

  const laden = useCallback(async () => {
    setFehler(null);
    try {
      const [a, l] = await Promise.all([api.get(`/aufenthalte/${id}`), api.get(`/aufenthalte/${id}/leistungen`)]);
      setAuf(a); setLeist(l);
    } catch (e) { setFehler(e.message); }
  }, [id]);
  useEffect(() => { setAuf(null); setBearbeiten(null); laden(); }, [laden]);

  const ausfuehren = async (fn) => {
    setLaeuft(true); setFehler(null);
    try { await fn(); await laden(); onGeaendert(); return true; } catch (e) { setFehler(e.message); return false; } finally { setLaeuft(false); setBestaetigen(null); }
  };

  if (fehler && !auf) return <p className="meldung fehler">{fehler}</p>;
  if (!auf || !leist) return <p className="leer">Wird geladen …</p>;
  const gesperrt = auf.hat_rechnung;
  const n = naechte(auf.von, auf.bis);

  return (
    <div className="panel aufenthalt-panel">
      <h2>{auf.vorname} {auf.nachname}</h2>
      <p>
        <span className={`marke-status ton-${auf.status === "eingecheckt" ? "ok" : "info"}`}>{auf.status === "eingecheckt" ? "Auf dem Platz" : "Abgereist"}</span>
        {auf.reservationsnummer && <> <a className="nummer" href={`#/reservationen?id=${auf.reservationsanfrage_id}`}>Reservation {auf.reservationsnummer}</a></>}
        {gesperrt && <span className="hinweis"> · abgerechnet, nicht mehr änderbar</span>}
      </p>
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}

      {/* Zeitraum */}
      <section className="panel-abschnitt">
        <div className="abschnitt-kopf">
          <h3>Aufenthalt</h3>
          {!gesperrt && bearbeiten !== "zeitraum" && <button className="link" onClick={() => setBearbeiten("zeitraum")}>Verlängern / verkürzen</button>}
        </div>
        {bearbeiten === "zeitraum" ? (
          <ZeitraumFormular auf={auf} heute={heute} laeuft={laeuft} onAbbrechen={() => setBearbeiten(null)}
            onSpeichern={async (w) => { if (await ausfuehren(() => api.patch(`/aufenthalte/${id}`, w))) setBearbeiten(null); }} />
        ) : (
          <dl className="angaben">
            <dt>Zeitraum</dt><dd>{datumVoll(auf.von)} bis {datumVoll(auf.bis)} ({anzahlText(n, "Nacht", "Nächte")})</dd>
            <dt>Stellplatz</dt><dd><TypMarke code={auf.stellplatz_typ} />{auf.platz ? `, Platz ${auf.platz}` : ""}</dd>
            <dt>Personen</dt><dd>{personenLang(auf.anzahl_erwachsene, auf.anzahl_kinder, auf.anzahl_kleinkinder)}
              {schwankend(leist) && <span className="leise"> (höchstens; je Nacht siehe unten)</span>}</dd>
          </dl>
        )}
      </section>

      {/* Leistungen */}
      <LeistungenAbschnitt id={id} auf={auf} leist={leist} gesperrt={gesperrt} laeuft={laeuft} preiseAktiv={preiseAktiv}
        ausfuehren={(fn) => ausfuehren(async () => setLeist(await fn()))} />

      {/* Gast */}
      <section className="panel-abschnitt">
        <div className="abschnitt-kopf">
          <h3>Gast</h3>
          {!gesperrt && bearbeiten !== "gast" && <button className="link" onClick={() => setBearbeiten("gast")}>Bearbeiten</button>}
        </div>
        {bearbeiten === "gast" ? (
          <GastFormular auf={auf} laeuft={laeuft} onAbbrechen={() => setBearbeiten(null)}
            onSpeichern={async (w) => { if (await ausfuehren(() => api.patch(`/aufenthalte/${id}`, w))) setBearbeiten(null); }} />
        ) : (
          <dl className="angaben">
            <dt>Nationalität</dt><dd>{LAENDER[auf.nationalitaet] ?? auf.nationalitaet ?? "–"}</dd>
            <dt>Geburtsdatum</dt><dd>{auf.geburtsdatum ? datumVoll(auf.geburtsdatum) : "–"}</dd>
            <dt>Adresse</dt><dd>{[auf.strasse, [auf.plz, auf.ort].filter(Boolean).join(" "), LAENDER[auf.land] ?? auf.land].filter(Boolean).join(", ") || "–"}</dd>
            <dt>Kontakt</dt><dd>{[auf.email, auf.telefon].filter(Boolean).join(", ") || "–"}</dd>
            {auf.bemerkung && <><dt>Bemerkung</dt><dd className="mehrzeilig">{auf.bemerkung}</dd></>}
          </dl>
        )}
      </section>

      {/* Abreise */}
      {!gesperrt && auf.status === "eingecheckt" && (
        <div className="aktionen">
          <label className="kompakt">Abreise am<input type="date" value={abreise} min={isoDatum(plusTage(ausIso(auf.von), 1))} onChange={(x) => setAbreise(x.target.value)} /></label>
          <button className="knopf haupt" disabled={laeuft} onClick={() => ausfuehren(() => api.post(`/aufenthalte/${id}/abreise`, { datum: abreise }))}>Abreise erfassen</button>
        </div>
      )}
      {!gesperrt && auf.status === "ausgecheckt" && (
        <div className="aktionen">
          <button className="knopf leise" disabled={laeuft} onClick={() => ausfuehren(() => api.post(`/aufenthalte/${id}/abreise-zuruecknehmen`))}>
            Abreise zurücknehmen (Gast ist noch da)
          </button>
        </div>
      )}
      {!gesperrt && (
        <Bestaetigung offen={bestaetigen === "loeschen"} onOeffnen={() => setBestaetigen("loeschen")} onAbbrechen={() => setBestaetigen(null)}
          knopf="Aufenthalt löschen" frage={`Aufenthalt von ${auf.vorname} ${auf.nachname} mit allen Leistungen löschen?${auf.reservationsanfrage_id ? " Die Reservation ist danach wieder «akzeptiert»." : ""}`}
          laeuft={laeuft} onJa={async () => {
            setLaeuft(true);
            try { await api.delete(`/aufenthalte/${id}`); onGeloescht(); } catch (e) { setFehler(e.message); setLaeuft(false); }
          }} />
      )}
    </div>
  );
}

const schwankend = (leist) => {
  const p = leist.personen_je_nacht;
  return p.some((x) => x.erwachsene !== p[0].erwachsene || x.kinder !== p[0].kinder || x.kleinkinder !== p[0].kleinkinder);
};

function ZeitraumFormular({ auf, heute, laeuft, onAbbrechen, onSpeichern }) {
  const [w, setW] = useState({ von: auf.von, bis: auf.bis });
  return (
    <form className="bearbeiten-form" onSubmit={(e) => { e.preventDefault(); onSpeichern(w); }}>
      <p className="hinweis">Gilt für den ganzen Aufenthalt: Leistungen, die bis zum bisherigen Ende liefen, ziehen mit;
        alles wird auf den neuen Zeitraum begrenzt. Personen, die früher gingen, bleiben, wie sie sind.</p>
      <div className="felder zwei">
        <label>Anreise<input type="date" required max={heute} value={w.von} onChange={(e) => setW({ ...w, von: e.target.value })} /></label>
        <label>Abreise<input type="date" required min={isoDatum(plusTage(ausIso(w.von), 1))} value={w.bis} onChange={(e) => setW({ ...w, bis: e.target.value })} /></label>
      </div>
      <div className="aktionen">
        <button className="knopf haupt" type="submit" disabled={laeuft}>Speichern</button>
        <button className="knopf leise" type="button" onClick={onAbbrechen}>Abbrechen</button>
      </div>
    </form>
  );
}

function GastFormular({ auf, laeuft, onAbbrechen, onSpeichern }) {
  const bekannt = !auf.nationalitaet || LAENDER[auf.nationalitaet];
  const [w, setW] = useState({
    vorname: auf.vorname, nachname: auf.nachname, nationalitaet: bekannt ? auf.nationalitaet || "" : ANDERES,
    nationalitaet_iso: bekannt ? "" : auf.nationalitaet, geburtsdatum: auf.geburtsdatum || "",
    strasse: auf.strasse || "", plz: auf.plz || "", ort: auf.ort || "", land: auf.land || "",
    email: auf.email || "", telefon: auf.telefon || "", platz: auf.platz || "", bemerkung: auf.bemerkung || "",
  });
  const [fehler, setFehler] = useState(null);
  const feld = (name) => ({ value: w[name], onChange: (e) => setW({ ...w, [name]: e.target.value }) });
  const absenden = (e) => {
    e.preventDefault();
    const nat = w.nationalitaet === ANDERES ? w.nationalitaet_iso.trim().toUpperCase() : w.nationalitaet;
    if (!/^[A-Z]{2}$/.test(nat)) { setFehler("Bitte die Nationalität angeben (für die HESTA-Meldung)."); return; }
    const { nationalitaet_iso, ...rest } = w; // eslint-disable-line no-unused-vars
    const leer = (x) => (x.trim() ? x.trim() : null);
    onSpeichern({
      ...rest, nationalitaet: nat, geburtsdatum: w.geburtsdatum || null, land: w.land || null, email: leer(w.email),
      strasse: leer(w.strasse), plz: leer(w.plz), ort: leer(w.ort), telefon: leer(w.telefon), platz: leer(w.platz),
      bemerkung: leer(w.bemerkung),
    });
  };
  return (
    <form className="bearbeiten-form" onSubmit={absenden}>
      <div className="felder zwei">
        <label>Vorname<input required {...feld("vorname")} /></label>
        <label>Nachname<input required {...feld("nachname")} /></label>
        <label>Nationalität
          <select required {...feld("nationalitaet")}>
            <option value="">Bitte wählen</option>
            {Object.entries(LAENDER).map(([c, n]) => <option key={c} value={c}>{n}</option>)}
            <option value={ANDERES}>Anderes Land …</option>
          </select></label>
        {w.nationalitaet === ANDERES
          ? <label>Ländercode (ISO)<input required maxLength={2} pattern="[A-Za-z]{2}" {...feld("nationalitaet_iso")} /></label>
          : <label>Geburtsdatum<input type="date" {...feld("geburtsdatum")} /></label>}
        {w.nationalitaet === ANDERES && <label>Geburtsdatum<input type="date" {...feld("geburtsdatum")} /></label>}
        <label>Platz<input {...feld("platz")} placeholder="z.B. 17" /></label>
        <label className="breit">Strasse<input {...feld("strasse")} autoComplete="off" /></label>
        <label>PLZ<input {...feld("plz")} /></label>
        <label>Ort<input {...feld("ort")} /></label>
        <label>Land<select {...feld("land")}><option value="">–</option>{Object.entries(LAENDER).map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select></label>
        <label>Telefon<input type="tel" {...feld("telefon")} /></label>
        <label className="breit">E-Mail<input type="email" {...feld("email")} /></label>
        <label className="breit">Bemerkung<textarea rows="2" {...feld("bemerkung")} /></label>
      </div>
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
      <div className="aktionen">
        <button className="knopf haupt" type="submit" disabled={laeuft}>Speichern</button>
        <button className="knopf leise" type="button" onClick={onAbbrechen}>Abbrechen</button>
      </div>
    </form>
  );
}

// --- Leistungen ------------------------------------------------------------------

const GRUPPEN = { person: "Personen", stellplatz: "Stellplatz", unterkunft: "Unterkunft", zusatz: "Zusatzleistungen" };

function mengeText(z) {
  if (z.einheit === "stueck") return anzahlText(z.menge, "Stück", "Stück");
  if (z.gruppe === "person") return anzahlText(z.menge, "Personennacht", "Personennächte");
  return anzahlText(z.menge, "Nacht", "Nächte");
}

function LeistungenAbschnitt({ id, auf, leist, gesperrt, laeuft, preiseAktiv, ausfuehren }) {
  const [form, setForm] = useState(null); // { art: "neu" } | { art: "aendern", zeile } | { art: "abwesend", zeile }
  const fertig = async (fn) => { await ausfuehren(fn); setForm(null); };
  const zeilen = leist.zeilen;
  const gruppen = [...new Set(zeilen.map((z) => z.gruppe))];
  const spalten = 4 + (preiseAktiv ? 1 : 0) + (gesperrt ? 0 : 1);
  const preisJe = Object.fromEntries(leist.preise.zeilen.map((p) => [p.leistung_id, p]));
  const taxenTotal = leist.taxen.reduce((s, t) => s + Number(t.betrag), 0);

  return (
    <section className="panel-abschnitt">
      <div className="abschnitt-kopf">
        <h3>Leistungen</h3>
        {!gesperrt && !form && <button className="link" onClick={() => setForm({ art: "neu" })}><Plus size={14} aria-hidden="true" /> Leistung hinzufügen</button>}
      </div>
      <p className="hinweis klein">Jede Zeile mit eigenem Zeitraum – z.B. zwei Kinder für zwei Nächte weg oder Besuch mit eigenem Zelt.</p>
      {form?.art === "neu" && (
        <LeistungFormular arten={leist.arten} auf={auf} laeuft={laeuft} onAbbrechen={() => setForm(null)}
          onSpeichern={(w) => fertig(() => api.post(`/aufenthalte/${id}/leistungen`, w))} />
      )}
      <div className="tabelle-rahmen">
      <table className="leistungen">
        <thead><tr><th>Leistung</th><th className="zahl">Anz.</th><th>Zeitraum</th><th className="zahl">Menge</th>
          {preiseAktiv && <th className="zahl">Betrag</th>}{!gesperrt && <th><span className="sr-only">Aktionen</span></th>}</tr></thead>
        {gruppen.map((g) => (
          <tbody key={g}>
            <tr className="gruppe"><th colSpan={spalten}>{GRUPPEN[g] ?? g}</th></tr>
            {zeilen.filter((z) => z.gruppe === g).map((z) => (
              <LeistungZeile key={z.id} z={z} auf={auf} gesperrt={gesperrt} laeuft={laeuft} form={form} setForm={setForm}
                preis={preiseAktiv ? preisJe[z.id] ?? null : undefined} spalten={spalten}
                onAendern={(w) => fertig(() => api.patch(`/aufenthalte/${id}/leistungen/${z.id}`, w))}
                onAbwesend={(w) => fertig(() => api.post(`/aufenthalte/${id}/leistungen/${z.id}/abwesenheit`, w))}
                onLoeschen={() => fertig(() => api.delete(`/aufenthalte/${id}/leistungen/${z.id}`))} />
            ))}
          </tbody>
        ))}
        {preiseAktiv && leist.preise.abzuege.map((a) => (
          <tbody key={a.bezeichnung}><tr className="abzug"><td colSpan={4}>{a.bezeichnung}</td><td className="zahl">{chf(a.betrag)}</td>{!gesperrt && <td />}</tr></tbody>
        ))}
        {zeilen.length === 0 && <tbody><tr><td colSpan={spalten} className="leer klein">Keine Leistungen erfasst.</td></tr></tbody>}
      </table>
      </div>

      {schwankend(leist) && <PersonenJeNacht liste={leist.personen_je_nacht} />}

      <div className="taxen">
        <h4>Taxen</h4>
        {leist.taxen.length === 0 ? <p className="leer klein">Keine Taxen (keine Erwachsenen oder keine Sätze hinterlegt).</p> : (
          <dl className="tax-liste">
            {leist.taxen.map((t) => (
              <div key={t.typ} className="tax-zeile"><dt>{t.bezeichnung}</dt>
                <dd>{anzahlText(t.personennaechte, "Personennacht", "Personennächte")} · <strong>{chf(t.betrag)}</strong></dd></div>
            ))}
          </dl>
        )}
        <p className="hinweis klein">Beherbergungsabgabe für alle Erwachsenen, Kurtaxe nur für Kurtaxepflichtige. Kinder und Kleinkinder ohne Taxen.</p>
      </div>

      {preiseAktiv && (
        <div className="total-box">
          {leist.preise.fehlende_preise && (
            <p className="meldung warnung">Für einzelne Leistungen fehlt ein Preis, meist weil die Nächte ausserhalb der Saison liegen – siehe «Artikel &amp; Preise».</p>
          )}
          <dl>
            <div><dt>Leistungen</dt><dd>{chf(leist.preise.total)}</dd></div>
            <div><dt>Taxen</dt><dd>{chf(taxenTotal)}</dd></div>
            <div className="summe"><dt>Total</dt><dd>{chf(leist.preise.total_mit_taxen)}</dd></div>
          </dl>
          <p className="hinweis klein">Endpreise; darin enthalten MWST {chf(leist.preise.mwst_total)}. Taxen ohne MWST.</p>
        </div>
      )}
    </section>
  );
}

function LeistungZeile({ z, auf, gesperrt, laeuft, form, setForm, preis, spalten, onAendern, onAbwesend, onLoeschen }) {
  const offen = form?.zeile?.id === z.id ? form.art : null;
  const [loeschen, setLoeschen] = useState(false);
  const zeitraum = z.einheit === "stueck" ? datumKurz(z.von) : `${datumKurz(z.von)} – ${datumKurz(z.bis)}`;
  const ganz = z.von === auf.von && z.bis === auf.bis;
  return (
    <>
      <tr className={offen ? "aktiv" : ""}>
        <td>{z.bezeichnung}
          {z.art === "erwachsene" && !z.kurtaxepflichtig && <span className="marke-status ton-info klein"> ohne Kurtaxe</span>}
          {z.bemerkung && <span className="leise klein"> · {z.bemerkung}</span>}</td>
        <td className="zahl">{z.anzahl}</td>
        <td className={ganz ? "leise" : "teilzeit"}>{zeitraum}</td>
        <td className="zahl">{mengeText(z)}</td>
        {preis !== undefined && (
          <td className="zahl betrag">
            {preis ? chf(preis.betrag) : "–"}
            {preis?.einzelpreis && Number(preis.betrag) > 0 && <span className="leise klein block">à {Number(preis.einzelpreis).toFixed(2)}</span>}
            {preis?.einzelpreise?.length > 1 && <span className="leise klein block">à {preis.einzelpreise.map((x) => Number(x).toFixed(2)).join(" / ")}</span>}
            {preis?.hinweis && <span className={`klein block ${preis.hinweis.includes("inbegriffen") ? "leise" : "warn-text"}`}>{preis.hinweis}</span>}
          </td>
        )}
        {!gesperrt && (
          <td className="zeilen-aktionen">
            {!form && (
              <>
                <button className="link" onClick={() => setForm({ art: "aendern", zeile: z })}>ändern</button>
                {z.einheit !== "stueck" && <button className="link" onClick={() => setForm({ art: "abwesend", zeile: z })}>abwesend</button>}
                {loeschen
                  ? <><button className="link gefahr" disabled={laeuft} onClick={onLoeschen}>wirklich?</button><button className="link" onClick={() => setLoeschen(false)}>nein</button></>
                  : <button className="link" onClick={() => setLoeschen(true)}>löschen</button>}
              </>
            )}
          </td>
        )}
      </tr>
      {offen && (
        <tr className="formzeile"><td colSpan={spalten}>
          {offen === "aendern" && <LeistungFormular zeile={z} auf={auf} laeuft={laeuft} onAbbrechen={() => setForm(null)} onSpeichern={onAendern} />}
          {offen === "abwesend" && <AbwesenheitFormular zeile={z} laeuft={laeuft} onAbbrechen={() => setForm(null)} onSpeichern={onAbwesend} />}
        </td></tr>
      )}
    </>
  );
}

function LeistungFormular({ arten, zeile, auf, laeuft, onAbbrechen, onSpeichern }) {
  const neu = !zeile;
  const [w, setW] = useState({
    art: zeile?.art ?? "erwachsene", anzahl: zeile?.anzahl ?? 1, von: zeile?.von ?? auf.von, bis: zeile?.bis ?? auf.bis,
    kurtaxepflichtig: zeile?.kurtaxepflichtig ?? true, bemerkung: zeile?.bemerkung ?? "",
  });
  const art = neu ? arten.find((a) => a.code === w.art) : { code: zeile.art, einheit: zeile.einheit };
  const stueck = art?.einheit === "stueck";
  const setze = (name, wert) => setW({ ...w, [name]: wert });
  const absenden = (e) => {
    e.preventDefault();
    const daten = { anzahl: Number(w.anzahl), von: w.von, bis: stueck ? null : w.bis, bemerkung: w.bemerkung.trim() || null };
    if (art.code === "erwachsene") daten.kurtaxepflichtig = w.kurtaxepflichtig;
    onSpeichern(neu ? { ...daten, art: w.art } : daten);
  };
  return (
    <form className="bearbeiten-form leistung-form" onSubmit={absenden}>
      <div className="felder vier">
        {neu ? (
          <label className="breit2">Leistung
            <select value={w.art} onChange={(e) => setze("art", e.target.value)}>
              {Object.entries(GRUPPEN).map(([g, name]) => (
                <optgroup key={g} label={name}>
                  {arten.filter((a) => a.gruppe === g).map((a) => <option key={a.code} value={a.code}>{a.bezeichnung}</option>)}
                </optgroup>
              ))}
            </select></label>
        ) : <p className="breit2"><strong>{zeile.bezeichnung}</strong></p>}
        <label>Anzahl<input type="number" min="1" max="99" required value={w.anzahl} onChange={(e) => setze("anzahl", e.target.value)} /></label>
        <label>{stueck ? "Datum" : "Von"}<input type="date" required min={auf.von} max={stueck ? auf.bis : isoDatum(plusTage(ausIso(auf.bis), -1))} value={w.von} onChange={(e) => setze("von", e.target.value)} /></label>
        {!stueck && <label>Bis (Abreise)<input type="date" required min={isoDatum(plusTage(ausIso(w.von), 1))} max={auf.bis} value={w.bis} onChange={(e) => setze("bis", e.target.value)} /></label>}
        <label className="breit2">Bemerkung<input maxLength={200} value={w.bemerkung} onChange={(e) => setze("bemerkung", e.target.value)} placeholder="z.B. Besuch Grosseltern" /></label>
        {art?.code === "erwachsene" && (
          <label className="kontrolle breit2"><input type="checkbox" checked={w.kurtaxepflichtig} onChange={(e) => setze("kurtaxepflichtig", e.target.checked)} />
            kurtaxepflichtig (nicht bei Wohnsitz in Aeschi)</label>
        )}
      </div>
      <div className="aktionen">
        <button className="knopf haupt" type="submit" disabled={laeuft}>{neu ? "Hinzufügen" : "Speichern"}</button>
        <button className="knopf leise" type="button" onClick={onAbbrechen}>Abbrechen</button>
      </div>
    </form>
  );
}

function AbwesenheitFormular({ zeile, laeuft, onAbbrechen, onSpeichern }) {
  const [w, setW] = useState({ anzahl: Math.min(zeile.anzahl, 1), von: zeile.von, bis: isoDatum(plusTage(ausIso(zeile.von), 1)) });
  return (
    <form className="bearbeiten-form leistung-form" onSubmit={(e) => { e.preventDefault(); onSpeichern({ ...w, anzahl: Number(w.anzahl) }); }}>
      <p className="hinweis klein">Wie viele von {zeile.anzahl} «{zeile.bezeichnung}» sind nicht auf dem Platz? Die Zeile wird aufgeteilt.</p>
      <div className="felder vier">
        <label>Anzahl<input type="number" min="1" max={zeile.anzahl} required value={w.anzahl} onChange={(e) => setW({ ...w, anzahl: e.target.value })} /></label>
        <label>Weg ab (erste Nacht)<input type="date" required min={zeile.von} max={isoDatum(plusTage(ausIso(zeile.bis), -1))} value={w.von} onChange={(e) => setW({ ...w, von: e.target.value })} /></label>
        <label>Zurück am<input type="date" required min={isoDatum(plusTage(ausIso(w.von), 1))} max={zeile.bis} value={w.bis} onChange={(e) => setW({ ...w, bis: e.target.value })} /></label>
      </div>
      <div className="aktionen">
        <button className="knopf haupt" type="submit" disabled={laeuft}>Abwesenheit erfassen</button>
        <button className="knopf leise" type="button" onClick={onAbbrechen}>Abbrechen</button>
      </div>
    </form>
  );
}

function PersonenJeNacht({ liste }) {
  return (
    <details className="je-nacht">
      <summary>Personen je Nacht</summary>
      <div className="je-nacht-raster" style={{ "--n": liste.length }}>
        {liste.map((p) => (
          <div key={p.datum}>
            <span className="leise">{datumKurz(p.datum)}</span>
            <strong>{p.erwachsene} E</strong>
            <span>{p.kinder} K{p.kleinkinder ? ` · ${p.kleinkinder} KK` : ""}</span>
          </div>
        ))}
      </div>
    </details>
  );
}
