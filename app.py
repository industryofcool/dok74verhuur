import os
import urllib.parse
from datetime import datetime

import requests
from flask import Flask, jsonify, redirect, render_template, request
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

app = Flask(__name__)

SENDGRID_API_KEY   = os.environ.get('SENDGRID_API_KEY', '')
FROM_EMAIL         = os.environ.get('FROM_EMAIL', 'noreply@dok74verhuur.nl')
TO_EMAIL           = os.environ.get('TO_EMAIL', 'info@dok74verhuur.nl')
AIRTABLE_API_KEY   = os.environ.get('AIRTABLE_API_KEY', '')
AIRTABLE_BASE_ID   = os.environ.get('AIRTABLE_BASE_ID', '')
AIRTABLE_TABLE          = os.environ.get('AIRTABLE_TABLE', 'Contactformulieren')
AIRTABLE_TABLE_INSCRIP  = os.environ.get('AIRTABLE_TABLE_INSCHRIJVINGEN', 'Inschrijvingen')

CATEGORY_LABELS = {
    'reparatie':              'Reparatie melden',
    'reparatie-verwarming':   'Reparatie — CV-ketel of verwarming',
    'reparatie-lekkage':      'Reparatie — Lekkage of wateroverlast',
    'reparatie-schimmel':     'Reparatie — Schimmel of vochtproblemen',
    'reparatie-raam':         'Reparatie — Ruit, raam of deur',
    'reparatie-elektra':      'Reparatie — Elektra of meterkast',
    'reparatie-overig':       'Reparatie — Overig',
    'sleutels':               'Sleutels & toegang',
    'klacht':                 'Klacht indienen',
    'contact':                'Contact opnemen',
    'contract-kopie':         'Kopie huurcontract opvragen',
    'contract-opzeggen':      'Huurovereenkomst opzeggen',
    'contract-adres':         'Adreswijziging doorgeven',
    'contract-medehuurder':   'Medehuurder toevoegen',
    'contract-vraag':         'Vraag over huurcontract',
    'betaling-factuur':       'Factuur of betaalbewijs opvragen',
    'betaling-methode':       'Betaalmethode wijzigen',
    'betaling-regeling':      'Betalingsregeling aanvragen',
    'betaling-aanmaning-form':'Aanmaning melden',
    'betaling-vraag':         'Vraag over betaling of facturen',
}

FIELD_LABELS = {
    'naam':          'Naam',
    'email':         'E-mail',
    'telefoon':      'Telefoon',
    'adres':         'Adres woning',
    'urgentie':      'Urgentie',
    'type_aanvraag':    'Soort aanvraag',
    'factuurnummer':    'Factuurnummer',
    'einddatum':        'Gewenste einddatum',
    'nieuw_adres':      'Nieuw adres',
    'ingangsdatum':     'Ingangsdatum',
    'naam_medehuurder': 'Naam medehuurder',
    'huidig_iban':      'Huidig rekeningnummer',
    'nieuw_iban':       'Nieuw rekeningnummer',
    'betaaldatum':      'Datum betaling',
    'bedrag':           'Betaald bedrag',
    'bericht':          'Bericht',
}

FIELD_ORDER = ['naam', 'email', 'telefoon', 'adres', 'urgentie', 'type_aanvraag',
               'factuurnummer', 'einddatum', 'nieuw_adres', 'ingangsdatum',
               'naam_medehuurder', 'huidig_iban', 'nieuw_iban',
               'betaaldatum', 'bedrag', 'bericht']


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/inschrijven')
def inschrijven():
    return render_template('inschrijven.html')


