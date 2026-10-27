import { useCallback, useEffect, useState } from "react";
import { Plus, Search } from "lucide-react";
import { api } from "../api.js";
import { datumVoll } from "../format.js";

const LEER = { vorname: "", nachname: "", geburtsdatum: "", nationalitaet: "", strasse: "", plz: "", ort: "", land: "", email: "", telefon: "" };

export default function Gaeste() {
  const [gaeste, setGaeste] = useState(null);
  const [suche, setSuche] = useState("");
  const [auswahl, setAuswahl] = useState(null); // Gast | "neu" | null
  const [gespeichertId, setGespeichertId] = useState(null);
  const waehle = (g) => { setAuswahl(g); setGespeichertId(null); };
  const [fehler, setFehler] = useState(null);

  const laden = useCallback((s = suche) => {
    api.get(`/gaeste${s.trim() ? `?suche=${encodeURIComponent(s.trim())}` : ""}`).then(setGaeste).catch((e) => setFehler(e.message));
  }, [suche]);
  useEffect(() => { const t = setTimeout(() => laden(suche), 250); return () => clearTimeout(t); }, [suche, laden]);

  return (
    <div className="seite">
      <header className="kopf">
        <h1>Gäste</h1>
        <button className="knopf haupt" onClick={() => waehle("neu")}><Plus size={18} aria-hidden="true" />Gast erfassen</button>
      </header>
      {fehler && <p className="meldung fehler">{fehler}</p>}
      <div className="zweiteilig">
        <section className="postfach" aria-label="Gästeliste">
          <label className="suchfeld">
            <Search size={16} aria-hidden="true" />
            <input type="search" placeholder="Name, Ort oder E-Mail suchen" value={suche} onChange={(e) => setSuche(e.target.value)} />
          </label>
          {gaeste === null && <p className="leer">Wird geladen …</p>}
          {gaeste && gaeste.length === 0 && <p className="leer">{suche ? "Kein Gast gefunden." : "Noch keine Gäste erfasst."}</p>}
          <ul className="anfrageliste">
            {(gaeste || []).map((g) => (
              <li key={g.id}>
                <button className="anfrage" aria-current={auswahl?.id === g.id ? "true" : undefined} onClick={() => waehle(g)}>
                  <span className="zeile1"><strong>{g.nachname}, {g.vorname}</strong></span>
                  <span className="zeile2">{[g.plz, g.ort].filter(Boolean).join(" ") || "Ort fehlt"}{g.land ? `, ${g.land}` : ""}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className="detail" aria-label="Gast">
          {auswahl === null && <p className="leer">Wählen Sie links einen Gast aus oder erfassen Sie einen neuen.</p>}
          {auswahl !== null && (
            <GastFormular
              key={auswahl === "neu" ? "neu" : auswahl.id}
              gast={auswahl === "neu" ? null : auswahl}
              frischGespeichert={auswahl !== "neu" && gespeichertId === auswahl.id}
              onGespeichert={(g) => { setAuswahl(g); setGespeichertId(g.id); laden(); }}
              onAbbrechen={() => waehle(null)}
            />
          )}
        </section>
      </div>
    </div>
  );
}

function GastFormular({ gast, frischGespeichert = false, onGespeichert, onAbbrechen }) {
  const [werte, setWerte] = useState(() => ({ ...LEER, ...Object.fromEntries(Object.entries(gast || {}).map(([k, v]) => [k, v ?? ""])) }));
  const [fehler, setFehler] = useState(null);
  const [gespeichert, setGespeichert] = useState(frischGespeichert);
  const setze = (feld) => (e) => { setWerte({ ...werte, [feld]: e.target.value }); setGespeichert(false); };

  const speichern = async (e) => {
    e.preventDefault();
    setFehler(null);
    const daten = Object.fromEntries(Object.keys(LEER).map((k) => [k, werte[k] === "" ? null : werte[k]]));
    daten.vorname = werte.vorname.trim();
    daten.nachname = werte.nachname.trim();
    try {
      const g = gast ? await api.put(`/gaeste/${gast.id}`, daten) : await api.post("/gaeste", daten);
      setGespeichert(true);
      onGespeichert(g);
    } catch (err) { setFehler(err.message); }
  };

  const feld = (name, text, props = {}) => (
    <label className={props.breit ? "breit" : undefined}>{text}
      <input value={werte[name]} onChange={setze(name)} autoComplete="off" {...{ ...props, breit: undefined }} />
    </label>
  );

  return (
    <form className="formular" onSubmit={speichern}>
      <h2>{gast ? `${gast.vorname} ${gast.nachname}` : "Gast erfassen"}</h2>
      {gast?.geburtsdatum && <p className="hinweis">Geboren am {datumVoll(gast.geburtsdatum)}</p>}
      <div className="felder">
        {feld("vorname", "Vorname", { required: true })}
        {feld("nachname", "Nachname", { required: true })}
        {feld("strasse", "Strasse", { breit: true })}
        {feld("plz", "PLZ")}
        {feld("ort", "Ort")}
        {feld("land", "Land")}
        {feld("nationalitaet", "Nationalität")}
        {feld("geburtsdatum", "Geburtsdatum", { type: "date" })}
        {feld("telefon", "Telefon")}
        {feld("email", "E-Mail", { type: "email", breit: true })}
      </div>
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
      {gespeichert && <p className="meldung ok" role="status">Gespeichert.</p>}
      <div className="aktionen">
        <button className="knopf haupt" type="submit">{gast ? "Änderungen speichern" : "Gast speichern"}</button>
        <button className="knopf leise" type="button" onClick={onAbbrechen}>Schliessen</button>
      </div>
    </form>
  );
}
