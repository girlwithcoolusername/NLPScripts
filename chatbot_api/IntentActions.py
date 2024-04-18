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
                if patternName == 'numeroCompte':
                    entities_dict[patternName] = int(value)
                else:
                    entities_dict[patternName] = value
            response_body = {"userId": userid, "entitiesDic": entities_dict}
            comptes = self.spring_api.post_data('/comptes/searchEntitiesDict', response_body)
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
                if 'demande_' not in patternName:
                    if patternName == "numeroCarte":
                        entities_dict[patternName] = int(value)
                    else:
                        entities_dict[patternName] = value
                else:
                    request_list.append(patternName)
            response_body = {"userId": userid, "entitiesDic": entities_dict}
            cartes = self.spring_api.post_data('/cartes/searchEntitiesDict', response_body)
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
                entities_dict[patternName] = value
            response_body = {"userId": userid, "entitiesDic": entities_dict}
            operations = self.spring_api.post_data('/operations/searchEntitiesDict', response_body)

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
            if len(entities_ner_regex.get('rib')) == 2:
                rib = entities_ner_regex.get('rib')[0].upper()
                newRib = entities_ner_regex.get('newRib')[1].upper()
            else:
                rib = entities_ner_regex.get('rib').upper()
                typeBeneficiaire = entities_ner_regex.get('typeBeneficiaire')
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                              locals().get(entity) is not None}
        if missing_entities:
            return self.handle_missing_entity(missing_entities, extracted_entities,
                                              f"Gestion_Bénéficiaires_{action_type.capitalize()}")
        else:
            if action_type == "ajout":
                message = f"Vous voulez ajouter un bénéficiaire avec le nom {nom}, le prénom {prenom} comme personne {typeBeneficiaire} ayant pour rib {rib}. Merci de confirmer cette demande!"
                return f"Required_Validation_Gestion_Bénéficiaires_{action_type.capitalize()}", message, extracted_entities
            elif action_type == "suppression":
                if rib: extracted_entities['rib'] = rib
                beneficiaries = self.check_beneficiaires(userid, extracted_entities)
                if beneficiaries:
                    if len(beneficiaries) == 1:
                        message = f"Vous voulez supprimer le bénéficiaire {nom} {prenom}. Merci de confirmer cette demande!"
                        return f"Required_Validation_Gestion_Bénéficiaires_{action_type.capitalize()}", message, extracted_entities
                    else:
                        extracted_entities['besoin_ribBeneficiaire'] = None
                        if rib:
                            message = f"Vous voulez supprimer le bénéficiaire ayant le {rib}. Merci de confirmer cette demande!"
                            return f"Required_Validation_Gestion_Bénéficiaires_{action_type.capitalize()}", message, extracted_entities
                        else:
                            message = f"Vous avez plusieurs bénéficiaires avec le même nom, merci de préciser le RIB du bénéficiaire!"
                            return f"Entity_Missing_Gestion_Bénéficiaires_{action_type.capitalize()}", message, extracted_entities
                else:
                    message = "Aucun bénéficiaire ne correspond à ces noms!"
                    extracted_entities.pop('nom')
                    extracted_entities.pop('prenom')
                    return f"Entity_Missing_Gestion_Bénéficiaires_{action_type.capitalize()}", message, extracted_entities
            elif action_type == "modification":
                if rib: extracted_entities['rib'] = rib
                beneficiaries = self.check_beneficiaires(userid, extracted_entities)
                if beneficiaries:
                    if len(beneficiaries) == 1:
                        message = f"Vous voulez modifier le bénéficiaire {nom} {prenom} avec le RIB {newRib}. Merci de confirmer cette demande!"
                        return "Required_Validation_Gestion_Bénéficiaires_Modification", message, extracted_entities
                    else:
                        extracted_entities['besoin_ribBeneficiaire'] = None
                        if rib:
                            message = f"Vous voulez modifier le bénéficiaire {nom} {prenom} avec le RIB {newRib}. Merci de confirmer cette demande!"
                            return "Required_Validation_Gestion_Bénéficiaires_Modification", message, extracted_entities
                        else:
                            message = f"Vous avez plusieurs bénéficiaires avec le même nom, merci préciser le RIB du bénéficiaire!"
                            return "Entity_Missing_Gestion_Bénéficiaires_Modification", message, extracted_entities
                else:
                    message = "Aucun bénéficiaire ne correspond à ces noms!"
                    extracted_entities.pop('nom')
                    extracted_entities.pop('prenom')
                    return "Entity_Missing_Gestion_Bénéficiaires_Suppression", message, extracted_entities

    def action_complete_process_beneficiaires(self, data, extracted_entities, patterns, context, required_entities,
                                              action_type):
        text = data['text'].lower()
        userid = data['userId']
        entities_ner_bert, entities_ner_regex = entity_extraction(text, patterns)
        extracted_entities = {}

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
            if len(entities_ner_regex.get('rib')) == 2:
                rib = entities_ner_regex.get('rib')[0].upper()
                newRib = entities_ner_regex.get('newRib')[1].upper()
            else:
                rib = entities_ner_regex.get('rib').upper()
                typeBeneficiaire = entities_ner_regex.get('typeBeneficiaire')

        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
        if action_type == "ajout":
            merged_entities = merge_entities(extracted_entities, new_extracted_entities)
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
                return "user_request", message, {}
            elif context == "Annulation_action":
                message = random.choice(CANCEL_ACTION)
                return "user_request", message, {}
            elif context == "Missing_Entity":
                missing_entities = [entity for entity in required_entities if entity not in merged_entities]
                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                key in MATCHING_PATTERNS]
                if missing_entities:
                    message = get_missing_entity_message(missing_entities_explication)
                    return f"Entity_Missing_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
                else:
                    message = f"Vous voulez ajouter un bénéficiaire avec le nom {merged_entities.get('nom')}, le prénom {merged_entities.get('prenom')} comme {merged_entities.get('typeBeneficiaire')} ayant pour rib {merged_entities.get('rib')}. Merci de confirmer cette demande!"
                    return f"Required_Validation_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
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
                    message = self.spring_api.post_data('/beneficiaires/delete/names', response_body)
                    return "user_request", message, {}
                else:
                    response_body = {
                        "userId": userid,
                        "beneficiaire": {
                            'rib': extracted_entities.get('rib')
                        }
                    }
                    message = self.spring_api.post_data('/beneficiaires/delete/rib', response_body)
                    return "user_request", message, {}
            elif context == "Annulation_Action":
                message = random.choice(CANCEL_ACTION)
                return "user_request", message, {}
            elif context == "Missing_Entity":
                if 'besoin_ribBeneficiaire' in extracted_entities.keys():
                    if 'rib' not in merged_entities.get('rib'):
                        message = "Veuillez préciser le RIB du bénéficiaire!"
                        return f"Entity_Missing_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
                    else:
                        if required_entities in merged_entities.keys():
                            response_body = {
                                "userId": userid,
                                "beneficiaire": {
                                    'rib': rib
                                }
                            }
                            message = self.spring_api.post_data('/beneficiaires/user/rib', response_body)
                            if message:
                                message = f"Souhaitez-vous supprimer le bénéficiaire avec le RIB {rib} ? Merci de confirmer cette demande!"
                                return f"Request_Validation_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
                            else:
                                message = f"Le RIB spécifié ne correspond à aucun bénéficiaire."
                                merged_entities.pop('rib')
                                return f"Entity_Missing_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
                        else:
                            missing_entities = [entity for entity in required_entities if entity not in merged_entities]
                            missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                            key in MATCHING_PATTERNS]
                            if missing_entities:
                                message = get_missing_entity_message(missing_entities_explication)
                                return f"Entity_Missing_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
                else:
                    missing_entities = [entity for entity in required_entities if entity not in merged_entities]
                    missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                    key in MATCHING_PATTERNS]
                    if missing_entities:
                        message = get_missing_entity_message(missing_entities_explication)
                        return f"Entity_Missing_Gestion_Bénéficiaires__{action_type.capitalize()}", message, merged_entities
                    else:
                        message = f"Vous voulez supprimer le bénéficiaire {merged_entities.get('nom')} {merged_entities.get('prenom')}. Merci de confirmer cette demande!"
                        return f"Required_Validation_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
        elif action_type == "modification":
            if rib: new_extracted_entities['rib'] = rib
            merged_entities = merge_entities(extracted_entities, new_extracted_entities)
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
                    message = self.spring_api.post_data('/beneficiaires/update/names', response_body)
                    return "user_request", message, {}
                else:
                    response_body = {
                        "userId": userid,
                        "oldRib": extracted_entities.get('rib'),
                        "newRib": extracted_entities.get('newRib')
                    }
                    message = self.spring_api.post_data('/beneficiaires/update/rib', response_body)
                    return "user_request", message, {}
            elif context == "Annulation_Action":
                message = random.choice(CANCEL_ACTION)
                return "user_request", message, {}
            elif context == "Missing_Entity":
                if 'besoin_ribBeneficiaire' in extracted_entities:
                    if 'rib' in merged_entities.get('rib'):
                        message = "Veuillez préciser le RIB du bénéficiaire à modifier"
                        return f"Entity_Missing_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
                    else:
                        if required_entities in merged_entities.keys():
                            response_body = {
                                "userId": userid,
                                'oldRib': rib,
                                'newRib': merged_entities.get('newRib')
                            }
                            message = self.spring_api.post_data('/beneficiaires/user/rib', response_body)
                            if message:
                                message = f"Souhaitez-vous modifier le bénéficiaire avec le RIB {rib} ? Merci de confirmer cette demande!"
                                return f"Request_Validation_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
                            else:
                                message = f"Le RIB spécifié ne correspond à aucun bénéficiaire."
                                merged_entities.pop('rib')
                                return f"Entity_Missing_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
                        else:
                            missing_entities = [entity for entity in required_entities if entity not in merged_entities]
                            missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                            key in MATCHING_PATTERNS]
                            if missing_entities:
                                message = get_missing_entity_message(missing_entities_explication)
                                return f"Entity_Missing_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
                else:
                    missing_entities = [entity for entity in required_entities if entity not in merged_entities]
                    missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                    key in MATCHING_PATTERNS]
                    if missing_entities:
                        message = get_missing_entity_message(missing_entities_explication)
                        return f"Entity_Missing_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities
                    else:
                        message = f"Vous voulez modifier le bénéficiaire {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le RIB {merged_entities.get('newRib')}. Merci de confirmer cette demande!"
                        return f"Required_Validation_Gestion_Bénéficiaires_{action_type.capitalize()}", message, merged_entities

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
                                                          required_entities, "modification")

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
        typeCarte = None
        services = None
        numeroCarte = None
        if entities_ner_regex:
            typeCarte = entities_ner_regex.get('typeCarte')
            services = entities_ner_regex.get('services')
            numeroCarte = int(entities_ner_regex.get('numeroCarte'))

        extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                              locals().get(entity) is not None}
        if numeroCarte: extracted_entities['numeroCarte'] = numeroCarte
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            return self.handle_missing_entity(missing_entities, extracted_entities, f"Gestion_Cartes_{status}")
        else:
            cartes = self.check_cartes(userid, extracted_entities)
            if cartes:
                if len(cartes) == 1:
                    if status == "Activation":
                        message = (
                            f"Vous voulez ajouter les services {services} pour votre carte {typeCarte}. Merci de "
                            f"confirmer cette demande!")
                        return f"Required_Validation_Gestion_Cartes_{status}", message, extracted_entities
                    elif status == "Désactivation":
                        message = (
                            f"Vous voulez supprimer les services {services} pour votre carte {typeCarte}. Merci de "
                            f"confirmer cette demande!")
                    return f"Required_Validation_Gestion_Cartes_{status}", message, extracted_entities
                else:
                    extracted_entities['besoin_numeroCarte'] = None
                    if numeroCarte:
                        message = (
                            f"Vous voulez ajouter les services {services} pour votre carte numéro {numeroCarte}. Merci de "
                            f"confirmer cette demande!")
                        return f"Required_Validation_Gestion_Cartes_{status}", message, extracted_entities
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
        typeCarte = None
        services = None
        numeroCarte = None

        if entities_ner_regex:
            typeCarte = entities_ner_regex.get('typeCarte')
            numeroCarte = int(entities_ner_regex.get('numeroCarte'))
            services = entities_ner_regex.get('services')

        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
        if numeroCarte: new_extracted_entities['numeroCarte'] = numeroCarte
        merged_entities = merge_entities(extracted_entities, new_extracted_entities)
        if context == "Confirmation_Action":
            if required_entities in extracted_entities.keys():
                response_body = {
                    "userId": userid,
                    "carte": {
                        'typeCarte': extracted_entities.get('typeCarte'),
                        "services": extracted_entities.get('services')
                    },
                    "status": "enable" if status == "Activation" else "disable"
                }
                message = self.spring_api.post_data('/cartes/updateByCardType', response_body)
                return "user_request", message, {}
            elif required_entities and 'besoin_numeroCarte' in extracted_entities.keys():
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
                    if required_entities in merged_entities.keys():
                        message = self.spring_api.get_data(f'/userCardsByNum/{numeroCarte}')
                        if message:
                            message = f"Souhaitez-vous modifier les services permis par votre carte {typeCarte} numéro {numeroCarte} ? Merci de confirmer cette demande!"
                            return f"Request_Validation_Gestion_Cartes_{status}", message, merged_entities
                        else:
                            message = f"Aucune carte ne correspond à ce numéro!"
                            merged_entities.pop('numeroCarte')
                            return f"Entity_Missing_Gestion_Cartes_{status}", message, merged_entities
                    else:
                        missing_entities = [entity for entity in required_entities if entity not in merged_entities]
                        missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                        key in MATCHING_PATTERNS]
                        if missing_entities:
                            message = get_missing_entity_message(missing_entities_explication)
                            return f"Entity_Missing_Gestion_Cartes_{status}", message, merged_entities
            else:
                missing_entities = [entity for entity in required_entities if entity not in merged_entities]
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
        extracted_entities = {}
        typeCarte = None
        raisonsOpposition = None
        numeroCarte = None
        if entities_ner_regex:
            typeCarte = entities_ner_regex.get('typeCarte')
            raisonsOpposition = entities_ner_regex.get('raisonsOpposition')
            numeroCarte = int(entities_ner_regex.get('numeroCarte'))
        extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                              locals().get(entity) is not None}
        if numeroCarte: extracted_entities['numeroCarte'] = numeroCarte
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            return self.handle_missing_entity(missing_entities, extracted_entities, "Gestion_Cartes_Opposition")
        else:
            cartes = self.check_cartes(userid, extracted_entities)
            if cartes:
                if len(cartes) == 1:
                    message = (
                        f"Vous voulez opposer votre carte {typeCarte} pour {raisonsOpposition}. Merci de "
                        f"confirmer cette demande!")
                    return f"Required_Validation_Gestion_Cartes_Opposition", message, extracted_entities
                else:
                    extracted_entities['besoin_numeroCarte'] = None
                    if numeroCarte:
                        message = (
                            f"Vous voulez opposer votre carte numéro {numeroCarte} pour {raisonsOpposition}. Merci de "
                            f"confirmer cette demande!")
                        return f"Required_Validation_Gestion_Cartes_Opposition", message, extracted_entities
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
        typeCarte = None
        raisonsOpposition = None
        numeroCarte = None

        if entities_ner_regex:
            typeCarte = entities_ner_regex.get('typeCarte')
            numeroCarte = int(entities_ner_regex.get('numeroCarte'))
            raisonsOpposition = entities_ner_regex.get('raisonsOpposition')

        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
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
                message = self.spring_api.post_data('/cartes/opposeByCardType', response_body)
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
                message = self.spring_api.post_data('/cartes/opposeByCardNum', response_body)
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
                    if required_entities in merged_entities.keys():
                        message = self.spring_api.get_data(f'/userCardsByNum/{numeroCarte}')
                        if message:
                            message = f"Souhaitez-vous opposer votre carte {merged_entities.get('typeCarte')} numéro {merged_entities.get('numeroCarte')} pour {merged_entities.get('raisonsOpposition')}? Merci de confirmer cette demande!"
                            return f"Request_Validation_Gestion_Cartes_Opposition", message, merged_entities
                        else:
                            message = f"Aucune carte ne correspond à ce numéro!"
                            return f"Entity_Missing_Gestion_Cartes_Opposition", message, merged_entities.pop(
                                'numeroCarte')
                    else:
                        missing_entities = [entity for entity in required_entities if entity not in merged_entities]
                        missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                        key in MATCHING_PATTERNS]
                        if missing_entities:
                            message = get_missing_entity_message(missing_entities_explication)
                            return f"Entity_Missing_Gestion_Cartes_Opposition", message, merged_entities
            missing_entities = [entity for entity in required_entities if entity not in merged_entities]
            missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                            key in MATCHING_PATTERNS]
            if missing_entities:
                message = get_missing_entity_message(missing_entities_explication)
                return f"Entity_Missing_Gestion_Cartes_Opposition", message, merged_entities
            else:
                message = f"Souhaitez-vous opposer votre carte {merged_entities.get('typeCarte')} pour {merged_entities.get('raisonsOpposition')}? Merci de confirmer cette demande!"
                return f"Request_Validation_Gestion_Cartes_Opposition", message, merged_entities

    def action_plafond_carte(self, data, patterns, status):
        text = data['text'].lower()
        userid = data['userId']
        _, entities_ner_regex = entity_extraction(text, patterns)
        required_entities = ['typeCarte', 'plafond', 'typePlafond']
        extracted_entities = {}
        typeCarte = None
        typePlafond = None
        plafond = None
        numeroCarte = None
        if entities_ner_regex:
            typeCarte = entities_ner_regex.get('typeCarte')
            typePlafond = entities_ner_regex.get('typePlafond')
            plafond = decimal.Decimal(entities_ner_regex.get('montant'))
            numeroCarte = int(entities_ner_regex.get('numeroCarte'))

        extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                              locals().get(entity) is not None}
        if numeroCarte: extracted_entities['numeroCarte'] = numeroCarte
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            return self.handle_missing_entity(missing_entities, extracted_entities, f"Gestion_Cartes_Plafond_{status}")
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
                    extracted_entities['besoin_numeroCarte'] = None
                    if numeroCarte:
                        if status == "Augmenter":
                            message = (
                                f"Vous voulez augmenter le plafon de {typePlafond} pour votre carte numéro {numeroCarte}. Merci de "
                                f"confirmer cette demande!")
                        elif status == "Diminuer":
                            message = (
                                f"Vous voulez diminuer le plafon de {typePlafond} pour votre carte numéro {numeroCarte}. Merci de "
                                f"confirmer cette demande!")
                        return f"Required_Validation_Gestion_Cartes_Plafond_{status}", message, extracted_entities
                    else:
                        message = (
                            f"Vous avez plusieurs cartes du même type, merci de préciser le numéro de votre carte "
                            f"bancaire!")
                        return f"Entity_Missing_Gestion_Cartes_Plafond_{status}", message, extracted_entities
            else:
                message = "Aucune carte ne correspond à ces données"
                extracted_entities.pop('typeCarte')
                return f"Entity_Missing_Gestion_Cartes_Plafond_{status}", message, extracted_entities

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
            numeroCarte = int(entities_ner_regex.get('numeroCarte'))
            typePlafond = entities_ner_regex.get('typePlafond')
            plafond = decimal.Decimal(entities_ner_regex.get('montant'))

        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
        if numeroCarte: new_extracted_entities['numeroCarte'] = numeroCarte
        merged_entities = merge_entities(extracted_entities, new_extracted_entities)
        if context == "Confirmation_Action":
            if 'besoin_numeroCarte' not in extracted_entities.keys():
                response_body = {
                    "userId": userid,
                    'typeCarte': extracted_entities.get('typeCarte'),
                    "typePlafond": extracted_entities.get('typePlafond'),
                    "plafond": extracted_entities.get('montant'),
                    "statut": "add" if status == "Augmenter" else "disable",
                    "duration": ""
                }
                message = self.spring_api.post_data('/plafond/updateByCardType', response_body)
                return "user_request", message, {}
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
                return "user_request", message, {}
        elif context == "Annulation_Action":
            message = random.choice(CANCEL_ACTION)
            return "user_request", message, {}
        elif context == "Missing_Entity":
            if 'besoin_numeroCarte' in extracted_entities.keys():
                if 'numeroCarte' not in merged_entities.keys():
                    message = "Veuillez préciser votre numéro de carte!"
                    return f"Entity_Missing_Gestion_Cartes_Plafond_{status}", message, merged_entities
                else:
                    if required_entities in merged_entities.keys():
                        message = self.spring_api.get_data(f'/userCardsByNum/{numeroCarte}')
                        if message:
                            message = f"Souhaitez-vous modifier le plafond {merged_entities.get('typePlafond')} permis par votre carte {merged_entities.get('typeCarte')} numéro {numeroCarte} ? Merci de confirmer cette demande!"
                            return f"Request_Validation_Gestion_Cartes_Plafond_{status}", message, merged_entities
                        else:
                            message = f"Aucune carte ne correspond à ce numéro!"
                            merged_entities.pop('numeroCarte')
                            return f"Entity_Missing_Gestion_Cartes_Plafond_{status}", message, merged_entities
                    else:
                        missing_entities = [entity for entity in required_entities if entity not in merged_entities]
                        missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                        key in MATCHING_PATTERNS]
                        if missing_entities:
                            message = get_missing_entity_message(missing_entities_explication)
                            return f"Entity_Missing_Gestion_Cartes_Plafond_{status}", message, merged_entities
            else:
                missing_entities = [entity for entity in required_entities if entity not in merged_entities]
                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                key in MATCHING_PATTERNS]
                if missing_entities:
                    message = get_missing_entity_message(missing_entities_explication)
                    return f"Entity_Missing_Gestion_Cartes_Plafond_{status}", message, merged_entities
                else:
                    message = f"Souhaitez-vous modifier le plafond {merged_entities.get('typePlafond')} permis par votre carte {merged_entities.get('typeCarte')} ? Merci de confirmer cette demande!"
                    return f"Request_Validation_Gestion_Cartes_Plafond_{status}", message, merged_entities

    def action_plafond_augmenter(self, data, patterns, status):
        return self.action_services_cartes(data, patterns, "Augmenter")

    def action_plafond_diminuer(self, data, patterns):
        return self.action_services_cartes(data, patterns, "Diminuer")

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
        nom = None
        prenom = None
        typeCompte = None
        numeroCompte = None
        ribBeneficiaire = None
        typeOperation = None
        montant = None
        motif = None

        if entities_ner_regex:
            typeCompte = entities_ner_regex.get('typeCompte')
            ribBeneficiaire = entities_ner_regex.get('rib')
            numeroCompte = entities_ner_regex.get('numeroCompte').upper()
            typeOperation = entities_ner_regex.get('typeOperation')
            montant = decimal.Decimal(entities_ner_regex.get('montant'))
            motif = entities_ner_regex.get('motif')

        if entities_ner_bert:
            for entity in entities_ner_bert:
                if entity['entity_group'] == 'PER':
                    prenom = entity['word'].split(" ")[0].capitalize()
                    nom = entity['word'].split(" ")[1].capitalize()

        extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                              locals().get(entity) is not None}
        for entity in optional_entities:
            if locals().get(entity):
                extracted_entities[entity] = locals().get(entity)
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            return self.handle_missing_entity(required_entities, extracted_entities, 'Transaction_Virement')
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
                        if ribBeneficiaire:
                            extracted_entities['rib'] = ribBeneficiaire
                            message = (
                                f"Vous souhaitez passer un virement {typeOperation} pour {nom} {prenom} avec le montant {montant} dirhams avec votre compte {typeCompte}. Merci de "
                                f"confirmer cette demande!")
                            return f"Required_Validation_Transaction_Virement", message, extracted_entities
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
                            return f"Required_Validation_Transaction_Virement", message, extracted_entities
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
                            return f"Required_Validation_Transaction_Virement", message, extracted_entities
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
        new_extracted_entities = {}
        typeCompte = None
        numeroCompte = None
        ribBeneficiaire = None
        typeOperation = None
        montant = None
        motif = None
        if entities_ner_regex:
            typeCompte = entities_ner_regex.get('typeCompte')
            numeroCompte = entities_ner_regex.get('numeroCompte').upper()
            typeOperation = entities_ner_regex.get('typeOperation')
            montant = decimal.Decimal(entities_ner_regex.get('montant'))
            motif = entities_ner_regex.get('motif')
            ribBeneficiaire = entities_ner_regex('rib').upper()

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
        merged_entities = merge_entities(extracted_entities, new_extracted_entities)
        if context == "Confirmation_Action":
            if required_entities in extracted_entities.keys() and 'besoin_numeroCompte' not in extracted_entities.keys() and 'besoin_ribBeneficiaire' not in extracted_entities.keys():
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
                return "user_request", message, {}
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
                return "user_request", message, {}
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
                return "user_request", message, {}
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
                    if 'besoin_ribBeneficiare' in extracted_entities.keys():
                        if ribBeneficiaire is None:
                            message += "Veuillez préciser le RIB du bénéficiaire!"
                            return "Entity_Missing_Transaction_Virement", message, merged_entities
                        else:
                            if required_entities in merged_entities.keys():
                                message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                                return "Request_Validation_Transaction_Virement", message, merged_entities
                            else:
                                missing_entities = [entity for entity in required_entities if
                                                    entity not in merged_entities]
                                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                                key in MATCHING_PATTERNS]
                                if missing_entities:
                                    message = get_missing_entity_message(missing_entities_explication)
                                    return "Entity_Missing_Transaction_Virement", message, merged_entities
                    else:
                        if required_entities in merged_entities.keys():
                            message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                            return "Request_Validation_Transaction_Virement", message, merged_entities
                        else:
                            missing_entities = [entity for entity in required_entities if
                                                entity not in merged_entities]
                            missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                            key in MATCHING_PATTERNS]
                            if missing_entities:
                                message = get_missing_entity_message(missing_entities_explication)
                                return "Entity_Missing_Transaction_Virement", message, merged_entities
            if 'besoin_ribBeneficiare' in extracted_entities.keys():
                if ribBeneficiaire is None:
                    message += "Veuillez préciser le RIB du bénéficiaire!"
                    return "Entity_Missing_Transaction_Virement", message, merged_entities
                else:
                    if 'besoin_numeroCompte' in extracted_entities.keys():
                        if numeroCompte is None:
                            message += "Veuillez préciser le numéro de votre compte!"
                            return "Entity_Missing_Transaction_Virement", message, merged_entities
                        else:
                            if required_entities in merged_entities.keys():
                                message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                                return "Request_Validation_Transaction_Virement", message, merged_entities
                            else:
                                missing_entities = [entity for entity in required_entities if
                                                    entity not in merged_entities]
                                missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                                key in MATCHING_PATTERNS]
                                if missing_entities:
                                    message = get_missing_entity_message(missing_entities_explication)
                                    return "Entity_Missing_Transaction_Virement", message, merged_entities
                    else:
                        if required_entities in merged_entities.keys():
                            message = f"Vous souhaitez passer un virement {merged_entities.get('typeOperation')} pour {merged_entities.get('nom')} {merged_entities.get('prenom')} avec le montant {merged_entities.get('montant')} dirhams avec votre compte {merged_entities.get('typeCompte')}. Merci de confirmer!"
                            return "Request_Validation_Transaction_Virement", message, merged_entities
                        else:
                            missing_entities = [entity for entity in required_entities if
                                                entity not in merged_entities]
                            missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                            key in MATCHING_PATTERNS]
                            if missing_entities:
                                message = get_missing_entity_message(missing_entities_explication)
                                return "Entity_Missing_Transaction_Virement", message, merged_entities
            else:
                missing_entities = [entity for entity in required_entities if entity not in merged_entities]
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
        typeCompte = None
        numeroFacture = None
        numeroCompte = None
        if entities_ner_regex:
            typeCompte = entities_ner_regex.get('typeCompte')
            numeroFacture = entities_ner_regex.get('numeroFacture').upper()
            numeroCompte = entities_ner_regex.get('numeroCompte').upper()
        extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                              locals().get(entity) is not None}
        if numeroCompte: extracted_entities['numeroCompte'] = numeroCompte
        missing_entities = [entity for entity in required_entities if locals().get(entity) is None]
        if missing_entities:
            return self.handle_missing_entity(missing_entities, extracted_entities, "Transaction_PaiementFacture")
        else:
            comptes = self.check_comptes(userid, extracted_entities)
            if comptes:
                if len(comptes) == 1:
                    message = (f"Vous voulez payer la facture {numeroFacture} avec votre compte {typeCompte}. Merci de "
                               f"confirmer cette demande!")
                    return "Required_Validation_Transaction_PaiementFacture", message, extracted_entities
                else:
                    extracted_entities['besoin_numeroCompte'] = None
                    if numeroCompte:
                        message = (
                            f"Vous voulez payer la facture {numeroFacture} avec votre compte {typeCompte} de numéro {numeroCompte}. Merci de "
                            f"confirmer cette demande!")
                        return "Required_Validation_Transaction_PaiementFacture", message, extracted_entities
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
        typeCompte = None
        numeroFacture = None
        numeroCompte = None

        if entities_ner_regex:
            typeCompte = entities_ner_regex.get('typeCompte')
            numeroFacture = entities_ner_regex.get('numeroFacture').upper()
            numeroCompte = entities_ner_regex.get('numeroCompte').upper()
        new_extracted_entities = {entity: locals().get(entity) for entity in required_entities if
                                  locals().get(entity) is not None}
        if numeroCompte: new_extracted_entities['numeroCompte'] = numeroCompte
        merged_entities = merge_entities(extracted_entities, new_extracted_entities)
        if context == "Confirmation_Action":
            if 'besoin_numeroCompte' not in extracted_entities.keys():
                response_body = {
                    "userId": userid,
                    'numeroFacture': extracted_entities.get('numeroFacture'),
                    "typeCompte": extracted_entities.get('typeCompte')
                }
                message = self.spring_api.post_data('/paimenent-facture/addInvoiceByAccountType', response_body)
                return "user_request", message, {}
            else:
                response_body = {
                    "userId": userid,
                    'numeroFacture': extracted_entities.get('numeroFacture'),
                    "numeroCompte": extracted_entities.get('numeroCompte'),
                    "typeCompte": extracted_entities.get('typeCompte')
                }
                message = self.spring_api.post_data('/paimenent-facture/addInvoiceByAccountNum', response_body)
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
                    compte = self.spring_api.get_data(f'/userNumCompte/{userid}/{numeroCompte}')
                    if compte:
                        if required_entities in merged_entities.keys():
                            message = f"Souhaitez-vous payer la facture numéro {merged_entities.get('numeroFacture')} avec le compte bancaire numéro {numeroCompte} ? Merci de confirmer cette demande!"
                            return "Request_Validation_Transaction_PaiementFacture", message, merged_entities
                        else:
                            missing_entities = [entity for entity in required_entities if entity not in merged_entities]
                            missing_entities_explication = [MATCHING_PATTERNS[key] for key in missing_entities if
                                                            key in MATCHING_PATTERNS]
                            if missing_entities:
                                message = get_missing_entity_message(missing_entities_explication)
                                return "Entity_Missing_Transaction_PaiementFacture", message, merged_entities
                    else:
                        message = f"Aucun compte bancaire ne correspond à ce numéro."
                        return "Entity_Missing_Transaction_PaiementFacture", message, merged_entities
            else:
                missing_entities = [entity for entity in required_entities if entity not in merged_entities]
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
