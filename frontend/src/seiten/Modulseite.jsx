// Platzhalter für Module, die im Backend fertig sind, deren Bedienoberfläche
// aber erst in einer späteren Phase gebaut wird.
const API_BEREICH = {
  buchungen: "Buchungen", artikel: "Artikel & Preise", rechnungen: "Rechnungen",
  auswertungen: "Auswertungen", hesta: "HESTA", feratel: "Feratel",
};

export default function Modulseite({ modul }) {
  const bereich = API_BEREICH[modul?.code];
  return (
    <div className="seite schmal">
      <header className="kopf"><h1>{modul?.bezeichnung}</h1></header>
      <p>{modul?.beschreibung}.</p>
      <p className="hinweis">
        Die Funktionen dieses Moduls sind in der Anwendung vorhanden. Eine eigene Bedienoberfläche dafür folgt in einer späteren Phase.
        Bis dahin lassen sie sich über die <a href={`/docs#/${encodeURIComponent(bereich ?? "")}`}>technische Schnittstelle</a> nutzen.
      </p>
    </div>
  );
}
