from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request, Depends
from starlette.middleware.sessions import SessionMiddleware

from chatbot_api.utils.bot import handle_first_request, handle_security_question, handle_request, \
    handle_request_validation, handle_missing_entity
from chatbot_api.utils.contstants import INTENT_ACTIONS, MODEL, TOKENIZER, LABEL_ENCODER

app = FastAPI()

# Adding session middleware to manage session data
app.add_middleware(SessionMiddleware, secret_key="!secret")


# Use this function to get the session object from request
def get_session(request: Request):
    return request.session


@app.post('/')
async def main_handle_request(request: Request, session: dict = Depends(get_session)):
    # Initialize session if it does not exist
    if 'session_id' not in session:
        session['session_id'] = str(uuid4())
        session['context'] = None
        session['security_question'] = None
        session['extracted_entities'] = {}

    # Get text data from request
    data = await request.json()

    # Logic based on context stored in session
    context = session['context']
    security_question = session['security_question']
    extracted_entities = session['extracted_entities']

    # Handle first request
    if context is None:
        session['context'] = "first_request"
        response, security_question = handle_first_request()
        session['context'] = "security_question"
        session['security_question'] = security_question
        return {"response": response + security_question}

    # Handle security question
    elif context == "security_question":
        new_context, response = handle_security_question(security_question, data)
        session['context'] = new_context if new_context else None
        return {"response": response}

    # Handle missing entity
    elif "Entity_Missing" in context:
        context, response, extracted_entities = handle_missing_entity(data, context, extracted_entities, MODEL,
                                                                      TOKENIZER, LABEL_ENCODER)
        session['context'] = context
        session['extracted_entities'] = extracted_entities
        return {"response": response}

    # Handle request validation
    elif "Request_Validation" in context:
        context, response, extracted_entities = handle_request_validation(data, context, MODEL, TOKENIZER,
                                                                          LABEL_ENCODER, extracted_entities)
        session['context'] = context
        session['extracted_entities'] = extracted_entities
        return {"response": response}

    # Handle general user requests
    elif context == "user_request" or context in INTENT_ACTIONS:
        answer = handle_request(data, MODEL, TOKENIZER, LABEL_ENCODER)
        if len(answer) == 2:
            context, response = answer
            session['context'] = context
        elif len(answer) == 3:
            context, response, extracted_entities = answer
            session['context'] = context
            session['extracted_entities'] = extracted_entities
        else:
            response = answer
        return {"response": response}


if __name__ == "__main__":
    uvicorn.run(app, host='0.0.0.0', port=8000)
