import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { SPRACHEN, datumVoll } from "../format.js";

const BEREICHE = [
  { code: "vorlagen", name: "Antwortvorlagen" },
  { code: "betrieb", name: "Betriebsangaben" },
  { code: "mwst", name: "MWST-Sätze" },
  { code: "postfach", name: "Postfach" },
  { code: "module", name: "Module" },
];

export default function Einstellungen({ module, onGeaendert }) {
  const [bereich, setBereich] = useState("vorlagen");
  return (
    <div className={`seite${bereich === "vorlagen" ? "" : " schmal"}`}>
      <header className="kopf"><h1>Einstellungen</h1></header>
      <div className="ablagen" role="tablist" aria-label="Bereich">
        {BEREICHE.map((b) => (
          <button key={b.code} role="tab" aria-selected={bereich === b.code} onClick={() => setBereich(b.code)}>{b.name}</button>
        ))}
      </div>
      {bereich === "vorlagen" && <Vorlagen />}
      {bereich === "betrieb" && <Betrieb />}
      {bereich === "mwst" && <MwstSaetze />}
      {bereich === "postfach" && <Postfach />}
      {bereich === "module" && <Module module={module} onGeaendert={onGeaendert} />}
    </div>
  );
}

const VORLAGENTYPEN = [
  { typ: "erstantwort_zahlungsinfo", name: "Antwort mit Anzahlung",
    hinweis: "Antwort auf eine Reservationsanfrage mit den Zahlungsangaben.",
    vorschau: "Mit einer erfundenen Anfrage, Anzahlung CHF 120.00 und Frist 31.3.2027." },
  { typ: "freie_antwort", name: "Freie Antwort",
    hinweis: "Rahmen für Antworten auf Fragen des Gastes, ohne Anzahlung: Anrede, Platz für Ihren Text, Gruss und Signatur. Der eigene Text kommt nach der ersten Leerzeile.",
    vorschau: "Mit einer erfundenen Anfrage und der Gastfrage «Sind Hunde erlaubt?» als letztem Betreff." },
];

