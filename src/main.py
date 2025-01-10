
import json
import base64
from typing import Any
from twilio.rest import Client
from celery import Celery
from celery.schedules import crontab
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
import asyncio
import websockets
import xml.etree.ElementTree as ET
import logging

from fastapi import (
    FastAPI, 
    BackgroundTasks, 
    HTTPException, 
    WebSocket, 
    WebSocketDisconnect, 
    Request,
)
from fastapi.responses import (
    JSONResponse, 
    Response,
)

import os

from .settings import (
    TWILIO_AUTH_TOKEN,
    TWILIO_ACCOUNT_SID,
    TWILIO_PHONE_NUMBER,
    OPENAI_API_KEY,
    POSTGRES_URL,
    REDIS_URL,
    TIMEZONE,
    OPENAI_REALTIME_API_URL,
    LOGGER_NAME,
    INITIAL_WAIT_MESSAGE,
    SERVER_URL,
    LOG_EVENT_TYPES,
    VOICE,
    SYSTEM_MESSAGE,
    DEBUG,
    GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_FILE,
    SPREADSHEET_ID,
)

from .models import (
    ClientData,
)

# utils
from .utils import (
    validate_twilio_request,
    get_caller_first_message
)
from .logs import logger as magnus_logger

logger = logging.getLogger(LOGGER_NAME)

app = FastAPI()

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
redis_client = redis.Redis.from_url(REDIS_URL)
celery_app = Celery('magnus_tasks', broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.beat_schedule = {
    'daily-client-calls': {
        'task': 'make_daily_calls',
        'schedule': crontab(hour=9, minute=0),
    },
}
celery_app.conf.timezone = TIMEZONE


async def send_session_update(openai_ws):
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {
                "type": "server_vad"
            },
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
            "input_audio_transcription": {
                "model": "whisper-1",
            },
            "tools": [

            ]
        },
        
    }
    await openai_ws.send(json.dumps(session_update))
    print("Sent session update")

@app.websocket("/media-stream/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = {
        "session_id": "",
        "conversation": [],
    }
    
    stream_sid = None

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1"
    }

    try:
        async with websockets.connect(
            OPENAI_REALTIME_API_URL,
            extra_headers=headers,
        ) as openai_ws:
            

            async def stream_events_on_twilio():
                '''
                Stream events received by twilio
                '''
                nonlocal stream_sid

            async def stream_events_on_openai():
                nonlocal stream_sid

                '''
                Stream events received by openai
                '''

                try:
                    async for openai_message in openai_ws:
                        data:dict[str, Any] = json.loads(openai_message)
                    
                        if data["type"] == "session.updated":
                            print(f"Session updated: {data=}")

                        if data["type"] == "response.audio.delta" and data.get("delta"):
                            try:
                                audio_payload = base64.b64encode(base64.b64decode(data["delta"])).decode()
                                audio_delta = {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {
                                        "payload": audio_payload,
                                        
                                    }
                                }
                                await websocket.send_json(audio_delta)
                            except Exception as e:
                                print(f"Error processing audio: {e}")
                                return
                        
                        if data["type"] == "response.audio.done":
                            print("The model-generated audio is either done, interrupted, incomplete, or cancelled")

                        if data["type"] == "response.audio_transcript.delta" and data.get("delta"):
                            message = data["delta"]
                            session["conversation"].append()

                except WebSocketDisconnect:
                    print("OpenAI disconnected")
                    if websocket.client_state != 3:
                        await websocket.close()
                    return
                except Exception as e:  
                    print(f"Error sending to Twilio: {e}")
                    return
            
            await asyncio.gather(
                stream_events_on_twilio(), 
                stream_events_on_openai(),
            )
    except WebSocketDisconnect:
        print("WebSocket disconnected.")
    except Exception as e:
        print(f"Error in WebSocket interaction: {e}")


@celery_app.task
def make_call_task(phone_number: str, name: str):
    try:

        host = SERVER_URL
        response = ET.Element("Response")
        connect = ET.SubElement(response, "Connect")
        stream = ET.SubElement(connect, "Stream", url=f"wss://{host}/media-stream")
        
        twiml_response = ET.tostring(response, encoding="unicode")
        call = twilio_client.calls.create(
            twiml=twiml_response,
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER
        )
        return call.sid
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during call: {e}")

@celery_app.task(name='make_daily_calls')
def make_daily_calls():
    try:
        client_phone_number = "+254793787653"
        client_name = "Jarib Wetshi"
        make_call_task.delay(
            client_phone_number, 
            client_name
        )
    except Exception as e:
        print(f"Error in daily call task: {e}")
    

@app.api_route("/answer-call", methods=["GET", "POST"])
@validate_twilio_request
async def answer_call(request: Request):
    logger.info("Incoming call")

    request_form_data ={}
    request_query_params = {}
    request_json = {}

    try:
        request_form_data = await request.form()
        request_form_data = dict(request_form_data)
    except Exception as e:
        logger.exception("an error occurred while parsing form data")

    try:
        request_query_params = request.query_params
        request_query_params = dict(request_query_params)
    except Exception as e:
        logger.exception("an error occurred while parsing query params")


    try:
        request_json = await request.json()
        request_json = dict(request_json)
    except Exception as e:
        logger.exception("an error occurred while parsing json data")

    twilio_params = {**request_form_data, **request_query_params, **request_json}

    logger.info(f"Twilio params: {twilio_params}")

    caller_number = twilio_params.get("From")
    caller_city = twilio_params.get("FromCity")
    caller_sid = twilio_params.get("CallSid")

    first_message = INITIAL_WAIT_MESSAGE
    first_message_dict = get_caller_first_message(caller_number)
    if first_message_dict:
        first_message = f"""
Hello again {first_message_dict.get("full_name")}. On our last call, {first_message_dict.get("call_summary")}.
Would you like to continue from where we left off? or
"""

    host = request.url.hostname
    response = ET.Element("Response")
    connect = ET.SubElement(response, "Connect")
    stream = ET.SubElement(connect, "Stream", url=f"wss://{host}/media-stream")
    ET.SubElement(stream, "Parameter", name="firstMessage", value=first_message)
    ET.SubElement(stream, "Parameter", name="callerNumber", value=caller_number)

    twiml_response = ET.tostring(response, encoding="unicode")

    return Response(content=twiml_response, media_type="text/xml")





