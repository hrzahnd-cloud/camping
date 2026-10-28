import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "../api.js";
import { TYPEN, ausIso, datumKurz, isoDatum, personen, plusTage, statusName } from "../format.js";
import { TypMarke, typStil } from "../typen.jsx";

const WOCHENTAG = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
const MONAT = new Intl.DateTimeFormat("de-CH", { month: "long", year: "numeric" });

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

export default function Belegung() {
  const heute = new Date();
  const [ansicht, setAnsicht] = useState("monat");
  const [bezug, setBezug] = useState(heute);
  const [frei, setFrei] = useState({ von: isoDatum(heute), bis: isoDatum(plusTage(heute, 13)) });
  const [status, setStatus] = useState("alle");
  const [darstellung, setDarstellung] = useState("zeitband");
  const [daten, setDaten] = useState(null);
  const [fehler, setFehler] = useState(null);

  const { von, bis, titel } = bereich(ansicht, bezug, frei);
  const vonIso = von ? isoDatum(von) : "", bisIso = bis ? isoDatum(bis) : "";

  useEffect(() => {
    if (!vonIso || !bisIso || bisIso < vonIso) { setFehler("Bitte einen gültigen Zeitraum wählen."); return; }
    setFehler(null);
    api.get(`/belegung?von=${vonIso}&bis=${bisIso}&status=${status}`).then(setDaten).catch((e) => setFehler(e.message));
  }, [vonIso, bisIso, status]);

  const blaettern = (richtung) => {
    if (ansicht === "monat") setBezug(new Date(bezug.getFullYear(), bezug.getMonth() + richtung, 1));
    else setBezug(plusTage(bezug, 7 * richtung));
  };

  return (
    <div className="seite">
      <header className="kopf">
        <h1>Belegung</h1>
        <div className="steuerung">
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
            <button aria-pressed={darstellung === "zeitband"} onClick={() => setDarstellung("zeitband")}>Zeitband</button>
            <button aria-pressed={darstellung === "liste"} onClick={() => setDarstellung("liste")}>Liste</button>
          </div>
        </div>
      </header>

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
        <p className="legende">
          <span className="probe akzeptiert" aria-hidden="true" />Akzeptiert (volle Fläche)
          <span className="probe offen" aria-hidden="true" />Offene Anfrage (schraffiert)
          <span className="erklaerung">E = Erwachsene, K = Kinder</span>
        </p>
      </div>

      {fehler && <p className="meldung fehler">{fehler}</p>}
      {!fehler && !daten && <p className="leer">Wird geladen …</p>}
      {!fehler && daten && (darstellung === "zeitband"
        ? <Zeitband daten={daten} heute={isoDatum(heute)} />
        : <Liste daten={daten} />)}
    </div>
  );
}

function Zeitband({ daten, heute }) {
  const tage = daten.nach_typ[0]?.tage.map((t) => t.datum) ?? [];
  const index = Object.fromEntries(tage.map((d, i) => [d, i]));
  const proTyp = useMemo(() => TYPEN.map((t) => ({
    ...t,
    uebersicht: daten.nach_typ.find((x) => x.stellplatz_typ === t.code),
    zeilen: aufZeilen(daten.eintraege.filter((e) => e.stellplatz_typ === t.code)),
  })), [daten]);
  const ohneTyp = daten.eintraege.filter((e) => !e.stellplatz_typ);

  // Balken: Spalte 1 = Beschriftung, Spalten 2.. = Tage; Abreisetag ist keine Nacht
  const spalten = (e) => {
    const start = e.von < tage[0] ? 0 : index[e.von];
    const ende = e.bis > tage[tage.length - 1] ? tage.length : index[e.bis];
    return { gridColumn: `${start + 2} / ${ende + 2}` };
  };

  return (
    <div className="zeitband-rahmen">
      <div className="zeitband" style={{ "--tage": tage.length }}>
        <div className="zb-ecke" />
        {tage.map((d) => {
          const datum = ausIso(d);
          const we = datum.getDay() === 0 || datum.getDay() === 6;
          return (
            <div key={d} className={`zb-tag${we ? " wochenende" : ""}${d === heute ? " heute" : ""}`}>
              <span>{WOCHENTAG[datum.getDay()]}</span><strong>{datum.getDate()}</strong>
            </div>
          );
        })}

        {proTyp.map((t) => (
          <div key={t.code} className="zb-gruppe" role="rowgroup" aria-label={t.name} style={{ "--typ": typStil(t.code).farbe }}>
            <div className="zb-typ">
              <strong><TypMarke code={t.code} groesse={18} /></strong>
              <span>{t.uebersicht?.anzahl_reservationen || "keine"} {t.uebersicht?.anzahl_reservationen === 1 ? "Reservation" : "Reservationen"}</span>
            </div>
            {t.uebersicht?.tage.map((s) => (
              <div key={s.datum} className={`zb-summe${s.anzahl ? " belegt" : ""}`} title={`${datumKurz(s.datum)}: ${s.anzahl} Reservationen, ${s.erwachsene} Erwachsene, ${s.kinder} Kinder`}>
                {s.anzahl > 0 && <><strong>{s.anzahl}</strong><span>{s.erwachsene}E</span><span>{s.kinder}K</span></>}
              </div>
            ))}
            {t.zeilen.map((zeile, i) => (
              <div key={i} className="zb-spur">
                {zeile.map((e) => (
                  <a key={e.anfrage_id} href="#/reservationen" className={`zb-balken ${e.akzeptiert ? "akzeptiert" : "offen"}`} style={spalten(e)}
                    title={`${e.gast_name}: ${datumKurz(e.von)} – ${datumKurz(e.bis)}, ${e.naechte} Nächte, ${e.erwachsene} Erwachsene, ${e.kinder} Kinder, ${statusName(e.status)}`}>
                    <span className="innen">
                      <span className="name">{e.gast_name}</span>
                      <span className="pers">{e.erwachsene}E {e.kinder}K</span>
                    </span>
                  </a>
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

function Liste({ daten }) {
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
            <caption style={{ "--typ": typStil(g.code).farbe }}>{g.code ? <TypMarke code={g.code} groesse={18} /> : g.name} <span>{g.eintraege.length} {g.eintraege.length === 1 ? "Reservation" : "Reservationen"}, {personen(summe[0], summe[1])}</span></caption>
            <colgroup><col className="c-gast" /><col className="c-datum" /><col className="c-datum" /><col className="c-zahl" /><col className="c-zahl" /><col className="c-zahl" /><col className="c-status" /></colgroup>
            <thead><tr><th>Gast</th><th>Anreise</th><th>Abreise</th><th className="zahl">Nächte</th><th className="zahl">E</th><th className="zahl">K</th><th>Status</th></tr></thead>
            <tbody>
              {g.eintraege.map((e) => (
                <tr key={e.anfrage_id}>
                  <td>{e.gast_name}</td><td>{datumKurz(e.von)}</td><td>{datumKurz(e.bis)}</td>
                  <td className="zahl">{e.naechte}</td><td className="zahl">{e.erwachsene}</td><td className="zahl">{e.kinder}</td>
                  <td><span className={`punkt ${e.akzeptiert ? "akzeptiert" : "offen"}`} aria-hidden="true" />{statusName(e.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        );
      })}
    </div>
  );
}
