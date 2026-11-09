// Modul «Artikel & Preise»: Saisons je Jahr und Preise zentral pflegen.
// Saisonale Artikel je Vor-, Haupt- und Nachsaison; ganzjährige gelten für alle Jahre.
import { useCallback, useEffect, useMemo, useState } from "react";
import { CopyPlus, Save } from "lucide-react";
import { api } from "../api.js";

const SAISONS = [
  { typ: "vorsaison", name: "Vorsaison" },
  { typ: "hauptsaison", name: "Hauptsaison" },
  { typ: "nachsaison", name: "Nachsaison" },
];
const betragText = (x) => (x === null || x === undefined || x === "" ? "" : Number(x).toFixed(2));

export default function ArtikelPreise() {
  const [jahr, setJahr] = useState(null);
  const [liste, setListe] = useState(null);
  const [entwurf, setEntwurf] = useState({ saisons: {}, preise: {} });
  const [fehler, setFehler] = useState(null);
  const [meldung, setMeldung] = useState(null);
  const [laeuft, setLaeuft] = useState(false);

  const laden = useCallback(async (j) => {
    setFehler(null);
    try {
      let ziel = j;
      if (!ziel) {
        const jahre = await api.get("/preise/jahre");
        // nach der Saison (ab Oktober) gleich das nächste Jahr zeigen
        const heute = new Date();
        const wunsch = heute.getMonth() >= 9 ? heute.getFullYear() + 1 : heute.getFullYear();
        ziel = jahre.includes(wunsch) ? wunsch : jahre[jahre.length - 1] ?? wunsch;
      }
      const d = await api.get(`/preise/${ziel}`);
      setJahr(ziel); setListe(d); setEntwurf({ saisons: {}, preise: {} });
    } catch (e) { setFehler(e.message); }
  }, []);
  useEffect(() => { laden(null); }, [laden]);

  const geaendert = Object.keys(entwurf.saisons).length + Object.keys(entwurf.preise).length;

  useEffect(() => {
    const warnen = (e) => { if (geaendert) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warnen);
    return () => window.removeEventListener("beforeunload", warnen);
  }, [geaendert]);

  const saisonWert = (s, feld) => entwurf.saisons[s.typ]?.[feld] ?? s[feld];
  const preisWert = (a, saison) => entwurf.preise[`${a.id}|${saison}`] ?? betragText(a.preise[saison]);
  const setzeSaison = (s, feld, wert) => setEntwurf((x) => ({
    ...x, saisons: { ...x.saisons, [s.typ]: { gueltig_ab: saisonWert(s, "gueltig_ab"), gueltig_bis: saisonWert(s, "gueltig_bis"), [feld]: wert } },
  }));
  const setzePreis = (a, saison, wert) => setEntwurf((x) => {
    const schluessel = `${a.id}|${saison}`;
    const preise = { ...x.preise };
    if (wert === betragText(a.preise[saison])) delete preise[schluessel]; else preise[schluessel] = wert;
    return { ...x, preise };
  });

  const speichern = async () => {
    setFehler(null); setMeldung(null);
    const preise = [];
    for (const [schluessel, wert] of Object.entries(entwurf.preise)) {
      const [artikel_id, saison] = schluessel.split("|");
      const zahl = Number(String(wert).replace(",", "."));
      if (wert === "" || Number.isNaN(zahl) || zahl < 0) { setFehler("Bitte nur Beträge ab 0 eingeben (z.B. 7.50)."); return; }
      preise.push({ artikel_id, saison, preis: zahl.toFixed(2) });
    }
    const saisons = Object.entries(entwurf.saisons).map(([typ, w]) => ({ typ, ...w }));
    setLaeuft(true);
    try {
      const d = await api.put(`/preise/${jahr}`, { saisons, preise });
      setListe(d); setEntwurf({ saisons: {}, preise: {} });
      setMeldung(`Gespeichert: ${geaendert} ${geaendert === 1 ? "Änderung" : "Änderungen"} für ${jahr}.`);
    } catch (e) { setFehler(e.message); } finally { setLaeuft(false); }
  };

  const naechstesJahr = liste ? Math.max(...liste.jahre, jahr) + 1 : null;
  const uebernehmen = async () => {
    setFehler(null); setMeldung(null); setLaeuft(true);
    try {
      const d = await api.post(`/preise/${naechstesJahr}/uebernehmen`, { von_jahr: naechstesJahr - 1 });
      setJahr(naechstesJahr); setListe(d); setEntwurf({ saisons: {}, preise: {} });
      setMeldung(`${naechstesJahr} aus ${naechstesJahr - 1} übernommen. Jetzt Daten und Preise anpassen und speichern.`);
    } catch (e) { setFehler(e.message); } finally { setLaeuft(false); }
  };

  const wechseln = (j) => {
    if (geaendert && !window.confirm("Ungespeicherte Änderungen verwerfen?")) return; // eslint-disable-line no-alert
    laden(j);
  };

  const saisonal = useMemo(() => (liste?.artikel || []).filter((a) => a.saisonal), [liste]);
  const ganzjaehrig = useMemo(() => (liste?.artikel || []).filter((a) => !a.saisonal), [liste]);

  return (
    <div className="seite preise-seite">
      <header className="kopf">
        <h1>Artikel &amp; Preise</h1>
        <div className="aktionen">
          {liste && <button className="knopf neben" disabled={laeuft} onClick={uebernehmen}>
            <CopyPlus size={18} aria-hidden="true" />{naechstesJahr} aus {naechstesJahr - 1} übernehmen</button>}
        </div>
      </header>

      {liste && (
        <div className="ablagen" role="tablist" aria-label="Jahr">
          {liste.jahre.map((j) => (
            <button key={j} role="tab" aria-selected={j === jahr} onClick={() => wechseln(j)}>{j}</button>
          ))}
        </div>
      )}
      {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
      {meldung && <p className="meldung ok" role="status">{meldung}</p>}
      {!liste && !fehler && <p className="leer">Wird geladen …</p>}

      {liste && liste.saisons.length === 0 && (
        <p className="leer">Für {jahr} sind keine Saisons erfasst. Mit «{naechstesJahr} aus {naechstesJahr - 1} übernehmen» anlegen.</p>
      )}

      {liste && liste.saisons.length > 0 && (
        <>
          <section className="karte preise-karte">
            <h2>Saisons {jahr}</h2>
            <p className="hinweis">Ausserhalb der Saisons ist der Platz geschlossen; saisonale Artikel haben dann keinen Preis.</p>
            <div className="saison-raster">
              {liste.saisons.map((s) => (
                <fieldset key={s.typ} className={entwurf.saisons[s.typ] ? "geaendert" : ""}>
                  <legend>{SAISONS.find((x) => x.typ === s.typ)?.name ?? s.bezeichnung}</legend>
                  <label>Von<input type="date" min={`${jahr}-01-01`} max={`${jahr}-12-31`} value={saisonWert(s, "gueltig_ab")}
                    onChange={(e) => setzeSaison(s, "gueltig_ab", e.target.value)} /></label>
                  <label>Bis<input type="date" min={`${jahr}-01-01`} max={`${jahr}-12-31`} value={saisonWert(s, "gueltig_bis")}
                    onChange={(e) => setzeSaison(s, "gueltig_bis", e.target.value)} /></label>
                </fieldset>
              ))}
            </div>
          </section>

          <section className="karte preise-karte">
            <h2>Preise je Saison {jahr}</h2>
            <p className="hinweis">Endpreise in CHF inkl. MWST. Gelten nur für {jahr}.</p>
            <div className="tabelle-rahmen">
              <table className="preistabelle">
                <thead><tr><th>Artikel</th><th>Einheit</th>{SAISONS.map((s) => <th key={s.typ} className="zahl">{s.name}</th>)}<th className="zahl">MWST</th></tr></thead>
                <tbody>
                  {saisonal.map((a) => (
                    <tr key={a.id}>
                      <th scope="row">{a.bezeichnung}</th>
                      <td className="leise">{a.einheit}</td>
                      {SAISONS.map((s) => (
                        <td key={s.typ} className="zahl">
                          <PreisFeld wert={preisWert(a, s.typ)} geaendert={`${a.id}|${s.typ}` in entwurf.preise}
                            label={`${a.bezeichnung} ${s.name}`} onChange={(w) => setzePreis(a, s.typ, w)} />
                        </td>
                      ))}
                      <td className="zahl leise">{a.mwst_prozent ?? "–"} %</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="karte preise-karte">
            <h2>Ganzjährige Preise</h2>
            <p className="hinweis">Gelten für alle Jahre. Wassertankfüllung nur bei 1 Übernachtung, ab 2 Nächten inbegriffen.
              Zwärgli und Spycher pro Nacht für 2 Personen, weitere Personen zum Personenpreis.</p>
            <div className="tabelle-rahmen">
              <table className="preistabelle">
                <thead><tr><th>Artikel</th><th>Einheit</th><th className="zahl">Preis</th><th className="zahl">MWST</th></tr></thead>
                <tbody>
                  {ganzjaehrig.map((a) => (
                    <tr key={a.id}>
                      <th scope="row">{a.bezeichnung}</th>
                      <td className="leise">{a.einheit}</td>
                      <td className="zahl"><PreisFeld wert={preisWert(a, "ganzjaehrig")} geaendert={`${a.id}|ganzjaehrig` in entwurf.preise}
                        label={a.bezeichnung} onChange={(w) => setzePreis(a, "ganzjaehrig", w)} /></td>
                      <td className="zahl leise">{a.mwst_prozent ?? "–"} %</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="hinweis klein">Kurtaxe (CHF 3.50, Erwachsene) und Beherbergungsabgabe (CHF 1.00) sind Abgaben und
              werden separat berechnet. MWST-Sätze unter Einstellungen.</p>
          </section>

          <div className={`speicherleiste${geaendert ? " aktiv" : ""}`}>
            <span>{geaendert ? `${geaendert} ungespeicherte ${geaendert === 1 ? "Änderung" : "Änderungen"}` : "Keine Änderungen"}</span>
            {geaendert > 0 && <button className="knopf leise" onClick={() => setEntwurf({ saisons: {}, preise: {} })}>Verwerfen</button>}
            <button className="knopf haupt" disabled={!geaendert || laeuft} onClick={speichern}><Save size={18} aria-hidden="true" />Speichern</button>
          </div>
        </>
      )}
    </div>
  );
}

function PreisFeld({ wert, geaendert, label, onChange }) {
  return (
    <input className={`preisfeld${geaendert ? " geaendert" : ""}`} inputMode="decimal" aria-label={label} value={wert}
      onChange={(e) => onChange(e.target.value.replace(/[^0-9.,]/g, ""))}
      onBlur={(e) => { const z = Number(e.target.value.replace(",", ".")); if (e.target.value !== "" && !Number.isNaN(z)) onChange(z.toFixed(2)); }} />
  );
}
