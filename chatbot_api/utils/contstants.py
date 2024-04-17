# Constant NLU
import joblib
import torch
from transformers import AutoTokenizer, CamembertForSequenceClassification

from chatbot_api.utils.util_functions import extract_info

MODEL_PATH = (r'C:\Users\HP\Documents\AAAprojet PFE\docs '
              r'pfe\models\small_dataset\intent_recognition_by_fine_tuning_camemebert_classification_default_classifier'
              r'.pt')
LABEL_ENCODER_PATH = r'C:\Users\HP\Documents\AAAprojet PFE\docs pfe\models\label_encoder\saved_label_encoder.pkl'
GOOGLE_CLOUD_API = 'AIzaSyDKGk7FgPTfRI84pYQMMczszd-VsnspoHQ'
HF_TOKEN = "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"
MODEL = CamembertForSequenceClassification.from_pretrained("camembert-base", num_labels=18)
MODEL.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu')))
TOKENIZER = AutoTokenizer.from_pretrained("camembert-base")
LABEL_ENCODER = joblib.load(LABEL_ENCODER_PATH)
SPRING_BASE_URL = "http://localhost:8080"

USERNAME = "username"
PASSWORD = "password"
ROLE = "ADMIN"

CANCEL_ACTION = {
    "D'accord votre demande a été annulée. Que puis-je faire d'autre pour vous aujourd'hui ?",
    "Entendu, l'action a été annulé. Si vous avez d'autres questions ou besoins, n'hésitez pas à demander."
    "Compris, votre demande a été annulée. Si vous avez besoin de plus d'assistance ou si vous souhaitez effectuer une autre action, je suis là pour vous aider.",
    "Aucun problème, j'annule l'action . N'hésitez pas à me dire si vous avez besoin d'aide pour autre chose.",
    "Bien reçu, l'action a été annulée. Si vous avez d'autres demandes, je suis à votre disposition."
}
# Security questions
QUESTION_TO_FUNCTION = {
    # "Pouvez-vous fournir votre clé de RIB ?": provide_account_number,
    # "Pouvez-vous fournir le code PIN de votre carte crédit?": provide_card_number,
    "Quelle est votre date de naissance ?": "provide_date_of_birth",
    "Quelle est votre adresse e-mail associée à votre compte bancaire ?": "provide_email_address",
    "Quelle est votre adresse postale enregistrée ?": "provide_postal_address",
    "Quel est le montant de votre dernier dépôt ou retrait ?": "provide_last_transaction_amount",
    "Quel est le nom de votre agence bancaire ?": "provide_agency",
    "Pouvez-vous fournir un numéro de téléphone associé à votre compte ?": "provide_phone_number"
}
# Greet responses
GREET_RESPONSES = [
    "Bonjour! Avant de commencer, je vais devoir vous poser quelques questions de sécurité pour confirmer votre "
    "identité.",
    "Bonjour! Avant de continuer, veuillez répondre à quelques questions de sécurité pour protéger votre compte.",
    "Salut! Avant de poursuivre, je dois m'assurer que vous êtes bien la bonne personne.",
    "Bonjour! Avant de discuter de vos besoins bancaires, je dois d'abord vérifier votre identité.",
    "Bonjour! Pour des raisons de sécurité, je vais devoir vous poser quelques questions rapides avant de continuer.",
    "Bonjour! Pour garantir la sécurité de votre compte, je vais d'abord devoir vérifier quelques détails avec vous."
]

# Fallback responses
FALLBACK_RESPONSES = [
    "Je ne suis pas sûr d'avoir compris ce que vous voulez dire. Pourriez-vous reformuler votre question ?",
    "J'ai besoin de plus d'informations pour comprendre votre demande. Pouvez-vous être plus précis ?",
    "Je suis encore en apprentissage. Pouvez-vous essayer de demander d'une autre manière ?",
    "Il semble que je manque de contexte. Pouvez-vous fournir des détails supplémentaires sur votre demande ?",
    "Je n'ai pas compris quelle opération vous souhaitez effectuer. Pouvez-vous s'il vous plaît me donner plus de "
    "détails ?"
]
PATTERNS = {
    "typeCompte": r"\b(?:compte\s+)?(principal|courant|habituel|chèques|à\svue|personnel|individuel|dépôt|virtuel"
                  r"|épargne|d'entreprise|professionnel|placement)",
    "numeroCompte": r"\b0{3}[0-9]{3}[a-zA-Z][0-9]{9}\b",
    "typeCarte": r"\b(?:mastercard|visa|visa electron)\s+(.*)$",
    "numeroCarte": r"^\d{4}(?:\s?\d{4}){3}$",
    "statutCarte": r"\b(?:active|bloquée|expirée|annulée|en cours de fabrication|en attente de réception|opposée)",
    "montant": r"\b(\d+)\s*(?=(?:dirhams?|dh|MAD)\b)",
    "categorieOperation": r"\b(?:retrait|dépôt|virement|paiement|prélèvement)",
    "motif": r"\b(?:achat|retrait|virement|paiement|salaire|loyer|facture|remboursement|dépense|alimentation|logement"
             r"|transport|divertissement|santé|épargne|impôts)",
    "dateExpiration": r"(date d'expiration|expiration)",
    "cvv": r"(code|Card Verification Value |cvv|CVV)",
    "statusCarte": r"statut",
    "codePin": r"(code pin|pin|code)",
    "rib": r"\b(\d{24}|\d{4}(?: \d{4}){5})\b",
    "typeBeneficiaire": r"\b(physique|morale)",
    "numeroFacture": r"\b(INV|FACT|BL|PO)[A-Za-z0-9-_]{4,19}\b",
    "services": r"\b(?:paiements\s+(?:en\s+ligne|sans\s+contact|à\s+l'étranger)|retraits\s+d'espèces|tous\s+les\s"
                r"+services|assurances\s+(?:voyage|assistance)|conciergerie|rachat\s+("
                r"?:frais|franchise)|protections\s+(?:fraudeux|achats)|remise\s+(?:immédiate|différée)|privilèges\s+("
                r"?:exclusifs|voyage)|offres\s+(?:spéciales|partenaires)|accès\s+(?:aéroports|salons)|services\s+("
                r"?:bancaires|mobiles))\b",
    "raisonsOpposition": r"(fraude|utilisation\snon\sautorisée|transaction\ssuspecte|hameçonnage|escroquerie|vol"
                         r"|perte)",
    "typePlafond": r"(retraits|paiements|achats|dépenses|transferts|transactions|cashback|avance|crédit|débit)"
}

