# CLAUDE.md — dok74verhuur klantenportaal

## Projectdoel

Klantenportaal voor **DOK74 Verhuur BV** — een verhuurbedrijf. Huurders worden via een tile-navigatie begeleid naar de juiste informatie of een contextspecifiek contactformulier. Ingevulde formulieren worden gemaild (via SendGrid) en opgeslagen in Airtable.

Bedoeld voor deployment op **Railway**.

## Architectuur

```
app.py                        Flask backend: routes, API-endpoints, REPAIR_CATEGORIES dict
templates/index.html          Hoofdpagina: home / contract / betaling (JS-navigatie, geen page reloads)
templates/inschrijven.html    Inschrijfpagina met uitgebreid formulier
templates/reparatie.html      Reparatiepagina: verantwoordelijkheden + 6 category-tiles
templates/reparatie_form.html Generiek Jinja2-formulier voor alle 6 reparatiecategorieën
static/logodok74.jpg          DOK74-logo (alleen gebouwicoontje zichtbaar via CSS-clip)
requirements.txt              Python dependencies
Procfile                      Railway startcommando (gunicorn)
.env.example                  Template voor environment variables
```

### Navigatiemodel

**index.html** — drie schermen via JS (geen page reloads):
- **home** — 7 tiles: inschrijven (page), reparatie (page), contract (screen), betaling (screen), sleutels (modal), klacht (modal), contact (modal)
- **contract** — 6 sub-tiles (modals)
- **betaling** — 6 sub-tiles (modals)

Tiles met `type: 'page'` navigeren via `window.location.href`. Tiles met `type: 'screen'` wisselen het scherm. Tiles met `type: 'modal'` openen een overlay.

Modals zijn `type: 'info'` (FAQ + optionele contactknop) of `type: 'form'` (formulier → `/api/contact`).

**Losse pagina's (server-side):**
- `/inschrijven` → `inschrijven.html`
- `/reparatie` → `reparatie.html` (2 verantwoordelijkheidsblokken + 6 link-tiles)
- `/reparatie/<slug>` → `reparatie_form.html` (generiek, driven by `REPAIR_CATEGORIES` in `app.py`)

### Reparatie-formulieren

`REPAIR_CATEGORIES` in `app.py` definieert alle 6 categorieën: `verwarming`, `lekkage`, `schimmel`, `raam`, `elektra`, `overig`. Elke entry bevat: `title`, `note` (HTML-string of None), `contact_optional` (bool), `fields` (lijst van dict met `id`, `label`, `type`, `required`, `placeholder`, en evt. `options`).

`reparatie_form.html` rendert fields server-side: input/textarea/select afhankelijk van `field.type`. JS submit gaat naar `/api/contact` met `category: reparatie-${SLUG}`. Succes toont "Terug naar reparaties" knop. Terug-link gaat naar `/reparatie`.

## Hoe te starten

```bash
python3 app.py
# Opent op http://localhost:8081
```

Poort 5000 is op macOS bezet door AirPlay, poort 8080 door SABnzbd. Standaardpoort is 8081. Op Railway wordt `$PORT` uit de omgeving gebruikt. `debug=True` is actief voor auto-reload tijdens development.

## Afhankelijkheden

```
flask==3.1.0
sendgrid==6.11.0
requests==2.32.3
gunicorn==23.0.0
```

Installeren: `pip3 install -r requirements.txt`

## Environment variables

| Variabele                       | Waarde                        |
|---------------------------------|-------------------------------|
| `SENDGRID_API_KEY`              | SendGrid API key              |
| `FROM_EMAIL`                    | `noreply@dok74verhuur.nl`     |
| `TO_EMAIL`                      | `info@dok74verhuur.nl`        |
| `AIRTABLE_API_KEY`              | Airtable personal access token|
| `AIRTABLE_BASE_ID`              | ID van de Airtable base       |
| `AIRTABLE_TABLE`                | Tabelnaam contactformulieren (standaard: `Contactformulieren`) |
| `AIRTABLE_TABLE_INSCHRIJVINGEN` | Tabelnaam inschrijvingen (standaard: `Inschrijvingen`) |

Lokaal: kopieer `.env.example` naar `.env` en vul in. Op Railway: stel in als Environment Variables.

## Airtable tabelstructuur

**Tabel `Contactformulieren`**
`Naam` · `E-mail` · `Telefoon` · `Adres` · `Categorie` · `Bericht` · `Details` · `Datum`

**Tabel `Inschrijvingen`**
`Naam` · `Voorletters` · `E-mail` · `Telefoon` · `Adres` · `Notities` · `Bedrijf` · `Datum`

## API endpoints

| Methode | Route               | Beschrijving                                  |
|---------|---------------------|-----------------------------------------------|
| GET     | `/`                 | Hoofdpagina (index.html)                      |
| GET     | `/inschrijven`      | Inschrijfpagina                               |
| GET     | `/reparatie`        | Reparatie-overzichtspagina                    |
| GET     | `/reparatie/<slug>` | Reparatieformulier voor specifieke categorie  |
| POST    | `/api/contact`      | Verwerkt contactformulieren → mail + Airtable |
| POST    | `/api/inschrijven`  | Verwerkt inschrijvingen → mail + Airtable     |

## Stijl & huisstijl

- **Primaire kleur:** geel `#F5C900`
- **Tekstkleur:** donkergrijs `#2A2A2A`
- **Achtergrond:** lichtgrijs `#F5F5F5`
- **Groen accent:** `#059669` (reparatiepagina: "Dit regelt u zelf" kaart)
- Logo staat in de hero (alleen gebouwicoontje zichtbaar via CSS-clip): `.hero-logo-wrap { height: 60px; overflow: hidden; }` + `.hero-logo { height: 100px; }` — tekst wordt weggeclipped
- Hero: `flex-direction: column; align-items: center; text-align: center`
- Spoedmelding staat **onderaan** de home-tiles (niet bovenaan), alleen zichtbaar op home-scherm
- Footer bevat Facebook-link: `https://www.facebook.com/DOK74VERHUUR`
- Telefoonnummer in header: **085 401 1736**

## Taal & conventies

- Gebruikersinterface: **Nederlands**
- Code, variabelenamen, commentaar: **Engels**
- Geen externe CSS/JS frameworks — alles embedded in de templates

## Bekende valkuilen

- Bij ontbrekende `SENDGRID_API_KEY` of Airtable-config logt de backend een waarschuwing maar geeft de gebruiker altijd een succesmelding (fail silently).
- `AIRTABLE_TABLE` en `AIRTABLE_TABLE_INSCHRIJVINGEN` worden URL-encoded voor de API-call (ondersteunt spaties in tabelnamen).
- De modal-form in index.html is dynamisch opgebouwd via JS; event listeners worden per `openModal()`-aanroep opnieuw gekoppeld.
- `reparatie.html` bevat nog een `<script>` met een ongebruikt MODALS-object (overblijfsel van een eerdere versie). Kan worden verwijderd.
- `debug=True` staat aan in `app.py` — op Railway heeft dit geen effect omdat gunicorn via Procfile wordt gebruikt.
- Hard refresh nodig (Cmd+Shift+R) bij cached JS na frontend-wijzigingen tijdens development.
