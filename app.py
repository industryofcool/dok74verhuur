import base64
import os
import urllib.parse
from datetime import datetime

import requests
from flask import Flask, jsonify, redirect, render_template, request
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Attachment, FileContent, FileName, FileType, Disposition, Mail

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
            {'id': 'foto',     'label': 'Foto van de foutcode op het display (optioneel)', 'type': 'file', 'required': False, 'placeholder': '', 'accept': 'image/*', 'capture': 'environment'},
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
             'options': ['Normaal — deur klemt maar gaat open, of ruit gebarsten maar niet kapot', 'Spoed — deur gaat echt niet meer open/dicht of ruit ligt eruit']},
            {'id': 'bericht',  'label': 'Omschrijf het probleem',   'type': 'textarea', 'required': True,
             'placeholder': 'Bijv: slaapkamerraam sluit niet meer, kozijn verrot, buitendeur sluit niet af...'},
            {'id': 'foto',     'label': 'Foto van de schade (optioneel)', 'type': 'file', 'required': False, 'placeholder': '', 'accept': 'image/*', 'capture': 'environment'},
        ],
    },
    'elektra': {
        'title': 'Elektra of meterkast melden',
        'note': 'Is er brand of rookontwikkeling? Bel dan <strong>direct 112</strong>. In alle andere gevallen kunt u onderstaand formulier invullen.',
        'intro': '<h3>Eerst zelf checken: valt een groep uit?</h3><p>Valt een groep in de meterkast steeds uit, dan wordt dit in veruit de meeste gevallen veroorzaakt door een <strong>defect apparaat</strong> dat kortsluiting maakt. Loop onderstaande checklist langs voordat u een melding indient &mdash; als u het probleem hiermee kunt oplossen, scheelt dat voor u en voor ons tijd en kosten.</p><p><strong>Checklist — zo spoort u een defect apparaat op:</strong></p><ol><li>Zet de uitgeschakelde groep of aardlekschakelaar weer aan.</li><li>Haal <strong>alle stekkers</strong> uit de stopcontacten van die groep (denk aan waterkoker, oven, magnetron, wasmachine, droger, koelkast, tv, laders, enz.).</li><li>Valt de groep nu nog steeds uit zonder dat er apparaten aan hangen? Dan ligt het probleem waarschijnlijk aan de installatie &mdash; vul het formulier in.</li><li>Blijft de groep aan? Steek dan &eacute;&eacute;n voor &eacute;&eacute;n de apparaten terug en kijk welk apparaat de storing veroorzaakt.</li><li>Het apparaat dat de groep doet uitvallen is defect en maakt kortsluiting. Dit apparaat is uw eigen verantwoordelijkheid &mdash; DOK74 Verhuur kan hier niets aan doen.</li></ol><p>Komt u er niet uit, of ligt het probleem aan de installatie zelf (bijvoorbeeld een stopcontact dat niet werkt of een defecte groep zonder aangesloten apparaten)? Vul dan het formulier hieronder in.</p>',
        'contact_optional': False,
        'fields': [
            {'id': 'naam',     'label': 'Naam',                    'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',              'type': 'email',    'required': True,  'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',           'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning',      'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'bericht',  'label': 'Omschrijf het probleem',   'type': 'textarea', 'required': True,
             'placeholder': 'Bijv: groep 3 valt steeds uit, stopcontact in de keuken werkt niet...'},
        ],
    },
    'afvoer': {
        'title': 'Verstopte afvoer melden',
        'note': None,
        'intro': 'Heeft u last van een verstopte riolering, afvoer, dakgoot of ander rioolprobleem? Vul het formulier in en omschrijf duidelijk waar het probleem zit en wat er aan de hand is. Hoe meer informatie u ons geeft, hoe sneller wij u kunnen helpen.',
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
            {'id': 'foto',     'label': 'Foto ter verduidelijking (optioneel)', 'type': 'file', 'required': False, 'placeholder': '', 'accept': 'image/*', 'capture': 'environment'},
        ],
    },
    'kookapparatuur': {
        'title': 'Problemen met kookapparatuur melden',
        'note': None,
        'intro': '<h3>Eerst zelf checken: gebruikt u de juiste pannen?</h3><p>In veruit de meeste gevallen waarin een inductiekookplaat "niet werkt", blijkt de kookplaat zelf helemaal in orde te zijn &mdash; maar worden er <strong>verkeerde pannen</strong> gebruikt. Een inductiekookplaat werkt alleen met pannen die geschikt zijn voor inductie.</p><p><strong>Hoe test u of uw pannen geschikt zijn?</strong></p><ul><li>Houd een magneet tegen de bodem van de pan. Blijft de magneet plakken? Dan is de pan geschikt voor inductie.</li><li>Blijft de magneet niet plakken? Dan is de pan <strong>niet geschikt</strong> en werkt hij niet op een inductieplaat.</li><li>Let ook op de diameter: te kleine pannen (kleiner dan de kookzone) worden soms niet herkend door de plaat.</li></ul><p><strong>Let op:</strong> pannen van aluminium, koper, glas of oud roestvrij staal werken meestal niet op inductie. Ook sommige "RVS"-pannen zijn niet geschikt. Weet u zeker dat uw pannen wél geschikt zijn? Vul dan het formulier in.</p>',
        'contact_optional': False,
        'fields': [
            {'id': 'naam',     'label': 'Naam',                  'type': 'text',     'required': True,  'placeholder': 'Uw volledige naam'},
            {'id': 'email',    'label': 'E-mailadres',            'type': 'email',    'required': True,  'placeholder': 'u@voorbeeld.nl'},
            {'id': 'telefoon', 'label': 'Telefoonnummer',         'type': 'tel',      'required': False, 'placeholder': '06 12345678'},
            {'id': 'adres',    'label': 'Adres van uw woning',    'type': 'text',     'required': True,  'placeholder': 'Straatnaam 74, Rotterdam'},
            {'id': 'bericht',  'label': 'Omschrijf het probleem', 'type': 'textarea', 'required': True,
             'placeholder': 'Bijv: kookzone links voor wordt niet warm, display geeft foutcode, kookplaat start niet...'},
            {'id': 'foto',     'label': 'Foto van het probleem of foutcode (optioneel)', 'type': 'file', 'required': False, 'placeholder': '', 'accept': 'image/*', 'capture': 'environment'},
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
        'intro': 'Extra sleutel nodig, sleutel kwijt of pas defect? Vul het formulier in en wij nemen zo snel mogelijk contact met u op.<br><br><strong>Let op:</strong> voor het aanmaken van een extra sleutel of het vervangen van een sleutel worden kosten in rekening gebracht.',
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


@app.route('/reparatie/schimmel')
def reparatie_schimmel():
    return render_template('info.html',
        title='Schimmel of vochtproblemen',
        back_url='/reparatie',
        contact_url='/formulier/contact',
        content="""
        <h3>Wat is de oorzaak van schimmel?</h3>
        <p>Schimmel in huis ontstaat bijna altijd door <strong>te veel vocht in combinatie met te weinig ventilatie</strong>. In de meeste woningen ligt de oorzaak dus niet bij een bouwkundig gebrek, maar bij hoe er met vocht en lucht wordt omgegaan.</p>

        <div class="info-box">
          <strong>Let op:</strong> wordt de schimmel veroorzaakt door een <strong>lekkage</strong> (bijvoorbeeld een natte plek op het plafond onder de badkamer)? Meld dit dan via de <a href="/reparatie/lekkage" style="color:var(--yellow-dark);font-weight:600">lekkage-pagina</a>. Wij komen dat graag voor u oplossen.
        </div>

        <h3>Waarom ontstaat er vocht in huis?</h3>
        <p>Een gemiddeld gezin produceert per dag <strong>10 tot 15 liter vocht</strong>:</p>
        <ul>
          <li>Ademen en transpireren (ongeveer 1 liter per persoon per dag)</li>
          <li>Douchen en baden</li>
          <li>Koken, afwassen en thee- of koffiezetten</li>
          <li>Was drogen (vooral binnen drogen!)</li>
          <li>Kamer- en buitenplanten</li>
          <li>Huisdieren</li>
        </ul>
        <p>Dit vocht moet ergens heen. Kan het niet naar buiten, dan slaat het neer op koudere oppervlakken &mdash; ramen, hoeken, achter meubels &mdash; en daar krijgt schimmel alle kans om te groeien.</p>

        <h3>Ventileren: 24 uur per dag, het hele jaar door</h3>
        <p>Ventileren is <strong>niet hetzelfde als luchten</strong>. Ventileren betekent dat er continu een klein beetje frisse lucht binnenkomt, 24 uur per dag, 7 dagen per week &mdash; ook in de winter.</p>
        <ul>
          <li><strong>Zet roosters open</strong> in ramen, deuren en muren. Deze zijn bedoeld om open te staan.</li>
          <li><strong>Laat mechanische ventilatie aan staan</strong>, ook 's nachts en als u weg bent. Zet hem op de hoogste stand tijdens koken en douchen.</li>
          <li><strong>Sluit binnendeuren niet helemaal af</strong> &mdash; zorg dat lucht vrij kan stromen tussen kamers.</li>
        </ul>

        <h3>Luchten: kort maar krachtig</h3>
        <p>Naast ventileren is het verstandig om dagelijks even te luchten: zet ramen en deuren <strong>10 à 15 minuten wijd open</strong> (liefst tegenover elkaar voor doorstroming). Dit voert snel veel vocht en vieze lucht af.</p>

        <h3>Extra tips om schimmel te voorkomen</h3>
        <ul>
          <li><strong>Sluit de badkamerdeur</strong> tijdens en na het douchen. Zet het ventilatierooster of de mechanische ventilatie op de hoogste stand.</li>
          <li><strong>Droog de douche en badkamer na</strong> met een trekker of doek &mdash; dat scheelt enorm.</li>
          <li><strong>Was binnen drogen? Altijd in een goed geventileerde ruimte</strong>, liefst met raam open. Nooit in de slaapkamer.</li>
          <li><strong>Dek pannen af</strong> tijdens het koken en zet de afzuigkap aan.</li>
          <li><strong>Zet meubels niet pal tegen buitenmuren</strong>. Houd minimaal 5 cm ruimte zodat de lucht achter kasten kan stromen.</li>
          <li><strong>Stook voldoende</strong>. Een koude woning vangt sneller vocht dan een goed verwarmde woning. Zet in ongebruikte kamers de verwarming niet helemaal uit.</li>
        </ul>

        <h3>Heeft u al schimmel?</h3>
        <p>Kleine schimmelplekken kunt u zelf verwijderen met schimmelverwijderaar of een oplossing van water met een beetje chloor of soda. Draag handschoenen en zorg voor ventilatie tijdens het schoonmaken. Pak de <strong>oorzaak</strong> aan door beter te ventileren, anders komt de schimmel gegarandeerd terug.</p>

        <p>Heeft u beter geventileerd en blijft het probleem terugkomen, of is de schimmelplek groot en diep in de muur doorgedrongen? Neem dan contact met ons op.</p>
        """)


@app.route('/storingen/water')
def storingen_water():
    return render_template('info.html',
        title='Geen water',
        back_url='/storingen',
        contact_url=None,
        content="""
        <h3>Heeft u geen water?</h3>
        <p>Waterstoringen worden niet door DOK74 Verhuur verholpen, maar door het waterleidingbedrijf van uw regio. Wij hebben hier geen invloed op.</p>

        <div class="info-box">
          Ga naar <strong><a href="https://www.waterstoring.nl" target="_blank" rel="noopener" style="color:var(--yellow-dark)">waterstoring.nl</a></strong> om te kijken of de storing al bekend is. Staat uw storing er niet tussen? Dan kunt u hem daar direct zelf melden bij het waterleidingbedrijf.
        </div>

        <h3>Wat kunt u zelf controleren?</h3>
        <ul>
          <li>Staat de hoofdkraan in uw woning open?</li>
          <li>Hebben uw buren ook geen water? Dan is er waarschijnlijk een storing in de wijk.</li>
          <li>Heeft u alleen geen warm water? Dan ligt het probleem meestal bij de CV-ketel of warmtepomp &mdash; meld dat via de <a href="/reparatie/verwarming" style="color:var(--yellow-dark);font-weight:600">CV-ketel pagina</a>.</li>
        </ul>

        <p>Is er een lekkage? Draai dan eerst de hoofdkraan dicht en meld het via de <a href="/reparatie/lekkage" style="color:var(--yellow-dark);font-weight:600">lekkage-pagina</a>.</p>
        """)


@app.route('/storingen/gas-stroom')
def storingen_gas_stroom():
    return render_template('info.html',
        title='Geen gas of stroom',
        back_url='/storingen',
        contact_url=None,
        content="""
        <h3>Heeft u geen gas of stroom?</h3>
        <p>Gas- en stroomstoringen worden niet door DOK74 Verhuur verholpen, maar door de netbeheerder van uw regio. Wij hebben hier geen invloed op.</p>

        <div class="info-box">
          <strong>Eerst zelf controleren!</strong> Zit het probleem misschien in uw eigen woning? Loop de checklist hieronder door voordat u een storing meldt.
        </div>

        <h3>Checklist: ligt het probleem in uw eigen woning?</h3>
        <ol>
          <li><strong>Kijk in de meterkast.</strong> Staat er een schakelaar (groep of aardlekschakelaar) in de onderste stand? Zet hem weer omhoog.</li>
          <li><strong>Valt hij direct weer uit?</strong> Dan maakt waarschijnlijk een defect apparaat kortsluiting. Haal alle stekkers uit de stopcontacten van die groep en probeer opnieuw. Steek daarna &eacute;&eacute;n voor &eacute;&eacute;n de apparaten terug om te kijken welk apparaat het probleem veroorzaakt. Dit apparaat is uw eigen verantwoordelijkheid.</li>
          <li><strong>Hebben uw buren ook geen stroom of gas?</strong> Dan is er waarschijnlijk een storing in de wijk of straat &mdash; die moet gemeld worden bij de netbeheerder.</li>
        </ol>

        <h3>Storing bij de netbeheerder?</h3>
        <p>Is uw meterkast in orde en hebben uw buren ook last, of is er duidelijk sprake van een storing buiten uw woning?</p>

        <div class="info-box">
          Ga naar <strong><a href="https://www.gasenstroomstoringen.nl" target="_blank" rel="noopener" style="color:var(--yellow-dark)">gasenstroomstoringen.nl</a></strong> om te kijken of de storing al bekend is. Staat uw storing er niet tussen? Dan kunt u hem daar direct zelf melden bij de netbeheerder.
        </div>

        <p><strong>Bij gaslucht in huis:</strong> sluit de hoofdkraan van het gas, maak geen vuur, gebruik geen elektrische schakelaars en bel <strong>direct 0800-9009</strong> (Nationaal Storingsnummer Gas).</p>

        <p>Is er een probleem met de elektra-installatie in uw woning zelf (bijvoorbeeld een groep die blijft uitvallen zonder dat er apparaten aan hangen)? Meld dat via de <a href="/reparatie/elektra" style="color:var(--yellow-dark);font-weight:600">elektra-pagina</a>.</p>
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
    files    = data.get('files', {}) or {}  # {field_id: {name, type, size, base64}}

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
    if files:
        lines.append('')
        lines.append('Bijlagen:')
        for fid, finfo in files.items():
            if isinstance(finfo, dict) and finfo.get('name'):
                lines.append(f'  - {finfo["name"]} ({finfo.get("type", "?")}, {finfo.get("size", 0)} bytes)')
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
            for field_id, finfo in files.items():
                if not isinstance(finfo, dict) or not finfo.get('base64'):
                    continue
                attachment = Attachment()
                attachment.file_content = FileContent(finfo['base64'])
                attachment.file_type    = FileType(finfo.get('type') or 'application/octet-stream')
                attachment.file_name    = FileName(finfo.get('name') or f'{field_id}.bin')
                attachment.disposition  = Disposition('attachment')
                msg.add_attachment(attachment)
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

Datum/tijd     : {timestamp}
Naam           : {naam_vol}
Voorletters    : {fields.get('voorletters', '')}
Bedrijf        : {fields.get('bedrijf', '—')}
E-mail         : {fields.get('email', '')}
Telefoon       : {fields.get('telefoon', '')}
Adres          : {adres_vol}
Voorkeursplaats: {fields.get('voorkeur_plaats', '')}
Afstand (km)   : {fields.get('afstand_km', '—')}
Slaapkamers    : {fields.get('slaapkamers', '—')}
Herkomst       : {fields.get('herkomst', '')}

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
