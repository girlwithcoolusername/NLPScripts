import random
import decimal
from chatbot_api.faq_logic.longchain_helper import get_qa_chain
from chatbot_api.utils.contstants import CANCEL_ACTION, ASSISTANCE_ACTION, MATCHING_PATTERNS
from chatbot_api.utils.nlu import entity_extraction
from chatbot_api.utils.util_functions import filter_operations, get_cartes_message, get_operations_message, \
    get_comptes_message, get_agences_messages, get_missing_entity_message, merge_entities


class IntentActions:
    def __init__(self, spring_api_service):
        self.spring_api = spring_api_service

    def info_assistance_action(self):
        response = random.choice(ASSISTANCE_ACTION)
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
        _, entities_ner_regex = entity_extraction(text, patterns)
        if entities_ner_regex:
            for patternName, value in entities_ner_regex.items():
                if value:
                    entities_dict[patternName] = value[0]
            response_body = {"userId": userid, "entitiesDic": entities_dict}
            comptes = self.spring_api.post_data('comptes/searchEntitiesDict', response_body)
            return get_comptes_message(comptes)
        else:
            comptes = self.spring_api.get_data(f"comptes/user/{userid}")
            return get_comptes_message(comptes)

    def consultation_cartes_action(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        entities_dict = {}
        request_list = []
        _, entities_ner_regex = entity_extraction(text, patterns)
        if entities_ner_regex:
            for patternName, value in entities_ner_regex.items():
                if value:
                    if 'demande_' not in patternName:
                        if patternName == "numeroCarte":
                            entities_dict[patternName] = int(value[0])
                        else:
                            entities_dict[patternName] = value[0]
                    else:
                        request_list.append(patternName)
            response_body = {"userId": userid, "entitiesDic": entities_dict}
            cartes = self.spring_api.post_data('cartes/searchEntitiesDict', response_body)
            return get_cartes_message(request_list, cartes)
        else:
            cartes = self.spring_api.get_data(f"cartes/user/{userid}")
            return get_cartes_message(request_list, cartes)

    def consultation_operations_action(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        entities_dict = {}
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)

        if entities_ner_regex is None:
            operations = self.spring_api.get_data(f"operations/user/{userid}")
        else:
            for patternName, value in entities_ner_regex.items():
                if value:
                    entities_dict[patternName] = value[0]
            response_body = {"userId": userid, "entitiesDic": entities_dict}
            operations = self.spring_api.post_data('operations/searchEntitiesDict', response_body)

        if operations:
            filtered_operations = filter_operations(operations, entities_ner_bert)
            return get_operations_message(operations, filtered_operations)
        else:
            return "Désolé, je n'ai trouvé aucune opération associée à votre compte."

    def action_process_beneficiaire(self, data, patterns, required_entities, action_type):
        text = data['text'].lower()
        userid = data['userId']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        extracted_entities = {}
        missing_entities = []
        nom = None
        prenom = None
        rib = None
        typeBeneficiaire = None
        newRib = None
        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()
        if entities_ner_regex:
            if entities_ner_regex.get('typeBeneficiaire'):
                typeBeneficiaire = entities_ner_regex.get('typeBeneficiaire')[0]
            if entities_ner_regex.get('rib'):
                if len(entities_ner_regex.get('rib')) == 2:
                    if self.which_rib(userid, entities_ner_regex):
                        rib = entities_ner_regex.get('rib')[0].upper()
                        newRib = entities_ner_regex.get('rib')[1].upper()
                    else:
                        rib = entities_ner_regex.get('rib')[1].upper()
                        newRib = entities_ner_regex.get('rib')[0].upper()
                else:
                    if action_type == "modification":
                        if self.which_rib(userid, entities_ner_regex):
                            rib = entities_ner_regex.get('rib')[0].upper()
                        else:
                            newRib = entities_ner_regex.get('rib')[0].upper()
                    else:
                        rib = entities_ner_regex.get('rib')[0].upper()

        for entity in required_entities:
            if locals().get(entity) is None:
                missing_entities.append(entity)
            else:
                extracted_entities[entity] = locals().get(entity)
        missing_entities = list(set(missing_entities))
        if missing_entities:
            return self.handle_missing_entity(missing_entities, extracted_entities,
                                              f"Gestion_Bénéficiare_{action_type.capitalize()}")
        else:
            if action_type == "ajout":
                message = f"Vous voulez ajouter un bénéficiaire avec le nom {nom}, le prénom {prenom} comme personne {typeBeneficiaire} ayant pour rib {rib}. Merci de confirmer cette demande!"
                return f"Request_Validation_Gestion_Bénéficiare_{action_type.capitalize()}", message, extracted_entities
            elif action_type == "suppression":
                if rib: extracted_entities['rib'] = rib
                beneficiaries = self.check_beneficiaires(userid, extracted_entities)
                if beneficiaries:
                    if len(beneficiaries) == 1:
                        message = f"Vous voulez supprimer le bénéficiaire {nom} {prenom}. Merci de confirmer cette demande!"
                        return f"Request_Validation_Gestion_Bénéficiare_{action_type.capitalize()}", message, extracted_entities
                    else:
                        extracted_entities['besoin_ribBeneficiaire'] = None
                        if rib:
                            message = f"Vous voulez supprimer le bénéficiaire ayant le {rib}. Merci de confirmer cette demande!"
                            return f"Request_Validation_Gestion_Bénéficiare_{action_type.capitalize()}", message, extracted_entities
                        else:
                            message = f"Vous avez plusieurs bénéficiaires avec le même nom, merci de préciser le RIB du bénéficiaire!"
                            return f"Entity_Missing_Gestion_Bénéficiare_{action_type.capitalize()}", message, extracted_entities
                else:
                    message = "Aucun bénéficiaire ne correspond à ces noms!"
                    extracted_entities.pop('nom')
                    extracted_entities.pop('prenom')
                    return f"Entity_Missing_Gestion_Bénéficiare_{action_type.capitalize()}", message, extracted_entities
            elif action_type == "modification":
                if rib: extracted_entities['rib'] = rib
                beneficiaries = self.check_beneficiaires(userid, extracted_entities)
                if beneficiaries:
                    if len(beneficiaries) == 1:
                        message = f"Vous voulez modifier le bénéficiaire {nom} {prenom} avec le nouveau RIB {newRib}. Merci de confirmer cette demande!"
                        return "Request_Validation_Gestion_Bénéficiare_Modification", message, extracted_entities
                    else:
                        extracted_entities['besoin_ribBeneficiaire'] = None
                        if rib:
                            message = f"Vous voulez modifier le bénéficiaire {nom} {prenom} avec le nouveau RIB {newRib}. Merci de confirmer cette demande!"
                            return "Request_Validation_Gestion_Bénéficiare_Modification", message, extracted_entities
                        else:
                            message = f"Vous avez plusieurs bénéficiaires avec le même nom, merci préciser le RIB du bénéficiaire!"
                            return "Entity_Missing_Gestion_Bénéficiare_Modification", message, extracted_entities
                else:
                    message = "Aucun bénéficiaire ne correspond à ces noms!"
                    extracted_entities.pop('nom')
                    extracted_entities.pop('prenom')
                    return "Entity_Missing_Gestion_Bénéficiare_Suppression", message, extracted_entities

    def action_complete_process_beneficiaires(self, data, extracted_entities, patterns, context, required_entities,
                                              action_type):
        text = data['text'].lower()
        userid = data['userId']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        new_extracted_entities = {}
        missing_entities = []
        nom = None
        prenom = None
        rib = None
        typeBeneficiaire = None
        newRib = None

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()

        if entities_ner_regex:
            if entities_ner_regex.get('typeBeneficiaire'):
                typeBeneficiaire = entities_ner_regex.get('typeBeneficiaire')[0]
            if entities_ner_regex.get('rib'):
                if len(entities_ner_regex.get('rib')) == 2:
                    if self.which_rib(userid, entities_ner_regex):
                        rib = entities_ner_regex.get('rib')[0].upper()
                        newRib = entities_ner_regex.get('rib')[1].upper()
                    else:
                        rib = entities_ner_regex.get('rib')[1].upper()
                        newRib = entities_ner_regex.get('rib')[0].upper()
                else:
                    if action_type == "modification" and context == "Missing_Entity":
                        if 'besoin_ribBeneficiaire' in extracted_entities.keys():
                            if 'rib' in extracted_entities.keys():
                                newRib = entities_ner_regex.get('rib')[0].upper()
                            else:
                                if self.which_rib(userid, entities_ner_regex):
                                    rib = entities_ner_regex.get('rib')[0].upper()
                                else:
                                    newRib = entities_ner_regex.get('rib')[0].upper()
                        else:
                            newRib = entities_ner_regex.get('rib')[0].upper()
                    else:
                        rib = entities_ner_regex.get('rib')[0].upper()
        for entity in required_entities:
            if locals().get(entity) is not None:
                new_extracted_entities[entity] = locals().get(entity)
        if action_type == "ajout":
            merged_entities = merge_entities(extracted_entities, new_extracted_entities)
            if context == "Confirmation_Action":
                response_body = {
                    "userId": userid,
                    "beneficiaire": {
                        "nom": extracted_entities.get('nom'),
                        "prenom": extracted_entities.get("prenom"),
                        "rib": extracted_entities.get("rib"),
                        "typeBeneficiaire": extracted_entities.get('typeBeneficiaire')
                    }
                }
                message = self.spring_api.post_data_text('beneficiaires/add', response_body)
                return "user_request", message, {}
            elif context == "Annulation_action":
                message = random.choice(CANCEL_ACTION)
                return "user_request", message, {}
            elif context == "Missing_Entity":
                for entity in required_entities:
                    if entity not in merged_entities:
                        missing_entities.append(entity)
                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                key in MATCHING_PATTERNS]
                if missing_entities:
                    message = get_missing_entity_message(missing_entities_explication)
                    return f"Entity_Missing_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
                else:
                    message = f"Vous voulez ajouter un bénéficiaire avec le nom {merged_entities.get('nom')}, le prénom {merged_entities.get('prenom')} comme {merged_entities.get('typeBeneficiaire')} ayant pour rib {merged_entities.get('rib')}. Merci de confirmer cette demande!"
                    return f"Request_Validation_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
        elif action_type == "suppression":
            if rib: new_extracted_entities['rib'] = rib
            merged_entities = merge_entities(extracted_entities, new_extracted_entities)
            if context == "Confirmation_Action":
                if 'besoin_ribBeneficiaire' not in extracted_entities.keys():
                    response_body = {
                        "userId": userid,
                        "beneficiaire": {
                            'nom': extracted_entities.get('nom'),
                            "prenom": extracted_entities.get("prenom"),
                        }
                    }
                    message = self.spring_api.delete_data('beneficiaires/delete/names', response_body)
                    return "user_request", message, {}
                else:
                    response_body = {
                        "userId": userid,
                        "beneficiaire": {
                            'rib': extracted_entities.get('rib')
                        }
                    }
                    message = self.spring_api.delete_data('beneficiaires/delete/rib', response_body)
                    return "user_request", message, {}
            elif context == "Annulation_Action":
                message = random.choice(CANCEL_ACTION)
                return "user_request", message, {}
            elif context == "Missing_Entity":
                if 'besoin_ribBeneficiaire' in extracted_entities.keys():
                    if 'rib' not in merged_entities.keys():
                        message = "Veuillez préciser le RIB du bénéficiaire!"
                        return f"Entity_Missing_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
                    else:
                        if all(entity in merged_entities.keys() for entity in required_entities):
                            response_body = {
                                "userId": userid,
                                "beneficiaire": {
                                    'rib': rib
                                }
                            }
                            beneficiaire = self.spring_api.post_data('beneficiaires/user/rib', response_body)
                            if beneficiaire:
                                message = f"Souhaitez-vous supprimer le bénéficiaire avec le RIB {rib} ? Merci de confirmer cette demande!"
                                return f"Request_Validation_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
                            else:
                                message = f"Le RIB spécifié ne correspond à aucun bénéficiaire."
                                merged_entities.pop('rib')
                                return f"Entity_Missing_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
                        else:
                            for entity in required_entities:
                                if entity not in merged_entities:
                                    missing_entities.append(entity)
                            missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                            key in MATCHING_PATTERNS]
                            if missing_entities:
                                message = get_missing_entity_message(missing_entities_explication)
                                return f"Entity_Missing_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
                else:
                    for entity in required_entities:
                        if entity not in merged_entities:
                            missing_entities.append(entity)
                    missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                    key in MATCHING_PATTERNS]
                    if missing_entities:
                        message = get_missing_entity_message(missing_entities_explication)
                        return f"Entity_Missing_Gestion_Bénéficiare__{action_type.capitalize()}", message, merged_entities
                    else:
                        message = f"Vous voulez supprimer le bénéficiaire {merged_entities.get('nom')} {merged_entities.get('prenom')}. Merci de confirmer cette demande!"
                        return f"Request_Validation_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
        elif action_type == "modification":
            if context == "Confirmation_Action":
                if 'besoin_ribBeneficiaire' not in extracted_entities:
                    response_body = {
                        "userId": userid,
                        "beneficiaire": {
                            'nom': extracted_entities.get('nom'),
                            "prenom": extracted_entities.get("prenom"),
                        },
                        "newRib": extracted_entities.get('newRib')
                    }
                    message = self.spring_api.put_data('beneficiaires/update/names', response_body)
                    return "user_request", message, {}
                else:
                    response_body = {
                        "userId": userid,
                        "oldRib": extracted_entities.get('rib'),
                        "newRib": extracted_entities.get('newRib')
                    }
                    message = self.spring_api.put_data('beneficiaires/update/rib', response_body)
                    return "user_request", message, {}
            elif context == "Annulation_Action":
                message = random.choice(CANCEL_ACTION)
                return "user_request", message, {}
            elif context == "Missing_Entity":
                if rib: new_extracted_entities['rib'] = rib
                merged_entities = merge_entities(extracted_entities, new_extracted_entities)
                if 'besoin_ribBeneficiaire' in extracted_entities:
                    if 'rib' in merged_entities.keys():
                        message = "Veuillez préciser le RIB du bénéficiaire à modifier"
                        return f"Entity_Missing_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
                    else:
                        if all(entity in merged_entities.keys() for entity in required_entities):
                            response_body = {
                                "userId": userid,
                                'beneficiaire': {
                                    "rib": merged_entities.get('rib')
                                }
                            }
                            beneficiaire = self.spring_api.post_data_check('beneficiaires/user/rib', response_body)
                            if beneficiaire:
                                message = f"Souhaitez-vous modifier le bénéficiaire avec le RIB {rib} ? Merci de confirmer cette demande!"
                                return f"Request_Validation_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
                            else:
                                message = f"Le RIB spécifié ne correspond à aucun bénéficiaire."
                                merged_entities.pop('rib')
                                return f"Entity_Missing_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
                        else:
                            for entity in required_entities:
                                if entity not in merged_entities:
                                    missing_entities.append(entity)
                            missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                            key in MATCHING_PATTERNS]
                            if missing_entities:
                                message = get_missing_entity_message(missing_entities_explication)
                                return f"Entity_Missing_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
                else:
                    for entity in required_entities:
                        if entity not in merged_entities:
                            missing_entities.append(entity)
                    missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                    key in MATCHING_PATTERNS]
                    if missing_entities:
                        message = get_missing_entity_message(missing_entities_explication)
                        return f"Entity_Missing_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities
                    else:
                        message = f"Vous voulez modifier le bénéficiaire {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le RIB {merged_entities.get('newRib')}. Merci de confirmer cette demande!"
                        return f"Request_Validation_Gestion_Bénéficiare_{action_type.capitalize()}", message, merged_entities

    def action_ajout_beneficiaire(self, data, patterns):
        required_entities = ['nom', 'prenom', 'rib', 'typeBeneficiaire']
        return self.action_process_beneficiaire(data, patterns, required_entities, "ajout")

    def action_complete_ajout_beneficiaire(self, data, extracted_entities, patterns, context):
        required_entities = ['nom', 'prenom', 'rib', 'typeBeneficiaire']
        return self.action_complete_process_beneficiaires(data, extracted_entities, patterns, context,
                                                          required_entities,
                                                          "ajout")

    def action_suppression_beneficiaire(self, data, patterns):
        required_entities = ['nom', 'prenom']
        return self.action_process_beneficiaire(data, patterns, required_entities, "suppression")

    def action_complete_suppression_beneficiaire(self, data, extracted_entities, patterns, context):
        required_entities = ['nom', 'prenom']
        return self.action_complete_process_beneficiaires(data, extracted_entities, patterns, context,
                                                          required_entities, "suppression")

    def action_modification_beneficiaire(self, data, patterns):
        required_entities = ['nom', 'prenom', 'newRib']
        return self.action_process_beneficiaire(data, patterns, required_entities, "modification")

    def action_complete_modification_beneficiaire(self, data, extracted_entities, patterns, context):
        required_entities = ['nom', 'prenom', 'newRib']
        return self.action_complete_process_beneficiaires(data, extracted_entities, patterns, context,
                                                          required_entities, "modification")

    def action_services_cartes(self, data, patterns, status):
        text = data['text'].lower()
        userid = data['userId']
        _, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCarte', 'services']
        extracted_entities = {}
        missing_entities = []
        typeCarte,services,numeroCarte,numero_carte_str = None,None,None,None

        if entities_ner_regex:
            if entities_ner_regex.get('typeCarte'):
                typeCarte = entities_ner_regex.get('typeCarte')[0]
            if entities_ner_regex.get('services'):
                services = entities_ner_regex.get('services')
            if entities_ner_regex.get('numeroCarte'):
                numero_carte_str = entities_ner_regex.get('numeroCarte')[0]
                numeroCarte = int(numero_carte_str)

        for entity in required_entities:
            if locals().get(entity) is None:
                missing_entities.append(entity)
            else:
                extracted_entities[entity] = locals().get(entity)
        missing_entities = list(set(missing_entities))
        if numeroCarte: extracted_entities['numeroCarte'] = numeroCarte
        if missing_entities:
            return self.handle_missing_entity(missing_entities, extracted_entities, f"Gestion_Cartes_{status}")
        else:
            cartes = self.check_cartes(userid, extracted_entities)
            if cartes:
                if len(cartes) == 1:
                    if status == "Activation":
                        message = (
                            f"Vous voulez ajouter les services {', '.join(services)} pour votre carte {typeCarte}. Merci de "
                            f"confirmer cette demande!")
                        return f"Request_Validation_Gestion_Cartes_{status}", message, extracted_entities
                    elif status == "Désactivation":
                        message = (
                            f"Vous voulez supprimer les services {', '.join(services)} pour votre carte {typeCarte}. Merci de "
                            f"confirmer cette demande!")
                    return f"Request_Validation_Gestion_Cartes_{status}", message, extracted_entities
                else:
                    extracted_entities['besoin_numeroCarte'] = None
                    if numeroCarte:
                        message = (
                            f"Vous voulez ajouter les services {', '.join(services)} pour votre carte numéro {numeroCarte}. Merci de "
                            f"confirmer cette demande!")
                        return f"Request_Validation_Gestion_Cartes_{status}", message, extracted_entities
                    else:
                        message = (
                            f"Vous avez plusieurs cartes du même type, merci de préciser le numéro de votre carte "
                            f"bancaire!")
                        return f"Entity_Missing_Gestion_Cartes_{status}", message, extracted_entities
            else:
                message = "Aucune carte ne correspond aux informations que vous venez de donner!"
                extracted_entities.pop('typeCarte')
                return f"Entity_Missing_Gestion_Cartes_{status}", message, extracted_entities

    def action_complete_services_cartes(self, data, extracted_entities, patterns, context, status):
        text = data['text'].lower()
        userid = data['userId']
        required_entities = ['typeCarte', 'services']
        _, entities_ner_regex = entity_extraction(text, patterns)
        new_extracted_entities = {}
        missing_entities = []
        typeCarte,services,numeroCarte,numero_carte_str = None,None,None,None

        if entities_ner_regex:
            if entities_ner_regex.get('typeCarte'):
                typeCarte = entities_ner_regex.get('typeCarte')[0]
            if entities_ner_regex.get('services'):
                services = entities_ner_regex.get('services')
            if entities_ner_regex.get('numeroCarte'):
                numero_carte_str = entities_ner_regex.get('numeroCarte')[0]
                numeroCarte = int(numero_carte_str)

        for entity in required_entities:
            if locals().get(entity) is not None:
                new_extracted_entities[entity] = locals().get(entity)
        if numeroCarte: new_extracted_entities['numeroCarte'] = numeroCarte
        merged_entities = merge_entities(extracted_entities, new_extracted_entities)
        if context == "Confirmation_Action":
            if all(entity in extracted_entities.keys() for entity in required_entities):
                response_body = {
                    "userId": userid,
                    "carte": {
                        'typeCarte': extracted_entities.get('typeCarte'),
                    },
                    "services": extracted_entities.get('services'),
                    "status": "enable" if status == "Activation" else "disable"
                }
                message = self.spring_api.put_data('cartes/updateByCardType', response_body)
                return "user_request", message, {}
            elif all(entity in extracted_entities.keys() for entity in required_entities) and 'besoin_numeroCarte' in extracted_entities:
                response_body = {
                    "userId": userid,
                    "carte": {
                        'typeCarte': extracted_entities.get('typeCarte'),
                        'numeroCarte': extracted_entities.get('numeroCarte')
                    },
                    "services": extracted_entities.get('services'),
                    "status": "enable" if status == "Activation" else "disable"
                }
                message = self.spring_api.put_data('cartes/updateByCardNum', response_body)
                return "user_request", message, {}
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return "user_request", message, {}
        elif context == "Missing_Entity":
            if 'besoin_numeroCarte' in extracted_entities.keys():
                if 'numeroCarte' not in merged_entities.keys():
                    message = "Veuillez préciser votre numéro de carte!"
                    return f"Entity_Missing_Gestion_Cartes_{status}", message, merged_entities
                else:
                    if all(entity in merged_entities.keys() for entity in required_entities):
                        message = self.spring_api.get_data(f'/userCardsByNum/{numeroCarte}')
                        if message:
                            message = f"Souhaitez-vous modifier les services permis par votre carte {typeCarte} numéro {numeroCarte} ? Merci de confirmer cette demande!"
                            return f"Request_Validation_Gestion_Cartes_{status}", message, merged_entities
                        else:
                            message = f"Aucune carte ne correspond à ce numéro!"
                            merged_entities.pop('numeroCarte')
                            return f"Entity_Missing_Gestion_Cartes_{status}", message, merged_entities
                    else:
                        for entity in required_entities:
                            if entity not in merged_entities:
                                missing_entities.append(entity)
                        missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                        key in MATCHING_PATTERNS]
                        if missing_entities:
                            message = get_missing_entity_message(missing_entities_explication)
                            return f"Entity_Missing_Gestion_Cartes_{status}", message, merged_entities
            else:
                for entity in required_entities:
                    if entity not in merged_entities:
                        missing_entities.append(entity)
                missing_entities = list(set(missing_entities))
                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                key in MATCHING_PATTERNS]
                if missing_entities:
                    message = get_missing_entity_message(missing_entities_explication)
                    return f"Entity_Missing_Gestion_Cartes_{status}", message, merged_entities
                else:
                    message = f"Souhaitez-vous modifier les services {merged_entities.get('services')} permis par votre carte {merged_entities.get('typeCarte')} ? Merci de confirmer cette demande!"
                    return f"Request_Validation_Gestion_Cartes_{status}", message, merged_entities

    def action_activation_carte(self, data, patterns):
        return self.action_services_cartes(data, patterns, "Activation")

    def action_desactivation_carte(self, data, patterns):
        return self.action_services_cartes(data, patterns, "Désactivation")

    def action_complete_activation_carte(self, data, extracted_entities, patterns, context):
        return self.action_complete_services_cartes(data, extracted_entities, patterns, context, "Activation")

    def action_complete_desactivation_carte(self, data, extracted_entities, patterns, context):
        return self.action_complete_services_cartes(data, extracted_entities, patterns, context, "Désactivation")

    def action_opposition_carte(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        _, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCarte', 'raisonsOpposition']
        numero_carte_str, numeroCarte, typeCarte, raisonsOpposition = None, None, None, None
        extracted_entities = {}
        missing_entities = []
        if entities_ner_regex:
            if entities_ner_regex.get('typeCarte'):
                typeCarte = entities_ner_regex.get('typeCarte')[0]
            if entities_ner_regex.get('raisonsOpposition'):
                raisonsOpposition = entities_ner_regex.get('raisonsOpposition')[0]
            if entities_ner_regex.get('numeroCarte'):
                numero_carte_str = entities_ner_regex.get('numeroCarte')[0]
                if numero_carte_str:
                    numeroCarte = int(numero_carte_str)
        # Check for each required entity
        for entity in required_entities:
            if locals()[entity] is None:
                missing_entities.append(entity)
            else:
                extracted_entities[entity] = locals()[entity]
        # Remove duplicate entries in missing_entities, if any
        missing_entities = list(set(missing_entities))
        if numeroCarte: extracted_entities['numeroCarte'] = numeroCarte
        if missing_entities:
            return self.handle_missing_entity(missing_entities, extracted_entities, "Gestion_Cartes_Opposition")
        else:
            cartes = self.check_cartes(userid, extracted_entities)
            if cartes:
                if len(cartes) == 1:
                    message = (
                        f"Vous voulez opposer votre carte {typeCarte} pour {raisonsOpposition}. Merci de "
                        f"confirmer cette demande!")
                    return f"Request_Validation_Gestion_Cartes_Opposition", message, extracted_entities
                else:
                    extracted_entities['besoin_numeroCarte'] = None
                    if numeroCarte:
                        message = (
                            f"Vous voulez opposer votre carte {typeCarte} numéro {numeroCarte} pour {raisonsOpposition}. Merci de "
                            f"confirmer cette demande!")
                        return f"Request_Validation_Gestion_Cartes_Opposition", message, extracted_entities
                    else:
                        message = (
                            f"Vous avez plusieurs cartes du même type, merci de préciser le numéro de votre carte "
                            f"bancaire!")
                        return f"Entity_Missing_Gestion_Cartes_Opposition", message, extracted_entities
            else:
                message = "Aucune carte ne correspond aux informations données!"
                extracted_entities.pop('typeCarte')
                return 'f"Entity_Missing_Gestion_Cartes_Opposition"', message, extracted_entities

    def action_complete_opposition_carte(self, data, extracted_entities, patterns, context):
        text = data['text'].lower()
        userid = data['userId']
        required_entities = ['typeCarte', 'raisonsOpposition']
        _, entities_ner_regex = entity_extraction(text, patterns)
        new_extracted_entities = {}
        missing_entities = []
        typeCarte, raisonsOpposition, numeroCarte, card_number_str = None, None, None, None

        if entities_ner_regex:
            if entities_ner_regex.get('typeCarte'):
                typeCarte = entities_ner_regex.get('typeCarte')[0]
            elif entities_ner_regex.get('raisonsOpposition'):
                raisonsOpposition = entities_ner_regex.get('raisonsOpposition')[0]
            elif entities_ner_regex.get('numeroCarte'):
                card_number_str = entities_ner_regex.get('numeroCarte')[0]
                if card_number_str:
                    numeroCarte = int(card_number_str)
        for entity in required_entities:
            if locals().get(entity) is not None:
                new_extracted_entities[entity] = locals().get(entity)
        if numeroCarte: new_extracted_entities['numeroCarte'] = numeroCarte
        merged_entities = merge_entities(extracted_entities, new_extracted_entities)
        if context == "Confirmation_Action":
            if 'besoin_numeroCarte' not in extracted_entities.keys():
                response_body = {
                    "userId": userid,
                    "carte": {
                        'typeCarte': extracted_entities.get('typeCarte'),
                        "raisonsOpposition": extracted_entities.get('raisonsOpposition')
                    }
                }
                message = self.spring_api.put_data('cartes/opposeByCardType', response_body)
                return "user_request", message, {}
            else:
                response_body = {
                    "userId": userid,
                    "carte": {
                        'typeCarte': extracted_entities.get('typeCarte'),
                        "raisonsOpposition": extracted_entities.get('raisonsOpposition'),
                        'numeroCarte': extracted_entities.get('numeroCarte')
                    }
                }
                message = self.spring_api.put_data('cartes/opposeByCardNum', response_body)
                return "user_request", message, {}
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return "user_request", message, {}
        elif context == "Missing_Entity":
            if 'besoin_numeroCarte' in extracted_entities.keys():
                if 'numeroCarte' not in merged_entities.keys():
                    message = "Veuillez préciser votre numéro de carte!"
                    return f"Entity_Missing_Gestion_Cartes_Opposition", message, merged_entities
                else:
                    if all(entity in merged_entities.keys() for entity in required_entities):
                        message = self.spring_api.get_data(f'/userCardsByNum/{numeroCarte}')
                        if message:
                            message = f"Souhaitez-vous opposer votre carte {merged_entities.get('typeCarte')} numéro {merged_entities.get('numeroCarte')} pour {merged_entities.get('raisonsOpposition')}? Merci de confirmer cette demande!"
                            return f"Request_Validation_Gestion_Cartes_Opposition", message, merged_entities
                        else:
                            message = f"Aucune carte ne correspond à ce numéro!"
                            return f"Entity_Missing_Gestion_Cartes_Opposition", message, merged_entities.pop(
                                'numeroCarte')
                    else:
                        for entity in required_entities:
                            if entity not in merged_entities:
                                missing_entities.append(entity)
                        missing_entities = list(set(missing_entities))
                        missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                        key in MATCHING_PATTERNS]
                        if missing_entities:
                            message = get_missing_entity_message(missing_entities_explication)
                            return f"Entity_Missing_Gestion_Cartes_Opposition", message, merged_entities
            else:
                for entity in required_entities:
                    if entity not in merged_entities:
                        missing_entities.append(entity)
                missing_entities = list(set(missing_entities))
                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                key in MATCHING_PATTERNS]
                if missing_entities:
                    message = get_missing_entity_message(missing_entities_explication)
                    return "Entity_Missing_Gestion_Cartes_Opposition", message, merged_entities
                else:
                    message = f"Souhaitez-vous opposer votre carte {merged_entities.get('typeCarte')} pour {merged_entities.get('raisonsOpposition')}? Merci de confirmer cette demande!"
                    return "Request_Validation_Gestion_Cartes_Opposition", message, merged_entities

    def action_plafond_carte(self, data, patterns, status):
        text = data['text'].lower()
        userid = data['userId']
        _, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCarte', 'plafond', 'typePlafond']
        extracted_entities = {}
        missing_entities = []
        typeCarte, typePlafond, plafond, numeroCarte, card_number_str = None, None, None, None, None
        if entities_ner_regex:
            if entities_ner_regex.get('typeCarte'):
                typeCarte = entities_ner_regex.get('typeCarte')[0]
            if entities_ner_regex.get('typePlafond'):
                typePlafond = entities_ner_regex.get('typePlafond')[0]
            if entities_ner_regex.get('montant'):
                montant_str = entities_ner_regex.get('montant')[0]
                plafond = int(montant_str)
            if entities_ner_regex.get('numeroCarte'):
                card_number_str = entities_ner_regex.get('numeroCarte')[0]
                numeroCarte = int(card_number_str)

        for entity in required_entities:
            if locals().get(entity) is None:
                missing_entities.append(entity)
            else:
                extracted_entities[entity] = locals().get(entity)
        missing_entities = list(set(missing_entities))
        if numeroCarte: extracted_entities['numeroCarte'] = numeroCarte
        if missing_entities:
            return self.handle_missing_entity(missing_entities, extracted_entities, f"Gestion_Cartes_{status}_Plafond")
        else:
            cartes = self.check_cartes(userid, extracted_entities)
            if cartes:
                if len(cartes) == 1:
                    if status == "Augmenter":
                        message = (
                            f"Vous voulez augmenter le plafond de {typePlafond} pour votre carte {typeCarte}. Merci de "
                            f"confirmer cette demande!")
                    elif status == "Diminuer":
                        message = (
                            f"Vous voulez diminuer le plafond de {typePlafond} pour votre carte {typeCarte}. Merci de "
                            f"confirmer cette demande!")
                    return f"Request_Validation_Gestion_Cartes_{status}_Plafond", message, extracted_entities
                else:
                    extracted_entities['besoin_numeroCarte'] = None
                    if numeroCarte:
                        if status == "Augmenter":
                            message = (
                                f"Vous voulez augmenter le plafond de {typePlafond} pour votre carte numéro {numeroCarte}. Merci de "
                                f"confirmer cette demande!")
                        elif status == "Diminuer":
                            message = (
                                f"Vous voulez diminuer le plafond de {typePlafond} pour votre carte numéro {numeroCarte}. Merci de "
                                f"confirmer cette demande!")
                        return f"Request_Validation_Gestion_Cartes_{status}_Plafond", message, extracted_entities
                    else:
                        message = (
                            f"Vous avez plusieurs cartes du même type, merci de préciser le numéro de votre carte "
                            f"bancaire!")
                        return f"Entity_Missing_Gestion_Cartes_{status}_Plafond", message, extracted_entities
            else:
                message = "Aucune carte ne correspond à ces données"
                extracted_entities.pop('typeCarte')
                return f"Entity_Missing_Gestion_Cartes_{status}_Plafond", message, extracted_entities

    def action_complete_plafond(self, data, extracted_entities, patterns, context, status):
        text = data['text'].lower()
        userid = data['userId']
        required_entities = ['typeCarte', 'typePlafond', 'plafond']
        _, entities_ner_regex = entity_extraction(text, patterns)
        new_extracted_entities = {}
        missing_entities = []
        typeCarte, typePlafond, plafond, numeroCarte, card_number_str = None, None, None, None, None
        if entities_ner_regex:
            if entities_ner_regex.get('typeCarte'):
                typeCarte = entities_ner_regex.get('typeCarte')[0]
            if entities_ner_regex.get('typePlafond'):
                typePlafond = entities_ner_regex.get('typePlafond')[0]
            if entities_ner_regex.get('montant'):
                montant_str = entities_ner_regex.get('montant')[0]
                plafond = int(montant_str)
            if entities_ner_regex.get('numeroCarte'):
                card_number_str = entities_ner_regex.get('numeroCarte')[0]
                numeroCarte = int(card_number_str)

        for entity in required_entities:
            if locals().get(entity) is not None:
                new_extracted_entities[entity] = locals().get(entity)
        if numeroCarte: new_extracted_entities['numeroCarte'] = numeroCarte
        merged_entities = merge_entities(extracted_entities, new_extracted_entities)
        if context == "Confirmation_Action":
            if 'besoin_numeroCarte' not in extracted_entities.keys():
                response_body = {
                    "userId": userid,
                    "carte": {
                        "typeCarte": extracted_entities.get('typeCarte')
                    },
                    "plafond": {
                        "typePlafond": extracted_entities.get('typePlafond'),
                        "montantPlafond": extracted_entities.get('plafond'),
                    },
                    "statut": "add" if status == "Augmenter" else "disable",
                    "duration": ""
                }
                message = self.spring_api.put_data('plafond/updateByCardType', response_body)
                return "user_request", message, {}
            else:
                response_body = {
                    "userId": userid,
                    "carte": {
                        "typeCarte": extracted_entities.get('typeCarte'),
                        'numeroCarte': extracted_entities.get('numeroCarte'),

                    },
                    "plafond": {
                        "typePlafond": extracted_entities.get('typePlafond'),
                        "montantPlafond": extracted_entities.get('plafond'),
                    },
                    "statut": "add" if status == "Augmenter" else "disable",
                    "duration": ""
                }
                message = self.spring_api.put_data('plafond/updateByCardNum', response_body)
                return "user_request", message, {}
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return "user_request", message, {}
        elif context == "Missing_Entity":
            if 'besoin_numeroCarte' in extracted_entities.keys():
                if 'numeroCarte' not in merged_entities.keys():
                    message = "Veuillez préciser votre numéro de carte!"
                    return f"Entity_Missing_Gestion_Cartes_{status}_Plafond", message, merged_entities
                else:
                    if all(entity in merged_entities.keys() for entity in required_entities):
                        message = self.spring_api.get_data(f'/userCardsByNum/{numeroCarte}')
                        if message:
                            message = f"Souhaitez-vous {status.lower()} le plafond {merged_entities.get('typePlafond')} permis par votre carte {merged_entities.get('typeCarte')} numéro {numeroCarte} ? Merci de confirmer cette demande!"
                            return f"Request_Validation_Gestion_Cartes_{status}_Plafond", message, merged_entities
                        else:
                            message = f"Aucune carte ne correspond à ce numéro!"
                            merged_entities.pop('numeroCarte')
                            return f"Entity_Missing_Gestion_Cartes_{status}_Plafond", message, merged_entities
                    else:
                        for entity in required_entities:
                            if entity not in merged_entities:
                                missing_entities.append(entity)
                        missing_entities = list(set(missing_entities))
                        missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                        key in MATCHING_PATTERNS]
                        if missing_entities:
                            message = get_missing_entity_message(missing_entities_explication)
                            return f"Entity_Missing_Gestion_Cartes_{status}_Plafond", message, merged_entities
            else:
                for entity in required_entities:
                    if entity not in merged_entities:
                        missing_entities.append(entity)
                missing_entities = list(set(missing_entities))
                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                key in MATCHING_PATTERNS]
                if missing_entities:
                    message = get_missing_entity_message(missing_entities_explication)
                    return f"Entity_Missing_Gestion_Cartes_{status}_Plafond", message, merged_entities
                else:
                    message = f"Souhaitez-vous {status.lower()} le plafond {merged_entities.get('typePlafond')} permis par votre carte {merged_entities.get('typeCarte')} ? Merci de confirmer cette demande!"
                    return f"Request_Validation_Gestion_Cartes_{status}_Plafond", message, merged_entities

    def action_plafond_augmenter(self, data, patterns, status):
        return self.action_plafond_carte(data, patterns, "Augmenter")

    def action_plafond_diminuer(self, data, patterns):
        return self.action_plafond_carte(data, patterns, "Diminuer")

    def action_complete_plafond_augmenter(self, data, extracted_entities, patterns, context):
        return self.action_complete_plafond(data, extracted_entities, patterns, context, "Augmenter")

    def action_complete_plafond_diminuer(self, data, extracted_entities, patterns, context):
        return self.action_complete_plafond(data, extracted_entities, patterns, context, "Diminuer")

    def action_ajout_transaction_virement(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCompte', 'nom', 'prenom', 'montant', 'typeOperation']
        optional_entities = ['rib', 'numeroCompte', 'motif']
        extracted_entities = {}
        missing_entities = []
        nom,prenom,typeCompte,numeroCompte,ribBeneficiaire,typeOperation,montant,motif = None,None,None,None,None,None,None,None

        if entities_ner_regex:
            if entities_ner_regex.get('typeCompte'):
                typeCompte = entities_ner_regex.get('typeCompte')[0]
            if entities_ner_regex.get('rib'):
                ribBeneficiaire = entities_ner_regex.get('rib')[0]
            if entities_ner_regex.get('numeroCompte'):
                numeroCompte = entities_ner_regex.get('numeroCompte')[0].upper()
            if entities_ner_regex.get('typeOperation'):
                typeOperation = entities_ner_regex.get('typeOperation')[0]
            if entities_ner_regex.get('montant'):
                montant = int(entities_ner_regex.get('montant')[0])
            if entities_ner_regex.get('motif'):
                motif = entities_ner_regex.get('motif')[0]

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()

        for entity in required_entities:
            if locals().get(entity):
                extracted_entities[entity] = locals().get(entity)
            else:
                missing_entities.append(entity)
        for entity in optional_entities:
            if locals().get(entity):
                extracted_entities[entity] = locals().get(entity)
        missing_entities = list(set(missing_entities))
        if missing_entities:
            return self.handle_missing_entity(missing_entities, extracted_entities, 'Transaction_Virement')
        else:
            comptes = self.check_comptes(userid, extracted_entities)
            beneficiaries = self.check_beneficiaires(userid, extracted_entities)
            if comptes and beneficiaries:
                if len(comptes) == 1:
                    if len(beneficiaries) == 1:
                        message = (
                            f"Vous souhaitez passer un virement {typeOperation} pour {nom} {prenom} avec le montant {montant} dirhams avec votre compte {typeCompte}. Merci de "
                            f"confirmer cette demande!")
                        return f"Request_Validation_Transaction_Virement", message, extracted_entities
                    else:
                        extracted_entities['besoin_ribBeneficiaire'] = None
                        if ribBeneficiaire:
                            extracted_entities['rib'] = ribBeneficiaire
                            message = (
                                f"Vous souhaitez passer un virement {typeOperation} pour {nom} {prenom} avec le montant {montant} dirhams avec votre compte {typeCompte}. Merci de "
                                f"confirmer cette demande!")
                            return f"Request_Validation_Transaction_Virement", message, extracted_entities
                        else:
                            message = "Vous avez plusieurs bénéficiaires avec les mêmes noms, merci de préciser le numéro de RIB de votre bénéficiaire"
                            return f"Entity_Missing_Transaction_Virement", message, extracted_entities
                else:
                    if len(beneficiaries) == 1:
                        extracted_entities['besoin_numeroCompte'] = None
                        if numeroCompte:
                            extracted_entities['numeroCompte'] = numeroCompte
                            message = (
                                f"Vous souhaitez passer un virement {typeOperation} pour {nom} {prenom} avec le montant {montant} dirhams avec votre compte {typeCompte}. Merci de "
                                f"confirmer cette demande!")
                            return f"Request_Validation_Transaction_Virement", message, extracted_entities
                        else:
                            message = "Vous avez plusieurs comptes du même type, merci de préciser le numéro de compte avec lequel vous souhaiter passer le virement!"
                            return f"Entity_Missing_Transaction_Virement", message, extracted_entities
                    else:
                        extracted_entities['besoin_ribBeneficiaire'] = None
                        extracted_entities['besoin_numeroCompte'] = None
                        if numeroCompte is not None and ribBeneficiaire is not None:
                            extracted_entities['numeroCompte'] = numeroCompte
                            extracted_entities['rib'] = ribBeneficiaire
                            message = (
                                f"Vous souhaitez passer un virement {typeOperation} pour {nom} {prenom} avec le montant {montant} dirhams avec votre compte {typeCompte}. Merci de "
                                f"confirmer cette demande!")
                            return f"Request_Validation_Transaction_Virement", message, extracted_entities
                        else:
                            message = "Vous avez plusieurs comptes du même type et plusieurs bénéficiaires avec les mêmes noms, merci de préciser le numéro de compte et le RIB du bénéficiare avec lesquels vous souhaiter passer le virement!"
                            return f"Entity_Missing_Transaction_Virement", message, extracted_entities
            else:
                message = "Le type de compte ou les noms du bénéficiaires sont incorrectes!"
                extracted_entities.pop('typeCompte')
                extracted_entities.pop('nom')
                extracted_entities.pop('prenom')
                return f"Entity_Missing_Transaction_Virement", message, extracted_entities

    def action_complete_ajout_transaction_virement(self, data, extracted_entities, patterns, context):
        text = data['text'].lower()
        userid = data['userId']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCompte', 'nom', 'prenom', 'montant', 'typeOperation']
        optional_entities = ['rib', 'numeroCompte', 'motif']
        new_extracted_entities = {}
        missing_entities = []
        nom,prenom,typeCompte,numeroCompte,ribBeneficiaire,typeOperation,montant,motif = None, None, None, None,None,None,None,None

        if entities_ner_regex:
            if entities_ner_regex.get('typeCompte'):
                typeCompte = entities_ner_regex.get('typeCompte')[0]
            if entities_ner_regex.get('rib'):
                ribBeneficiaire = entities_ner_regex.get('rib')[0]
            if entities_ner_regex.get('numeroCompte'):
                numeroCompte = entities_ner_regex.get('numeroCompte')[0].upper()
            if entities_ner_regex.get('typeOperation'):
                typeOperation = entities_ner_regex.get('typeOperation')[0]
            if entities_ner_regex.get('montant'):
                montant = int(entities_ner_regex.get('montant')[0])
            if entities_ner_regex.get('motif'):
                motif = entities_ner_regex.get('motif')[0]

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()

        for entity in required_entities:
            if locals().get(entity):
                new_extracted_entities[entity] = locals().get(entity)
        for entity in optional_entities:
            if locals().get(entity):
                new_extracted_entities[entity] = locals().get(entity)
        merged_entities = merge_entities(extracted_entities, new_extracted_entities)
        if context == "Confirmation_Action":
            required_entities_rib_account_type = ['typeCompte', 'rib', 'montant', 'typeOperation']
            required_entities_rib_account_num = ['numeroCompte', 'rib', 'montant', 'typeOperation']
            required_entities_names_account_num = ['numeroCompte', 'nom', 'prenom', 'montant', 'typeOperation']
            if all(entity in extracted_entities.keys() for entity in required_entities) and 'besoin_numeroCompte' not in extracted_entities.keys() and 'besoin_ribBeneficiaire' not in extracted_entities.keys():
                response_body = {
                    "userId": userid,
                    "compte": {
                        "typeCompte": extracted_entities.get('typeCompte')
                    },
                    "beneficiaire": {
                        "nom": extracted_entities.get('nom'),
                        "prenom": extracted_entities.get('prenom')
                    },
                    "operation": {
                        "motif": extracted_entities.get('motif') if extracted_entities.get('motif') else "",
                        "montant": extracted_entities.get('montant'),
                        "typeOperation": extracted_entities.get('typeOperation')
                    }
                }
                message = self.spring_api.post_data_text('operations/addByAccountTypeBeneficiaryNames', response_body)
                return "user_request", message, {}
            elif all(entity in extracted_entities.keys() for entity in required_entities_rib_account_type):
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
                message = self.spring_api.post_data_text('operations/addByAccountTypeAndRib', response_body)
                return "user_request", message, {}
            elif all(entity in extracted_entities.keys() for entity in required_entities_rib_account_num):
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
                message = self.spring_api.post_data_text('operations/addByAccountNumAndRib', response_body)
                return "user_request", message, {}
            elif all(entity in extracted_entities.keys() for entity in required_entities_names_account_num):
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
                message = self.spring_api.post_data_text('operations/addByAccountNumBeneficiaryNames', response_body)
                return "user_request", message, {}
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return "user_request", message, {}
        elif context == "Missing_Entity":
            message = ""
            if 'besoin_numeroCompte' in extracted_entities.keys():
                if numeroCompte is None:
                    message = "Veuillez préciser votre numéro de compte!"
                    return "Entity_Missing_Transaction_Virement", message, merged_entities
                else:
                    if 'besoin_ribBeneficiaire' in extracted_entities.keys():
                        if ribBeneficiaire is None:
                            message += "Veuillez préciser le RIB du bénéficiaire!"
                            return "Entity_Missing_Transaction_Virement", message, merged_entities
                        else:
                            if all(entity in merged_entities.keys() for entity in required_entities):
                                message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                                return "Request_Validation_Transaction_Virement", message, merged_entities
                            else:
                                for entity in required_entities:
                                    if entity not in merged_entities:
                                        missing_entities.append(entity)
                                missing_entities = list(set(missing_entities))
                                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                                key in MATCHING_PATTERNS]
                                if missing_entities:
                                    message = get_missing_entity_message(missing_entities_explication)
                                    return "Entity_Missing_Transaction_Virement", message, merged_entities
                    else:
                        if all(entity in merged_entities.keys() for entity in required_entities):
                            message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                            return "Request_Validation_Transaction_Virement", message, merged_entities
                        else:
                            for entity in required_entities:
                                if entity not in merged_entities:
                                    missing_entities.append(entity)
                            missing_entities = list(set(missing_entities))
                            missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                            key in MATCHING_PATTERNS]
                            if missing_entities:
                                message = get_missing_entity_message(missing_entities_explication)
                                return "Entity_Missing_Transaction_Virement", message, merged_entities
            elif 'besoin_ribBeneficiaire' in extracted_entities.keys():
                if ribBeneficiaire is None:
                    message += "Veuillez préciser le RIB du bénéficiaire!"
                    return "Entity_Missing_Transaction_Virement", message, merged_entities
                else:
                    if 'besoin_numeroCompte' in extracted_entities.keys():
                        if numeroCompte is None:
                            message += "Veuillez préciser le numéro de votre compte!"
                            return "Entity_Missing_Transaction_Virement", message, merged_entities
                        else:
                            if all(entity in merged_entities.keys() for entity in required_entities):
                                message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                                return "Request_Validation_Transaction_Virement", message, merged_entities
                            else:
                                for entity in required_entities:
                                    if entity not in merged_entities:
                                        missing_entities.append(entity)
                                missing_entities = list(set(missing_entities))
                                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                                key in MATCHING_PATTERNS]
                                if missing_entities:
                                    message = get_missing_entity_message(missing_entities_explication)
                                    return "Entity_Missing_Transaction_Virement", message, merged_entities
                    else:
                        if all(entity in merged_entities.keys() for entity in required_entities):
                            message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                            return "Request_Validation_Transaction_Virement", message, merged_entities
                        else:
                            for entity in required_entities:
                                if entity not in merged_entities:
                                    missing_entities.append(entity)
                            missing_entities = list(set(missing_entities))
                            missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                            key in MATCHING_PATTERNS]
                            if missing_entities:
                                message = get_missing_entity_message(missing_entities_explication)
                                return "Entity_Missing_Transaction_Virement", message, merged_entities
            else:
                for entity in required_entities:
                    if entity not in merged_entities:
                        missing_entities.append(entity)
                missing_entities = list(set(missing_entities))
                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                key in MATCHING_PATTERNS]
                if missing_entities:
                    message = get_missing_entity_message(missing_entities_explication)
                    return "Entity_Missing_Transaction_Virement", message, merged_entities
                else:
                    message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                    return "Request_Validation_Transaction_Virement", message, merged_entities

    def action_ajout_transaction_paiement(self, data, patterns):
        text = data['text'].lower()
        userid = data['userId']
        _, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCompte', 'numeroFacture']
        extracted_entities = {}
        missing_entities = []
        typeCompte,numeroCompte,numeroFacture = None,None,None
        if entities_ner_regex:
            if entities_ner_regex.get('typeCompte'):
                typeCompte = entities_ner_regex.get('typeCompte')[0]
            if entities_ner_regex.get('numeroFacture'):
                numeroFacture = entities_ner_regex.get('numeroFacture')[0].upper()
            if entities_ner_regex.get('numeroCompte'):
                numeroCompte = entities_ner_regex.get('numeroCompte')[0].upper()
        for entity in required_entities:
            if locals().get(entity) is None:
                missing_entities.append(entity)
            else:
                extracted_entities[entity] = locals().get(entity)
        missing_entities = list(set(missing_entities))
        if numeroCompte: extracted_entities['numeroCompte'] = numeroCompte
        if missing_entities:
            return self.handle_missing_entity(missing_entities, extracted_entities, "Transaction_PaiementFacture")
        else:
            comptes = self.check_comptes(userid, extracted_entities)
            if comptes:
                if len(comptes) == 1:
                    message = (f"Vous voulez payer la facture {numeroFacture} avec votre compte {typeCompte}. Merci de "
                               f"confirmer cette demande!")
                    return "Request_Validation_Transaction_PaiementFacture", message, extracted_entities
                else:
                    extracted_entities['besoin_numeroCompte'] = None
                    if numeroCompte:
                        message = (
                            f"Vous voulez payer la facture {numeroFacture} avec votre compte {typeCompte} de numéro {numeroCompte}. Merci de "
                            f"confirmer cette demande!")
                        return "Request_Validation_Transaction_PaiementFacture", message, extracted_entities
                    else:
                        message = (
                            f"Vous avez plusieurs comptes du même type, merci de préciser le numéro de votre compte "
                            f"bancaire!")
                        return "Entity_Missing_Transaction_PaiementFacture", message, extracted_entities
            else:
                message = "Aucun compte ne correspond au type que vous avez précisé!"
                extracted_entities.pop('typeCompte')
                return "Entity_Missing_Transaction_PaiementFacture", message, extracted_entities

    def action_complete_ajout_transaction_paiement(self, data, extracted_entities, patterns, context):
        text = data['text'].lower()
        userid = data['userId']
        required_entities = ['typeCompte', 'numeroFacture']
        _, entities_ner_regex = entity_extraction(text, patterns)
        new_extracted_entities = {}
        missing_entities = []
        typeCompte, numeroFacture, numeroCompte = None , None, None

        if entities_ner_regex:
            if entities_ner_regex.get('typeCompte'):
                typeCompte = entities_ner_regex.get('typeCompte')[0]
            if entities_ner_regex.get('numeroFacture'):
                numeroFacture = entities_ner_regex.get('numeroFacture')[0].upper()
            if entities_ner_regex.get('numeroCompte'):
                numeroCompte = entities_ner_regex.get('numeroCompte')[0].upper()
        for entity in required_entities:
            if locals().get(entity) is not None:
                new_extracted_entities[entity] = locals().get(entity)
        if numeroCompte: new_extracted_entities['numeroCompte'] = numeroCompte
        merged_entities = merge_entities(extracted_entities, new_extracted_entities)
        if context == "Confirmation_Action":
            if 'besoin_numeroCompte' not in extracted_entities.keys():
                response_body = {
                    "userId": userid,
                    'numeroFacture': extracted_entities.get('numeroFacture'),
                    "typeCompte": extracted_entities.get('typeCompte')
                }
                message = self.spring_api.post_data_text('paimenent-facture/addInvoiceByAccountType', response_body)
                return "user_request", message, {}
            else:
                response_body = {
                    "userId": userid,
                    'numeroFacture': extracted_entities.get('numeroFacture'),
                    "numeroCompte": extracted_entities.get('numeroCompte'),
                    "typeCompte": extracted_entities.get('typeCompte')
                }
                message = self.spring_api.post_data_text('paimenent-facture/addInvoiceByAccountNum', response_body)
                return "user_request", message, {}
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return "user_request", message, {}
        elif context == "Missing_Entity":
            if 'besoin_numeroCompte' in extracted_entities.keys():
                if numeroCompte is None:
                    message = "Veuillez préciser votre numéro de compte!"
                    return "Entity_Missing_Transaction_PaiementFacture", message, merged_entities
                else:
                    compte = None
                    compte = self.spring_api.get_data(f'comptes/userNumCompte/{userid}/{numeroCompte}')
                    if compte:
                        if all(entity in merged_entities.keys() for entity in required_entities):
                            message = f"Souhaitez-vous payer la facture numéro {merged_entities.get('numeroFacture')} avec le compte bancaire numéro {numeroCompte} ? Merci de confirmer cette demande!"
                            return "Request_Validation_Transaction_PaiementFacture", message, merged_entities
                        else:
                            for entity in required_entities:
                                if entity not in merged_entities:
                                    missing_entities.append(entity)
                            missing_entities = list(set(missing_entities))
                            missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                            key in MATCHING_PATTERNS]
                            if missing_entities:
                                message = get_missing_entity_message(missing_entities_explication)
                                return "Entity_Missing_Transaction_PaiementFacture", message, merged_entities
                    else:
                        message = f"Aucun compte bancaire ne correspond à ce numéro."
                        return "Entity_Missing_Transaction_PaiementFacture", message, merged_entities
            else:
                for entity in required_entities:
                    if entity not in merged_entities:
                        missing_entities.append(entity)
                missing_entities = list(set(missing_entities))
                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                key in MATCHING_PATTERNS]
                if missing_entities:
                    message = get_missing_entity_message(missing_entities_explication)
                    return "Entity_Missing_Transaction_PaiementFacture", message, merged_entities
                else:
                    message = f"Souhaitez-vous payer la facture numéro {merged_entities.get('numeroFacture')} avec votre compte {merged_entities.get('typeCompte')} ? Merci de confirmer cette demande!"
                    return "Request_Validation_Transaction_PaiementFacture", message, merged_entities

    def handle_missing_entity(self, missing_entities, extracted_entities, context):
        missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if key in MATCHING_PATTERNS]
        message = get_missing_entity_message(missing_entities_explication)
        return f"Entity_Missing_{context}", message, extracted_entities

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
        beneficiaires = self.spring_api.post_data_check('beneficiaires/user/names', response_body)

        return beneficiaires

    def check_comptes(self, userid, extracted_entities):
        type_compte = extracted_entities.get('typeCompte')

        comptes = self.spring_api.get_data(f'comptes/userTypeCompte/{userid}/{type_compte}')

        return comptes

    def check_cartes(self, userid, extracted_entities):
        type_carte = extracted_entities.get('typeCarte')

        cartes = self.spring_api.get_data(f'cartes/userCardsByType/{userid}/{type_carte}')

        return cartes

    def which_rib(self, userid, entities_ner_regex):
        rib = entities_ner_regex.get('rib')[0].upper()
        response_body = {
            "userId": userid,
            "beneficiaire": rib
        }
        beneficiaire = self.spring_api.post_data_check('beneficiaires/user/rib', response_body)

        return beneficiaire