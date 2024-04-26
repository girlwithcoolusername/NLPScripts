import asyncio
import time
import uvicorn
from fastapi import FastAPI, Request

from chatbot_api.utils.bot import handle_first_request, handle_security_question, handle_request, \
    handle_request_validation, handle_missing_entity
from chatbot_api.utils.contstants import MODEL, LABEL_ENCODER, TOKENIZER, INTENT_ACTIONS

app = FastAPI()

user_contexts = {}
user_security_questions = {}
user_extracted_entities = {}


@app.on_event("startup")
async def startup_event():
    # Start a cleanup task that runs periodically to clear expired user data
    asyncio.create_task(cleanup_user_data())


@app.post('/')
async def main_handle_request(request: Request):
    data = await request.json()
    user_id = data["userId"]

    # Initialize user data if this is a new user
    if user_id not in user_contexts:
        user_contexts[user_id] = {'timestamp': time.time(), 'context': None}
        user_security_questions[user_id] = None
        user_extracted_entities[user_id] = {}

    # Update timestamp with each interaction
    user_contexts[user_id]['timestamp'] = time.time()

    # Retrieve specific user context information
    context = user_contexts[user_id]['context']
    security_question = user_security_questions[user_id]
    extracted_entities = user_extracted_entities[user_id]

    # Logic based on the context stored in the user's session
    if context is None:
        context, response, security_question = handle_first_request()
        user_contexts[user_id] = {'timestamp': time.time(), 'context': context}
        user_security_questions[user_id] = security_question
        return {"response": response + security_question}

    elif context == "security_question":
        new_context, response = handle_security_question(security_question, data)
        user_contexts[user_id]['context'] = new_context if new_context else None
        return {"response": response}

    elif "Entity_Missing" in context:
        context, response, extracted_entities = handle_missing_entity(data, context, extracted_entities, MODEL,
                                                                      TOKENIZER, LABEL_ENCODER)
        user_contexts[user_id]['context'], user_extracted_entities[user_id] = context, extracted_entities
        return {"response": response}

    elif "Request_Validation" in context:
        context, response, extracted_entities = handle_request_validation(data, context, MODEL, TOKENIZER,
                                                                          LABEL_ENCODER, extracted_entities)
        user_contexts[user_id]['context'], user_extracted_entities[user_id] = context, extracted_entities
        return {"response": response}

    elif context == "user_request" or context in INTENT_ACTIONS:
        answer = handle_request(data, MODEL, TOKENIZER, LABEL_ENCODER)
        if len(answer) == 2:
            if not isinstance(answer, list):
                context, response = answer
            else:
                response = answer
        elif len(answer) == 3:
            context, response, extracted_entities = answer
        else:
            response = answer
        user_contexts[user_id]['context'], user_extracted_entities[user_id] = context, extracted_entities
        return {"response": response}


async def cleanup_user_data(interval_seconds=3600):  # Clean up every hour
    while True:
        current_time = time.time()
        expired_users = [user_id for user_id, user in user_contexts.items() if
                         (current_time - user['timestamp']) > interval_seconds]
        for user_id in expired_users:
            del user_contexts[user_id]
            del user_security_questions[user_id]
            del user_extracted_entities[user_id]
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    uvicorn.run(app, host='0.0.0.0', port=8000)
