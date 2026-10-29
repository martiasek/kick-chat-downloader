# Kick Chat Downloader

Webová appka (Flask), která stáhne chat z Kick VOD přes API Kicku a uloží ho jako
**TwitchDownloader JSON** (stejný formát jako `*_twitch.json` ze Kicklet konverze).

## Rychlý start (Windows)

1. Nainstaluj [Python 3.10+](https://www.python.org/downloads/) (při instalaci zaškrtni *Add to PATH*).
2. Stáhni repozitář (`git clone …` nebo *Code → Download ZIP* na GitHubu) a rozbal.
3. Dvojklik na **`run.bat`**. Poprvé si doinstaluje závislosti a otevře prohlížeč na http://127.0.0.1:5000.

macOS / Linux: `./run.sh`

Ručně:

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                                      # http://127.0.0.1:5000
```

## Použití

Vlož URL ve tvaru `https://kick.com/<kanál>/videos/<uuid>`, klikni na **Stáhnout chat**
a po dokončení **Stáhnout JSON**. Soubor se zároveň uloží do složky `output/`.

- *Přibalit emoty a badge*: stáhne obrázky emotů a globálních badgů (collectibles jako GOAT, Golden K, level…) do `embeddedData`. Globální badge se ukládají jen ty, které má uživatel vybrané k zobrazení.
  Badge kanálu: *subscriber* má obrázky z API (podle tieru/měsíců), ostatní (moderátor, VIP, founder, OG…)
  nemají v API obrázek, proto se kreslí vlastní jednoduché ikony (`kickchat/badges.py`).
- *Délka VOD* (pokročilé): pokud Kick délku videa nevrátí, appka skončí až po 30 min bez zprávy.
  Když po streamu v chatu dál píšou, zadej délku ručně.

## Jak to funguje

1. `kick.com/api/v2/channels/{slug}` → id kanálu
2. `web.kick.com/api/v1/channels/{id}/videos` → start VOD (pro starší VOD se čte z UUIDv7)
3. `web.kick.com/api/v1/chat/{id}/history?start_time=…` → zprávy v 5s oknech, paralelně
4. převod do TwitchDownloader JSON (`kickchat/convert.py`)

Kick API je neoficiální a může se změnit. Kick drží chat zhruba rok. Cloudflare blokuje běžné HTTP
klienty, proto se používá `curl_cffi` (napodobuje Chrome).

## Vývoj

```bash
pip install -r requirements-dev.txt
pytest
```

Testy běží nad falešným API (`tests/fakes.py`), na Kick se nepřipojují.

## Struktura

```
app.py              Flask server + REST API (/api/jobs…)
kickchat/client.py  HTTP klient pro Kick (curl_cffi, retry)
kickchat/job.py     řízení stahování, progress, zrušení
kickchat/convert.py převod do TwitchDownloader JSON
kickchat/urls.py    parsování URL, UUIDv7
templates/          webové UI
```
