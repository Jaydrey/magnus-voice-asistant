import json
import base64
import datetime
from typing import Any
from twilio.rest import Client
from celery import Celery
from celery.schedules import crontab
import uvicorn
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
import asyncio
import websockets
import xml.etree.ElementTree as ET
import logging

from twilio.twiml.voice_response import (
    VoiceResponse, 
    Connect, 
    Say, 
    Stream
)

from src.models import Conversation
from .settings import (
    TWILIO_AUTH_TOKEN,
    TWILIO_ACCOUNT_SID,
    TWILIO_PHONE_NUMBER,
    OPENAI_API_KEY,
    POSTGRES_URL,
    REDIS_URL,
    TIMEZONE,
    OPENAI_REALTIME_API_URL,
    VOICE
)

from fastapi import (
    FastAPI, 
    WebSocket, 
    WebSocketDisconnect, 
    Request,
)
from fastapi.responses import (
    Response,
)


app = FastAPI()

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
celery_app = Celery('magnus_tasks', broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.beat_schedule = {
    'daily-client-calls': {
        'task': 'make_daily_calls',
        'schedule': crontab(hour=9, minute=0),
    },
}
celery_app.conf.timezone = TIMEZONE

logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', 
    filename="pet_store.log",
    encoding='utf-8',
    filemode='a+',
)

pet_store_logger = logging.getLogger("pet_logger")

PET_STORE_SYSTEM_MESSAGE = """
You are a virtual assistant for a veterinarian and pet store, responsible for handling calls with warmth, friendliness, and empathy. 
You check in on pets after visits, book and manage appointments, recommend products, and follow up on adoption inquiries. 
You actively listen, personalize interactions by referencing client and pet details, and provide general pet care advice based on your knowledge base. 
In emergencies, you calmly advise immediate action and escalate calls to the appropriate staff or veterinarian when necessary. 
You log all call details, respect data privacy, and ensure professional and efficient service in every interaction.
"""

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
            "instructions": PET_STORE_SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
            "input_audio_transcription": {
                "model": "whisper-1",
            },
        },
        
    }
    await openai_ws.send(json.dumps(session_update))
    print("Sent session update")

open_ai_ws_open = False