VIEW_CARD_PATTERNS = extract_info(PATTERNS, ['dateExpiration', 'cvv', 'statusCarte', 'codePin'])

INTENT_ACTIONS = {
    "Consultation_Solde": {
        "action": "consultation_solde_action",
        "patterns": extract_info(PATTERNS, ['typeCompte', 'numeroCompte'])
    },
    "Consultation_Opérations": {
        "action": "consultation_operations_action",
        "patterns": extract_info(PATTERNS, ['typeCompte', 'numeroCompte', 'categorieOperation', 'montant', 'motif'])
    },
    "Consultation_Cartes": {
        "action": "consultation_cartes_action",
        "patterns": extract_info(PATTERNS, ['typeCarte', 'numeroCarte', 'statutCarte'])
    },
    "Gestion_Bénéficiaires_Ajout": {
        "action": "action_ajout_beneficiaire",
        "complete_action": "action_complete_ajout_beneficiaire",
        "patterns": extract_info(PATTERNS, ['rib', "typeBeneficiaire"])
    },
    "Gestion_Bénéficiaires_Suppression": {
        "action": "action_suppression_beneficiaire",
        "patterns": extract_info(PATTERNS, ['rib'])
    },
    "Gestion_Bénéficiaires_Modification": {
        "action": "action_modification_beneficiaire",
        "patterns": extract_info(PATTERNS, ['rib'])
    },
    "Info_Assistance": {
        "action": "info_assistance_action"
    },
    "Info_FAQ": {
        "action": "info_faq_action"
    },
    "Info_Geolocalisation": {
        "action": "info_geolocalisation_action"
    },
    "Transaction_Virement": {
        "action": "action_ajout_transaction",
        "patterns": extract_info(PATTERNS, ['typeCompte', 'numeroCompte', 'montant', 'motif'])
    },
    "Transaction_PaiementFacture": {
        "action": "action_ajout_transaction_paiement",
        "complete_action": "action_complete_ajout_transaction_paiement",
        "patterns": extract_info(PATTERNS, ['typeCompte', 'numeroCompte', 'numeroFacture'])
    },
    "Gestion_Cartes_Activation": {
        "action": "action_activation_carte",
        "complete_action": "action_complete_activation_carte",
        "patterns": extract_info(PATTERNS, ['typeCompte', 'numeroCompte', 'services'])
    },
    "Gestion_Cartes_Désactivation": {
        "action": "action_desactivation_carte",
        "complete_action": "action_complete_desactivation_carte",
        "patterns": extract_info(PATTERNS, ['typeCompte', 'numeroCompte', 'services'])
    },
    "Gestion_Cartes_Opposition": {
        "action": "action_opposition_carte",
        "complete_action": "action_complete_opposition_carte",
        "patterns": extract_info(PATTERNS, ['typeCompte', 'numeroCompte', 'raisonsOpposition'])
    },
    "Gestion_Cartes_Plafond_Augmenter": {
        "action": "action_plafond_augmenter",
        "complete_action": "action_complete_plafond_augmenter",
        "patterns": extract_info(PATTERNS, ['numeroCarte', 'typeCarte', 'montant', 'typePlafond'])
    },
    "Gestion_Cartes_Plafond_Diminuer": {
        "action": "action_plafond_diminuer",
        "complete_action": "action_complete_plafond_diminuer",
        "patterns": extract_info(PATTERNS, ['numeroCarte', 'typeCarte', 'montant', 'typePlafond'])
    }
}
