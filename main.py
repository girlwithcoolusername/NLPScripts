import uvicorn
from fastapi import FastAPI, Request
from chatbot_api.utils.contstants import INTENT_ACTIONS, MODEL, TOKENIZER, LABEL_ENCODER
from chatbot_api.utils.bot import handle_first_request, handle_security_question, handle_request
from chatbot_api.utils.nlu import intent_recognition

app = FastAPI()
# Define global variables to track state
context = None
security_question = None
entities_extracted = []


# Define endpoint for handling the request
@app.post('/')
async def main_handle_request(request: Request):
    global context, security_question, extracted_entities

    # Get text data from request
    data = await request.json()

    # If context is None, it means it's the first request
    if context is None:
        context = "first_request"
        response, security_question = handle_first_request()
        context = "security_question"
        return {"response": response, "question": security_question}

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
        intent = context.split("Entity_Missing_")[1]
        if intent in INTENT_ACTIONS:
            return INTENT_ACTIONS[intent]['complete_action'](data, extracted_entities, INTENT_ACTIONS[intent]["patterns"],"Missing_Entity")

    elif "Request_Validation" in context:
        previous_intent = context.split("Request_Validation_")[1]
        text = data['text'].lower()
        intent = intent_recognition(text, MODEL, TOKENIZER, LABEL_ENCODER)
        if intent == "Confirmation_Action":
            if previous_intent in INTENT_ACTIONS:
                return INTENT_ACTIONS[previous_intent]['complete_action'](data, extracted_entities,
                                                                          INTENT_ACTIONS[previous_intent]["patterns"],
                                                                          intent)
        elif intent == "Annulation_Action":
            if previous_intent in INTENT_ACTIONS:
                return INTENT_ACTIONS[previous_intent]['complete_action'](data, extracted_entities,
                                                                          INTENT_ACTIONS[previous_intent]["patterns"],
                                                                          intent)
    # Otherwise, handle the user's request based on the current context
    elif context == "user_request" or context in INTENT_ACTIONS:
        response = None
        answer = handle_request(data, MODEL, TOKENIZER, LABEL_ENCODER)
        if len(answer) == 2:
            context, response = answer
        elif len(answer) == 3:
            context, response, extracted_entities = answer
        return {"response": response}


if __name__ == "__main__":
    uvicorn.run(app, host='localhost', port=8000)
