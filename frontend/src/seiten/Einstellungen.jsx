import { useState } from "react";
import { api } from "../api.js";

export default function Einstellungen({ module, onGeaendert }) {
  const [fehler, setFehler] = useState(null);
  const [laeuft, setLaeuft] = useState(null);

  const schalten = async (code, aktiv) => {
    setLaeuft(code); setFehler(null);
    try { onGeaendert(await api.put(`/einstellungen/module/${code}`, { aktiv })); }
    catch (e) { setFehler(e.message); } finally { setLaeuft(null); }
  };

  const fest = module.filter((m) => !m.umschaltbar);
  const wahl = module.filter((m) => m.umschaltbar);

  return (
    <div className="seite schmal">
      <header className="kopf"><h1>Einstellungen</h1></header>
      <section>
        <h2>Module im Menü</h2>
        <p className="hinweis">
          Ausgeschaltete Module sind fertig eingerichtet, ihre Daten bleiben erhalten. Sie erscheinen nur nicht im Menü.
          Einschalten wirkt sofort, ohne neues Deployment.
        </p>
        {fehler && <p className="meldung fehler" role="alert">{fehler}</p>}
        <ul className="schalterliste">
          {wahl.map((m) => (
            <li key={m.code}>
              <label>
                <span className="text"><strong>{m.bezeichnung}</strong><span>{m.beschreibung}</span></span>
                <input type="checkbox" role="switch" className="schalter" checked={m.aktiv} disabled={laeuft === m.code}
                  onChange={(e) => schalten(m.code, e.target.checked)} />
              </label>
            </li>
          ))}
        </ul>
        <p className="hinweis">Immer eingeschaltet: {fest.map((m) => m.bezeichnung).join(", ")}.</p>
      </section>
    </div>
  );
}
