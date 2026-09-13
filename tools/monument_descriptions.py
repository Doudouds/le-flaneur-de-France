"""Source-preserving descriptions and deterministic factual POP summaries."""
import re

SYNTHESIS_SOURCE = 'Synthèse rédigée à partir des informations POP / Mérimée'

def clean(value):
    return re.sub(r'\s+', ' ', value or '').strip(' ;')

def sentence(value):
    value = clean(value)
    return value if value.endswith(('.', '!', '?')) else value + '.'

def pop_summary(monument, row):
    """Compose only documented facts; preserve uncertainty and attribution wording."""
    name = clean(monument['name'])
    commune = clean(monument.get('commune', '')).replace(';', ', ')
    department = clean(monument.get('departmentName', ''))
    location = ', '.join(value for value in (commune, department) if value)
    parts = [sentence(f'« {name} » est recensé dans la base Mérimée' + (f' à {location}' if location else '') + f" sous la référence {monument['reference']}")]
    fields = [
        ('Dénomination', monument.get('category')),
        ('Période de construction indiquée', monument.get('period') or row.get('Datation_de_l_edifice')),
        ('Auteurs mentionnés', row.get('Auteur_de_l_edifice')),
        ('Éléments remarquables signalés', row.get('Elements_remarquables_dans_l_edifice')),
        ('Matériaux du gros œuvre', row.get('Materiaux_du_gros_oeuvre')),
        ('État de conservation signalé', row.get('etat_de_conservation')),
        ('Protection au titre des monuments historiques', monument.get('protectionDates') or monument.get('protection')),
    ]
    for label, value in fields:
        if clean(value): parts.append(sentence(label + ' : ' + clean(value).replace(';', ' ; ')))
    # Protection scope can identify the surviving parts when architectural prose
    # is absent. Preserve the official statement instead of inferring accessibility.
    details = clean(monument.get('protectionDetails'))
    if details and len(details) <= 900: parts.append(sentence('La notice précise les éléments protégés : ' + details))
    return ' '.join(parts)

def enrich_description(monument, wikipedia, fallback):
    page = wikipedia.get('page', {})
    if wikipedia.get('method') == 'wikidata:P380-exact' and not page:
        monument['wikipediaUrl'] = wikipedia['url']
    if page.get('valid') and page.get('url'):
        monument['wikipediaUrl'] = page['url']
    description = monument['description'].strip()
    # Historical synthetic POP entries are not an architectural description and
    # should give way to the actual article now available.
    legacy_summary = description.startswith('La notice POP identifie ce monument')
    source = monument['descriptionSource']
    if page.get('valid') and page.get('extract') and (not description or legacy_summary or source in ('Wikipédia', 'Wikidata', 'OpenStreetMap')):
        monument['description'] = page['extract']
        monument['descriptionSource'] = (f"Wikipédia — « {page['title']} » — contributeurs, CC BY-SA 4.0"
            + (f" — version {page['revision']}" if page.get('revision') else ''))
    elif not description and monument['history'].strip():
        monument['description'] = monument['history']
        monument['descriptionSource'] = monument['historySource']
    elif not description or legacy_summary:
        monument['description'] = fallback
        monument['descriptionSource'] = SYNTHESIS_SOURCE
    monument['shortDescription'] = monument['description'][:240]
    return monument
