import uvicorn
from fastapi import FastAPI, Request

from chatbot_api.SpringAPIService import SpringAPIService
from chatbot_api.SecurityValidator import SecurityValidator
from chatbot_api.utils.contstants import SPRING_BASE_URL, \
    USERNAME, PASSWORD, ROLE

app = FastAPI()
# Define global variables to track state
context = None
security_question = None
entities_extracted = []


# Define endpoint for handling the request
@app.get('/')
async def main_handle_request(request: Request):
    spring_api = SpringAPIService(SPRING_BASE_URL,USERNAME,PASSWORD,ROLE)
    security_validator = SecurityValidator(spring_api,1)
    # Tester les différentes méthodes de SecurityValidator
    print("Date de naissance:", security_validator.provide_date_of_birth())
    print("Adresse email:", security_validator.provide_email_address())
    print("Adresse postale:", security_validator.provide_postal_address())
    print("Numéro de téléphone:", security_validator.provide_phone_number())
    print("Montant de la dernière transaction:", security_validator.provide_last_transaction_amount())
    print("Agence:", security_validator.provide_agency())


if __name__ == "__main__":
    uvicorn.run(app, host='localhost', port=8000)
