import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { ausIso, datumKurz, fehlendText, heuteIso, isoDatum, naechte, personen, plusTage } from "../format.js";
import { Panorama, TYP_STIL, TypMarke } from "../typen.jsx";
import { StatusMarke } from "./Reservationen.jsx";

const AKTIV = new Set(["neu", "unvollstaendig", "geprueft_vollstaendig", "in_abklaerung", "erstantwort_gesendet", "zahlung_ausstehend", "bezahlt_akzeptiert", "angereist"]);
const ZU_BEARBEITEN = new Set(["neu", "unvollstaendig", "geprueft_vollstaendig"]);
const LANG = new Intl.DateTimeFormat("de-CH", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const WOCHENTAG = new Intl.DateTimeFormat("de-CH", { weekday: "short" });

const tageSeit = (iso) => Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
const alterText = (iso) => {
  const t = tageSeit(iso);
  return t <= 0 ? "heute eingegangen" : t === 1 ? "seit gestern" : `seit ${t} Tagen`;
};
const anzahl = (n, eins, mehr) => `${n} ${n === 1 ? eins : mehr}`;

export default function Heute() {
  const heute = heuteIso();
  const [anfragen, setAnfragen] = useState(null);
  const [woche, setWoche] = useState(null);
  const [nichtAngereist, setNichtAngereist] = useState([]);
  const [fehler, setFehler] = useState(null);

  const laden = useCallback(() => {
    const bis = isoDatum(plusTage(new Date(), 6));
    Promise.all([api.get("/reservationsanfragen"), api.get(`/belegung?von=${heute}&bis=${bis}`), api.get("/belegung/nicht-angereist")])
      .then(([a, w, n]) => { setAnfragen(a); setWoche(w); setNichtAngereist(n); })
      .catch((e) => setFehler(e.message));
  }, [heute]);
  useEffect(laden, [laden]);

  const nichtErschienen = async (id) => {
    try { await api.post(`/reservationsanfragen/${id}/nicht-erschienen`); laden(); } catch (e) { setFehler(e.message); }
  };

  const { anreisen, abreisen, offen } = useMemo(() => {
    const aktiv = (anfragen || []).filter((a) => AKTIV.has(a.status));
    return {
      anreisen: aktiv.filter((a) => a.gewuenscht_von === heute),
      abreisen: aktiv.filter((a) => a.gewuenscht_bis === heute),
      // Anfragen mit neuer Mail des Gastes zuerst, dann die älteste unbearbeitete
      offen: (anfragen || []).filter((a) => ZU_BEARBEITEN.has(a.status) || a.neue_mails > 0)
        .sort((x, y) => (y.neue_mails > 0) - (x.neue_mails > 0) || x.eingangs_datum.localeCompare(y.eingangs_datum)),
    };
  }, [anfragen, heute]);

  const zusammenfassung = anfragen
    ? [anzahl(anreisen.length, "Anreise", "Anreisen"), anzahl(abreisen.length, "Abreise", "Abreisen"),
      `${anzahl(offen.length, "Anfrage", "Anfragen")} zu bearbeiten`].join(", ")
    : "";

  return (
    <div className="seite">
      <header className="heute-band">
        <Panorama className="heute-panorama" />
        <div className="heute-text">
          <h1>{LANG.format(new Date())}</h1>
          <p>{zusammenfassung}</p>
        </div>
      </header>
      {fehler && <p className="meldung fehler">{fehler}</p>}
      {!fehler && !anfragen && <p className="leer">Wird geladen …</p>}

      {nichtAngereist.length > 0 && (
        <section className="heute-karte nicht-angereist" aria-labelledby="h-nicht-angereist">
          <h2 id="h-nicht-angereist">Nicht angereist</h2>
          <p className="hinweis">Akzeptierte Reservationen mit Anreise vor heute, ohne Check-in. Angereist? Dann in der Belegung einchecken – sonst den Platz freigeben.</p>
          <ul className="heute-liste">
            {nichtAngereist.map((a) => (
              <li key={a.anfrage_id} className="mit-aktionen">
                <span className="zeile1"><strong>{a.gast_name}</strong>{a.nummer && <span className="nummer">{a.nummer}</span>}</span>
                <span className="zeile2"><TypMarke code={a.stellplatz_typ} /> Anreise {datumKurz(a.von)}{a.gast_telefon ? ` · ${a.gast_telefon}` : ""}</span>
                <span className="aktionen">
                  <a className="knopf neben klein" href={`#/belegung?tag=${a.von}&eintrag=${a.anfrage_id}`}>In der Belegung</a>
                  <button className="knopf leise klein" onClick={() => nichtErschienen(a.anfrage_id)}>Nicht erschienen, Platz freigeben</button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {anfragen && (
        <div className="heute-raster">
          <Liste titel="Anreisen heute" leer="Heute reist niemand an." eintraege={anreisen} />
          <Liste titel="Abreisen heute" leer="Heute reist niemand ab." eintraege={abreisen} />
          <section className="heute-karte" aria-labelledby="h-offen">
            <h2 id="h-offen">Zu bearbeiten</h2>
            {offen.length === 0 && <p className="leer">Alle Anfragen sind bearbeitet.</p>}
            <ul className="heute-liste">
              {offen.slice(0, 8).map((a) => (
                <li key={a.id}>
                  <a href="#/reservationen">
                    <span className="zeile1"><strong>{a.gast_name}</strong><StatusMarke status={a.status} /></span>
                    {a.neue_mails > 0 && <span className="marke-neu">{a.neue_mails === 1 ? "Neue Mail vom Gast" : `${a.neue_mails} neue Mails vom Gast`}</span>}
                    <span className="zeile2">
                      {a.vollstaendig ? <><TypMarke code={a.stellplatz_typ} /> {datumKurz(a.gewuenscht_von)}</> : <>Es fehlt: {fehlendText(a.fehlende_angaben)}</>}
                    </span>
                    <span className="alter">{alterText(a.eingangs_datum)}</span>
                  </a>
                </li>
              ))}
            </ul>
            {offen.length > 8 && <a href="#/reservationen">Alle {offen.length} anzeigen</a>}
          </section>
        </div>
      )}

      {woche && <Woche woche={woche} heute={heute} />}
    </div>
  );
}

function Liste({ titel, leer, eintraege }) {
  return (
    <section className="heute-karte" aria-label={titel}>
      <h2>{titel}</h2>
      {eintraege.length === 0 && <p className="leer">{leer}</p>}
      <ul className="heute-liste">
        {eintraege.map((a) => {
          const n = naechte(a.gewuenscht_von, a.gewuenscht_bis);
          return (
            <li key={a.id}>
              <a href={`#/belegung?tag=${a.gewuenscht_von}&eintrag=${a.id}`}>
                <span className="zeile1"><strong>{a.gast_name}</strong><StatusMarke status={a.status} /></span>
                <span className="zeile2">
                  <TypMarke code={a.stellplatz_typ} />
                  <span>{personen(a.anzahl_erwachsene, a.anzahl_kinder)}</span>
                  {n ? <span>{anzahl(n, "Nacht", "Nächte")}</span> : null}
                </span>
              </a>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Woche({ woche, heute }) {
  const tage = woche.nach_typ[0]?.tage.map((t) => t.datum) ?? [];
  const max = Math.max(1, ...woche.nach_typ.flatMap((t) => t.tage.map((d) => d.anzahl)));
  return (
    <section className="heute-karte woche" aria-labelledby="h-woche">
      <div className="kopf">
        <h2 id="h-woche">Die nächsten 7 Tage</h2>
        <a href="#/belegung">Zur Belegung</a>
      </div>
      <table className="woche-tabelle">
        <thead>
          <tr>
            <th scope="col"><span className="sr-only">Stellplatz-Typ</span></th>
            {tage.map((d) => (
              <th key={d} scope="col" className={d === heute ? "heute" : undefined}>
                <span>{WOCHENTAG.format(ausIso(d))}</span><strong>{ausIso(d).getDate()}</strong>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {woche.nach_typ.map((t) => (
            <tr key={t.stellplatz_typ} style={{ "--typ": TYP_STIL[t.stellplatz_typ]?.farbe }}>
              <th scope="row"><TypMarke code={t.stellplatz_typ} /></th>
              {t.tage.map((d) => (
                <td key={d.datum} title={`${datumKurz(d.datum)}: ${anzahl(d.anzahl, "Reservation", "Reservationen")}, ${personen(d.erwachsene, d.kinder)}`}>
                  {d.anzahl > 0 ? (
                    <span className="woche-wert" style={{ "--anteil": d.anzahl / max }}>
                      <strong>{d.anzahl}</strong><span>{d.erwachsene}E {d.kinder}K</span>
                    </span>
                  ) : <span className="woche-null" aria-label="keine">–</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hinweis">Pro Tag: Anzahl Reservationen mit Erwachsenen (E) und Kindern (K), akzeptierte und offene zusammen.</p>
    </section>
  );
}