REPAIR_CATEGORIES = {
    'verwarming': {
        'title': 'CV-ketel of verwarming melden',
        'note': 'Heeft u helemaal geen verwarming of warm water? Bel direct onze spoedlijn: <strong><a href="tel:0854011736" style="color:inherit">085&nbsp;401&nbsp;1736</a></strong> (24/7 bereikbaar).',
        'contact_optional': True,
        'fields': [
            {'id': 'naam',     'label': 'Naam',                    'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',              'type': 'email',    'required': False, 'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',           'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning',      'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'urgentie', 'label': 'Urgentie',                 'type': 'select',   'required': True,
             'options': ['Normaal — binnen enkele werkdagen', 'Spoed — geen verwarming of warm water']},
            {'id': 'bericht',  'label': 'Omschrijf het probleem',   'type': 'textarea', 'required': True,
             'placeholder': 'Bijv: ketel geeft foutcode E5, display knippert, geen warm water meer...'},
        ],
    },
    'lekkage': {
        'title': 'Lekkage of wateroverlast melden',
        'note': 'Bij actieve lekkage die direct schade veroorzaakt: bel direct <strong><a href="tel:0854011736" style="color:inherit">085&nbsp;401&nbsp;1736</a></strong> (24/7).',
        'contact_optional': True,
        'fields': [
            {'id': 'naam',     'label': 'Naam',                    'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',              'type': 'email',    'required': False, 'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',           'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning',      'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'urgentie', 'label': 'Urgentie',                 'type': 'select',   'required': True,
             'options': ['Normaal — druppelende lekkage, watervlek', 'Spoed — actieve lekkage of wateroverlast']},
            {'id': 'bericht',  'label': 'Omschrijf het probleem',   'type': 'textarea', 'required': True,
             'placeholder': 'Bijv: waterlek in het plafond van de badkamer, vlak bij de lamp...'},
        ],
    },
    'schimmel': {
        'title': 'Schimmel of vochtproblemen melden',
        'note': None,
        'contact_optional': False,
        'fields': [
            {'id': 'naam',     'label': 'Naam',                    'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',              'type': 'email',    'required': True,  'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',           'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning',      'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'bericht',  'label': 'Omschrijf het probleem',   'type': 'textarea', 'required': True,
             'placeholder': 'Bijv: schimmel op de slaapkamermuur, vochtige plekken op het plafond...'},
        ],
    },
    'raam': {
        'title': 'Kapotte ruit, raam of deur melden',
        'note': None,
        'contact_optional': True,
        'fields': [
            {'id': 'naam',     'label': 'Naam',                    'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',              'type': 'email',    'required': False, 'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',           'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning',      'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'urgentie', 'label': 'Urgentie',                 'type': 'select',   'required': True,
             'options': ['Normaal — klem, beschadigd of tocht', 'Spoed — gebarsten ruit of deur sluit niet af']},
            {'id': 'bericht',  'label': 'Omschrijf het probleem',   'type': 'textarea', 'required': True,
             'placeholder': 'Bijv: slaapkamerraam sluit niet meer, kozijn verrot, buitendeur sluit niet af...'},
        ],
    },
    'elektra': {
        'title': 'Elektra of meterkast melden',
        'note': 'Ruikt u brandlucht of ziet u vonken? Bel direct <strong><a href="tel:0854011736" style="color:inherit">085&nbsp;401&nbsp;1736</a></strong> en schakel de stroom uit.',
        'contact_optional': False,
        'fields': [
            {'id': 'naam',     'label': 'Naam',                    'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',              'type': 'email',    'required': True,  'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',           'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning',      'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'bericht',  'label': 'Omschrijf het probleem',   'type': 'textarea', 'required': True,
             'placeholder': 'Bijv: groep 3 valt steeds uit als ik de magnetron aanzet...'},
        ],
    },
    'overig': {
        'title': 'Overige reparatie melden',
        'note': None,
        'contact_optional': True,
        'fields': [
            {'id': 'naam',     'label': 'Naam',                    'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',              'type': 'email',    'required': False, 'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',           'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning',      'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'urgentie', 'label': 'Urgentie',                 'type': 'select',   'required': True,
             'options': ['Normaal — binnen enkele werkdagen', 'Spoed — zo snel mogelijk']},
            {'id': 'bericht',  'label': 'Omschrijf het probleem',   'type': 'textarea', 'required': True,
             'placeholder': 'Beschrijf zo duidelijk mogelijk wat er aan de hand is...'},
        ],
    },
}


@app.route('/reparatie')
def reparatie_page():
    return render_template('reparatie.html')


@app.route('/reparatie/<slug>')
def reparatie_detail(slug):
    cat = REPAIR_CATEGORIES.get(slug)
    if not cat:
        return redirect('/reparatie')
    return render_template('reparatie_form.html', slug=slug, **cat)


