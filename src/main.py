from typing import Any
import os
import logging
import json
import asyncio
import base64
import websockets

from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.websockets import WebSocketDisconnect

from twilio.twiml.voice_response import (
    VoiceResponse, 
    Connect, 
)

# settings

from settings import (
    INITIAL_WAIT_MESSAGE,
    OPENAI_API_KEY,
    OPENAI_REALTIME_API_URL,
    LOG_EVENT_TYPES,
    SYSTEM_MESSAGE,
    VOICE,
    LOGGER_NAME,
)

# utils
from utils import (
    validate_twilio_request,
)
from logs import logger as magnus_logger

logger = logging.getLogger(LOGGER_NAME)

app = FastAPI()

@app.get("/", response_class=JSONResponse)
async def index():
    return {"message": "Hello FastAPI World"}


@app.api_route("/incoming-call", methods=["GET", "POST"])
@validate_twilio_request
async def handle_incoming_call(request: Request):
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

    response = VoiceResponse()
    response.say(INITIAL_WAIT_MESSAGE)
    response.pause(length=1)
    response.say("O.K. you can start talking now.")

    host = request.url.hostname

    connect = Connect()
    connect.stream(url=f"wss://{host}/media-stream")
    
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")
    
@app.websocket("/media-stream")
@validate_twilio_request
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    print("Connected to media stream")

    if OPENAI_API_KEY:
        raise ValueError("Set OPENAI_API_KEY environment variable to use this feature.")

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1"
    }

    async with websockets.connect(
        OPENAI_REALTIME_API_URL,
        extra_headers=headers,
    ) as openai_ws:
        await send_session_update(openai_ws)
        stream_sid = None

        # messages sent from twilio to open AI
        async def receive_from_twilio():
            nonlocal stream_sid

            try:
                async for message in websocket.iter_text():
                    data:dict[str, Any] = json.loads(message)
                    if data["event"] == "start":
                        stream_sid = data["start"]["streamSid"]
                        print(f"Incoming stream has started {stream_sid}")
                    elif data["event"] == "media" and openai_ws.open:
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data["media"]["payload"]
                        }
                        await openai_ws.send(json.dumps(audio_append))
                    
            except WebSocketDisconnect:
                print("Twilio disconnected")
                if openai_ws.open:
                    await openai_ws.close()
                return
            except Exception as e:
                print(f"Error receiving from Twilio: {e}")
                return
        
        # messages sent from open AI to twilio
        async def send_to_twilio():
            nonlocal stream_sid
            try:
                async for openai_message in openai_ws:
                    data:dict[str, Any] = json.loads(openai_message)
                    if data["type"] in LOG_EVENT_TYPES:
                        print(f"Received event: {data['type']}, {data=}")
                    
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
                        
            except WebSocketDisconnect:
                print("OpenAI disconnected")
                if websocket.client_state != 3:
                    await websocket.close()
                return
            except Exception as e:  
                print(f"Error sending to Twilio: {e}")
                return
            
        await asyncio.gather(receive_from_twilio(), send_to_twilio())


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
            }
        },
        
    }
    await openai_ws.send(json.dumps(session_update))
    print("Sent session update")



