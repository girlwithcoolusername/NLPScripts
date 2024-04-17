import datetime

from dateparser import parse as parse_date


def extract_info(data, keys):
    result = {}
    for key in keys:
        if key in data:
            result[key] = data[key]
    return result


def extract_date_from_entities(entities):
    extracted_dates = {}
    for entity in entities:
        parsed_date = parse_date(entity, languages=["fr"],
                                 settings={'TIMEZONE': 'Africa/Casablanca', 'RETURN_AS_TIMEZONE_AWARE': False})
        if parsed_date:
            extracted_dates[entity] = parsed_date
    return extracted_dates


def timestamp_to_datetime(timestamp):
    return datetime.datetime.fromtimestamp(timestamp / 1000.0)


def compare_dates(date1, date2):
    delta = datetime.timedelta(days=20)
    datetime1 = timestamp_to_datetime(date1)
    datetime2 = timestamp_to_datetime(date2)

    if abs(datetime1 - datetime2) < delta:
        return True
    else:
        return False


def filter_operations(operations, entities):
    filtered_operations = []
    for operation in operations:
        if any(entity['entity_group'] == 'DATE' and compare_dates(extract_date_from_entities(entity['word']).values(),
                                                                  operation['dateOperation']) for entity in
               entities):
            filtered_operations.append(operation)
        elif any(entity['entity_group'] == 'PER' and (
                entity['word'] in (operation['beneficiaire']['nom'], operation['beneficiaire']['pernom'])) for
                 entity in entities):
            filtered_operations.append(operation)
    return filtered_operations


def get_cartes_message(cartes):
    if len(cartes) == 1:
        carte = cartes[0]
        message = f"Voici les informations de votre carte :\n\nType de carte: {carte['typeCarte']}\nNuméro de carte: {carte['numeroCarte']}\nDate d'expiration: {carte['dateExpiration']}\nCode PIN: {carte['codePin']}\nCVV: {carte['cvv']}\nStatut de la carte: {carte['statutCarte']}\nServices associés: {carte['services']}"
        if carte['statutCarte'] == "opposée":
            message += f"\nDate d'opposition: {carte['dateOpposition']}\nRaisons d'opposition: {carte['raisonOpposition']}"
    else:
        message = "Voici les informations de vos cartes bancaires :\n\n"
        for carte in cartes:
            message += f"Type de carte: {carte['typeCarte']}\nNuméro de carte: {carte['numeroCarte']}\nDate d'expiration: {carte['dateExpiration']}\nCode PIN: {carte['codePin']}\nCVV: {carte['cvv']}\nStatut de la carte: {carte['statutCarte']}\nServices associés: {carte['services']}\n\n"
            if carte['statutCarte'] == "opposée":
                message += f"Date d'opposition: {carte['dateOpposition']}\nRaisons d'opposition: {carte['raisonOpposition']}\n\n"
    return message


def get_operations_message(operations, filtered_operations):
    message = "Voici les informations de vos opérations bancaires :\n\n"
    if filtered_operations:
        for operation in filtered_operations:
            message += f"Vous avez effectué un : {operation['categorieOperation']} avec votre compte {operation['compte']['typeCompte']} le {operation['dateOperation']} avec le montant {operation['montant']} au compte de {operation['beneficiaire']['nom']} {operation['beneficiaire']['prenom']}"
            if operation['motif']:
                message += f" pour {operation['motif']}"
        return message
    else:
        for operation in operations:
            message += f"Vous avez effectué un : {operation['categorieOperation']} avec votre compte {operation['compte']['typeCompte']} le {operation['dateOperation']} avec le montant {operation['montant']} au compte de {operation['beneficiaire']['nom']} {operation['beneficiaire']['prenom']}"
            if operation['motif']:
                message += f" pour {operation['motif']}"
        return message
