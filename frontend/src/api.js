// Dünne Hülle um fetch: gleiche Herkunft wie die Oberfläche, Fehlermeldungen
// der API (FastAPI "detail") werden als lesbarer Text weitergegeben.
async function anfrage(methode, pfad, daten) {
  const antwort = await fetch(pfad, {
    method: methode,
    headers: daten ? { "Content-Type": "application/json" } : undefined,
    body: daten ? JSON.stringify(daten) : undefined,
  });
  if (!antwort.ok) {
    let text = `Fehler ${antwort.status}`;
    try {
      const inhalt = await antwort.json();
      if (typeof inhalt.detail === "string") text = inhalt.detail;
      else if (Array.isArray(inhalt.detail)) {
        text = inhalt.detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
      }
    } catch { /* keine JSON-Antwort */ }
    throw new Error(text);
  }
  return antwort.status === 204 ? null : antwort.json();
}

export const api = {
  get: (pfad) => anfrage("GET", pfad),
  post: (pfad, daten) => anfrage("POST", pfad, daten),
  put: (pfad, daten) => anfrage("PUT", pfad, daten),
  patch: (pfad, daten) => anfrage("PATCH", pfad, daten),
};
