import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, LogIn, X } from "lucide-react";
import { api } from "../api.js";
import {
  STATUS, TYPEN, ausIso, datumKurz, datumVoll, heuteIso, isoDatum, personen, personenLang, plusTage, statusName,
} from "../format.js";
import { TypMarke, typStil } from "../typen.jsx";

const WOCHENTAG = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
const TAG_LANG = new Intl.DateTimeFormat("de-CH", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const MONAT = new Intl.DateTimeFormat("de-CH", { month: "long", year: "numeric" });
const STELLPLAETZE = ["zeltwiese", "wohnwagen", "camper"];
// häufige Herkunftsländer zuerst; weitere über «Anderes Land» als ISO-Code (HESTA)
const LAENDER = { CH: "Schweiz", DE: "Deutschland", NL: "Niederlande", FR: "Frankreich", IT: "Italien", BE: "Belgien",
  AT: "Österreich", GB: "Grossbritannien", LU: "Luxemburg", DK: "Dänemark", SE: "Schweden", NO: "Norwegen", FI: "Finnland",
  ES: "Spanien", PT: "Portugal", PL: "Polen", CZ: "Tschechien", SK: "Slowakei", HU: "Ungarn", SI: "Slowenien", HR: "Kroatien",
  IE: "Irland", LI: "Liechtenstein", US: "USA", CA: "Kanada", AU: "Australien", NZ: "Neuseeland", IL: "Israel",
  CN: "China", JP: "Japan", KR: "Südkorea", IN: "Indien" };
const ANDERES = "__anderes";

function bereich(ansicht, bezug, frei) {
  if (ansicht === "monat") {
    const von = new Date(bezug.getFullYear(), bezug.getMonth(), 1);
    const bis = new Date(bezug.getFullYear(), bezug.getMonth() + 1, 0);
    return { von, bis, titel: MONAT.format(von) };
  }
  if (ansicht === "woche") {
    const von = plusTage(bezug, -((bezug.getDay() + 6) % 7)); // Montag
    const bis = plusTage(von, 6);
    return { von, bis, titel: `Woche ${datumKurz(isoDatum(von))} – ${datumKurz(isoDatum(bis))}` };
  }
  const von = ausIso(frei.von), bis = ausIso(frei.bis);
  return { von, bis, titel: `${datumKurz(frei.von)} – ${datumKurz(frei.bis)}` };
}

// Reservationen eines Typs auf möglichst wenige Zeilen verteilen, ohne Überlappung
function aufZeilen(eintraege) {
  const zeilen = [];
  for (const e of [...eintraege].sort((a, b) => a.von.localeCompare(b.von))) {
    const zeile = zeilen.find((z) => z[z.length - 1].bis <= e.von);
    if (zeile) zeile.push(e); else zeilen.push([e]);
  }
  return zeilen;
}

const hashParameter = () => new URLSearchParams(window.location.hash.split("?")[1] || "");
const istAufenthalt = (e) => e.art === "aufenthalt";
const eintragStatus = (e) => (istAufenthalt(e) ? (e.status === "eingecheckt" ? "Eingecheckt" : "Abgereist") : statusName(e.status));

export default function Belegung() {
  const heute = heuteIso();
  const start = hashParameter();
  const [ansicht, setAnsicht] = useState("monat");
  const [bezug, setBezug] = useState(start.get("tag") ? ausIso(start.get("tag")) : new Date());
  const [frei, setFrei] = useState({ von: heute, bis: isoDatum(plusTage(new Date(), 13)) });
  const [status, setStatus] = useState("alle");
  const [darstellung, setDarstellung] = useState("uebersicht");
  const [daten, setDaten] = useState(null);
  const [fehler, setFehler] = useState(null);
  // Schublade: { art: "tag", datum } | { art: "eintrag", id } | { art: "checkin", eintrag? }
  const [schublade, setSchublade] = useState(start.get("eintrag") ? { art: "eintrag", id: start.get("eintrag") }
    : start.get("tag") ? { art: "tag", datum: start.get("tag") } : null);

  const { von, bis, titel } = bereich(ansicht, bezug, frei);
  const vonIso = von ? isoDatum(von) : "", bisIso = bis ? isoDatum(bis) : "";

  const laden = useCallback(() => {
    if (!vonIso || !bisIso || bisIso < vonIso) { setFehler("Bitte einen gültigen Zeitraum wählen."); return; }
    setFehler(null);
    api.get(`/belegung?von=${vonIso}&bis=${bisIso}&status=${status}`).then(setDaten).catch((e) => setFehler(e.message));
  }, [vonIso, bisIso, status]);
  useEffect(laden, [laden]);

  // Links wie #/belegung?tag=…&eintrag=… auch bei bereits geöffneter Seite übernehmen
  useEffect(() => {
    const uebernehmen = () => {
      const q = hashParameter();
      if (q.get("tag")) setBezug(ausIso(q.get("tag")));
      if (q.get("eintrag")) setSchublade({ art: "eintrag", id: q.get("eintrag") });
      else if (q.get("tag")) setSchublade({ art: "tag", datum: q.get("tag") });
    };
    window.addEventListener("hashchange", uebernehmen);
    return () => window.removeEventListener("hashchange", uebernehmen);
  }, []);

  useEffect(() => {
    const zu = (e) => { if (e.key === "Escape") setSchublade(null); };
    window.addEventListener("keydown", zu);
    return () => window.removeEventListener("keydown", zu);
  }, []);

  const blaettern = (richtung) => {
    if (ansicht === "monat") setBezug(new Date(bezug.getFullYear(), bezug.getMonth() + richtung, 1));
    else setBezug(plusTage(bezug, 7 * richtung));
  };
  const nachAenderung = () => { laden(); };

  return (
    <div className="seite">
      <header className="kopf">
        <h1>Belegung</h1>
        <div className="aktionen">
          <button className="knopf haupt" onClick={() => setSchublade({ art: "checkin" })}>
            <LogIn size={18} aria-hidden="true" />Check-in ohne Reservation
          </button>
        </div>
      </header>

      <div className="steuerung belegung-steuerung">
        <label className="kompakt">Ansicht
          <select value={ansicht} onChange={(e) => setAnsicht(e.target.value)}>
            <option value="monat">Monat</option><option value="woche">Woche</option><option value="frei">Freier Zeitraum</option>
          </select>
        </label>
        <label className="kompakt">Zeigen
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="alle">Akzeptierte und offene</option><option value="akzeptiert">Nur akzeptierte</option><option value="offen">Nur offene Anfragen</option>
          </select>
        </label>
        <div className="umschalter" role="group" aria-label="Darstellung">
          <button aria-pressed={darstellung === "uebersicht"} onClick={() => setDarstellung("uebersicht")}>Übersicht</button>
          <button aria-pressed={darstellung === "zeitband"} onClick={() => setDarstellung("zeitband")}>Zeitband</button>
          <button aria-pressed={darstellung === "liste"} onClick={() => setDarstellung("liste")}>Liste</button>
        </div>
      </div>

      <div className="zeitraumleiste">
        {ansicht === "frei" ? (
          <div className="freier-zeitraum">
            <label className="kompakt">Von<input type="date" value={frei.von} onChange={(e) => setFrei({ ...frei, von: e.target.value })} /></label>
            <label className="kompakt">Bis<input type="date" value={frei.bis} onChange={(e) => setFrei({ ...frei, bis: e.target.value })} /></label>
          </div>
        ) : (
          <>
            <button className="knopf symbol" onClick={() => blaettern(-1)} aria-label="Zurück"><ChevronLeft size={18} /></button>
            <h2>{titel}</h2>
            <button className="knopf symbol" onClick={() => blaettern(1)} aria-label="Weiter"><ChevronRight size={18} /></button>
            <button className="knopf neben" onClick={() => setBezug(new Date())}>Heute</button>
          </>
        )}
        {daten && (
          <p className="legende">
            <span className="probe-stufe hoch" aria-hidden="true" />ab {daten.meldung_ab} Plätzen
            <span className="probe-stufe voll" aria-hidden="true" />voll ({daten.plaetze})
            {darstellung === "zeitband" && <>
              <span className="probe akzeptiert" aria-hidden="true" />Akzeptiert
              <span className="probe offen" aria-hidden="true" />Offen
            </>}
          </p>
        )}
      </div>

      {fehler && <p className="meldung fehler">{fehler}</p>}
      {!fehler && !daten && <p className="leer">Wird geladen …</p>}
      {!fehler && daten && darstellung === "uebersicht" && (
        <Uebersicht daten={daten} heute={heute} gewaehlt={schublade?.art === "tag" ? schublade.datum : null}
          onTag={(datum) => setSchublade({ art: "tag", datum })} />
      )}
      {!fehler && daten && darstellung === "zeitband" && (
        <Zeitband daten={daten} heute={heute} onTag={(datum) => setSchublade({ art: "tag", datum })}
          onEintrag={(e) => setSchublade({ art: "eintrag", id: e.id })} />
      )}
      {!fehler && daten && darstellung === "liste" && <Liste daten={daten} onEintrag={(e) => setSchublade({ art: "eintrag", id: e.id })} />}

      {schublade && (
        <Schublade onSchliessen={() => setSchublade(null)}>
          {schublade.art === "tag" && (
            <TagPanel datum={schublade.datum} heute={heute}
              onEintrag={(e) => setSchublade({ art: "eintrag", id: e.id, zurueck: schublade.datum })} />
          )}
          {schublade.art === "eintrag" && (
            <EintragPanel id={schublade.id} heute={heute} zurueck={schublade.zurueck}
              onZurueck={(datum) => setSchublade({ art: "tag", datum })}
              onCheckin={(e) => setSchublade({ art: "checkin", eintrag: e, zurueck: schublade.zurueck })}
              onGeaendert={nachAenderung} onGeloescht={() => { nachAenderung(); setSchublade(schublade.zurueck ? { art: "tag", datum: schublade.zurueck } : null); }} />
          )}
          {schublade.art === "checkin" && (
            <CheckIn eintrag={schublade.eintrag} heute={heute}
              onAbbrechen={() => setSchublade(schublade.eintrag ? { art: "eintrag", id: schublade.eintrag.id, zurueck: schublade.zurueck } : null)}
              onEingecheckt={(a) => { nachAenderung(); setSchublade({ art: "eintrag", id: a.buchung_id, zurueck: schublade.zurueck }); }} />
          )}
        </Schublade>
      )}
    </div>
  );
}

function Schublade({ children, onSchliessen }) {
  return (
    <>
      <div className="schublade-hintergrund" onClick={onSchliessen} aria-hidden="true" />
      <aside className="schublade" role="dialog" aria-modal="false" aria-label="Details zur Belegung">
        <button className="knopf symbol schliessen" onClick={onSchliessen} aria-label="Schliessen"><X size={18} /></button>
        {children}
      </aside>
    </>
  );
}

// --- Übersicht: Auslastung und Zahlen je Typ, kompakt ---------------------------

function Uebersicht({ daten, heute, gewaehlt, onTag }) {
  const tage = daten.auslastung.map((a) => a.datum);
  const proTyp = Object.fromEntries(daten.nach_typ.map((t) => [t.stellplatz_typ, t]));
  const bewegungen = useMemo(() => {
    const m = Object.fromEntries(tage.map((d) => [d, { an: 0, ab: 0 }]));
    for (const e of daten.eintraege) {
      if (!e.akzeptiert) continue;
      if (m[e.von]) m[e.von].an += 1;
      if (m[e.bis]) m[e.bis].ab += 1;
    }
    return m;
  }, [daten]); // eslint-disable-line react-hooks/exhaustive-deps
  const offen = daten.eintraege.filter((e) => !e.akzeptiert).length;
  const spitze = Math.max(...daten.auslastung.map((a) => a.belegt), 0);
  const hoch = daten.auslastung.filter((a) => a.stufe !== "normal");

  return (
    <div className="zeitband-rahmen">
      <p className="belegung-fazit">
        Höchste Belegung: <strong>{spitze} von {daten.plaetze}</strong> Stellplätzen
        {hoch.length > 0 && <> · <span className="warnwort">{hoch.length} {hoch.length === 1 ? "Nacht" : "Nächte"} ab {daten.meldung_ab}</span></>}
        {offen > 0 && <> · {offen} offene {offen === 1 ? "Anfrage" : "Anfragen"} (nicht gezählt)</>}
      </p>
      <div className="uebersicht-raster" style={{ "--tage": tage.length }}>
        <div className="ue-ecke" />
        {tage.map((d) => {
          const datum = ausIso(d);
          const we = datum.getDay() === 0 || datum.getDay() === 6;
          return (
            <button key={d} className={`ue-tag${we ? " wochenende" : ""}${d === heute ? " heute" : ""}${d === gewaehlt ? " gewaehlt" : ""}`}
              onClick={() => onTag(d)} aria-label={`${TAG_LANG.format(datum)} anzeigen`}>
              <span>{WOCHENTAG[datum.getDay()]}</span><strong>{datum.getDate()}</strong>
            </button>
          );
        })}

        <div className="ue-titel ue-auslastung-titel"><strong>Stellplätze</strong><span>belegt von {daten.plaetze}</span></div>
        {daten.auslastung.map((a) => (
          <button key={a.datum} className={`ue-auslastung ${a.stufe}${a.datum === gewaehlt ? " gewaehlt" : ""}`} onClick={() => onTag(a.datum)}
            title={`${datumVoll(a.datum)}: ${a.belegt} von ${daten.plaetze} Stellplätzen belegt`}
            style={{ "--anteil": Math.min(1, a.belegt / daten.plaetze) }}>
            <strong>{a.belegt}</strong>
          </button>
        ))}

        {TYPEN.map((t) => (
          <Zeile key={t.code} typ={t.code} uebersicht={proTyp[t.code]} gewaehlt={gewaehlt} onTag={onTag}
            trenner={t.code === "zwaergli"} />
        ))}

        {[["an", "Anreisen"], ["ab", "Abreisen"]].map(([art, titel]) => (
          <BewegungsZeile key={art} art={art} titel={titel} tage={tage} bewegungen={bewegungen} gewaehlt={gewaehlt} onTag={onTag} />
        ))}
      </div>
      <p className="hinweis">
        Pro Nacht: akzeptierte Reservationen und Aufenthalte. Zelt, Wohnwagen und Camper zählen zu den {daten.plaetze} Stellplätzen,
        Zwärgli und Spycher separat. Klicken Sie auf einen Tag für Anreisen, Abreisen und Check-in.
      </p>
    </div>
  );
}

function BewegungsZeile({ art, titel, tage, bewegungen, gewaehlt, onTag }) {
  return (
    <>
      <div className={`ue-titel ue-klein${art === "an" ? " trenner-oben" : ""}`}><span>{titel}</span></div>
      {tage.map((d) => (
        <button key={d} className={`ue-bewegung ${art}${art === "an" ? " trenner-oben" : ""}${d === gewaehlt ? " gewaehlt" : ""}`}
          onClick={() => onTag(d)} title={`${datumVoll(d)}: ${bewegungen[d][art]} ${titel}`}>
          {bewegungen[d][art] || ""}
        </button>
      ))}
    </>
  );
}

function Zeile({ typ, uebersicht, gewaehlt, onTag, trenner }) {
  if (!uebersicht) return null;
  return (
    <>
      <div className={`ue-titel${trenner ? " trenner-oben" : ""}`} style={{ "--typ": typStil(typ).farbe }}>
        <TypMarke code={typ} groesse={16} />
        {!STELLPLAETZE.includes(typ) && <span>separat</span>}
      </div>
      {uebersicht.tage.map((s) => (
        <button key={s.datum} className={`ue-zahl${s.anzahl ? " belegt" : ""}${trenner ? " trenner-oben" : ""}${s.datum === gewaehlt ? " gewaehlt" : ""}`}
          style={{ "--typ": typStil(typ).farbe }} onClick={() => onTag(s.datum)}
          title={`${datumVoll(s.datum)}: ${s.anzahl} Reservationen, ${s.erwachsene} Erwachsene, ${s.kinder} Kinder`}>
          {s.anzahl > 0 ? s.anzahl : ""}
        </button>
      ))}
    </>
  );
}

// --- Zeitband (wie bisher, Balken öffnen die Schublade) --------------------------

function Zeitband({ daten, heute, onTag, onEintrag }) {
  const tage = daten.nach_typ[0]?.tage.map((t) => t.datum) ?? [];
  const index = Object.fromEntries(tage.map((d, i) => [d, i]));
  const proTyp = useMemo(() => TYPEN.map((t) => ({
    ...t,
    uebersicht: daten.nach_typ.find((x) => x.stellplatz_typ === t.code),
    zeilen: aufZeilen(daten.eintraege.filter((e) => e.stellplatz_typ === t.code)),
  })), [daten]);
  const ohneTyp = daten.eintraege.filter((e) => !e.stellplatz_typ);
  const auslastung = Object.fromEntries(daten.auslastung.map((a) => [a.datum, a]));

  const spalten = (e) => {
    const start = e.von < tage[0] ? 0 : index[e.von];
    const ende = e.bis > tage[tage.length - 1] ? tage.length : index[e.bis];
    return { gridColumn: `${start + 2} / ${ende + 2}` };
  };

  return (
    <div className="zeitband-rahmen">
      <div className="zeitband kompakt" style={{ "--tage": tage.length }}>
        <div className="zb-ecke" />
        {tage.map((d) => {
          const datum = ausIso(d);
          const we = datum.getDay() === 0 || datum.getDay() === 6;
          const a = auslastung[d];
          return (
            <button key={d} className={`zb-tag${we ? " wochenende" : ""}${d === heute ? " heute" : ""} stufe-${a?.stufe ?? "normal"}`}
              onClick={() => onTag(d)} title={a ? `${a.belegt} von ${daten.plaetze} Stellplätzen belegt` : undefined}>
              <span>{WOCHENTAG[datum.getDay()]}</span><strong>{datum.getDate()}</strong><em>{a?.belegt ?? ""}</em>
            </button>
          );
        })}

        {proTyp.map((t) => (
          <div key={t.code} className="zb-gruppe" role="rowgroup" aria-label={t.name} style={{ "--typ": typStil(t.code).farbe }}>
            <div className="zb-typ">
              <strong><TypMarke code={t.code} groesse={18} /></strong>
              <span>{t.uebersicht?.anzahl_reservationen || "keine"} {t.uebersicht?.anzahl_reservationen === 1 ? "Eintrag" : "Einträge"}</span>
            </div>
            {t.uebersicht?.tage.map((s) => (
              <div key={s.datum} className={`zb-summe${s.anzahl ? " belegt" : ""}`} title={`${datumKurz(s.datum)}: ${s.anzahl} Reservationen, ${s.erwachsene} Erwachsene, ${s.kinder} Kinder`}>
                {s.anzahl > 0 && <><strong>{s.anzahl}</strong><span>{s.erwachsene}E {s.kinder}K</span></>}
              </div>
            ))}
            {t.zeilen.map((zeile, i) => (
              <div key={i} className="zb-spur">
                {zeile.map((e) => (
                  <button key={e.id} onClick={() => onEintrag(e)}
                    className={`zb-balken ${e.akzeptiert ? "akzeptiert" : "offen"}${istAufenthalt(e) ? " aufenthalt" : ""}`} style={spalten(e)}
                    title={`${e.gast_name}${e.nummer ? ` (${e.nummer})` : ""}: ${datumKurz(e.von)} – ${datumKurz(e.bis)}, ${e.naechte} Nächte, ${e.erwachsene} E, ${e.kinder} K, ${eintragStatus(e)}`}>
                    <span className="innen">
                      <span className="name">{e.platz ? `${e.platz} · ` : ""}{e.gast_name}</span>
                      <span className="pers">{e.erwachsene}E {e.kinder}K</span>
                    </span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        ))}
      </div>
      {ohneTyp.length > 0 && (
        <p className="meldung warnung">{ohneTyp.length} Anfrage(n) in diesem Zeitraum ohne Stellplatz-Typ: {ohneTyp.map((e) => e.gast_name).join(", ")}. Ergänzen Sie den Typ unter Reservationen.</p>
      )}
    </div>
  );
}

function Liste({ daten, onEintrag }) {
  if (daten.eintraege.length === 0) {
    return <p className="leer">Keine Reservationen in diesem Zeitraum.</p>;
  }
  const gruppen = [...TYPEN, { code: null, name: "Ohne Stellplatz-Typ" }]
    .map((t) => ({ ...t, eintraege: daten.eintraege.filter((e) => (e.stellplatz_typ ?? null) === t.code) }))
    .filter((g) => g.eintraege.length);
  return (
    <div className="tabellen">
      {gruppen.map((g) => {
        const summe = g.eintraege.reduce((s, e) => [s[0] + e.erwachsene, s[1] + e.kinder], [0, 0]);
        return (
          <table key={g.code ?? "ohne"} className="tabelle">
            <caption style={{ "--typ": typStil(g.code).farbe }}>{g.code ? <TypMarke code={g.code} groesse={18} /> : g.name} <span>{g.eintraege.length} {g.eintraege.length === 1 ? "Eintrag" : "Einträge"}, {personen(summe[0], summe[1])}</span></caption>
            <colgroup><col className="c-gast" /><col className="c-datum" /><col className="c-datum" /><col className="c-zahl" /><col className="c-zahl" /><col className="c-zahl" /><col className="c-status" /></colgroup>
            <thead><tr><th>Gast</th><th>Anreise</th><th>Abreise</th><th className="zahl">Nächte</th><th className="zahl">E</th><th className="zahl">K</th><th>Status</th></tr></thead>
            <tbody>
              {g.eintraege.map((e) => (
                <tr key={e.id}>
                  <td><button className="link" onClick={() => onEintrag(e)}>{e.gast_name}</button>{e.nummer && <span className="nummer"> {e.nummer}</span>}</td>
                  <td>{datumKurz(e.von)}</td><td>{datumKurz(e.bis)}</td>
                  <td className="zahl">{e.naechte}</td><td className="zahl">{e.erwachsene}</td><td className="zahl">{e.kinder}</td>
                  <td><span className={`punkt ${e.akzeptiert ? "akzeptiert" : "offen"}`} aria-hidden="true" />{eintragStatus(e)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        );
      })}
    </div>
  );
}

// --- Schublade: Tag, Eintrag, Check-in ------------------------------------------

function TagPanel({ datum, heute, onEintrag }) {
  const [daten, setDaten] = useState(null);
  const [fehler, setFehler] = useState(null);
  useEffect(() => {
    setDaten(null);
    api.get(`/belegung?von=${datum}&bis=${datum}&status=alle`).then(setDaten).catch((e) => setFehler(e.message));
  }, [datum]);
  // Abreisen: Einträge mit bis = datum liegen nicht mehr in der Nacht – separat laden
  const [abreisen, setAbreisen] = useState([]);
  useEffect(() => {
    const vortag = isoDatum(plusTage(ausIso(datum), -1));
    api.get(`/belegung?von=${vortag}&bis=${vortag}&status=akzeptiert`)
      .then((d) => setAbreisen(d.eintraege.filter((e) => e.bis === datum))).catch(() => {});
  }, [datum]);

  if (fehler) return <p className="meldung fehler">{fehler}</p>;
  if (!daten) return <p className="leer">Wird geladen …</p>;
  const a = daten.auslastung[0];
  const anreisen = daten.eintraege.filter((e) => e.von === datum);
  const anwesend = daten.eintraege.filter((e) => e.von < datum && e.akzeptiert);
  const offen = anreisen.filter((e) => !e.akzeptiert);
  const akzAnreisen = anreisen.filter((e) => e.akzeptiert);

  return (
    <div className="panel">
      <h2>{TAG_LANG.format(ausIso(datum))}</h2>
      <p className={`auslastung-satz ${a.stufe}`}>
        <strong>{a.belegt} von {daten.plaetze}</strong> Stellplätzen belegt
        {a.stufe === "hoch" && " – hohe Belegung"}{a.stufe === "voll" && (a.belegt > daten.plaetze ? ` – überbucht (${a.belegt - daten.plaetze} zu viel)` : " – ausgebucht")}
      </p>
      <PanelListe titel="Anreisen" leer="Keine Anreisen." eintraege={akzAnreisen} onEintrag={onEintrag}
        aktion={(e) => (!istAufenthalt(e) && e.status === "bezahlt_akzeptiert" && datum <= heute ? "einchecken" : null)} />
      <PanelListe titel="Abreisen" leer="Keine Abreisen." eintraege={abreisen} onEintrag={onEintrag} />
      <PanelListe titel="Bleiben über Nacht" leer="Niemand." eintraege={anwesend} onEintrag={onEintrag} einklappbar />
      {offen.length > 0 && <PanelListe titel="Offene Anfragen mit Anreise" eintraege={offen} onEintrag={onEintrag} />}
    </div>
  );
}

function PanelListe({ titel, leer, eintraege, onEintrag, aktion, einklappbar }) {
  const inhalt = eintraege.length === 0 ? <p className="leer klein">{leer}</p> : (
    <ul className="panel-liste">
      {eintraege.map((e) => (
        <li key={e.id}>
          <button onClick={() => onEintrag(e)} style={{ "--typ": typStil(e.stellplatz_typ).farbe }}>
            <span className="zeile1">
              <strong>{e.platz ? `${e.platz} · ` : ""}{e.gast_name}</strong>
              <span className={`marke-status ton-${istAufenthalt(e) ? "ok" : STATUS[e.status]?.ton ?? "info"}`}>{eintragStatus(e)}</span>
            </span>
            <span className="zeile2">
              <TypMarke code={e.stellplatz_typ} groesse={14} /> {datumKurz(e.von)} – {datumKurz(e.bis)} · {personen(e.erwachsene, e.kinder)}
              {aktion?.(e) === "einchecken" && <span className="hinweis-aktion">einchecken →</span>}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
  if (einklappbar) {
    return <details className="panel-abschnitt"><summary>{titel} ({eintraege.length})</summary>{inhalt}</details>;
  }
  return <section className="panel-abschnitt"><h3>{titel} ({eintraege.length})</h3>{inhalt}</section>;
}

function EintragPanel({ id, heute, zurueck, onZurueck, onCheckin, onGeaendert, onGeloescht }) {
  const [eintrag, setEintrag] = useState(null);
  const [fehler, setFehler] = useState(null);
  const [laeuft, setLaeuft] = useState(false);
  const [bestaetigen, setBestaetigen] = useState(null); // "loeschen" | "stornieren" | "nicht_erschienen"
  const [abreise, setAbreise] = useState(heute);

  const laden = useCallback(async () => {
    setFehler(null);
    // id ist eine Reservation oder ein Aufenthalt (Buchung)
    try {
      const a = await api.get(`/reservationsanfragen/${id}`).catch(() => null);
      if (a && !(a.status === "angereist" && a.buchung_id)) { setEintrag({ art: "reservation", ...a }); return; }
      const b = await api.get(`/aufenthalte/${a ? a.buchung_id : id}`);
      const anfrage = a ?? (b.reservationsanfrage_id ? await api.get(`/reservationsanfragen/${b.reservationsanfrage_id}`).catch(() => null) : null);
      setEintrag({ art: "aufenthalt", ...b, anfrage });
    } catch (e) { setFehler(e.message); }
  }, [id]);
  useEffect(() => { laden(); }, [laden]);

  const ausfuehren = async (fn) => {
    setLaeuft(true); setFehler(null);
    try { await fn(); } catch (e) { setFehler(e.message); } finally { setLaeuft(false); setBestaetigen(null); }
  };

  if (fehler && !eintrag) return <p className="meldung fehler">{fehler}</p>;
  if (!eintrag) return <p className="leer">Wird geladen …</p>;

  const zurueckKnopf = zurueck && <button className="link zurueck" onClick={() => onZurueck(zurueck)}>← {TAG_LANG.format(ausIso(zurueck))}</button>;

  if (eintrag.art === "aufenthalt") {
    const e = eintrag;
    return (
      <div className="panel">
        {zurueckKnopf}
        <h2>{e.vorname} {e.nachname}</h2>
        <p><span className="marke-status ton-ok">{e.status === "eingecheckt" ? "Eingecheckt" : "Abgereist"}</span>
          {e.anfrage?.nummer && <span className="nummer"> Reservation {e.anfrage.nummer}</span>}</p>
        <dl className="angaben">
          <dt>Aufenthalt</dt><dd>{datumVoll(e.von)} bis {datumVoll(e.bis)}</dd>
          <dt>Stellplatz</dt><dd><TypMarke code={e.stellplatz_typ} />{e.platz ? `, Platz ${e.platz}` : ""}</dd>
          <dt>Personen</dt><dd>{personenLang(e.anzahl_erwachsene, e.anzahl_kinder, e.anzahl_kleinkinder)}</dd>
          <dt>Nationalität</dt><dd>{LAENDER[e.nationalitaet] ?? e.nationalitaet ?? "–"}</dd>
          <dt>Adresse</dt><dd>{[e.strasse, [e.plz, e.ort].filter(Boolean).join(" "), LAENDER[e.land] ?? e.land].filter(Boolean).join(", ") || "–"}</dd>
          <dt>Kontakt</dt><dd>{[e.email, e.telefon].filter(Boolean).join(", ") || "–"}</dd>
          {e.anfrage?.anzahlung_erhalten && <><dt>Anzahlung</dt><dd>CHF {Number(e.anfrage.anzahlung_erhalten).toFixed(2)} erhalten</dd></>}
          {e.bemerkung && <><dt>Bemerkung</dt><dd className="mehrzeilig">{e.bemerkung}</dd></>}
        </dl>
        {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
        {e.status === "eingecheckt" && (
          <div className="aktionen">
            <label className="kompakt">Abreise am<input type="date" value={abreise} min={isoDatum(plusTage(ausIso(e.von), 1))} onChange={(x) => setAbreise(x.target.value)} /></label>
            <button className="knopf haupt" disabled={laeuft} onClick={() => ausfuehren(async () => {
              setEintrag({ ...eintrag, ...(await api.post(`/aufenthalte/${e.buchung_id}/abreise`, { datum: abreise })) }); onGeaendert();
            })}>Abreise erfassen</button>
          </div>
        )}
        <Bestaetigung offen={bestaetigen === "loeschen"} onOeffnen={() => setBestaetigen("loeschen")} onAbbrechen={() => setBestaetigen(null)}
          knopf="Aufenthalt löschen" frage={`Aufenthalt von ${e.vorname} ${e.nachname} löschen?${e.anfrage ? " Die Reservation ist danach wieder «akzeptiert»." : ""}`}
          laeuft={laeuft} onJa={() => ausfuehren(async () => { await api.delete(`/aufenthalte/${e.buchung_id}`); onGeloescht(); })} />
      </div>
    );
  }

  const a = eintrag;
  const akzeptiert = a.status === "bezahlt_akzeptiert";
  const angereistMoeglich = akzeptiert && a.gewuenscht_von <= heute;
  return (
    <div className="panel">
      {zurueckKnopf}
      <h2>{a.gast_name}</h2>
      <p><span className={`marke-status ton-${STATUS[a.status]?.ton ?? "info"}`}>{statusName(a.status)}</span>
        {a.nummer && <span className="nummer"> Nr. {a.nummer}</span>}</p>
      <dl className="angaben">
        <dt>Zeitraum</dt><dd>{datumVoll(a.gewuenscht_von)} bis {datumVoll(a.gewuenscht_bis)}</dd>
        <dt>Stellplatz</dt><dd><TypMarke code={a.stellplatz_typ} /></dd>
        <dt>Personen</dt><dd>{personenLang(a.anzahl_erwachsene, a.anzahl_kinder, a.anzahl_kleinkinder)}</dd>
        <dt>Kontakt</dt><dd>{[a.gast_email, a.gast_telefon].filter(Boolean).join(", ")}</dd>
        {(a.anzahlung_erhalten || akzeptiert) && <><dt>Anzahlung</dt><dd>{a.anzahlung_erhalten ? `CHF ${Number(a.anzahlung_erhalten).toFixed(2)} erhalten` : "ohne Anzahlung"}</dd></>}
        {a.bemerkung && <><dt>Bemerkung</dt><dd className="mehrzeilig">{a.bemerkung}</dd></>}
      </dl>
      {a.hohe_belegung?.length > 0 && <HoheBelegung liste={a.hohe_belegung} />}
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
      <div className="aktionen">
        {angereistMoeglich && (
          <button className="knopf haupt" onClick={() => onCheckin(a)}><LogIn size={18} aria-hidden="true" />Angereist – einchecken</button>
        )}
        {akzeptiert && !angereistMoeglich && <p className="hinweis">Einchecken ist ab dem Anreisetag ({datumVoll(a.gewuenscht_von)}) möglich.</p>}
        <a className="knopf neben" href={`#/reservationen?id=${a.id}`}>In Reservationen öffnen</a>
      </div>
      {angereistMoeglich && (
        <Bestaetigung offen={bestaetigen === "nicht_erschienen"} onOeffnen={() => setBestaetigen("nicht_erschienen")} onAbbrechen={() => setBestaetigen(null)}
          knopf="Nicht angereist" frage={`${a.gast_name} ist nicht erschienen? Der Platz wird freigegeben${a.anzahlung_erhalten ? ", die Anzahlung bleibt erfasst" : ""}.`}
          laeuft={laeuft} onJa={() => ausfuehren(async () => { await api.post(`/reservationsanfragen/${a.id}/nicht-erschienen`); await laden(); onGeaendert(); })} />
      )}
      {!["storniert", "abgelehnt", "nicht_erschienen"].includes(a.status) && (
        <Bestaetigung offen={bestaetigen === "stornieren"} onOeffnen={() => setBestaetigen("stornieren")} onAbbrechen={() => setBestaetigen(null)}
          knopf="Stornieren" frage={`Reservation von ${a.gast_name} stornieren? Sie bleibt mit Mailverlauf erhalten (Ablage «Abgelehnt / storniert»).`}
          laeuft={laeuft} onJa={() => ausfuehren(async () => { await api.post(`/reservationsanfragen/${a.id}/status`, { status: "storniert" }); await laden(); onGeaendert(); })} />
      )}
      <Bestaetigung offen={bestaetigen === "loeschen"} onOeffnen={() => setBestaetigen("loeschen")} onAbbrechen={() => setBestaetigen(null)}
        knopf="Endgültig löschen" frage={`Anfrage von ${a.gast_name} mit Mailverlauf und Zahlungen endgültig löschen? Für Absagen besser «Stornieren».`}
        laeuft={laeuft} onJa={() => ausfuehren(async () => { await api.delete(`/reservationsanfragen/${a.id}`); onGeloescht(); })} />
    </div>
  );
}

export function HoheBelegung({ liste }) {
  const voll = liste.filter((h) => h.mit_dieser > h.plaetze);
  return (
    <p className={`meldung ${voll.length ? "fehler" : "warnung"}`}>
      Hohe Belegung: {liste.map((h) => `${datumKurz(h.datum)} ${h.mit_dieser}/${h.plaetze}`).join(", ")}
      {voll.length ? " – damit überbucht!" : " (mit dieser Reservation)."}
    </p>
  );
}

function Bestaetigung({ offen, onOeffnen, onAbbrechen, knopf, frage, laeuft, onJa }) {
  if (!offen) return <div className="aktionen"><button className="knopf leise" onClick={onOeffnen}>{knopf}</button></div>;
  return (
    <div className="bestaetigung" role="group" aria-label={knopf}>
      <p>{frage}</p>
      <div className="aktionen">
        <button className="knopf gefahr" disabled={laeuft} onClick={onJa}>{knopf}</button>
        <button className="knopf leise" onClick={onAbbrechen}>Abbrechen</button>
      </div>
    </div>
  );
}

function CheckIn({ eintrag, heute, onAbbrechen, onEingecheckt }) {
  const teile = (eintrag?.gast_name || "").trim().split(/\s+/);
  const [werte, setWerte] = useState({
    vorname: teile.length > 1 ? teile.slice(0, -1).join(" ") : teile[0] || "",
    nachname: teile.length > 1 ? teile[teile.length - 1] : "",
    nationalitaet: "", nationalitaet_iso: "",
    strasse: "", plz: "", ort: "", land: "", email: eintrag?.gast_email || "", telefon: eintrag?.gast_telefon || "",
    stellplatz_typ: eintrag?.stellplatz_typ || "zeltwiese", platz: "",
    von: eintrag ? (eintrag.gewuenscht_von < heute ? eintrag.gewuenscht_von : heute) : heute,
    bis: eintrag?.gewuenscht_bis || isoDatum(plusTage(new Date(), 1)),
    anzahl_erwachsene: eintrag?.anzahl_erwachsene ?? 2, anzahl_kinder: eintrag?.anzahl_kinder ?? 0,
    anzahl_kleinkinder: eintrag?.anzahl_kleinkinder ?? 0, bemerkung: "",
  });
  const [fehler, setFehler] = useState(null);
  const [laeuft, setLaeuft] = useState(false);
  const feld = (name) => ({ id: `ci-${name}`, value: werte[name], onChange: (e) => setWerte({ ...werte, [name]: e.target.value }) });

  const nationalitaet = werte.nationalitaet === ANDERES ? werte.nationalitaet_iso.trim().toUpperCase() : werte.nationalitaet;

  const absenden = async (e) => {
    e.preventDefault(); setFehler(null);
    if (!/^[A-Z]{2}$/.test(nationalitaet)) { setFehler("Bitte die Nationalität angeben (für die HESTA-Meldung)."); return; }
    setLaeuft(true);
    try {
      const { nationalitaet_iso, ...rest } = werte; // eslint-disable-line no-unused-vars
      onEingecheckt(await api.post("/aufenthalte", {
        ...rest, nationalitaet, reservationsanfrage_id: eintrag?.id ?? null,
        email: werte.email || null, telefon: werte.telefon || null, strasse: werte.strasse || null,
        plz: werte.plz || null, ort: werte.ort || null, land: werte.land || null, bemerkung: werte.bemerkung || null,
        anzahl_erwachsene: Number(werte.anzahl_erwachsene), anzahl_kinder: Number(werte.anzahl_kinder),
        anzahl_kleinkinder: Number(werte.anzahl_kleinkinder),
      }));
    } catch (err) { setFehler(err.message); } finally { setLaeuft(false); }
  };

  return (
    <form className="panel formular-schmal" onSubmit={absenden}>
      <h2>{eintrag ? `Check-in ${eintrag.gast_name}` : "Check-in ohne Reservation"}</h2>
      <p className="hinweis">
        Erfasst Buchung und Aufenthalt{eintrag?.nummer ? ` zur Reservation ${eintrag.nummer}` : ""}. Nötig sind Name und
        Nationalität (für die HESTA-Meldung), alles Weitere ist freiwillig.
      </p>
      <div className="felder zwei">
        <div className="feld"><label htmlFor="ci-vorname">Vorname</label><input required {...feld("vorname")} /></div>
        <div className="feld"><label htmlFor="ci-nachname">Nachname</label><input required {...feld("nachname")} /></div>
        <div className={`feld${werte.nationalitaet === ANDERES ? "" : " breit"}`}><label htmlFor="ci-nationalitaet">Nationalität</label>
          <select required {...feld("nationalitaet")}>
            <option value="">Bitte wählen</option>
            {Object.entries(LAENDER).map(([c, n]) => <option key={c} value={c}>{n}</option>)}
            <option value={ANDERES}>Anderes Land …</option>
          </select></div>
        {werte.nationalitaet === ANDERES && (
          <div className="feld"><label htmlFor="ci-nationalitaet_iso">Ländercode (ISO, 2 Buchstaben)</label>
            <input required maxLength={2} pattern="[A-Za-z]{2}" placeholder="z.B. GR" {...feld("nationalitaet_iso")} /></div>
        )}
        <div className="feld"><label htmlFor="ci-stellplatz_typ">Stellplatz</label>
          <select {...feld("stellplatz_typ")}>{TYPEN.map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}</select></div>
        <div className="feld"><label htmlFor="ci-platz">Platz (optional)</label><input {...feld("platz")} placeholder="z.B. 17" /></div>
        <div className="feld"><label htmlFor="ci-von">Anreise</label><input type="date" required max={heute} {...feld("von")} /></div>
        <div className="feld"><label htmlFor="ci-bis">Abreise</label><input type="date" required min={isoDatum(plusTage(ausIso(werte.von), 1))} {...feld("bis")} /></div>
        <div className="feld"><label htmlFor="ci-anzahl_erwachsene">Erwachsene (ab 16)</label><input type="number" min="0" max="50" required {...feld("anzahl_erwachsene")} /></div>
        <div className="feld"><label htmlFor="ci-anzahl_kinder">Kinder (6–15)</label><input type="number" min="0" max="50" required {...feld("anzahl_kinder")} /></div>
        <div className="feld"><label htmlFor="ci-anzahl_kleinkinder">Kleinkinder (0–5)</label><input type="number" min="0" max="50" required {...feld("anzahl_kleinkinder")} /></div>
        <div className="feld breit"><label htmlFor="ci-bemerkung">Bemerkung</label><textarea rows="2" {...feld("bemerkung")} /></div>
      </div>
      <details className="optional">
        <summary>Adresse und Kontakt (optional)</summary>
        <div className="felder zwei">
          <div className="feld breit"><label htmlFor="ci-strasse">Strasse</label><input {...feld("strasse")} autoComplete="off" /></div>
          <div className="feld"><label htmlFor="ci-plz">PLZ</label><input {...feld("plz")} /></div>
          <div className="feld"><label htmlFor="ci-ort">Ort</label><input {...feld("ort")} /></div>
          <div className="feld"><label htmlFor="ci-land">Land</label>
            <select {...feld("land")}><option value="">–</option>{Object.entries(LAENDER).map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select></div>
          <div className="feld"><label htmlFor="ci-telefon">Telefon</label><input type="tel" {...feld("telefon")} /></div>
          <div className="feld breit"><label htmlFor="ci-email">E-Mail</label><input type="email" {...feld("email")} /></div>
        </div>
      </details>
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
      <div className="aktionen">
        <button className="knopf haupt" type="submit" disabled={laeuft}><LogIn size={18} aria-hidden="true" />Einchecken</button>
        <button className="knopf leise" type="button" onClick={onAbbrechen}>Abbrechen</button>
      </div>
    </form>
  );
}