@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    pet_store_logger.info("media stream websocket connected")

    session = {
        "session_id": "",
        "conversation": [],
    }

    stream_sid = None
    latest_media_timestamp = 0
    last_assistant_item = None
    mark_queue = []
    response_start_timestamp_twilio = None
    global open_ai_ws_open

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1"
    }

    try:

        async with websockets.connect(
            OPENAI_REALTIME_API_URL,
            additional_headers=headers
        ) as openai_ws:
            open_ai_ws_open = True
            pet_store_logger.info(f"connected to openai realtime api {openai_ws}")
            await send_session_update(openai_ws)

            async def stream_events_on_twilio():
                '''
                Stream events received by twilio
                '''
                nonlocal stream_sid, latest_media_timestamp
                global open_ai_ws_open
                try:
                    async for message in websocket.iter_text():
                        twilio_data:dict[str, Any] = json.loads(message)

                        if twilio_data.get("event") == "start":
                            pet_store_logger.info(f"Start of Twilio Stream {twilio_data}")
                            custom_parameters = twilio_data["start"]["customParameters"]
                            pet_store_logger.info(custom_parameters)
                            stream_sid = twilio_data["start"]["streamSid"]

                            response_start_timestamp_twilio = None
                            latest_media_timestamp = 0
                            last_assistant_item = None

                        if twilio_data.get("event") == "media":
                            pet_store_logger.info("Raw audio data from twilio")

                            try:
                                audio_payload = twilio_data["media"]["payload"]
                                latest_media_timestamp = int(str(twilio_data["media"]["timestamp"]))

                                if open_ai_ws_open:
                                    audio_message = {
                                        "type": "input_audio_buffer.append",
                                        "audio": audio_payload,
                                    }

                                    await openai_ws.send(json.dumps(audio_message))
                                    pet_store_logger.info("Audio sent to OpenAI")
                                else:
                                    pet_store_logger.warning("OpenAI WebSocket is not open. Skipping audio.")

                            except Exception as e:
                                pet_store_logger.exception ("error sending audio to openai")

                        if twilio_data.get("event") == "mark":
                            if mark_queue:
                                mark_queue.pop(0)

                except Exception as e:
                    pet_store_logger.info("Error in Twilio event handling")
                    raise
                

            async def stream_events_on_openai():
                nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio
                global open_ai_ws_open

                '''
                Stream events received by openai
                '''

                try:
                    async for openai_message in openai_ws:
                        data:dict[str, Any] = json.loads(openai_message)
                        timestamp = datetime.datetime.now(datetime.timezone.utc)

                        if data["type"] == "session.created":
                            pet_store_logger.info("openai websocket session created")
                    
                        if data["type"] == "session.updated":
                            pet_store_logger.info(f"Session updated")

                        if data["type"] == "conversation.item.input_audio_transcription.completed":
                            user_message = data["transcript"]
                            conversation = Conversation(
                                user="user",
                                message=user_message,
                                stream_sid=stream_sid or "",
                                timestamp=timestamp,
                            )
                            pet_store_logger.info(conversation)

                            session["conversation"].append(conversation)

                        if data["type"] == "response.audio.delta" and data.get("delta"):
                            try:
                                audio_payload = base64.b64encode(base64.b64decode(data["delta"])).decode("utf-8")
                                audio_delta = {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {
                                        "payload": audio_payload,
                                        
                                    }
                                }
                                await websocket.send_json(audio_delta)

                                if response_start_timestamp_twilio is None:
                                    response_start_timestamp_twilio = latest_media_timestamp

                                if data["item_id"]:
                                    last_assistant_item = data["item_id"]

                                if stream_sid:
                                    await send_mark(websocket, stream_sid)

                            except Exception as e:
                                print(f"Error processing audio: {e}")
                                return
                        
                        if data["type"] == "response.audio.done":
                            print("The model-generated audio is either done, interrupted, incomplete, or cancelled")

                        if data["type"] == "response.audio_transcript.done" and data.get("delta"):
                            agent_message = data["delta"]
                            conversation = Conversation(
                                user="agent",
                                message=agent_message,
                                stream_sid=stream_sid or "",
                                timestamp=timestamp,
                            )
                            pet_store_logger.info(conversation)
                            session["conversation"].append(conversation)

                        if data["type"] == "rate_limits.updated":
                            pet_store_logger.info(f"rate limit: {data}")

                        if data["type"] == "input_audio_buffer.speech_started":
                            pet_store_logger.info("speech started detected from user")
                            if last_assistant_item:
                                await handle_speech_started_event()

                except websockets.ConnectionClosed:
                    open_ai_ws_open = False
                    pet_store_logger.exception("OpenAI Websocket connection closed")
                except Exception as e:  
                    open_ai_ws_open = False
                    pet_store_logger.exception(f"Error in OpenAI Stream: {e}")
                finally:
                    open_ai_ws_open = False
            

            async def handle_speech_started_event():
                """Handle interruption when the caller's speech starts."""
                nonlocal response_start_timestamp_twilio, last_assistant_item
                print("Handling speech started event.")
                if last_assistant_item and response_start_timestamp_twilio is not None:
                    elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
                    
                    truncate_event = {
                        "type": "conversation.item.truncate",
                        "item_id": last_assistant_item,
                        "content_index": 0,
                        "audio_end_ms": elapsed_time
                    }
                    await openai_ws.send(json.dumps(truncate_event))

                    await websocket.send_json({
                        "event": "clear",
                        "streamSid": stream_sid
                    })

                    mark_queue.clear()
                    last_assistant_item = None
                    response_start_timestamp_twilio = None

            async def send_mark(connection, stream_sid):
                if stream_sid:
                    mark_event = {
                        "event": "mark",
                        "streamSid": stream_sid,
                        "mark": {"name": "responsePart"}
                    }
                    await connection.send_json(mark_event)

            await asyncio.gather(
                stream_events_on_twilio(), 
                stream_events_on_openai(),
            )

            pet_store_logger.info(session["conversation"])

    except WebSocketDisconnect:
        pet_store_logger.warning("OpenAI WebSocket disconnected")
    except Exception as e:
        pet_store_logger.error(f"Error in OpenAI WebSocket: {e}")
    finally:
        open_ai_ws_open = False
        if openai_ws.state != 3:  # Ensure connection is closed
            await openai_ws.close()
        await websocket.close()



@app.api_route("/answer-call", methods=["GET", "POST"])
async def answer_call(request: Request):
    pet_store_logger.info("Incoming call")

    request_form_data ={}
    request_query_params = {}
    request_json = {}

    try:
        request_form_data = await request.form()
        request_form_data = dict(request_form_data)
    except Exception as e:
        pet_store_logger.exception("an error occurred while parsing form data")

    try:
        request_query_params = request.query_params
        request_query_params = dict(request_query_params)
    except Exception as e:
        pet_store_logger.exception("an error occurred while parsing query params")


    try:
        request_json = await request.json()
        request_json = dict(request_json)
    except Exception as e:
        pet_store_logger.exception("an error occurred while parsing json data")

    twilio_params = {**request_form_data, **request_query_params, **request_json}

    pet_store_logger.info(f"Twilio params: {twilio_params}")

    caller_country = twilio_params.get("CallerCountry")
    caller_state = twilio_params.get("CallerState")
    caller_city = twilio_params.get("CallerCity")
    caller_zip = twilio_params.get("CallerZip")
    caller_number = twilio_params.get("From")



    host = request.url.hostname

    response = VoiceResponse()
    welcome_say = Say("Hello Caleno. Connecting you to the Pet Store Agent. Please wait for a second!")

    connect = Connect()

    stream = Stream(
        url=f"wss://{host}/media-stream",
        name="media_stream",
    )

    connect.append(stream)
    response.append(welcome_say)
    response.append(connect)

    return Response(content=str(response), media_type="text/xml")


