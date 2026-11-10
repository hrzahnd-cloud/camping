// Modul «Gästekarte»: Zugang zum feratel Web Client von Thun-Thunersee Tourismus.
// Dort erfasst die Betreiberin von Hand den Meldeschein; daraus entstehen die
// PanoramaCard und die Abrechnung der Kur- und Beherbergungstaxe.
// Der Web Client lässt sich nicht in andere Seiten einbetten (frame-ancestors 'none'),
// deshalb öffnet er sich in einem eigenen Fenster. Zugangsdaten laufen nie durch dieses Tool.
import { ExternalLink, FileText } from "lucide-react";

const WEBCLIENT = "https://webclient4.deskline.net/GRI/de/Login";
const ANLEITUNG = "https://www.thunersee.ch/fileadmin/pdf/ttst/gastgeber/anleitung-webclient-vollmitglied-hotel-gruppe-camping.pdf";

export default function Gaestekarte() {
  const oeffnen = () => {
    const w = window.open(WEBCLIENT, "feratel-webclient");
    if (w) w.focus(); else window.location.href = WEBCLIENT; // Popup blockiert: im selben Fenster
  };
  return (
    <div className="seite schmal gaestekarte">
      <header className="kopf"><h1>Gästekarte</h1></header>
      <section className="karte zugang-karte">
        <h2>Web Client Thunersee Tourismus</h2>
        <p>Meldeschein und PanoramaCard erfassen Sie im Web Client von Thun-Thunersee Tourismus (feratel). Aus den Meldescheinen
          entsteht die Abrechnung der Kur- und Beherbergungstaxe, die periodisch als Rechnung an den Camping geht.</p>
        <div className="aktionen">
          <button className="knopf haupt gross" onClick={oeffnen}><ExternalLink size={20} aria-hidden="true" />Web Client öffnen (Anmeldung)</button>
          <a className="knopf neben" href={ANLEITUNG} target="_blank" rel="noreferrer"><FileText size={18} aria-hidden="true" />Anleitung (PDF)</a>
        </div>
        <p className="hinweis">Der Web Client öffnet sich in einem eigenen Fenster; in dieses Tool lässt er sich aus Sicherheitsgründen nicht einbetten.
          Benutzername und Passwort stehen im Zugangsdokument von Thun-Thunersee Tourismus – Ihr Browser kann sie für das nächste Mal speichern.
          Die Zugangsdaten werden nicht in diesem Tool gespeichert.</p>
        <dl className="angaben">
          <dt>Adresse</dt><dd><a href={WEBCLIENT} target="_blank" rel="noreferrer">webclient4.deskline.net/GRI/de/Login</a></dd>
          <dt>Fragen, Stornos</dt><dd>Thun-Thunersee Tourismus, <a href="mailto:fewo@thunersee.ch">fewo@thunersee.ch</a>, <a href="tel:+41332259010">033 225 90 10</a></dd>
          <dt>Kontrolle</dt><dd>Übernachtungen und Taxen pro Monat unter <a href="#/auswertungen">Auswertungen › Übernachtungen &amp; Taxen</a></dd>
        </dl>
      </section>
    </div>
  );
}
