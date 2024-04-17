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


def get_cartes_message(request_list, cartes):
    def build_message_for_request(request_list, carte):
        message = f"Votre carte {carte['typeCarte']}"
        for request in request_list:
            if 'dateExpiration' in request:
                message += f"expire le {carte['dateExpiration']}. "
            elif 'cvv' in request:
                message += f"Elle a pour code de sécurité {carte['cvv']}."
            elif 'statutCarte' in request:
                message += f" est actuellement {carte['statutCarte']}."
            elif 'codePin' in request:
                message += f"son code PIN est {carte['codePin']}."
        return message

    if len(cartes) == 1:
        message = ""
        carte = cartes[0]
        if request_list:
            message += build_message_for_request(request_list, carte)
        else:
            message = f"Votre carte {carte['typeCarte']} de numéro  {carte['numeroCarte']} expire le {carte['dateExpiration']}. Elle a pour code PIN {carte['codePin']} son code de sécurité (CVV) est {carte['cvv']}.La carte est actuellement {carte['statutCarte']} et possède pour services {carte['services']}"
            if carte['statutCarte'] == "opposée":
                message += f"Elle a été opposé le {carte['dateOpposition']} pour {carte['raisonOpposition']}."
    else:
        message = "Voici les informations de vos cartes bancaires :\n\n"
        for carte in cartes:
            if request_list:
                message += build_message_for_request(request_list, carte)
            else:
                message = f"Votre carte {carte['typeCarte']} de numéro {carte['numeroCarte']} expire le {carte['dateExpiration']}. Elle a pour code PIN {carte['codePin']} son code de sécurité (CVV) est {carte['cvv']}.La carte est actuellement {carte['statutCarte']} et possède pour services {carte['services']}"
                if carte['statutCarte'] == "opposée":
                    message += f"Elle a été opposé le {carte['dateOpposition']} pour {carte['raisonOpposition']}."
    return message


def get_operations_message(operations, filtered_operations):
    def build_message_info_operation(operation):
        message = f"Vous avez effectué un : {operation['categorieOperation']} avec votre compte {operation['compte']['typeCompte']} le {operation['dateOperation']} avec le montant {operation['montant']} au compte de {operation['beneficiaire']['nom']} {operation['beneficiaire']['prenom']}"
        if operation['motif']:
            message += f" pour {operation['motif']}"
        return message
    message = "Voici les informations de vos opérations bancaires :\n\n"
    if filtered_operations:
        for operation in filtered_operations:
            message += build_message_info_operation(operation)
        return message
    else:
        for operation in operations:
            message += build_message_info_operation(operation)
        return message

def get_comptes_message(comptes):
    if comptes:
        if len(comptes) == 1:
            compte = comptes[0]
            message = f"Le solde disponible sur votre compte {compte['typeCompte']} est de {compte['solde']} dirhams."
        else:
            message = "Voici les soldes de vos comptes bancaires :\n\n"
            for compte in comptes:
                message += f"Il vous reste {compte['solde']} dirhams dans votre compte {compte['typeCompte']}.\n\n"
        return message
    else:
        return "Désolé, je n'ai trouvé aucun compte associé à votre compte."

def get_agences_messages(agences):
    if agences:
        if len(agences) == 1:
            agence = agences[0]
            message = f"Vous pouvez trouver notre agence {agence['nomAgence']} située au {agence['adresse']}. Elle est ouverte de {agence['horairesOuverture']} et propose les services suivants : {agence['servicesDisponibles']}. Vous pouvez également la contacter au {agence['telephone']}."
        else:
            message = "Voici les agences les plus proches :\n"
            for agence in agences:
                message += f"- {agence['nomAgence']} située au {agence['adresse']}. Elle est ouverte de {agence['horairesOuverture']} et propose les services suivants : {agence['servicesDisponibles']}. Vous pouvez également la contacter au {agence['telephone']}.\n"
    else:
        message = "Aucune agence n'est trouvée."
    return message