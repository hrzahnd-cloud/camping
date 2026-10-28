import { useCallback, useEffect, useState } from "react";
import {
  BarChart3, BedDouble, CalendarRange, FileText, Inbox, Map, Package, Send, Settings, Sun, Users,
} from "lucide-react";
import { api } from "./api.js";
import Heute from "./seiten/Heute.jsx";
import Reservationen from "./seiten/Reservationen.jsx";
import Belegung from "./seiten/Belegung.jsx";
import Gaeste from "./seiten/Gaeste.jsx";
import Einstellungen from "./seiten/Einstellungen.jsx";
import Modulseite from "./seiten/Modulseite.jsx";

// Reihenfolge = Reihenfolge im Menü. Module, die unter Einstellungen
// ausgeschaltet sind, erscheinen nicht.
const SEITEN = [
  { code: "heute", pfad: "heute", name: "Heute", icon: Sun, Komponente: Heute },
  { code: "reservationen", pfad: "reservationen", name: "Reservationen", icon: Inbox, Komponente: Reservationen },
  { code: "belegung", pfad: "belegung", name: "Belegung", icon: CalendarRange, Komponente: Belegung },
  { code: "gaeste", pfad: "gaeste", name: "Gäste", icon: Users, Komponente: Gaeste },
  { code: "buchungen", pfad: "buchungen", name: "Buchungen", icon: BedDouble },
  { code: "artikel", pfad: "artikel", name: "Artikel & Preise", icon: Package },
  { code: "rechnungen", pfad: "rechnungen", name: "Rechnungen", icon: FileText },
  { code: "auswertungen", pfad: "auswertungen", name: "Auswertungen", icon: BarChart3 },
  { code: "hesta", pfad: "hesta", name: "HESTA", icon: Send },
  { code: "feratel", pfad: "feratel", name: "Feratel", icon: Map },
];

const aktuellerPfad = () => window.location.hash.replace(/^#\/?/, "").split("?")[0] || "heute";

export default function App() {
  const [pfad, setPfad] = useState(aktuellerPfad());
  const [module, setModule] = useState(null);
  const [fehler, setFehler] = useState(null);

  useEffect(() => {
    const weiter = () => setPfad(aktuellerPfad());
    window.addEventListener("hashchange", weiter);
    return () => window.removeEventListener("hashchange", weiter);
  }, []);

  const moduleLaden = useCallback(() => {
    api.get("/einstellungen/module").then(setModule).catch((e) => setFehler(e.message));
  }, []);
  useEffect(moduleLaden, [moduleLaden]);

  // "Heute" ist eine reine Übersicht der Oberfläche und immer eingeschaltet
  const aktiv = (code) => code === "heute" || module?.find((m) => m.code === code)?.aktiv;
  const sichtbar = SEITEN.filter((s) => aktiv(s.code));
  const seite = pfad === "einstellungen" ? null : SEITEN.find((s) => s.pfad === pfad);
  const modulInfo = module?.find((m) => m.code === seite?.code);

  let inhalt;
  if (fehler) inhalt = <p className="meldung fehler">Die Anwendung ist nicht erreichbar: {fehler}</p>;
  else if (!module) inhalt = <p className="leer">Wird geladen …</p>;
  else if (pfad === "einstellungen") inhalt = <Einstellungen module={module} onGeaendert={setModule} />;
  else if (!seite) inhalt = <p className="leer">Diese Seite gibt es nicht. <a href="#/heute">Zur Übersicht «Heute»</a></p>;
  else if (!aktiv(seite.code)) {
    inhalt = (
      <p className="leer">
        Das Modul «{seite.name}» ist ausgeschaltet. Unter <a href="#/einstellungen">Einstellungen</a> lässt es sich einschalten.
      </p>
    );
  } else if (seite.Komponente) inhalt = <seite.Komponente />;
  else inhalt = <Modulseite modul={modulInfo} />;

  return (
    <div className="rahmen">
      <nav className="menue" aria-label="Hauptmenü">
        <a className="marke" href="#/heute">
          <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 4 3 28h26z" /><path className="tuer" d="M16 14l-5 14h10z" /></svg>
          <span>Camping Aeschi<small>Verwaltung</small></span>
        </a>
        <ul>
          {sichtbar.map(({ pfad: p, name, icon: Icon }) => (
            <li key={p}>
              <a href={`#/${p}`} aria-current={pfad === p ? "page" : undefined}><Icon size={18} aria-hidden="true" />{name}</a>
            </li>
          ))}
        </ul>
        <a className="einstellungen-link" href="#/einstellungen" aria-current={pfad === "einstellungen" ? "page" : undefined}>
          <Settings size={18} aria-hidden="true" />Einstellungen
        </a>
      </nav>
      <main className="inhalt">{inhalt}</main>
    </div>
  );
}
