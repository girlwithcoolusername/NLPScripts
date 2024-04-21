import uvicorn
from fastapi import FastAPI, Request

from chatbot_api.IntentActions import IntentActions
from chatbot_api.utils.contstants import INTENT_ACTIONS, MODEL, TOKENIZER, LABEL_ENCODER
from chatbot_api.utils.bot import handle_first_request, handle_security_question, handle_request, \
    handle_request_validation, handle_missing_entity
from chatbot_api.utils.nlu import intent_recognition

app = FastAPI()
# Define global variables to track state
context = None
security_question = None
entities_extracted = []


@app.post('/')
async def main_handle_request(request: Request):
    global context, security_question, extracted_entities

    # Get text data from request
    data = await request.json()

    # If context is None, it means it's the first request
    if context is None:
        context = "first_request"
        response, security_question = handle_first_request()
        context = "user_request"
        return {"response": response + security_question}

    # If context is "security_question", handle the security question
    elif context == "security_question":
        new_context, response = handle_security_question(security_question, data)
        if new_context:
            context = new_context
        else:
            context = None
        return {"response": response}

    # If an entity is missing in the user's answer
    elif "Entity_Missing" in context:
        context, response, extracted_entities = handle_missing_entity(data,context,extracted_entities)
        return {"response" : response}

    elif "Request_Validation" in context:
        context, response, extracted_entities = handle_request_validation(data, context, MODEL, TOKENIZER,
                                                                          LABEL_ENCODER, extracted_entities)
        return {"response": response}

    # Otherwise, handle the user's request based on the current context
    elif context == "user_request" or context in INTENT_ACTIONS:
        answer = handle_request(data, MODEL, TOKENIZER, LABEL_ENCODER)
        if len(answer) == 2:
            context, response = answer
        elif len(answer) == 3:
            context, response, extracted_entities = answer
        else:
            response = answer
        return {"response": response}


if __name__ == "__main__":
    uvicorn.run(app, host='0.0.0.0', port=8000)