function Vorlagen() {
  const [typ, setTyp] = useState(VORLAGENTYPEN[0].typ);
  const [vorlagen, setVorlagen] = useState(null);
  const [platzhalter, setPlatzhalter] = useState([]);
  const [sprache, setSprache] = useState("de");
  const [entwurf, setEntwurf] = useState(null); // {betreff, koerper}
  const [vorschau, setVorschau] = useState(null);
  const [meldung, setMeldung] = useState(null);
  const textfeld = useRef(null);

  useEffect(() => {
    api.get("/email-vorlagen/platzhalter").then(setPlatzhalter).catch(() => {});
  }, []);
  useEffect(() => {
    setVorlagen(null); setEntwurf(null); setVorschau(null);
    api.get(`/email-vorlagen?typ=${typ}`).then(setVorlagen).catch((e) => setMeldung({ art: "fehler", text: e.message }));
  }, [typ]);
  const art = VORLAGENTYPEN.find((t) => t.typ === typ);

  const vorlage = vorlagen?.find((v) => v.sprache === sprache);
  // nur beim Wechsel der Sprache neu laden, nicht nach dem Speichern
  useEffect(() => {
    if (vorlage) setEntwurf({ betreff: vorlage.betreff, koerper: vorlage.koerper });
    setMeldung(null);
  }, [vorlage?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!entwurf) return undefined;
    const t = setTimeout(() => {
      api.post("/email-vorlagen/vorschau", { ...entwurf, sprache, typ }).then(setVorschau).catch(() => {});
    }, 350);
    return () => clearTimeout(t);
  }, [entwurf, sprache, typ]);

  const geaendert = vorlage && entwurf && (vorlage.betreff !== entwurf.betreff || vorlage.koerper !== entwurf.koerper);

  const einfuegen = (name) => {
    const feld = textfeld.current;
    const marke = `{{${name}}}`;
    const start = feld?.selectionStart ?? entwurf.koerper.length;
    const ende = feld?.selectionEnd ?? start;
    setEntwurf({ ...entwurf, koerper: entwurf.koerper.slice(0, start) + marke + entwurf.koerper.slice(ende) });
    requestAnimationFrame(() => { feld?.focus(); feld?.setSelectionRange(start + marke.length, start + marke.length); });
  };

  const speichern = async () => {
    setMeldung(null);
    try {
      const neu = await api.put(`/email-vorlagen/${vorlage.id}`, { ...entwurf, aktiv: true });
      setVorlagen(vorlagen.map((v) => (v.id === neu.id ? neu : v)));
      setMeldung({ art: "ok", text: `Vorlage «${art.name}» ${SPRACHEN[sprache]} gespeichert.` });
    } catch (e) { setMeldung({ art: "fehler", text: e.message }); }
  };

  return (
    <section className="vorlagen">
      <div className="umschalter" role="group" aria-label="Antwortart">
        {VORLAGENTYPEN.map((t) => (
          <button key={t.typ} aria-pressed={typ === t.typ} onClick={() => setTyp(t.typ)}>{t.name}</button>
        ))}
      </div>
      <p className="hinweis">
        {art.hinweis} Pro Sprache eine Vorlage. Platzhalter in doppelten geschweiften Klammern werden beim Vorbereiten
        der Antwort durch die Angaben der Anfrage ersetzt.
      </p>
      {!vorlagen && <p className="leer">Wird geladen …</p>}
      {vorlagen && <div className="umschalter" role="group" aria-label="Sprache">
        {vorlagen.map((v) => (
          <button key={v.sprache} aria-pressed={sprache === v.sprache} onClick={() => setSprache(v.sprache)}>{SPRACHEN[v.sprache]}</button>
        ))}
      </div>}
      {vorlagen && entwurf && (
        <div className="vorlagen-raster">
          <div className="formular">
            <div className="feld">
              <label htmlFor="vorlage-betreff">Betreff</label>
              <input id="vorlage-betreff" value={entwurf.betreff} onChange={(e) => setEntwurf({ ...entwurf, betreff: e.target.value })} />
            </div>
            <div className="feld">
              <label htmlFor="vorlage-text">Text</label>
              <textarea id="vorlage-text" ref={textfeld} rows={typ === "freie_antwort" ? 10 : 24} value={entwurf.koerper} onChange={(e) => setEntwurf({ ...entwurf, koerper: e.target.value })} />
            </div>
            {meldung && <p className={`meldung ${meldung.art}`} role="status">{meldung.text}</p>}
            <div className="aktionen">
              <button className="knopf haupt" onClick={speichern} disabled={!geaendert}>Vorlage speichern</button>
              <button className="knopf leise" onClick={() => setEntwurf({ betreff: vorlage.betreff, koerper: vorlage.koerper })} disabled={!geaendert}>Änderungen verwerfen</button>
            </div>
            <details className="platzhalter">
              <summary>Platzhalter einfügen</summary>
              <ul>
                {platzhalter.map((p) => (
                  <li key={p.name}><button type="button" className="knopf neben klein" onClick={() => einfuegen(p.name)}>{`{{${p.name}}}`}</button><span>{p.beschreibung}</span></li>
                ))}
              </ul>
            </details>
          </div>
          <div className="vorschau" aria-live="polite">
            <h2>Vorschau</h2>
            <p className="hinweis">{art.vorschau}</p>
            {vorschau?.warnungen?.map((w) => <p key={w} className="meldung warnung">{w}. Unter «Betriebsangaben» ergänzen.</p>)}
            {vorschau?.unbekannte_platzhalter?.length > 0 && (
              <p className="meldung fehler">Unbekannte Platzhalter: {vorschau.unbekannte_platzhalter.map((u) => `{{${u}}}`).join(", ")}</p>
            )}
            {vorschau && (
              <div className="mail">
                <p className="mail-betreff">{vorschau.betreff}</p>
                <pre>{vorschau.text}</pre>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function Betrieb() {
  const [felder, setFelder] = useState(null);
  const [werte, setWerte] = useState({});
  const [meldung, setMeldung] = useState(null);

  useEffect(() => {
    api.get("/einstellungen/betrieb").then((f) => { setFelder(f); setWerte(Object.fromEntries(f.map((x) => [x.schluessel, x.wert]))); })
      .catch((e) => setMeldung({ art: "fehler", text: e.message }));
  }, []);

  const speichern = async (e) => {
    e.preventDefault(); setMeldung(null);
    try {
      const f = await api.put("/einstellungen/betrieb", werte);
      setFelder(f); setMeldung({ art: "ok", text: "Betriebsangaben gespeichert." });
    } catch (err) { setMeldung({ art: "fehler", text: err.message }); }
  };

  if (!felder) return meldung ? <p className="meldung fehler">{meldung.text}</p> : <p className="leer">Wird geladen …</p>;
  return (
    <form className="formular" onSubmit={speichern}>
      <p className="hinweis">Diese Angaben erscheinen in jeder Antwortmail.</p>
      {felder.map((f) => {
        const id = `betrieb-${f.schluessel}`;
        const props = {
          id, value: werte[f.schluessel] ?? "", "aria-describedby": f.hinweis ? `${id}-hinweis` : undefined,
          onChange: (e) => setWerte({ ...werte, [f.schluessel]: e.target.value }),
        };
        return (
          <div key={f.schluessel} className="feld">
            <label htmlFor={id}>{f.bezeichnung}</label>
            {f.mehrzeilig ? <textarea rows={f.schluessel === "infoblock" ? 16 : 9} {...props} /> : <input {...props} />}
            {f.hinweis && <span id={`${id}-hinweis`} className="feldhinweis">{f.hinweis}</span>}
          </div>
        );
      })}
      {meldung && <p className={`meldung ${meldung.art}`} role="status">{meldung.text}</p>}
      <div className="aktionen"><button className="knopf haupt" type="submit">Betriebsangaben speichern</button></div>
    </form>
  );
}

function Module({ module, onGeaendert }) {
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
    <section>
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
  );
}

const prozent = (wert) => `${Number(wert).toLocaleString("de-CH", { minimumFractionDigits: 1, maximumFractionDigits: 2 })} %`;

function MwstSaetze() {
  const [codes, setCodes] = useState(null);
  const [meldung, setMeldung] = useState(null);
  useEffect(() => { api.get("/mwst-saetze").then(setCodes).catch((e) => setMeldung({ art: "fehler", text: e.message })); }, []);

  if (!codes) return meldung ? <p className="meldung fehler">{meldung.text}</p> : <p className="leer">Wird geladen …</p>;
  return (
    <section>
      <p className="hinweis">
        Ein neuer Satz gilt ab dem gewählten Datum, der bisherige endet am Vortag. Rechnungen verwenden den Satz,
        der am Leistungsdatum gilt; bereits erstellte Rechnungen bleiben unverändert.
      </p>
      {meldung && <p className={`meldung ${meldung.art}`} role="status">{meldung.text}</p>}
      <div className="mwst-liste">
        {codes.map((c) => <MwstCode key={c.code} code={c} onGeaendert={(neu, text) => { setCodes(neu); setMeldung(text ? { art: "ok", text } : null); }}
          onFehler={(text) => setMeldung({ art: "fehler", text })} />)}
      </div>
    </section>
  );
}

function MwstCode({ code, onGeaendert, onFehler }) {
  const naechstesJahr = new Date().getFullYear() + 1;
  const [neu, setNeu] = useState({ satz: "", ab: `${naechstesJahr}-01-01` });
  const [offen, setOffen] = useState(false);
  const id = `mwst-${code.code.toLowerCase()}`;

  const hinterlegen = async (e) => {
    e.preventDefault();
    try {
      const liste = await api.post(`/mwst-saetze/${code.code}`, { satz_prozent: neu.satz, gueltig_ab: neu.ab });
      setOffen(false); setNeu({ satz: "", ab: neu.ab });
      onGeaendert(liste, `${code.bezeichnung}: ${prozent(neu.satz)} ab ${datumVoll(neu.ab)} hinterlegt.`);
    } catch (err) { onFehler(err.message); }
  };
  const entfernen = async (satz) => {
    try { onGeaendert(await api.delete(`/mwst-saetze/${satz.id}`), `Satz ab ${datumVoll(satz.gueltig_ab)} entfernt.`); }
    catch (err) { onFehler(err.message); }
  };

  return (
    <article className="mwst-karte" aria-labelledby={`${id}-titel`}>
      <header>
        <div>
          <h2 id={`${id}-titel`}>{code.bezeichnung}</h2>
          <span className="hinweis">{code.code}</span>
        </div>
        <p className="mwst-aktuell">{code.aktueller_satz !== null ? prozent(code.aktueller_satz) : "–"}<span>heute gültig</span></p>
      </header>
      <table className="mwst-verlauf">
        <thead><tr><th scope="col">Satz</th><th scope="col">gültig ab</th><th scope="col">gültig bis</th><th scope="col"><span className="sr-only">Aktion</span></th></tr></thead>
        <tbody>
          {code.saetze.map((s, i) => (
            <tr key={s.id} className={s.aktuell ? "aktuell" : undefined}>
              <td>{prozent(s.satz_prozent)}</td>
              <td>{datumVoll(s.gueltig_ab)}</td>
              <td>{s.gueltig_bis ? datumVoll(s.gueltig_bis) : "offen"}</td>
              <td>{i === 0 && s.zukuenftig && <button className="knopf leise klein" onClick={() => entfernen(s)}>Entfernen</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {offen ? (
        <form className="mwst-neu" onSubmit={hinterlegen}>
          <div className="feld"><label htmlFor={`${id}-satz`}>Neuer Satz in %</label>
            <input id={`${id}-satz`} required type="number" min="0" max="100" step="0.1" inputMode="decimal" value={neu.satz} onChange={(e) => setNeu({ ...neu, satz: e.target.value })} /></div>
          <div className="feld"><label htmlFor={`${id}-ab`}>gültig ab</label>
            <input id={`${id}-ab`} required type="date" value={neu.ab} onChange={(e) => setNeu({ ...neu, ab: e.target.value })} /></div>
          <div className="aktionen">
            <button className="knopf haupt" type="submit">Satz hinterlegen</button>
            <button className="knopf leise" type="button" onClick={() => setOffen(false)}>Abbrechen</button>
          </div>
        </form>
      ) : (
        <div className="aktionen"><button className="knopf neben" onClick={() => setOffen(true)}>Neuen Satz hinterlegen</button></div>
      )}
    </article>
  );
}

const ERGEBNIS_TEXTE = [
  ["neu", "neue Anfragen"], ["nachtraege", "Mails von Gästen zu bestehenden Anfragen"],
  ["antworten", "eigene Antworten zugeordnet"], ["nicht_zugeordnet", "nicht zugeordnet"],
  ["duplikate", "schon vorhanden"], ["uebersprungen", "übersprungen (z.B. Abwesenheitsnotiz)"],
];

function Postfach() {
  const [status, setStatus] = useState(null);
  const [anfragen, setAnfragen] = useState([]);
  const [meldung, setMeldung] = useState(null);
  const [laeuft, setLaeuft] = useState(false);
  const laden = () => api.get("/einstellungen/postfach").then(setStatus).catch((e) => setMeldung({ art: "fehler", text: e.message }));
  useEffect(() => { laden(); api.get("/reservationsanfragen").then(setAnfragen).catch(() => {}); }, []);

  const abrufen = async () => {
    setLaeuft(true); setMeldung(null);
    try {
      const e = await api.post("/reservationsanfragen/mail-import");
      const teile = ERGEBNIS_TEXTE.filter(([k]) => e[k]).map(([k, t]) => `${e[k]} ${t}`);
      setMeldung({ art: e.fehler?.length ? "warnung" : "ok", text: `Abgerufen: ${teile.join(", ") || "keine neuen Mails"}.${e.fehler?.length ? ` Fehler: ${e.fehler.join("; ")}` : ""}` });
      laden();
    } catch (err) { setMeldung({ art: "fehler", text: err.message }); } finally { setLaeuft(false); }
  };
  const zuordnen = async (mailId, anfrageId) => {
    try { setStatus(await api.post(`/einstellungen/postfach/mails/${mailId}/zuordnen`, { anfrage_id: anfrageId })); setMeldung({ art: "ok", text: "Mail zugeordnet." }); }
    catch (err) { setMeldung({ art: "fehler", text: err.message }); }
  };

  if (!status) return meldung ? <p className="meldung fehler">{meldung.text}</p> : <p className="leer">Wird geladen …</p>;
  const zeit = (iso) => new Date(iso).toLocaleString("de-CH", { dateStyle: "medium", timeStyle: "short" });
  return (
    <section>
      <p className="hinweis">
        Reservationsmails und Antworten gelangen per «Umleiten» (empfohlen) oder «Weiterleiten» aus dem Mailkonto des Campings
        in ein eigenes Postfach, das die App regelmässig abruft. Eigene Antworten (per BCC oder umgeleitet) werden der passenden
        Anfrage zugeordnet, Antworten von Gästen ebenfalls.
      </p>
      {!status.eingerichtet && (
        <p className="meldung warnung">
          Das Postfach ist noch nicht eingerichtet. Dafür braucht es in Atoll die Angaben IMAP_HOST, IMAP_USER und IMAP_PASSWORD.
        </p>
      )}
      <dl className="angaben postfach-angaben">
        <dt>Postfach</dt><dd>{status.server ?? "nicht eingerichtet"}, Ordner {status.ordner}</dd>
        <dt>Abruf</dt><dd>{status.intervall_sekunden > 0 ? `alle ${Math.round(status.intervall_sekunden / 60)} Minuten` : "nur von Hand"}</dd>
        <dt>Eigene Adressen</dt><dd>{status.eigene_adressen.join(", ")}</dd>
        <dt>Letzter Abruf</dt>
        <dd>
          {status.letzter_abruf ? zeit(status.letzter_abruf) : "noch keiner"}
          {status.ergebnis && (
            <span className="feldhinweis"> – {ERGEBNIS_TEXTE.filter(([k]) => status.ergebnis[k]).map(([k, t]) => `${status.ergebnis[k]} ${t}`).join(", ") || "keine neuen Mails"}
              {status.ergebnis.fehler?.length ? `; ${status.ergebnis.fehler.length} Fehler` : ""}</span>
          )}
        </dd>
      </dl>
      <div className="aktionen">
        <button className="knopf neben" onClick={abrufen} disabled={laeuft || !status.eingerichtet}>Postfach jetzt abrufen</button>
      </div>
      {meldung && <p className={`meldung ${meldung.art}`} role="status">{meldung.text}</p>}

      <h2>Nicht zugeordnete Mails</h2>
      {status.nicht_zugeordnet.length === 0 && <p className="leer">Keine. Alle Mails aus dem Postfach gehören zu einer Anfrage.</p>}
      <ul className="verlauf-liste">
        {status.nicht_zugeordnet.map((m) => (
          <li key={m.id} className={`mail ${m.richtung}`}>
            <p className="mail-kopf"><span className="richtung">{m.richtung === "eingang" ? "Eingang" : "Eigene Mail"}</span><time dateTime={m.datum}>{zeit(m.datum)}</time></p>
            <p className="mail-betreff">{m.betreff || "(ohne Betreff)"}<span>{m.richtung === "eingang" ? `von ${m.von}` : `an ${m.an ?? ""}`}</span></p>
            <pre>{m.text}</pre>
            <div className="feld zuordnen">
              <label htmlFor={`zuordnen-${m.id}`}>Einer Anfrage zuordnen</label>
              <select id={`zuordnen-${m.id}`} defaultValue="" onChange={(e) => e.target.value && zuordnen(m.id, e.target.value)}>
                <option value="">Anfrage wählen …</option>
                {anfragen.map((a) => <option key={a.id} value={a.id}>{a.gast_name} ({a.gast_email}){a.gewuenscht_von ? `, ab ${a.gewuenscht_von.split("-").reverse().join(".")}` : ""}</option>)}
              </select>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
