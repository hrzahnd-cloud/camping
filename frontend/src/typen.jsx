import { Bus, Caravan, House, Tent, Warehouse } from "lucide-react";

// Jeder Stellplatz-Typ hat eine eigene Farbe und ein Symbol. Die Farbe steht
// in der Belegung für den Typ, die Füllung für den Status (voll = akzeptiert,
// schraffiert = offene Anfrage).
export const TYP_STIL = {
  zeltwiese: { name: "Zelt", farbe: "#3f7a32", Icon: Tent },
  wohnwagen: { name: "Wohnwagen", farbe: "#1f6283", Icon: Caravan },
  camper: { name: "Camper", farbe: "#b04a2c", Icon: Bus },
  zwaergli: { name: "Zwärgli", farbe: "#8a5a1f", Icon: House },
  spycher: { name: "Spycher", farbe: "#5a5878", Icon: Warehouse },
};
const OHNE = { name: "ohne Typ", farbe: "#8a918a", Icon: null };

export const typStil = (code) => TYP_STIL[code] ?? OHNE;

export function TypMarke({ code, groesse = 16, nurSymbol = false }) {
  const { name, farbe, Icon } = typStil(code);
  return (
    <span className="typ-marke" style={{ "--typ": farbe }}>
      {Icon ? <Icon size={groesse} aria-hidden="true" /> : <span className="typ-punkt" aria-hidden="true" />}
      <span className={nurSymbol ? "sr-only" : "typ-name"}>{name}</span>
    </span>
  );
}

// Schlichte Silhouette mit Niesen (Pyramide) und Thunersee – das Bild vom Platz aus.
export function Panorama({ className }) {
  return (
    <svg className={className} viewBox="0 0 1200 220" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
      <path className="p-fern" d="M0 150 L90 118 L170 132 L260 96 L330 120 L420 88 L500 112 L560 100 L640 128 L720 104 L800 124 L880 92 L960 116 L1040 98 L1120 120 L1200 106 L1200 220 L0 220Z" />
      <path className="p-mitte" d="M0 172 L120 160 L210 166 L300 152 L380 162 L470 150 L560 160 L650 144 L725 152 L835 66 L855 60 L875 68 L975 150 L1050 140 L1130 156 L1200 148 L1200 220 L0 220Z" />
      <path className="p-see" d="M0 182 C200 176 400 186 600 180 C800 174 1000 184 1200 178 L1200 220 L0 220Z" />
      <path className="p-welle" d="M120 196 h70 M300 204 h110 M560 194 h60 M760 202 h120 M1000 196 h80" />
    </svg>
  );
}
