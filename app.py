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
    'reparatie-afvoer':       'Reparatie — Verstopte afvoer',
    'reparatie-overig':       'Reparatie — Overig',
    'sleutels':               'Sleutels & toegang',
    'klacht':                 'Laat ons weten hoe het beter kan',
    'overlast':               'Overlast melden',
    'storing-water':          'Storing — Geen water',
    'storing-stroom':         'Storing — Geen stroom',
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
        'note': 'Heeft u helemaal geen verwarming of warm water? Bel ons de volgende werkdag: <strong><a href="tel:0854011736" style="color:inherit">085&nbsp;401&nbsp;1736</a></strong> (bereikbaar tijdens kantooruren).',
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
        'note': 'Bij lekkage aan de waterleiding: draai altijd eerst de hoofdkraan dicht. Bij actieve lekkage die direct schade veroorzaakt: bel direct <strong><a href="tel:0854011736" style="color:inherit">085&nbsp;401&nbsp;1736</a></strong>.',
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
    'afvoer': {
        'title': 'Verstopte afvoer melden',
        'note': None,
        'contact_optional': True,
        'fields': [
            {'id': 'naam',     'label': 'Naam',                    'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',              'type': 'email',    'required': False, 'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',           'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning',      'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'bericht',  'label': 'Omschrijf het probleem',   'type': 'textarea', 'required': True,
             'placeholder': 'Bijv: verstopte gootsteen in de keuken, water loopt niet weg via de douche, verstopte dakgoot...'},
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


CONTACT_FORMS = {
    'sleutels': {
        'title': 'Sleutels & toegang',
        'category': 'sleutels',
        'back_url': '/',
        'button_text': 'Aanvraag versturen',
        'contact_optional': True,
        'intro': 'Extra sleutel nodig, sleutel kwijt of pas defect? Vul het formulier in en wij nemen zo snel mogelijk contact met u op.',
        'fields': [
            {'id': 'naam',          'label': 'Naam',               'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',         'label': 'E-mailadres',         'type': 'email',    'required': False, 'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon',      'label': 'Telefoonnummer',      'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',         'label': 'Adres van uw woning', 'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'type_aanvraag', 'label': 'Soort aanvraag',      'type': 'select',   'required': True,
             'options': ['Extra sleutel aanvragen', 'Sleutel kwijt / verloren', 'Toegangspas defect', 'Anders']},
            {'id': 'bericht',       'label': 'Toelichting',         'type': 'textarea', 'required': True,  'placeholder': 'Aanvullende informatie...'},
        ],
    },
    'klacht': {
        'title': 'Laat ons weten hoe het beter kan',
        'category': 'klacht',
        'back_url': '/',
        'button_text': 'Bericht versturen',
        'contact_optional': False,
        'intro': 'Wij willen graag weten wat er beter kan. Uw feedback helpt ons om onze dienstverlening te verbeteren.',
        'fields': [
            {'id': 'naam',     'label': 'Naam',               'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',         'type': 'email',    'required': True,  'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',      'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning', 'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'bericht',  'label': 'Omschrijf uw feedback', 'type': 'textarea', 'required': True, 'placeholder': 'Vertel ons wat er beter kan...'},
        ],
    },
    'contact': {
        'title': 'Contact opnemen',
        'category': 'contact',
        'back_url': '/',
        'button_text': 'Bericht versturen',
        'contact_optional': True,
        'fields': [
            {'id': 'naam',     'label': 'Naam',                                        'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',                                  'type': 'email',    'required': False, 'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',                               'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning (indien van toepassing)',   'type': 'text',     'required': False, 'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'bericht',  'label': 'Uw bericht',                                   'type': 'textarea', 'required': True,  'placeholder': 'Hoe kunnen wij u helpen?'},
        ],
    },
    'contract-opzeggen': {
        'title': 'Huuropzegging verzoek indienen',
        'category': 'contract-opzeggen',
        'back_url': '/',
        'button_text': 'Opzegging indienen',
        'contact_optional': False,
        'intro': '<p>Elk huurcontract heeft zijn eigen opzegtermijn. Raadpleeg uw huurovereenkomst voor de exacte voorwaarden.</p><h3>Hoe werkt het?</h3><p><strong>Stap 1 — Huur opzeggen</strong><br>We raden aan om de huur zo vroeg mogelijk op te zeggen. Hierdoor is de kans groter dat er een nieuwe huurder bekend is als u vertrekt. Met de nieuwe huurder kunt u onderling overnames regelen. Wij spelen geen actieve rol in de afspraken die huurders onderling maken over de overname.</p><p><strong>Stap 2 — Voor- en eindinspectie</strong><br>Bij de voorinspectie bekijken we of het huis in goede staat is en of er veranderingen zijn aangebracht. We geven aan hoe de woning opgeleverd moet worden. De voorinspectie wordt binnen 8 werkdagen na ontvangst van de huuropzegging ingepland. Bij de eindinspectie controleren we of de woning volgens afspraak is opgeleverd.</p><p><strong>Stap 3 — Nieuwe bewoners en overname</strong><br>Overname van spullen is alleen mogelijk als er een nieuwe huurder bekend is. Bij het opzeggen van de huur ontvangt u een formulier waarop u afspraken over de overname kunt vastleggen met de nieuwe huurder.<br><em>Let op: levert u geen overnameformulier in? Dan gaan wij ervan uit dat er niets wordt overgenomen.</em></p><p><strong>Stap 4 — Sleutels inleveren</strong><br>De einddatum van de huur staat in de bevestiging die u van ons krijgt. Hierin staat ook waar en wanneer u de sleutels moet inleveren.</p><p><strong>Stap 5 — Eindrekening</strong><br>Nadat u de sleutels hebt ingeleverd, ontvangt u van ons een eindafrekening binnen 8 werkdagen. Hierin ziet u of wij nog geld van u krijgen of u van ons. Eventuele reparatiekosten worden verrekend als de woning niet is achtergelaten zoals afgesproken bij de voorinspectie. Bij woningen met servicekosten ontvangt u nog een aparte afrekening voor de stook- en/of servicekosten.</p>',
        'fields': [
            {'id': 'naam',      'label': 'Naam',                  'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',     'label': 'E-mailadres',            'type': 'email',    'required': True,  'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon',  'label': 'Telefoonnummer',         'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',     'label': 'Adres van uw woning',    'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'einddatum', 'label': 'Gewenste einddatum',     'type': 'date',     'required': True,  'placeholder': ''},
            {'id': 'bericht',   'label': 'Aanvullende toelichting', 'type': 'textarea', 'required': False, 'placeholder': 'Optionele toelichting...'},
        ],
    },
    'contract-vraag': {
        'title': 'Vraag over uw huurcontract',
        'category': 'contract-vraag',
        'back_url': '/',
        'button_text': 'Vraag versturen',
        'contact_optional': False,
        'fields': [
            {'id': 'naam',     'label': 'Naam',               'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',         'type': 'email',    'required': True,  'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',      'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning', 'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'bericht',  'label': 'Uw vraag',            'type': 'textarea', 'required': True,  'placeholder': 'Waar kunnen wij u mee helpen?'},
        ],
    },
    'contract-medehuurder': {
        'title': 'Verzoek tot medehuurder',
        'category': 'contract-medehuurder',
        'back_url': '/',
        'button_text': 'Verzoek indienen',
        'contact_optional': False,
        'intro': 'Om een medehuurder toe te voegen hebben wij nodig:<ul style="margin:6px 0 0 16px;line-height:1.8"><li>Kopie geldig identiteitsbewijs van de medehuurder</li><li>Inkomensverklaring of werkgeversverklaring</li></ul><br>Dien uw verzoek in via dit formulier. Wij nemen contact op over de verdere procedure.',
        'fields': [
            {'id': 'naam',             'label': 'Uw naam',                'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',            'label': 'E-mailadres',             'type': 'email',    'required': True,  'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon',         'label': 'Telefoonnummer',          'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',            'label': 'Adres van de woning',     'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'naam_medehuurder', 'label': 'Naam medehuurder',        'type': 'text',     'required': True,  'placeholder': 'Volledige naam medehuurder'},
            {'id': 'bericht',          'label': 'Aanvullende informatie',  'type': 'textarea', 'required': False, 'placeholder': 'Eventuele toelichting...'},
        ],
    },
    'overlast': {
        'title': 'Overlast melden',
        'category': 'overlast',
        'back_url': '/',
        'button_text': 'Melding versturen',
        'contact_optional': False,
        'intro': 'Klachten over overlast van buren kunt u bij ons melden. Omschrijf de situatie zo duidelijk mogelijk zodat wij u kunnen helpen.',
        'fields': [
            {'id': 'naam',     'label': 'Naam',               'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',         'type': 'email',    'required': True,  'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',      'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning', 'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'bericht',  'label': 'Omschrijf de overlast', 'type': 'textarea', 'required': True, 'placeholder': 'Wat is er aan de hand, wanneer speelt het, wie betreft het...'},
        ],
    },
    'storing-water': {
        'title': 'Geen water melden',
        'category': 'storing-water',
        'back_url': '/storingen',
        'button_text': 'Melding versturen',
        'contact_optional': True,
        'fields': [
            {'id': 'naam',     'label': 'Naam',                  'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',            'type': 'email',    'required': False, 'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',         'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning',    'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'bericht',  'label': 'Omschrijf het probleem', 'type': 'textarea', 'required': True,  'placeholder': 'Bijv: helemaal geen water, alleen koud water, lage druk...'},
        ],
    },
    'storing-stroom': {
        'title': 'Geen stroom melden',
        'category': 'storing-stroom',
        'back_url': '/storingen',
        'button_text': 'Melding versturen',
        'contact_optional': True,
        'note': 'Controleer eerst uw meterkast. Staat een schakelaar naar beneden? Zet deze weer omhoog. Valt hij opnieuw uit, dan is er mogelijk een kortsluiting.',
        'fields': [
            {'id': 'naam',     'label': 'Naam',                  'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',            'type': 'email',    'required': False, 'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',         'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning',    'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'bericht',  'label': 'Omschrijf het probleem', 'type': 'textarea', 'required': True,  'placeholder': 'Bijv: hele woning geen stroom, groep valt steeds uit...'},
        ],
    },
}


@app.route('/formulier/<slug>')
def formulier(slug):
    form = CONTACT_FORMS.get(slug)
    if not form:
        return redirect('/')
    return render_template('formulier.html', **form)


@app.route('/contact')
def contact_page():
    return render_template('contact.html')


@app.route('/info/huisregels')
def info_huisregels():
    return render_template('info.html',
        title='Huisregels & afspraken',
        back_url='/',
        contact_url='/formulier/contract-vraag',
        content="""
        <p>Voor een prettige woonomgeving gelden de volgende regels:</p>
        <ul>
            <li><strong>Geluidsoverlast:</strong> Vermijd geluidsoverlast tussen 22:00 en 08:00.</li>
            <li><strong>Gemeenschappelijke ruimtes:</strong> Gangen, trappenhuizen en bergingen dienen vrij te blijven van privéspullen.</li>
            <li><strong>Huisdieren:</strong> Alleen toegestaan met schriftelijke toestemming van DOK74 Verhuur.</li>
            <li><strong>Verbouwingen:</strong> Aanpassingen aan de woning vereisen altijd schriftelijke toestemming.</li>
            <li><strong>Onderverhuur:</strong> Geheel of gedeeltelijk onderverhuren is niet toegestaan zonder toestemming.</li>
            <li><strong>Afval:</strong> Scheid uw afval en gebruik de daarvoor bestemde containers.</li>
            <li><strong>Roken:</strong> In gemeenschappelijke ruimtes is roken niet toegestaan.</li>
            <li><strong>Overlast:</strong> Klachten over overlast van buren kunt u bij ons melden.</li>
            <li><strong>Internet &amp; data:</strong> De internetaansluiting en het contract met een provider is de verantwoordelijkheid van de huurder, niet van de verhuurder.</li>
        </ul>
        <p>Het volledige huishoudelijk reglement staat in uw huurpakket.</p>
        """)


@app.route('/info/looptijd')
def info_looptijd():
    return render_template('info.html',
        title='Looptijd & verlenging contract',
        back_url='/',
        contact_url='/formulier/contract-vraag',
        content="""
        <p>Wilt u weten wat de looptijd of opzegtermijn van uw huurcontract is, of wanneer uw contract afloopt? Vraag het op via onderstaande knop &mdash; wij informeren u zo snel mogelijk.</p>
        """)


@app.route('/storingen')
def storingen():
    return render_template('storingen.html')


@app.route('/storingen/internet')
def storingen_internet():
    return render_template('storingen_internet.html')


@app.route('/landing')
def landing():
    return render_template('landing.html')


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
