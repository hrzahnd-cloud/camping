import React, { useState } from "react";
import {
  LayoutDashboard,
  Mail,
  CalendarRange,
  Users,
  FileText,
  BarChart3,
  Settings,
  Search,
  Bell,
  ChevronDown,
  Tent,
  Caravan,
  Home,
  Plus,
  ArrowUpRight,
  ArrowDownRight,
  CheckCircle2,
  Clock,
  CircleDot,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from "recharts";

/* ---------------------------------------------------------------------
   DESIGN TOKENS
   Alpine-Seeufer-Palette statt Standard-Cream/Terracotta:
   Tanne (dunkel), Moos (Primärakzent), See (Sekundärakzent),
   warmer Sand als Seitenhintergrund, Bernstein für Status-Hinweise.
------------------------------------------------------------------------ */
const C = {
  pine: "#1F2D24",
  pineSoft: "#2B3D30",
  moss: "#3A6B4C",
  mossSoft: "#E7EFE7",
  lake: "#3D6E82",
  lakeSoft: "#E5EFF2",
  amber: "#B9873A",
  amberSoft: "#F5EBD8",
  danger: "#AD4A3B",
  dangerSoft: "#F5E5E1",
  sand: "#F3EFE5",
  paper: "#FFFFFF",
  ink: "#242820",
  inkSoft: "#767C70",
  line: "#E3DECF",
  lineOnPaper: "#E7E4DA",
};

const FONTS = `
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&display=swap');
`;

/* ---------------------------------------------------------------------
   DEMO-DATEN (statisch, nur zur Illustration)
------------------------------------------------------------------------ */
const reservationsanfragen = [
  { id: 1, gast: "Family Verhoeven", land: "NL", quelle: "E-Mail", zeitraum: "12.–19. Jul 2026", typ: "Wohnwagen", personen: 4, status: "geprüft", sprache: "FR" },
  { id: 2, gast: "Sophie Bernard", land: "FR", quelle: "E-Mail", zeitraum: "03.–07. Aug 2026", typ: "Zelt", personen: 2, status: "erstantwort gesendet", sprache: "FR" },
  { id: 3, gast: "Marco Rossi", land: "IT", quelle: "Homepage", zeitraum: "20.–25. Aug 2026", typ: "Camper", personen: 3, status: "zahlung ausstehend", sprache: "IT" },
  { id: 4, gast: "Hans Zbinden", land: "CH", quelle: "E-Mail", zeitraum: "15.–18. Aug 2026", typ: "Zwärgli", personen: 2, status: "unvollständig", sprache: "DE" },
  { id: 5, gast: "Emma Clarke", land: "GB", quelle: "Homepage", zeitraum: "01.–06. Sep 2026", typ: "Wohnwagen", personen: 2, status: "akzeptiert", sprache: "EN" },
];

const statusStyles = {
  "geprüft": { bg: C.lakeSoft, fg: C.lake, icon: CircleDot },
  "erstantwort gesendet": { bg: C.amberSoft, fg: C.amber, icon: Clock },
  "zahlung ausstehend": { bg: C.amberSoft, fg: C.amber, icon: Clock },
  "unvollständig": { bg: C.dangerSoft, fg: C.danger, icon: Clock },
  "akzeptiert": { bg: C.mossSoft, fg: C.moss, icon: CheckCircle2 },
};

const stellplaetze = [
  { name: "A1 · Zelt", typ: "zelt", belegung: [0, 1, 1, 1, 0, 0, 1] },
  { name: "A2 · Zelt", typ: "zelt", belegung: [1, 1, 0, 0, 0, 1, 1] },
  { name: "B1 · Camper", typ: "camper", belegung: [1, 1, 1, 1, 1, 0, 0] },
  { name: "B2 · Camper", typ: "camper", belegung: [0, 0, 1, 1, 1, 1, 1] },
  { name: "C1 · Wohnwagen", typ: "wohnwagen", belegung: [1, 1, 1, 0, 0, 0, 1] },
  { name: "Zwärgli", typ: "huette", belegung: [1, 1, 1, 1, 1, 1, 0] },
  { name: "Spycher", typ: "huette", belegung: [0, 0, 0, 1, 1, 1, 1] },
];
const wochentage = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const typIcon = { zelt: Tent, camper: Caravan, wohnwagen: Caravan, huette: Home };

const gaeste = [
  { name: "Verhoeven, Familie", land: "NL", besuche: 3, letzterAufenthalt: "Aug 2025" },
  { name: "Bernard, Sophie", land: "FR", besuche: 1, letzterAufenthalt: "—" },
  { name: "Rossi, Marco", land: "IT", besuche: 2, letzterAufenthalt: "Jul 2024" },
  { name: "Zbinden, Hans", land: "CH", besuche: 6, letzterAufenthalt: "Aug 2025" },
  { name: "Clarke, Emma", land: "GB", besuche: 1, letzterAufenthalt: "—" },
  { name: "Meier, Ursula", land: "CH", besuche: 4, letzterAufenthalt: "Sep 2025" },
];

const rechnungen = [
  { nummer: "2026-1042", kunde: "Zbinden, Hans", datum: "18.08.2026", betrag: 214.50, zahlungsart: "TWINT", status: "bezahlt" },
  { nummer: "2026-1041", kunde: "Meier, Ursula", datum: "17.08.2026", betrag: 156.00, zahlungsart: "Bar", status: "bezahlt" },
  { nummer: "2026-1040", kunde: "Rossi, Marco", datum: "15.08.2026", betrag: 342.80, zahlungsart: "Banküberweisung", status: "offen" },
  { nummer: "2026-1039", kunde: "Dubois, Claire", datum: "12.08.2026", betrag: 189.20, zahlungsart: "Kreditkarte", status: "bezahlt" },
  { nummer: "2026-1038", kunde: "Weber, Peter", datum: "10.08.2026", betrag: 98.00, zahlungsart: "TWINT", status: "bezahlt" },
];

const umsatzProMonat = [
  { monat: "Mai", umsatz: 8200 },
  { monat: "Jun", umsatz: 15400 },
  { monat: "Jul", umsatz: 27100 },
  { monat: "Aug", umsatz: 31850 },
  { monat: "Sep", umsatz: 12300 },
];

const zahlungsmethoden = [
  { name: "TWINT", value: 42, color: C.moss },
  { name: "Bar", value: 26, color: C.lake },
  { name: "Banküberweisung", value: 20, color: C.amber },
  { name: "Kreditkarte", value: 12, color: C.pineSoft },
];

const umsatzNachArtikel = [
  { artikel: "Übernachtung Personen", umsatz: 41200 },
  { artikel: "Stellplatzmiete", umsatz: 33900 },
  { artikel: "Kurtaxe", umsatz: 6100 },
  { artikel: "Strom", umsatz: 4200 },
  { artikel: "Zwärgli/Spycher", umsatz: 9350 },
];

/* ---------------------------------------------------------------------
   KLEINE BAUSTEINE
------------------------------------------------------------------------ */
function Sidebar({ active, onSelect }) {
  const items = [
    { key: "dashboard", label: "Übersicht", icon: LayoutDashboard },
    { key: "anfragen", label: "Reservationsanfragen", icon: Mail, badge: 3 },
    { key: "belegung", label: "Belegungsplan", icon: CalendarRange },
    { key: "gaeste", label: "Gäste", icon: Users },
    { key: "rechnungen", label: "Rechnungen", icon: FileText },
    { key: "auswertungen", label: "Auswertungen", icon: BarChart3 },
  ];
  return (
    <div
      className="h-full flex flex-col justify-between"
      style={{ background: C.pine, width: "248px", flexShrink: 0 }}
    >
      <div>
        <div className="px-5 py-6 relative overflow-hidden" style={{ borderBottom: `1px solid ${C.pineSoft}` }}>
          {/* Signature: leises Konturlinien-Motiv, angelehnt an die Berge am Thunersee */}
          <svg
            viewBox="0 0 240 60"
            className="absolute left-0 bottom-0 w-full opacity-[0.12]"
            style={{ height: "40px" }}
            preserveAspectRatio="none"
          >
            <path d="M0 45 Q 30 20 55 38 T 110 30 T 165 42 T 240 25 L240 60 L0 60 Z" fill="#EFE6C8" />
            <path d="M0 52 Q 40 35 80 48 T 160 40 T 240 45 L240 60 L0 60 Z" fill="#DCE7DE" opacity="0.6" />
          </svg>
          <div className="relative flex items-center gap-2">
            <div
              className="flex items-center justify-center rounded-md"
              style={{ width: 30, height: 30, background: C.moss }}
            >
              <Tent size={16} color="#F3EFE5" />
            </div>
            <div>
              <div style={{ fontFamily: "Fraunces, serif", color: "#F3EFE5", fontSize: "16.5px", fontWeight: 600, lineHeight: 1.1 }}>
                Camping Aeschi
              </div>
              <div style={{ color: "#9FAB9E", fontSize: "10.5px", letterSpacing: "0.04em" }}>VERWALTUNG</div>
            </div>
          </div>
        </div>

        <nav className="px-3 py-4 space-y-1">
          {items.map((item) => {
            const Icon = item.icon;
            const isActive = active === item.key;
            return (
              <button
                key={item.key}
                onClick={() => onSelect(item.key)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors"
                style={{
                  background: isActive ? C.moss : "transparent",
                  color: isActive ? "#F3EFE5" : "#B7C0B6",
                  fontWeight: isActive ? 600 : 500,
                }}
              >
                <Icon size={16} />
                <span className="flex-1 text-left">{item.label}</span>
                {item.badge && (
                  <span
                    className="text-xs px-1.5 py-0.5 rounded-full"
                    style={{ background: isActive ? "rgba(255,255,255,0.2)" : C.amber, color: "#fff", fontSize: "10.5px" }}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="px-3 pb-4">
        <button
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm"
          style={{ color: "#B7C0B6" }}
        >
          <Settings size={16} />
          <span>Einstellungen</span>
        </button>
        <div
          className="mt-3 mx-1 px-3 py-2.5 rounded-lg flex items-center gap-2.5"
          style={{ background: C.pineSoft }}
        >
          <div
            className="rounded-full flex items-center justify-center flex-shrink-0"
            style={{ width: 28, height: 28, background: C.lake, color: "#fff", fontSize: "12px", fontWeight: 600 }}
          >
            RM
          </div>
          <div className="min-w-0">
            <div style={{ color: "#F3EFE5", fontSize: "12.5px", fontWeight: 600 }}>R. Mattli</div>
            <div style={{ color: "#8E9A8D", fontSize: "11px" }}>Rezeption</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Topbar({ title }) {
  return (
    <div
      className="flex items-center justify-between px-8 py-4"
      style={{ background: C.paper, borderBottom: `1px solid ${C.lineOnPaper}` }}
    >
      <div>
        <div style={{ fontFamily: "Fraunces, serif", fontSize: "20px", fontWeight: 600, color: C.ink }}>
          {title}
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
          style={{ background: C.sand, border: `1px solid ${C.line}`, width: "260px" }}
        >
          <Search size={14} color={C.inkSoft} />
          <input
            placeholder="Suchen…"
            disabled
            className="bg-transparent outline-none text-sm w-full"
            style={{ color: C.inkSoft }}
          />
        </div>
        <button className="relative" style={{ color: C.inkSoft }}>
          <Bell size={18} />
          <span
            className="absolute -top-1 -right-1 rounded-full"
            style={{ width: 7, height: 7, background: C.danger }}
          />
        </button>
      </div>
    </div>
  );
}

function StatCard({ label, value, delta, positive, icon: Icon, accent }) {
  return (
    <div
      className="rounded-xl p-5 flex-1"
      style={{ background: C.paper, border: `1px solid ${C.lineOnPaper}` }}
    >
      <div className="flex items-center justify-between mb-3">
        <span style={{ color: C.inkSoft, fontSize: "12.5px", fontWeight: 500 }}>{label}</span>
        <div
          className="rounded-md flex items-center justify-center"
          style={{ width: 26, height: 26, background: accent + "22" }}
        >
          <Icon size={13} color={accent} />
        </div>
      </div>
      <div style={{ fontFamily: "Fraunces, serif", fontSize: "26px", fontWeight: 600, color: C.ink }}>
        {value}
      </div>
      {delta && (
        <div className="flex items-center gap-1 mt-1.5" style={{ fontSize: "12px", color: positive ? C.moss : C.danger }}>
          {positive ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
          {delta}
        </div>
      )}
    </div>
  );
}

function Badge({ children, bg, fg }) {
  return (
    <span
      className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium"
      style={{ background: bg, color: fg }}
    >
      {children}
    </span>
  );
}

/* ---------------------------------------------------------------------
   SEITEN
------------------------------------------------------------------------ */
function DashboardView() {
  return (
    <div className="space-y-6">
      <div className="flex gap-4">
        <StatCard label="Heutige Anreisen" value="6" delta="+2 ggü. gestern" positive icon={ArrowDownRight} accent={C.moss} />
        <StatCard label="Heutige Abreisen" value="4" icon={ArrowUpRight} accent={C.lake} />
        <StatCard label="Offene Anfragen" value="3" delta="1 unvollständig" positive={false} icon={Mail} accent={C.amber} />
        <StatCard label="Belegung diese Woche" value="78%" delta="+6% ggü. Vorwoche" positive icon={CalendarRange} accent={C.pineSoft} />
      </div>

      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2 rounded-xl p-5" style={{ background: C.paper, border: `1px solid ${C.lineOnPaper}` }}>
          <div className="flex items-center justify-between mb-4">
            <span style={{ fontFamily: "Fraunces, serif", fontSize: "15px", fontWeight: 600, color: C.ink }}>
              Heutige Ankünfte
            </span>
            <Badge bg={C.mossSoft} fg={C.moss}>6 Buchungen</Badge>
          </div>
          <div className="space-y-3">
            {[
              { name: "Familie Steiner", plot: "B1 · Camper", zeit: "ab 14:00", pers: 4 },
              { name: "Lea Fontana", plot: "A2 · Zelt", zeit: "ab 13:00", pers: 2 },
              { name: "Familie van Dijk", plot: "C1 · Wohnwagen", zeit: "ab 15:00", pers: 3 },
            ].map((a, i) => (
              <div key={i} className="flex items-center justify-between py-2.5" style={{ borderBottom: i < 2 ? `1px solid ${C.sand}` : "none" }}>
                <div className="flex items-center gap-3">
                  <div className="rounded-full flex items-center justify-center" style={{ width: 32, height: 32, background: C.sand, color: C.ink, fontSize: "12px", fontWeight: 600 }}>
                    {a.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                  </div>
                  <div>
                    <div style={{ fontSize: "13.5px", fontWeight: 500, color: C.ink }}>{a.name}</div>
                    <div style={{ fontSize: "12px", color: C.inkSoft }}>{a.plot} · {a.pers} Pers.</div>
                  </div>
                </div>
                <span style={{ fontSize: "12.5px", color: C.inkSoft }}>{a.zeit}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl p-5" style={{ background: C.pine }}>
          <span style={{ fontFamily: "Fraunces, serif", fontSize: "15px", fontWeight: 600, color: "#F3EFE5" }}>
            Wetter Aeschi
          </span>
          <div style={{ fontFamily: "Fraunces, serif", fontSize: "38px", fontWeight: 600, color: "#F3EFE5", marginTop: "10px" }}>
            22°
          </div>
          <div style={{ fontSize: "12.5px", color: "#B7C0B6" }}>Leicht bewölkt · Thunersee</div>
          <div className="mt-5 pt-4 space-y-2" style={{ borderTop: `1px solid ${C.pineSoft}` }}>
            {["Do 21°", "Fr 23°", "Sa 19°"].map((d, i) => (
              <div key={i} className="flex justify-between" style={{ fontSize: "12.5px", color: "#B7C0B6" }}>
                <span>{d.split(" ")[0]}</span>
                <span>{d.split(" ")[1]}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function AnfragenView() {
  return (
    <div className="rounded-xl overflow-hidden" style={{ background: C.paper, border: `1px solid ${C.lineOnPaper}` }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: C.sand }}>
            {["Gast", "Quelle", "Zeitraum", "Typ", "Pers.", "Sprache", "Status"].map((h) => (
              <th key={h} className="text-left px-5 py-3" style={{ fontSize: "11.5px", fontWeight: 600, color: C.inkSoft, letterSpacing: "0.03em", textTransform: "uppercase" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {reservationsanfragen.map((r) => {
            const s = statusStyles[r.status];
            const Icon = s.icon;
            return (
              <tr key={r.id} style={{ borderTop: `1px solid ${C.lineOnPaper}` }}>
                <td className="px-5 py-3.5">
                  <div style={{ fontWeight: 500, color: C.ink }}>{r.gast}</div>
                  <div style={{ fontSize: "11.5px", color: C.inkSoft }}>{r.land}</div>
                </td>
                <td className="px-5 py-3.5" style={{ color: C.inkSoft }}>{r.quelle}</td>
                <td className="px-5 py-3.5" style={{ color: C.ink }}>{r.zeitraum}</td>
                <td className="px-5 py-3.5" style={{ color: C.ink }}>{r.typ}</td>
                <td className="px-5 py-3.5" style={{ color: C.ink }}>{r.personen}</td>
                <td className="px-5 py-3.5" style={{ color: C.inkSoft }}>{r.sprache}</td>
                <td className="px-5 py-3.5">
                  <Badge bg={s.bg} fg={s.fg}>
                    <Icon size={11} style={{ marginRight: "4px" }} />
                    {r.status}
                  </Badge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function BelegungView() {
  return (
    <div className="rounded-xl p-5" style={{ background: C.paper, border: `1px solid ${C.lineOnPaper}` }}>
      <div className="flex items-center justify-between mb-5">
        <span style={{ fontFamily: "Fraunces, serif", fontSize: "15px", fontWeight: 600, color: C.ink }}>
          Woche 34 · 17.–23. August 2026
        </span>
        <Badge bg={C.mossSoft} fg={C.moss}>78% belegt</Badge>
      </div>
      <div className="grid" style={{ gridTemplateColumns: "150px repeat(7, 1fr)" }}>
        <div />
        {wochentage.map((t) => (
          <div key={t} className="text-center py-2" style={{ fontSize: "11.5px", fontWeight: 600, color: C.inkSoft }}>
            {t}
          </div>
        ))}
        {stellplaetze.map((sp) => {
          const Icon = typIcon[sp.typ];
          return (
            <React.Fragment key={sp.name}>
              <div className="flex items-center gap-2 py-2" style={{ fontSize: "12.5px", color: C.ink }}>
                <Icon size={13} color={C.inkSoft} />
                {sp.name}
              </div>
              {sp.belegung.map((b, i) => (
                <div key={i} className="p-1">
                  <div
                    className="h-7 rounded-md"
                    style={{ background: b ? C.moss : C.sand, border: b ? "none" : `1px dashed ${C.line}` }}
                  />
                </div>
              ))}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

function GaesteView() {
  return (
    <div className="rounded-xl overflow-hidden" style={{ background: C.paper, border: `1px solid ${C.lineOnPaper}` }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: C.sand }}>
            {["Name", "Land", "Besuche", "Letzter Aufenthalt"].map((h) => (
              <th key={h} className="text-left px-5 py-3" style={{ fontSize: "11.5px", fontWeight: 600, color: C.inkSoft, letterSpacing: "0.03em", textTransform: "uppercase" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {gaeste.map((g, i) => (
            <tr key={i} style={{ borderTop: `1px solid ${C.lineOnPaper}` }}>
              <td className="px-5 py-3.5" style={{ fontWeight: 500, color: C.ink }}>{g.name}</td>
              <td className="px-5 py-3.5" style={{ color: C.inkSoft }}>{g.land}</td>
              <td className="px-5 py-3.5" style={{ color: C.ink }}>{g.besuche}×</td>
              <td className="px-5 py-3.5" style={{ color: C.inkSoft }}>{g.letzterAufenthalt}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RechnungenView() {
  const statusMap = {
    bezahlt: { bg: C.mossSoft, fg: C.moss },
    offen: { bg: C.amberSoft, fg: C.amber },
  };
  return (
    <div className="rounded-xl overflow-hidden" style={{ background: C.paper, border: `1px solid ${C.lineOnPaper}` }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: C.sand }}>
            {["Nummer", "Kunde", "Datum", "Betrag", "Zahlungsart", "Status", ""].map((h) => (
              <th key={h} className="text-left px-5 py-3" style={{ fontSize: "11.5px", fontWeight: 600, color: C.inkSoft, letterSpacing: "0.03em", textTransform: "uppercase" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rechnungen.map((r) => {
            const s = statusMap[r.status];
            return (
              <tr key={r.nummer} style={{ borderTop: `1px solid ${C.lineOnPaper}` }}>
                <td className="px-5 py-3.5" style={{ fontWeight: 500, color: C.ink, fontVariantNumeric: "tabular-nums" }}>{r.nummer}</td>
                <td className="px-5 py-3.5" style={{ color: C.ink }}>{r.kunde}</td>
                <td className="px-5 py-3.5" style={{ color: C.inkSoft }}>{r.datum}</td>
                <td className="px-5 py-3.5" style={{ color: C.ink, fontVariantNumeric: "tabular-nums" }}>CHF {r.betrag.toFixed(2)}</td>
                <td className="px-5 py-3.5" style={{ color: C.inkSoft }}>{r.zahlungsart}</td>
                <td className="px-5 py-3.5">
                  <Badge bg={s.bg} fg={s.fg}>{r.status}</Badge>
                </td>
                <td className="px-5 py-3.5 text-right" style={{ color: C.lake, fontSize: "12.5px" }}>PDF</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AuswertungenView() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2 rounded-xl p-5" style={{ background: C.paper, border: `1px solid ${C.lineOnPaper}` }}>
          <span style={{ fontFamily: "Fraunces, serif", fontSize: "15px", fontWeight: 600, color: C.ink }}>
            Umsatz pro Monat
          </span>
          <div style={{ height: "220px", marginTop: "12px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={umsatzProMonat}>
                <XAxis dataKey="monat" tick={{ fontSize: 12, fill: C.inkSoft }} axisLine={{ stroke: C.lineOnPaper }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: C.inkSoft }} axisLine={false} tickLine={false} width={44} />
                <Tooltip cursor={{ fill: C.sand }} formatter={(v) => [`CHF ${v}`, "Umsatz"]} />
                <Bar dataKey="umsatz" fill={C.moss} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl p-5" style={{ background: C.paper, border: `1px solid ${C.lineOnPaper}` }}>
          <span style={{ fontFamily: "Fraunces, serif", fontSize: "15px", fontWeight: 600, color: C.ink }}>
            Zahlungsmethoden
          </span>
          <div style={{ height: "180px", marginTop: "8px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={zahlungsmethoden} dataKey="value" nameKey="name" innerRadius={42} outerRadius={68} paddingAngle={2}>
                  {zahlungsmethoden.map((z, i) => (
                    <Cell key={i} fill={z.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(v, n) => [`${v}%`, n]} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-1.5 mt-1">
            {zahlungsmethoden.map((z) => (
              <div key={z.name} className="flex items-center justify-between" style={{ fontSize: "12px" }}>
                <div className="flex items-center gap-2">
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: z.color, display: "inline-block" }} />
                  <span style={{ color: C.inkSoft }}>{z.name}</span>
                </div>
                <span style={{ color: C.ink, fontWeight: 500 }}>{z.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-xl p-5" style={{ background: C.paper, border: `1px solid ${C.lineOnPaper}` }}>
        <span style={{ fontFamily: "Fraunces, serif", fontSize: "15px", fontWeight: 600, color: C.ink }}>
          Umsatz nach Artikel
        </span>
        <div style={{ height: "200px", marginTop: "12px" }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={umsatzNachArtikel} layout="vertical" margin={{ left: 20 }}>
              <XAxis type="number" tick={{ fontSize: 11, fill: C.inkSoft }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="artikel" tick={{ fontSize: 12, fill: C.ink }} axisLine={false} tickLine={false} width={150} />
              <Tooltip cursor={{ fill: C.sand }} formatter={(v) => [`CHF ${v}`, "Umsatz"]} />
              <Bar dataKey="umsatz" fill={C.lake} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------
   ROOT
------------------------------------------------------------------------ */
export default function CampingVerwaltungLookalike() {
  const [active, setActive] = useState("dashboard");

  const titles = {
    dashboard: "Übersicht",
    anfragen: "Reservationsanfragen",
    belegung: "Belegungsplan",
    gaeste: "Gäste",
    rechnungen: "Rechnungen",
    auswertungen: "Auswertungen",
  };

  const views = {
    dashboard: <DashboardView />,
    anfragen: <AnfragenView />,
    belegung: <BelegungView />,
    gaeste: <GaesteView />,
    rechnungen: <RechnungenView />,
    auswertungen: <AuswertungenView />,
  };

  return (
    <div style={{ fontFamily: "Inter, sans-serif" }}>
      <style>{FONTS}</style>
      <div className="flex" style={{ height: "760px", background: C.sand }}>
        <Sidebar active={active} onSelect={setActive} />
        <div className="flex-1 flex flex-col min-w-0">
          <Topbar title={titles[active]} />
          <div className="flex-1 overflow-y-auto px-8 py-6">
            <div className="flex items-center justify-between mb-5">
              <div
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full"
                style={{ background: C.amberSoft, fontSize: "11px", color: C.amber, fontWeight: 600 }}
              >
                Prototyp · Demo-Daten, nicht funktional
              </div>
              {active === "anfragen" && (
                <button
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium"
                  style={{ background: C.moss, color: "#fff" }}
                >
                  <Plus size={14} /> Anfrage erfassen
                </button>
              )}
            </div>
            {views[active]}
          </div>
        </div>
      </div>
    </div>
  );
}