@app.route('/api/contact', methods=['POST'])
def contact():
    data     = request.get_json(silent=True) or {}
    category = data.get('category', 'contact')
    fields   = {k: str(v).strip() for k, v in data.get('fields', {}).items()}

    naam     = fields.get('naam', '')
    email    = fields.get('email', '')
    telefoon = fields.get('telefoon', '')
    bericht  = fields.get('bericht', '')

    if not naam or not bericht:
        return jsonify({'ok': False, 'error': 'Vul alle verplichte velden in.'}), 400
    if not email and not telefoon:
        return jsonify({'ok': False, 'error': 'Vul uw e-mailadres of telefoonnummer in.'}), 400

    category_label = CATEGORY_LABELS.get(category, category)
    timestamp      = datetime.now().strftime('%d-%m-%Y %H:%M')

    # ── E-mail body ──────────────────────────────────────────────────────────
    lines = [
        'Nieuw contactformulier via dok74verhuur.nl',
        '',
        f'Categorie : {category_label}',
        f'Datum/tijd: {timestamp}',
        '',
    ]
    for key in FIELD_ORDER:
        val = fields.get(key, '')
        if val:
            lines.append(f'{FIELD_LABELS.get(key, key)}: {val}')
    for key, val in fields.items():
        if key not in FIELD_ORDER and val:
            lines.append(f'{key}: {val}')
    email_body = '\n'.join(lines)

    errors = []

    # ── SendGrid ─────────────────────────────────────────────────────────────
    if SENDGRID_API_KEY:
        try:
            sg  = SendGridAPIClient(SENDGRID_API_KEY)
            msg = Mail(
                from_email=FROM_EMAIL,
                to_emails=TO_EMAIL,
                subject=f'[DOK74] {category_label} — {naam}',
                plain_text_content=email_body,
            )
            sg.send(msg)
        except Exception as exc:
            errors.append(f'mail: {exc}')
    else:
        print('[contact] SENDGRID_API_KEY niet ingesteld — e-mail overgeslagen')

    # ── Airtable ─────────────────────────────────────────────────────────────
    if AIRTABLE_API_KEY and AIRTABLE_BASE_ID:
        extra = [
            f'{FIELD_LABELS.get(k, k)}: {v}'
            for k, v in fields.items()
            if k not in ('naam', 'email', 'telefoon', 'adres', 'bericht') and v
        ]
        at_fields = {
            'Naam':      naam,
            'Categorie': category_label,
            'Datum':     timestamp,
        }
        if email:              at_fields['E-mail']   = email
        if telefoon:           at_fields['Telefoon'] = telefoon
        if fields.get('adres'):at_fields['Adres']    = fields['adres']
        if bericht:            at_fields['Bericht']  = bericht
        if extra:              at_fields['Details']  = '\n'.join(extra)

        try:
            table_enc = urllib.parse.quote(AIRTABLE_TABLE)
            resp = requests.post(
                f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_enc}',
                headers={
                    'Authorization': f'Bearer {AIRTABLE_API_KEY}',
                    'Content-Type':  'application/json',
                },
                json={'fields': at_fields},
                timeout=10,
            )
            if not resp.ok:
                errors.append(f'airtable {resp.status_code}: {resp.text[:200]}')
        except Exception as exc:
            errors.append(f'airtable: {exc}')
    else:
        print('[contact] Airtable niet geconfigureerd — opslaan overgeslagen')

    if errors:
        print(f'[contact] waarschuwingen: {errors}', flush=True)

    return jsonify({'ok': True})


@app.route('/api/inschrijven', methods=['POST'])
def api_inschrijven():
    data   = request.get_json(silent=True) or {}
    fields = {k: str(v).strip() for k, v in data.get('fields', {}).items()}

    required = ['voornaam', 'achternaam', 'email', 'telefoon', 'straat', 'huisnummer', 'postcode', 'woonplaats', 'notities']
    if any(not fields.get(f) for f in required):
        return jsonify({'ok': False, 'error': 'Vul alle verplichte velden in.'}), 400

    timestamp  = datetime.now().strftime('%d-%m-%Y %H:%M')
    naam_vol   = f"{fields.get('voornaam', '')} {fields.get('achternaam', '')}".strip()
    adres_vol  = f"{fields.get('straat', '')} {fields.get('huisnummer', '')}{' ' + fields.get('toevoeging','') if fields.get('toevoeging') else ''}, {fields.get('postcode', '')} {fields.get('woonplaats', '')}".strip()

    email_body = f"""Nieuwe inschrijving via dok74verhuur.nl

Datum/tijd : {timestamp}
Naam       : {naam_vol}
Voorletters: {fields.get('voorletters', '')}
Bedrijf    : {fields.get('bedrijf', '—')}
E-mail     : {fields.get('email', '')}
Telefoon   : {fields.get('telefoon', '')}
Adres      : {adres_vol}

Wensen / regio:
{fields.get('notities', '')}
"""

    errors = []

    if SENDGRID_API_KEY:
        try:
            sg  = SendGridAPIClient(SENDGRID_API_KEY)
            msg = Mail(
                from_email=FROM_EMAIL,
                to_emails=TO_EMAIL,
                subject=f'[DOK74] Nieuwe inschrijving — {naam_vol}',
                plain_text_content=email_body,
            )
            sg.send(msg)
        except Exception as exc:
            errors.append(f'mail: {exc}')

    if AIRTABLE_API_KEY and AIRTABLE_BASE_ID:
        at_fields = {
            'Naam':        naam_vol,
            'Voorletters': fields.get('voorletters', ''),
            'E-mail':      fields.get('email', ''),
            'Telefoon':    fields.get('telefoon', ''),
            'Adres':       adres_vol,
            'Notities':    fields.get('notities', ''),
            'Datum':       timestamp,
        }
        if fields.get('bedrijf'):
            at_fields['Bedrijf'] = fields['bedrijf']
        try:
            table_enc = urllib.parse.quote(AIRTABLE_TABLE_INSCRIP)
            resp = requests.post(
                f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_enc}',
                headers={'Authorization': f'Bearer {AIRTABLE_API_KEY}', 'Content-Type': 'application/json'},
                json={'fields': at_fields},
                timeout=10,
            )
            if not resp.ok:
                errors.append(f'airtable {resp.status_code}: {resp.text[:200]}')
        except Exception as exc:
            errors.append(f'airtable: {exc}')

    if errors:
        print(f'[inschrijven] waarschuwingen: {errors}', flush=True)

    return jsonify({'ok': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8081))
    app.run(host='0.0.0.0', port=port, debug=True)
