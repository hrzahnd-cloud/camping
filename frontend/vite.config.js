import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Die gebaute Oberfläche liefert FastAPI unter "/" aus (app/main.py).
// Im Entwicklungsmodus leitet Vite API-Aufrufe an das lokale Backend weiter.
const api = ["/reservationsanfragen", "/gaeste", "/belegung", "/einstellungen", "/buchungen",
  "/artikel", "/rechnungen", "/auswertungen", "/hesta", "/feratel", "/health"];

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", assetsDir: "assets" },
  server: { proxy: Object.fromEntries(api.map((p) => [p, "http://127.0.0.1:8000"])) },
});
