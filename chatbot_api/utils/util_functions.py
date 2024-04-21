import datetime
from datetime import datetime, timedelta

import pytz
from dateparser import parse as parse_date


def extract_info(data, keys):
    result = {}
    for key in keys:
        if key in data:
            result[key] = data[key]
    return result


def convert_to_french_date(datetime_obj):
    if isinstance(datetime_obj, datetime):
        datetime_obj = datetime_obj.strftime("%Y-%m-%d")
    date_parts = datetime_obj.split("T")
    date_object = datetime.strptime(date_parts[0], "%Y-%m-%d")
    french_date_string = date_object.strftime("%d/%m/%Y")
    return french_date_string


def extract_date_from_entity(entity):
    # Parse the date string into a datetime object
    date_object = parse_date(entity, languages=["fr"],
                             settings={'TIMEZONE': 'Africa/Casablanca', 'RETURN_AS_TIMEZONE_AWARE': False})

    if date_object:
        # Format the datetime object into a French date string
        french_date_string = date_object.strftime("%d/%m/%Y")
        return french_date_string
    else:
        return None


def compare_dates(operation_date, date):
    date_object = datetime.strptime(date, '%d/%m/%Y').date()
    operation_date_object = datetime.fromisoformat(operation_date).date()
    # Convert to an aware datetime object
    if abs(operation_date_object - date_object) <= timedelta(days=20):
        return True
    else:
        return False


def filter_operations(operations, entities):
    filtered_operations = []
    for operation in operations:
        for entity in entities:
            if entity['entity_group'] == 'DATE':
                date_string = extract_date_from_entity(entity['word'])
                if date_string and compare_dates(operation['dateOperation'], date_string):
                    filtered_operations.append(operation)
                    break
            elif entity['entity_group'] == 'PER' and (
                    entity['word'] in (operation['beneficiaire']['nom'], operation['beneficiaire']['pernom'])):
                filtered_operations.append(operation)
                break
    return filtered_operations


def get_cartes_message(request_list, cartes):
    def build_message_for_request(request_list, carte):
        message = ""
        for request in request_list:
            if 'dateExpiration' in request and 'dateExpiration' in carte:
                french_date_string = convert_to_french_date(carte['dateExpiration'])
                message += f"Votre carte {carte['typeCarte']} va expirer le {french_date_string}. "
            elif 'cvv' in request and 'cvv' in carte:
                if message:
                    message += f"Elle a pour code de sécurité {carte['cvv']}. "
                else:
                    message += f"Votre carte {carte['typeCarte']} a pour code de sécurité {carte['cvv']}. "
            elif 'statutCarte' in request and 'statutCarte' in carte:
                if message:
                    message += f"La carte est actuellement {carte['statutCarte']}. "
                else:
                    message += f"Votre carte {carte['typeCarte']} est actuellement {carte['statutCarte']}. "
            elif 'codePin' in request and 'codePin' in carte:
                if message:
                    message += f"Elle a pour code de pin {carte['codePin']}. "
                else:
                    message += f"Votre carte {carte['typeCarte']} a pour code pin {carte['codePin']}. "
        return message.strip()

    if cartes:
        if len(cartes) == 1:
            message = ""
            carte = cartes[0]
            if request_list:
                message += build_message_for_request(request_list, carte)
            else:
                french_date_string = convert_to_french_date(carte['dateExpiration'])
                message = f"Votre carte {carte['typeCarte']} expire le {french_date_string}. Elle a pour code PIN {carte['codePin']} son code de sécurité (CVV) est {carte['cvv']}.La carte est actuellement {carte['statutCarte']} et possède pour services {carte['services']}"
                if carte['statutCarte'] == "opposée":
                    message += f"Elle a été opposé le {carte['dateOpposition']} pour {carte['raisonOpposition']}."
        else:
            message = "Voici les informations de vos cartes bancaires :\n\n"
            for carte in cartes:
                if request_list:
                    message += build_message_for_request(request_list, carte)
                else:
                    french_date_string = convert_to_french_date(carte['dateExpiration'])
                    message = f"Votre carte {carte['typeCarte']}  expire le {french_date_string}. Elle a pour code PIN {carte['codePin']} son code de sécurité (CVV) est {carte['cvv']}.La carte est actuellement {carte['statutCarte']} et possède pour services {carte['services']}"
                    if carte['statutCarte'] == "opposée":
                        message += f"Elle a été opposé le {carte['dateOpposition']} pour {carte['raisonOpposition']}."
    else:
        message = "Aucune carte ne correspond aux informations spécifiées!"
    return message


def get_operations_message(operations, filtered_operations):
    def build_message_info_operation(operation):
        french_date_string = convert_to_french_date(operation['dateOperation'])
        message = f"Vous avez effectué un : {operation['categorieOperation']} avec votre compte {operation['compte']['typeCompte']} le {french_date_string} avec le montant {operation['montant']} au compte de {operation['beneficiaire']['nom']} {operation['beneficiaire']['prenom']}"
        if operation['motif']:
            message += f" pour {operation['motif']}"
        return message

    message = "Voici les informations de vos opérations bancaires :"
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


def get_missing_entity_message(missing_entities):
    message = "Désolé, vous n'avez pas spécifié : " + ', '.join(missing_entities)
    if len(missing_entities) == 1:
        message += ". Veuillez les spécifier." if missing_entities[0][:3] == "les" else ". Veuillez le spécifier."
    else:
        message += ". Veuillez les spécifier."
    return message


def merge_entities(extracted_entities, new_extracted_entities):
    return {**extracted_entities, **new_extracted_entities}
