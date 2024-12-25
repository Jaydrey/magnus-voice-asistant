from typing import Any
import os
import json
import asyncio
import base64
import websockets

from fastapi import FastAPI, WebSocket, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.websockets import WebSocketDisconnect

from twilio.twiml.voice_response import VoiceResponse, Connect, Say, Stream

# settings
from .settings import (
    INITIAL_WAIT_MESSAGE,
    OPENAI_API_KEY,
    OPENAI_REALTIME_API_URL,
    PORT,
    LOG_EVENT_TYPES,
    SYSTEM_MESSAGE
)

app = FastAPI()

@app.get("/", response_class=JSONResponse)
async def index():
    return {"message": "Hello FastAPI World"}


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
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
        # await send_session_update(openai_ws)
        stream_sid = None

        async def receive_from_twilio():
            nonlocal stream_sid

            try:
                async for message in websocket.iter_text():
                    data:dict[str, Any] = json.loads(message)
                    if data["event"] == "start":
                        stream_sid = data["start"]["streamSid"]
                        print(f"Incoming stream has started {stream_sid}")
                        audio = data["audio"]
                        await openai_ws.send(audio)
                    
            except WebSocketDisconnect:
                print("Twilio disconnected")
                return
            except Exception as e:
                print(f"Error receiving from Twilio: {e}")
                return
