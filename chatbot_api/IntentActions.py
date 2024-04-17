import random

from chatbot_api.faq_logic.longchain_helper import get_qa_chain
from chatbot_api.utils.contstants import CANCEL_ACTION
from chatbot_api.utils.nlu import entity_extraction
from chatbot_api.utils.util_functions import filter_operations, get_cartes_message, get_operations_message, \
    get_comptes_message, get_agences_messages


class IntentActions:
    def __init__(self, spring_api_service):
        self.spring_api = spring_api_service

    def info_assistance_action(self):
        response = (
            "Une équipe dédiée est à votre disposition pour la prise en charge de vos demandes au : 05 22 58 88 "
            "55. Vous pouvez également nous contacter par email à l'adresse : 'attijarinet@attijariwafa.com'. "
            "Nos horaires d'ouverture sont du lundi au samedi de 8h à 20h. En période de Ramadan, nos horaires "
            "sont de 9h à 15h.")
        return response

    def info_faq_action(self, data):
        text = data['text'].lower()
        chain = get_qa_chain()
        answer = chain(text)
        response = answer["result"]
        return response

    def info_geolocalisation_action(self, json_data):
        if "location" in json_data:
            lat = json_data['location']["lat"]
            lng = json_data['location']["lng"]
            agences = self.spring_api.get_data(f"agences/location/{lat}/{lng}")
        else:
            user_id = json_data["userId"]
            agences = self.spring_api.get_data(f"agences/userAddress/{user_id}")

        return get_agences_messages(agences)

    def consultation_solde_action(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        entities_dict = {}
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        if entities_ner_bert is None and entities_ner_regex is None:
            comptes = self.spring_api.get_data(f"comptes/user/{userid}")
            return get_comptes_message(comptes)
        elif entities_ner_regex is not None:
            for patternName, value in entities_ner_regex.items():
                entities_dict[patternName] = value
            response_body = {"userId": userid, "entitiesDic": entities_dict}
            comptes = self.spring_api.post_data('/comptes/searchEntitiesDict', response_body)
            return get_comptes_message(comptes)
    def consultation_cartes_action(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        entities_dict = {}
        request_list = []
        _, entities_ner_regex = entity_extraction(text, patterns)
        if entities_ner_regex is None:
            cartes = self.spring_api.get_data(f"cartes/user/{userid}")
            if cartes:
                return get_cartes_message(cartes)
            else:
                return "Désolé, je n'ai trouvé aucune carte associée à votre compte."
        elif entities_ner_regex is not None:
            for patternName, value in entities_ner_regex.items():
                if 'demande_' not in patternName:
                    entities_dict[patternName] = value
                else:
                    request_list.append(patternName)
            response_body = {"userId": userid, "entitiesDic": entities_dict}
            cartes = self.spring_api.post_data('/cartes/searchEntitiesDict', response_body)
            if cartes:
                return get_cartes_message(cartes)
        else:
            return "Une erreur s'est produite lors de la récupération des informations de carte."

    def consultation_operations_action(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        entities_dict = {}
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)

        if entities_ner_regex is None:
            operations = self.spring_api.get_data(f"operations/user/{userid}")
        else:
            for patternName, value in entities_ner_regex.items():
                entities_dict[patternName] = value
            response_body = {"userId": userid, "entitiesDic": entities_dict}
            operations = self.spring_api.post_data('/operations/searchEntitiesDict', response_body)

        if operations:
            filtered_operations = filter_operations(operations, entities_ner_bert)
            if filtered_operations:
                return get_operations_message(filtered_operations)
        else:
            return "Désolé, je n'ai trouvé aucune opération associée à votre compte."

    def check_beneficiaires(self, userid, extracted_entities):
        nom = extracted_entities.get('nom')
        prenom = extracted_entities.get('prenom')

        response_body = {
            "userId": userid,
            "beneficiaire": {
                'nom': nom,
                "prenom": prenom,
            }
        }
        beneficiaires = self.spring_api.post_data('/beneficiaires/user/names', response_body)

        return beneficiaires

    def check_comptes(self, userid, extracted_entities):
        type_compte = extracted_entities.get('typeCompte')

        comptes = self.spring_api.get_data(f'/comptes/userTypeCompte/{userid}/{type_compte}')

        return comptes

    def check_cartes(self, userid, extracted_entities):
        type_carte = extracted_entities.get('typeCarte')

        cartes = self.spring_api.get_data(f'/cartes/userCardsByType/{userid}/{type_carte}')

        return cartes

    def action_ajout_beneficiaire(self, data, patterns):
        text = data['text'].lower()
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['nom', 'prenom', 'rib', 'typeBeneficiaire']
        extracted_entities = {}

        nom = None
        prenom = None
        rib = None
        typeBeneficiaire = None

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()

        if entities_ner_regex:
            rib = entities_ner_regex.get('rib')
            typeBeneficiaire = entities_ner_regex.get('typeBeneficiaire')

        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        extracted_entities = [locals().get(entity) for entity in required_entities if locals().get(entity) is not None]
        if missing_entities:
            message = "Désolé, vous n'avez pas spécifié le : " + ', '.join(
                missing_entities) + ". Veuillez les spécifier."
            if len(missing_entities) == 1:
                message += ". Veuillez le spécifier."
            else:
                message += ". Veuillez les spécifier."
            return "Entity_Missing_Gestion_Bénéficiaires_Ajout", message, extracted_entities

        message = f"Vous voulez ajouter un bénéficiaire avec le nom {nom}, le prénom {prenom} comme personne {typeBeneficiaire} ayant pour rib {rib}. Merci de confirmer cette demande!"
        return "Required_Validation_Gestion_Bénéficiaires_Ajout", message, extracted_entities

    def action_complete_ajout_beneficiaire(self, data, extracted_entities, patterns, context):
        text = data['text'].lower()
        userid = data['userId']
        required_entities = ['nom', 'prenom', 'rib', 'typeBeneficiaire']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)

        nom = None
        prenom = None
        rib = None
        typeBeneficiaire = None

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()

        if entities_ner_regex:
            rib = entities_ner_regex.get('rib')
            typeBeneficiaire = entities_ner_regex.get('typeBeneficiaire')
        if context == "Confirmation_Action":
            response_body = {
                "userId": userid,
                "beneficiaire": {
                    'nom': extracted_entities.get('nom'),
                    "prenom": extracted_entities.get("prenom"),
                    "rib": extracted_entities.get("rib"),
                    "typeBeneficiaire": extracted_entities.get('typeBeneficiaire')
                }
            }
            message = self.spring_api.post_data('/beneficiaires/add', response_body)
            return None, message, []
        elif context == "Annulation_action":
            message = random.choice(CANCEL_ACTION)
            return None, message, []
        elif context == "Missing_Entity":
            missing_entities = [entity for entity in required_entities if entity not in extracted_entities]
            new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                      entity not in extracted_entities}
            merged_entities = {**extracted_entities, **new_extracted_entities}
            if missing_entities:
                message = "Désolé, vous n'avez pas spécifié le champ suivant : " + ', '.join(missing_entities)
                if len(missing_entities) == 1:
                    message += ". Veuillez le spécifier."
                else:
                    message += ". Veuillez les spécifier."
                return "Entity_Missing_Gestion_Bénéficiaires_Ajout", message, merged_entities
            else:
                message = f"Vous voulez ajouter un bénéficiaire avec le nom {merged_entities.get('nom')}, le prénom {merged_entities.get('prenom')} comme {merged_entities.get('typeBeneficiaire')} ayant pour rib {merged_entities.get('rib')}. Merci de confirmer cette demande!"
                return "Required_Validation_Gestion_Bénéficiaires_Ajout", message, merged_entities

    def action_suppression_beneficiaire(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['nom', 'prenom']
        extracted_entities = {}
        nom = None
        prenom = None

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()
                    extracted_entities['nom'] = nom
                    extracted_entities['prenom'] = prenom
        extracted_entities = [locals().get(entity) for entity in required_entities if locals().get(entity) is not None]
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            message = "Désolé, vous n'avez pas spécifié le : " + ', '.join(
                missing_entities)
            if len(missing_entities) > 1:
                message += ". Veuillez les spécifier."
            else:
                message += ". Veuillez le spécifier."
            return "Entity_Missing_Gestion_Bénéficiaires_Suppression", message, extracted_entities
        else:
            beneficiaries = self.check_beneficiaires(userid, extracted_entities)
            if beneficiaries:
                if len(beneficiaries) == 1:
                    message = f"Vous voulez supprimer le bénéficiaire {nom} {prenom}. Merci de confirmer cette demande!"
                    return "Required_Validation_Gestion_Bénéficiaires_Suppression", message, extracted_entities
                else:
                    message = f"Vous avez plusieurs bénéficiaires avec le même nom, merci de préciser le RIB du bénéficiaire!"
                    return "Entity_Missing_Gestion_Bénéficiaires_Suppression", message, extracted_entities

    def action_complete_suppression_beneficiaire(self, data, extracted_entities, patterns, context):
        text = data['text'].lower()
        userid = data['userId']
        required_entities = ['nom', 'prenom']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        new_extracted_entities = {}
        nom = None
        prenom = None
        rib = None

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()

        if entities_ner_regex:
            rib = entities_ner_regex.get('rib')
        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
        merged_entities = {**extracted_entities, **new_extracted_entities}
        if context == "Confirmation_Action":
            if len(extracted_entities) == 2:
                response_body = {
                    "userId": userid,
                    "beneficiaire": {
                        'nom': extracted_entities.get('nom'),
                        "prenom": extracted_entities.get("prenom"),
                    }
                }
                message = self.spring_api.post_data('/beneficiaires/delete/names', response_body)
                return None, message, []
            else:
                response_body = {
                    "userId": userid,
                    "beneficiaire": {
                        'rib': extracted_entities.get('rib')
                    }
                }
                message = self.spring_api.post_data('/beneficiaires/delete/rib', response_body)
                return None, message, []
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return None, message, []
        elif context == "Missing_Entity":
            if len(extracted_entities) == len(required_entities) and rib is None:
                message = "Veuillez préciser le RIB du bénéficiaire"
                return "Entity_Missing_Gestion_Bénéficiaires_Suppression", message, merged_entities
            elif len(extracted_entities) == len(required_entities) and rib is not None:
                response_body = {
                    "userId": userid,
                    "beneficiaire": {
                        'rib': rib
                    }
                }
                message = self.spring_api.post_data('/beneficiaires/user/rib', response_body)
                if message:
                    message = f"Souhaitez-vous supprimer le bénéficiaire avec le RIB {rib} ? Merci de confirmer cette demande!"
                    return "Request_Validation_Gestion_Bénéficiaires_Suppression", message, merged_entities
                else:
                    message = f"Le RIB spécifié ne correspond à aucun bénéficiaire."
                    return "Entity_Missing_Gestion_Bénéficiaires_Suppression", message, merged_entities
            else:
                missing_entities = [entity for entity in required_entities if entity not in extracted_entities]
                if missing_entities:
                    message = "Désolé, vous n'avez pas spécifié le  : " + ', '.join(missing_entities)
                    if len(missing_entities) > 1:
                        message += ". Veuillez les spécifier."
                    else:
                        message += ". Veuillez le spécifier."
                    return extracted_entities, "Entity_Missing_Gestion_Bénéficiaires_Suppression", message
                else:
                    message = f"Vous voulez supprimer le bénéficiaire {merged_entities.get('nom')} {merged_entities.get('prenom')}. Merci de confirmer cette demande!"
                    return "Required_Validation_Gestion_Bénéficiaires_Suppression", message, merged_entities

    def action_modification_beneficiaire(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['nom', 'prenom', 'newRib']
        extracted_entities = {}
        nom = None
        prenom = None
        oldRib = None
        newRib = None

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()
        if entities_ner_regex:
            if len(entities_ner_regex.get('rib')) == 2:
                oldRib = entities_ner_regex.get('rib')[0]
                newRib = entities_ner_regex.get('rib')[1]
        extracted_entities = [locals().get(entity) for entity in required_entities if locals().get(entity) is not None]
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            message = "Désolé, vous n'avez pas spécifié le : " + ', '.join(
                missing_entities)
            if len(missing_entities) > 1:
                message += ". Veuillez les spécifier."
            else:
                message += ". Veuillez le spécifier."
            return "Entity_Missing_Gestion_Bénéficiaires_Modification", message, extracted_entities
        else:
            beneficiaries = self.check_beneficiaires(userid, extracted_entities)
            if beneficiaries:
                if len(beneficiaries) == 1:
                    message = f"Vous voulez modifier le bénéficiaire {nom} {prenom} ayant pour RIB {oldRib} avec le RIB {newRib}. Merci de confirmer cette demande!"
                    return "Required_Validation_Gestion_Bénéficiaires_Modification", message, extracted_entities
                else:
                    message = f"Vous avez plusieurs bénéficiaires avec le même nom, merci préciser le RIB du bénéficiaire!"
                    return "Entity_Missing_Gestion_Bénéficiaires_Modification", message, extracted_entities

    def action_complete_modification_beneficiaire(self, data, extracted_entities, patterns, context):
        text = data['text'].lower()
        userid = data['userId']
        required_entities = ['nom', 'prenom', 'newRib']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        new_extracted_entities = {}
        nom = None
        prenom = None
        oldRib = None
        newRib = None

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()

        if entities_ner_regex:
            oldRib = entities_ner_regex.get('rib')[0]
            newRib = entities_ner_regex.get('rib')[1]

        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
        merged_entities = {**extracted_entities, **new_extracted_entities}
        if context == "Confirmation_Action":
            if len(extracted_entities) == 3:
                response_body = {
                    "userId": userid,
                    "beneficiaire": {
                        'nom': extracted_entities.get('nom'),
                        "prenom": extracted_entities.get("prenom"),
                    },
                    "newRib": extracted_entities.get('newRib')
                }
                message = self.spring_api.post_data('/beneficiaires/update/names', response_body)
                return None, message, []
            else:
                response_body = {
                    "userId": userid,
                    "oldRib": extracted_entities.get('oldRib'),
                    "newRib": extracted_entities.get('newRib')
                }
                message = self.spring_api.post_data('/beneficiaires/update/rib', response_body)
                return None, message, []
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return None, message, []
        elif context == "Missing_Entity":
            if len(extracted_entities) == len(required_entities) and oldRib is None:
                message = "Veuillez préciser le RIB du bénéficiaire"
                return "Entity_Missing_Gestion_Bénéficiaires_Modification", message, merged_entities
            elif len(extracted_entities) == len(required_entities) and oldRib is not None:
                response_body = {
                    "userId": userid,
                    "beneficiaire": {
                        'rib': oldRib
                    }
                }
                message = self.spring_api.post_data('/beneficiaires/user/rib', response_body)
                if message:
                    message = f"Souhaitez-vous modifier le bénéficiaire avec le RIB {oldRib} ? Merci de confirmer cette demande!"
                    return "Request_Validation_Gestion_Bénéficiaires_Modification", message, merged_entities
                else:
                    message = f"Le RIB spécifié ne correspond à aucun bénéficiaire."
                    return "Entity_Missing_Gestion_Bénéficiaires_Modification", message, merged_entities
            else:
                missing_entities = [entity for entity in required_entities if entity not in extracted_entities]
                if missing_entities:
                    message = "Désolé, vous n'avez pas spécifié le  : " + ', '.join(missing_entities)
                    if len(missing_entities) > 1:
                        message += ". Veuillez les spécifier."
                    else:
                        message += ". Veuillez le spécifier."
                    return extracted_entities, "Entity_Missing_Gestion_Bénéficiaires_Modification", message
                else:
                    message = f"Vous voulez modifier le bénéficiaire {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le RIB {merged_entities.get('newRib')}. Merci de confirmer cette demande!"
                    return "Required_Validation_Gestion_Bénéficiaires_Modification", message, merged_entities

    def action_ajout_transaction_paiement(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        _, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCompte', 'numeroFacture']
        extracted_entities = {}
        typeCompte = None
        numeroFacture = None
        if entities_ner_regex:
            typeCompte = entities_ner_regex.get('typeCompte')
            numeroFacture = entities_ner_regex.get('numeroFacture')
        extracted_entities = [locals().get(entity) for entity in required_entities if locals().get(entity) is not None]
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            message = "Désolé, vous n'avez pas spécifié le : " + ', '.join(
                missing_entities)
            if len(missing_entities) > 1:
                message += ". Veuillez les spécifier."
            else:
                message += ". Veuillez le spécifier."
            return "Entity_Missing_Transaction_PaiementFacture", message, extracted_entities
        else:
            comptes = self.check_comptes(userid, extracted_entities)
            if comptes:
                if len(comptes) == 1:
                    message = (f"Vous voulez payer la facture {numeroFacture} avec votre compte {typeCompte}. Merci de "
                               f"confirmer cette demande!")
                    return "Required_Validation_Transaction_PaiementFacture", message, extracted_entities
                else:
                    message = (f"Vous avez plusieurs comptes du même type, merci de préciser le numéro de votre compte "
                               f"bancaire!")
                    return "Entity_Missing_Transaction_PaiementFacture", message, extracted_entities

    def action_complete_ajout_transaction_paiement(self, data, extracted_entities, patterns, context):
        text = data['text'].lower()
        userid = data['userId']
        required_entities = ['typeCompte', 'numeroFacture']
        _, entities_ner_regex = entity_extraction(text, patterns)
        new_extracted_entities = {}
        typeCompte = None
        numeroFacture = None
        numeroCompte = None

        if entities_ner_regex:
            typeCompte = entities_ner_regex.get('typeCompte')
            numeroFacture = entities_ner_regex.get('numeroFacture')
            numeroCompte = entities_ner_regex.get('numeroCompte')
        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
        merged_entities = {**extracted_entities, **new_extracted_entities}
        if context == "Confirmation_Action":
            if len(extracted_entities) == 2:
                response_body = {
                    "userId": userid,
                    'numeroFacture': extracted_entities.get('numeroFacture'),
                    "typeCompte": extracted_entities.get('typeCompte')
                }
                message = self.spring_api.post_data('/paimenent-facture/addInvoiceByAccountType', response_body)
                return None, message, []
            else:
                response_body = {
                    "userId": userid,
                    'numeroFacture': extracted_entities.get('numeroFacture'),
                    "numeroCompte": extracted_entities.get('numeroCompte'),
                    "typeCompte": extracted_entities.get('typeCompte')
                }
                message = self.spring_api.post_data('/paimenent-facture/addInvoiceByAccountNum', response_body)
                return None, message, []
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return None, message, []
        elif context == "Missing_Entity":
            if len(extracted_entities) == len(required_entities) and numeroCompte is None:
                message = "Veuillez préciser votre numéro de compte!"
                return "Entity_Missing_Transaction_PaiementFacture", message, merged_entities
            elif len(extracted_entities) == len(required_entities) and numeroCompte is not None:

                message = self.spring_api.get_data(f'/userNumCompte/{userid}/{numeroCompte}')
                if message:
                    message = f"Souhaitez-vous payer la facture numéro {numeroFacture} avec le compte bancaire numéro {numeroCompte} ? Merci de confirmer cette demande!"
                    return "Request_Validation_Transaction_PaiementFacture", message, merged_entities
                else:
                    message = f"Aucun compte bancaire ne correspond à ce numéro."
                    return "Entity_Missing_Transaction_PaiementFacture", message, merged_entities
            else:
                missing_entities = [entity for entity in required_entities if entity not in extracted_entities]
                if missing_entities:
                    message = "Désolé, vous n'avez pas spécifié le  : " + ', '.join(missing_entities)
                    if len(missing_entities) > 1:
                        message += ". Veuillez les spécifier."
                    else:
                        message += ". Veuillez le spécifier."
                    return extracted_entities, "Entity_Missing_Transaction_PaiementFacture", message
                else:
                    message = f"Souhaitez-vous payer la facture numéro {numeroFacture} avec le compte bancaire numéro {numeroCompte} ? Merci de confirmer cette demande!"
                    return "Request_Validation_Transaction_PaiementFacture", message, merged_entities

    def action_services_cartes(self, data, patterns, status):
        text = data['text'].lower()
        userid = data['userId']
        _, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCarte', 'services']
        extracted_entities = {}
        typeCarte = None
        services = None
        if entities_ner_regex:
            typeCarte = entities_ner_regex.get('typeCarte')
            services = entities_ner_regex.get('services')

        extracted_entities = [locals().get(entity) for entity in required_entities if locals().get(entity) is not None]
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            message = "Désolé, vous n'avez pas spécifié le : " + ', '.join(
                missing_entities)
            if len(missing_entities) > 1:
                message += ". Veuillez les spécifier."
            else:
                message += ". Veuillez le spécifier."
            return f"Entity_Missing_Gestion_Cartes_{status}", message, extracted_entities
        else:
            cartes = self.check_cartes(userid, extracted_entities)
            if cartes:
                if len(cartes) == 1:
                    if status == "Activation":
                        message = (
                            f"Vous voulez ajouter les services {services} pour votre carte {typeCarte}. Merci de "
                            f"confirmer cette demande!")
                    elif status == "Désactivation":
                        message = (
                            f"Vous voulez supprimer les services {services} pour votre carte {typeCarte}. Merci de "
                            f"confirmer cette demande!")
                    return f"Required_Validation_Gestion_Cartes_{status}", message, extracted_entities
                else:
                    message = (f"Vous avez plusieurs cartes du même type, merci de préciser le numéro de votre carte "
                               f"bancaire!")
                    return f"Entity_Missing_Gestion_Cartes_{status}", message, extracted_entities

    def action_opposition_carte(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        _, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCarte', 'raisonsOpposition']
        extracted_entities = {}
        typeCarte = None
        raisonsOpposition = None
        if entities_ner_regex:
            typeCarte = entities_ner_regex.get('typeCarte')
            raisonsOpposition = entities_ner_regex.get('raisonsOpposition')
        extracted_entities = [locals().get(entity) for entity in required_entities if locals().get(entity) is not None]
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            message = "Désolé, vous n'avez pas spécifié le : " + ', '.join(
                missing_entities)
            if len(missing_entities) > 1:
                message += ". Veuillez les spécifier."
            else:
                message += ". Veuillez le spécifier."
            return f"Entity_Missing_Gestion_Cartes_Opposition", message, extracted_entities
        else:
            cartes = self.check_cartes(userid, extracted_entities)
            if cartes:
                if len(cartes) == 1:
                    message = (
                        f"Vous voulez opposer votre carte {typeCarte} pour {raisonsOpposition}. Merci de "
                        f"confirmer cette demande!")
                    return f"Required_Validation_Gestion_Cartes_Opposition", message, extracted_entities
                else:
                    message = (f"Vous avez plusieurs cartes du même type, merci de préciser le numéro de votre carte "
                               f"bancaire!")
                    return f"Entity_Missing_Gestion_Cartes_Opposition", message, extracted_entities

    def action_plafond_carte(self, data, patterns, status):
        text = data['text'].lower()
        userid = data['userId']
        _, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCarte', 'plafond', 'typePlafond']
        extracted_entities = {}
        typeCarte = None
        typePlafond = None
        plafond = None
        if entities_ner_regex:
            typeCarte = entities_ner_regex.get('typeCarte')
            typePlafond = entities_ner_regex.get('typePlafond')
            plafond = entities_ner_regex.get('montant')

        extracted_entities = [locals().get(entity) for entity in required_entities if
                              locals().get(entity) is not None]
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            message = "Désolé, vous n'avez pas spécifié le : " + ', '.join(
                missing_entities)
            if len(missing_entities) > 1:
                message += ". Veuillez les spécifier."
            else:
                message += ". Veuillez le spécifier."
            return f"Entity_Missing_Gestion_Cartes_Plafond_{status}", message, extracted_entities
        else:
            cartes = self.check_cartes(userid, extracted_entities)
            if cartes:
                if len(cartes) == 1:
                    if status == "Augmenter":
                        message = (
                            f"Vous voulez augmenter le plafon de {typePlafond} pour votre carte {typeCarte}. Merci de "
                            f"confirmer cette demande!")
                    elif status == "Diminuer":
                        message = (
                            f"Vous voulez diminuer le plafon de {typePlafond} pour votre carte {typeCarte}. Merci de "
                            f"confirmer cette demande!")
                    return f"Required_Validation_Gestion_Cartes_Plafond_{status}", message, extracted_entities
                else:
                    message = (
                        f"Vous avez plusieurs cartes du même type, merci de préciser le numéro de votre carte "
                        f"bancaire!")
                    return f"Entity_Missing_Gestion_Cartes_Plafond_{status}", message, extracted_entities

    def action_activation_carte(self, data, patterns):
        return self.action_services_cartes(data, patterns, "Activation")

    def action_plafond_augmenter(self, data, patterns, status):
        return self.action_services_cartes(data, patterns, "Augmenter")

    def action_plafond_diminuer(self, data, patterns):
        return self.action_services_cartes(data, patterns, "Diminuer")

    def action_desactivation_carte(self, data, patterns):
        return self.action_services_cartes(data, patterns, "Désactivation")

    def action_complete_services_cartes(self, data, extracted_entities, patterns, context, status):
        text = data['text'].lower()
        userid = data['userId']
        required_entities = ['typeCarte', 'services']
        _, entities_ner_regex = entity_extraction(text, patterns)
        new_extracted_entities = {}
        typeCarte = None
        services = None
        numeroCarte = None

        if entities_ner_regex:
            typeCarte = entities_ner_regex.get('typeCarte')
            numeroCarte = entities_ner_regex.get('numeroCarte')
            services = entities_ner_regex.get('services')

        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
        merged_entities = {**extracted_entities, **new_extracted_entities}
        if context == "Confirmation_Action":
            if len(extracted_entities) == 2:
                response_body = {
                    "userId": userid,
                    "carte": {
                        'typeCarte': extracted_entities.get('typeCarte'),
                        "services": extracted_entities.get('services')
                    },
                    "status": "enable" if status == "Activation" else "disable"
                }
                message = self.spring_api.post_data('/cartes/updateByCardType', response_body)
                return None, message, []
            else:
                response_body = {
                    "userId": userid,
                    "carte": {
                        'typeCarte': extracted_entities.get('typeCarte'),
                        "services": extracted_entities.get('services'),
                        'numeroCarte': extracted_entities.get('numeroCarte')
                    },
                    "status": "enable" if status == "Activation" else "disable"

                }
                message = self.spring_api.post_data('/cartes/updateByCardNum', response_body)
                return None, message, []
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return None, message, []
        elif context == "Missing_Entity":
            if len(extracted_entities) == len(required_entities) and numeroCarte is None:
                message = "Veuillez préciser votre numéro de compte!"
                return f"Entity_Missing_Gestion_Cartes_{status}", message, merged_entities
            elif len(extracted_entities) == len(required_entities) and numeroCarte is not None:

                message = self.spring_api.get_data(f'/userCardsByNum/{numeroCarte}')
                if message:
                    message = f"Souhaitez-vous modifier les services permis par votre carte {typeCarte} numéro {numeroCarte} ? Merci de confirmer cette demande!"
                    return f"Request_Validation_Gestion_Cartes_{status}", message, merged_entities
                else:
                    message = f"Aucune carte ne correspond à ce numéro!"
                    return f"Entity_Missing_Gestion_Cartes_{status}", message, merged_entities
            else:
                missing_entities = [entity for entity in required_entities if entity not in extracted_entities]
                if missing_entities:
                    message = "Désolé, vous n'avez pas spécifié le  : " + ', '.join(missing_entities)
                    if len(missing_entities) > 1:
                        message += ". Veuillez les spécifier."
                    else:
                        message += ". Veuillez le spécifier."
                    return extracted_entities, f"Entity_Missing_Gestion_Cartes_{status}", message
                else:
                    message = f"Souhaitez-vous modifier les services permis par votre carte {typeCarte} numéro {numeroCarte} ? Merci de confirmer cette demande!"
                    return f"Request_Validation_Gestion_Cartes_{status}", message, merged_entities

    def action_complete_plafond(self, data, extracted_entities, patterns, context, status):
        text = data['text'].lower()
        userid = data['userId']
        required_entities = ['typeCarte', 'typePlafond']
        _, entities_ner_regex = entity_extraction(text, patterns)
        new_extracted_entities = {}
        typeCarte = None
        typePlafond = None
        numeroCarte = None
        plafond = None

        if entities_ner_regex:
            typeCarte = entities_ner_regex.get('typeCarte')
            numeroCarte = entities_ner_regex.get('numeroCarte')
            typePlafond = entities_ner_regex.get('typePlafond')
            plafond = entities_ner_regex.get('montant')

        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
        merged_entities = {**extracted_entities, **new_extracted_entities}
        if context == "Confirmation_Action":
            if len(extracted_entities) == 2:
                response_body = {
                    "userId": userid,
                    'typeCarte': extracted_entities.get('typeCarte'),
                    "typePlafond": extracted_entities.get('typePlafond'),
                    "plafond": extracted_entities.get('montant'),
                    "statut": "add" if status == "Augmenter" else "disable",
                    "duration": ""
                }
                message = self.spring_api.post_data('/plafond/updateByCardType', response_body)
                return None, message, []
            else:
                response_body = {
                    "userId": userid,
                    'typeCarte': extracted_entities.get('typeCarte'),
                    'numeroCarte': extracted_entities.get('numeroCarte'),
                    "typePlafond": extracted_entities.get('typePlafond'),
                    "plafond": extracted_entities.get('montant'),
                    "statut": "add" if status == "Augmenter" else "disable",
                    "duration": ""

                }
                message = self.spring_api.post_data('/plafond/updateByCardNum', response_body)
                return None, message, []
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return None, message, []
        elif context == "Missing_Entity":
            if len(extracted_entities) == len(required_entities) and numeroCarte is None:
                message = "Veuillez préciser votre numéro de compte!"
                return f"Entity_Missing_Gestion_Cartes_Plafond_{status}", message, merged_entities
            elif len(extracted_entities) == len(required_entities) and numeroCarte is not None:

                message = self.spring_api.get_data(f'/userCardsByNum/{numeroCarte}')
                if message:
                    message = f"Souhaitez-vous modifier le plafond {typePlafond} permis par votre carte {typeCarte} numéro {numeroCarte} ? Merci de confirmer cette demande!"
                    return f"Request_Validation_Gestion_Cartes_Plafond_{status}", message, merged_entities
                else:
                    message = f"Aucune carte ne correspond à ce numéro!"
                    return f"Entity_Missing_Gestion_Cartes_Plafond_{status}", message, merged_entities
            else:
                missing_entities = [entity for entity in required_entities if entity not in extracted_entities]
                if missing_entities:
                    message = "Désolé, vous n'avez pas spécifié le  : " + ', '.join(missing_entities)
                    if len(missing_entities) > 1:
                        message += ". Veuillez les spécifier."
                    else:
                        message += ". Veuillez le spécifier."
                    return extracted_entities, f"Entity_Missing_Gestion_Cartes_Plafond_{status}", message
                else:
                    message = f"Souhaitez-vous modifier le plafond {typePlafond} permis par votre carte {typeCarte} numéro {numeroCarte} ? Merci de confirmer cette demande!"
                    return f"Request_Validation_Gestion_Cartes_Plafond_{status}", message, merged_entities

    def action_complete_activation_carte(self, data, extracted_entities, patterns, context):
        return self.action_complete_services_cartes(data, extracted_entities, patterns, context, "Activation")

    def action_complete_desactivation_carte(self, data, extracted_entities, patterns, context):
        return self.action_complete_services_cartes(data, extracted_entities, patterns, context, "Désactivation")

    def action_complete_opposition_carte(self, data, extracted_entities, patterns, context):
        text = data['text'].lower()
        userid = data['userId']
        required_entities = ['typeCarte', 'raisonsOpposition']
        _, entities_ner_regex = entity_extraction(text, patterns)
        new_extracted_entities = {}
        typeCarte = None
        raisonsOpposition = None
        numeroCarte = None

        if entities_ner_regex:
            typeCarte = entities_ner_regex.get('typeCarte')
            numeroCarte = entities_ner_regex.get('numeroCarte')
            raisonsOpposition = entities_ner_regex.get('raisonsOpposition')

        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
        merged_entities = {**extracted_entities, **new_extracted_entities}
        if context == "Confirmation_Action":
            if len(extracted_entities) == 2:
                response_body = {
                    "userId": userid,
                    "carte": {
                        'typeCarte': extracted_entities.get('typeCarte'),
                        "raisonsOpposition": extracted_entities.get('raisonsOpposition')
                    }
                }
                message = self.spring_api.post_data('/cartes/opposeByCardType', response_body)
                return None, message, []
            else:
                response_body = {
                    "userId": userid,
                    "carte": {
                        'typeCarte': extracted_entities.get('typeCarte'),
                        "raisonsOpposition": extracted_entities.get('raisonsOpposition'),
                        'numeroCarte': extracted_entities.get('numeroCarte')
                    }
                }
                message = self.spring_api.post_data('/cartes/opposeByCardNum', response_body)
                return None, message, []
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return None, message, []
        elif context == "Missing_Entity":
            if len(extracted_entities) == len(required_entities) and numeroCarte is None:
                message = "Veuillez préciser votre numéro de compte!"
                return f"Entity_Missing_Gestion_Cartes_Opposition", message, merged_entities
            elif len(extracted_entities) == len(required_entities) and numeroCarte is not None:

                message = self.spring_api.get_data(f'/userCardsByNum/{numeroCarte}')
                if message:
                    message = f"Souhaitez-vous opposer votre carte {typeCarte} numéro {numeroCarte} pour {raisonsOpposition}? Merci de confirmer cette demande!"
                    return f"Request_Validation_Gestion_Cartes_Opposition", message, merged_entities
                else:
                    message = f"Aucune carte ne correspond à ce numéro!"
                    return f"Entity_Missing_Gestion_Cartes_Opposition", message, merged_entities
            else:
                missing_entities = [entity for entity in required_entities if entity not in extracted_entities]
                if missing_entities:
                    message = "Désolé, vous n'avez pas spécifié le  : " + ', '.join(missing_entities)
                    if len(missing_entities) > 1:
                        message += ". Veuillez les spécifier."
                    else:
                        message += ". Veuillez le spécifier."
                    return extracted_entities, f"Entity_Missing_Gestion_Cartes_Opposition", message
                else:
                    message = f"Souhaitez-vous opposer votre carte {typeCarte} numéro {numeroCarte} pour {raisonsOpposition}? Merci de confirmer cette demande!"
                    return f"Request_Validation_Gestion_Cartes_Opposition", message, merged_entities

    def action_complete_plafond_augmenter(self, data, extracted_entities, patterns, context):
        return self.action_complete_plafond(data, extracted_entities, patterns, context, "Augmenter")

    def action_complete_plafond_diminuer(self, data, extracted_entities, patterns, context):
        return self.action_complete_plafond(data, extracted_entities, patterns, context, "Diminuer")

    def action_complete_ajout_transaction_virement(self, data, extracted_entities, patterns, context):
        text = data['text'].lower()
        userid = data['userId']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCompte', 'nom', 'prenom', 'montant', 'typeOperation']
        new_extracted_entities = {}
        typeCompte = None
        numeroCompte = None
        ribBeneficiaire = None
        typeOperation = None
        montant = None
        motif = None
        if entities_ner_regex:
            typeCompte = entities_ner_regex.get('typeCompte')
            numeroCompte = entities_ner_regex.get('numeroCompte')
            typeOperation = entities_ner_regex.get('typeOperation')
            montant = entities_ner_regex.get('montant')
            motif = entities_ner_regex.get('motif')
            ribBeneficiaire = entities_ner_regex('rib')

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()

        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
        if motif: new_extracted_entities['motif'] = motif
        if ribBeneficiaire: new_extracted_entities['rib'] = ribBeneficiaire
        if numeroCompte: new_extracted_entities['numeroCompte'] = numeroCompte
        merged_entities = {**extracted_entities, **new_extracted_entities}
        if context == "Confirmation_Action":
            if ['typeCompte', 'nom', 'prenom', 'montant', 'typeOperation'] in extracted_entities.keys():
                response_body = {
                    "userId": userid,
                    "compte": {
                        'typeCompte': extracted_entities.get('typeCompte')
                    },
                    "beneficiaire": {
                        "nom": extracted_entities.get('nom'),
                        "prenom": extracted_entities.get('prenom')
                    },
                    "operation": {
                        "motif": extracted_entities.get('motif') if extracted_entities.get('motif') else "",
                        'montant': extracted_entities.get('montant'),
                        'typeOperation': extracted_entities('typeOperation')
                    }
                }
                message = self.spring_api.post_data('/operations/addByAccountTypeBeneficiaryNames', response_body)
                return None, message, []
            elif ['typeCompte', 'rib', 'montant', 'typeOperation'] in extracted_entities.keys():
                response_body = {
                    "userId": userid,
                    "compte": {
                        'typeCompte': extracted_entities.get('typeCompte')
                    },
                    "beneficiaire": {
                        "rib": extracted_entities.get('rib')
                    },
                    "operation": {
                        "motif": extracted_entities.get('motif') if extracted_entities.get('motif') else "",
                        'montant': extracted_entities.get('montant'),
                        'typeOperation': extracted_entities('typeOperation')
                    }
                }
                message = self.spring_api.post_data('/operations/addByAccountTypeAndRib', response_body)
                return None, message, []
            elif ['numeroCompte', 'rib', 'montant', 'typeOperation'] in extracted_entities.keys():
                response_body = {
                    "userId": userid,
                    "compte": {
                        'numeroCompte': extracted_entities.get('numeroCompte')
                    },
                    "beneficiaire": {
                        "rib": extracted_entities.get('rib')
                    },
                    "operation": {
                        "motif": extracted_entities.get('motif') if extracted_entities.get('motif') else "",
                        'montant': extracted_entities.get('montant'),
                        'typeOperation': extracted_entities('typeOperation')
                    }
                }
                message = self.spring_api.post_data('/operations/addByAccountNumAndRib', response_body)
                return None, message, []
            elif ['numeroCompte', 'nom', 'prenom', 'montant', 'typeOperation'] in extracted_entities.keys():
                response_body = {
                    "userId": userid,
                    "compte": {
                        'numeroCompte': extracted_entities.get('numeroCompte'),

                    },
                    "beneficiaire": {
                        "nom": extracted_entities.get('nom'),
                        "prenom": extracted_entities.get('prenom'),
                    },
                    "operation": {
                        'montant': extracted_entities.get('montant'),
                        'typeOperation': extracted_entities('typeOperation')
                    }
                }
                message = self.spring_api.post_data('/operations/addByAccountNumBeneficiaryNames', response_body)
                return None, message, []
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return None, message, []
        elif context == "Missing_Entity":
            if extracted_entities.keys() == required_entities:
                if 'besoin_numeroCompte' in extracted_entities.keys():
                    if numeroCompte is None:
                        message = "Veuillez préciser votre numéro de compte!"
                        return "Entity_Missing_Transaction_Virement", message, merged_entities
                    else:
                        message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                        return "Request_Validation_Transaction_Virement", message, merged_entities
                elif 'besoin_ribBeneficiaire' in extracted_entities.keys():
                    if ribBeneficiaire is None:
                        message = "Veuillez préciser le RIB du bénéficiaire!"
                        return "Entity_Missing_Transaction_Virement", message, merged_entities
                    else:
                        message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                        return "Request_Validation_Transaction_Virement", message, merged_entities
                elif 'besoin_ribBeneficiaire' and 'besoin_numeroCompte' in extracted_entities.keys():
                    if numeroCompte is None or ribBeneficiaire is None:
                        message = "Veuillez préciser le RIB du bénéficiaire et le numéro de votre compte bancaire!"
                        return "Entity_Missing_Transaction_Virement", message, merged_entities
                    else:
                        message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                        return "Request_Validation_Transaction_Virement", message, merged_entities
            else:
                missing_entities = [entity for entity in required_entities if entity not in extracted_entities]
                if missing_entities:
                    message = "Désolé, vous n'avez pas spécifié le  : " + ', '.join(missing_entities)
                    if len(missing_entities) > 1:
                        message += ". Veuillez les spécifier."
                    else:
                        message += ". Veuillez le spécifier."
                    return extracted_entities, "Request_Validation_Transaction_Virement", message
                else:
                    message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                    return "Request_Validation_Transaction_Virement", message, merged_entities

    def action_ajout_transaction_virement(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCompte', 'nom', 'prenom', 'montant', 'typeOperation']
        extracted_entities = {}
        typeCompte = None
        typeOperation = None
        montant = None
        motif = None
        if entities_ner_regex:
            typeCompte = entities_ner_regex.get('typeCompte')
            typeOperation = entities_ner_regex.get('typeOperation')
            montant = entities_ner_regex.get('montant')
            motif = entities_ner_regex.get('motif')

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()

        extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                              locals().get(entity) is not None}
        if motif: extracted_entities['motif'] = motif
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            message = "Désolé, vous n'avez pas spécifié le : " + ', '.join(
                missing_entities)
            if len(missing_entities) > 1:
                message += ". Veuillez les spécifier."
            else:
                message += ". Veuillez le spécifier."
            return f"Entity_Missing_Transaction_Virement", message, extracted_entities
        else:
            comptes = self.check_comptes(userid, extracted_entities)
            beneficiaries = self.check_beneficiaires(userid, extracted_entities)
            if comptes and beneficiaries:
                if len(comptes) == 1:
                    if len(beneficiaries) == 1:
                        message = (
                            f"Vous souhaitez passer un virement {typeOperation} pour {nom} {prenom} avec le montant {montant} dirhams avec votre compte {typeCompte}. Merci de "
                            f"confirmer cette demande!")
                        return f"Required_Validation_Transaction_Virement", message, extracted_entities
                    else:
                        extracted_entities['besoin_ribBeneficiaire'] = None
                        message = "Vous avez plusieurs bénéficiaires avec les mêmes noms, merci de préciser le numéro de RIB de votre bénéficiaire"
                    return f"Entity_Missing_Transaction_Virement", message, extracted_entities
                else:
                    if len(beneficiaries) == 1:
                        extracted_entities['besoin_numCompte'] = None
                        message = "Vous avez plusieurs comptes du même type, merci de préciser le numéro de compte avec lequel vous souhaiter passer le virement!"
                        return f"Entity_Missing_Transaction_Virement", message, extracted_entities
                    else:
                        extracted_entities['besoin_ribBeneficiaire'] = None
                        extracted_entities['besoin_numCompte'] = None
                        message = "Vous avez plusieurs comptes du même type et plusieurs bénéficiaires avec les mêmes noms, merci de préciser le numéro de compte et le RIB du bénéficiare avec lesquels vous souhaiter passer le virement!"
                        return f"Entity_Missing_Transaction_Virement", message, extracted_entities
            else:
                message = "Le type de compte ou les noms du bénéficiaires sont incorrectes!"
                return f"Entity_Missing_Transaction_Virement", message, extracted_entities
