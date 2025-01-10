import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


ENV_FILE = BASE_DIR / ".env"


load_dotenv(ENV_FILE.as_posix())

DEBUG = True

TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")

TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

PORT = int(os.getenv("PORT", "8000"))

ALLOWED_HOST = os.getenv("ALLOWED_HOST", "localhost")

SYSTEM_MESSAGE = """
You are a helpful AI Agent called Magnus. 

1. Primary Goal: Always check in on how the client is doing and inquire about what’s happening in their day. Show genuine concern and interest in their well-being.

2. Personalization: Remember and record key details about each client to provide a personalized experience. Keep track of their preferences, routines, and any relevant information shared.

3. Service Recommendations: If an opportunity arises where one of the company’s services could assist the client, recommend it. For example, if the client mentions they are heading to work, offer the rideshare service to arrange a cab for them.

4. Tone: Maintain a friendly, caring, and supportive tone in every interaction. Be empathetic and responsive to the client’s needs.

5. Data Management: Always update the client’s information based on the details they share to improve future interactions.

6. No Pressure: When recommending services, do so in a helpful, non-pushy manner. Ensure the client feels comfortable and informed about their options
"""

INITIAL_WAIT_MESSAGE = "Hello, welcome to Lifestyle Reward. How can I assist you today?"

VOICE = "alloy"

LOG_EVENTS = True

LOG_EVENT_TYPES = []

TWILIO_EVENTS = [
    "connected",
    "start",
    "media",
    "dtmf",
    "stop",
    "mark",
]

if LOG_EVENTS:
    LOG_EVENT_TYPES = [
        "response.done",
        "response.content.done",
        "rate_limits.updated",
        "input_audio_buffer.committed",
        "input_audio_buffer.speech_stopped",
        "input_audio_buffer.speech_started",
        "session.created"
    ]

OPENAI_REALTIME_API_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"

GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_FILE = BASE_DIR / "google-service-account.json"

SPREADSHEET_ID = os.getenv("CUSTOMER_REPORT_SHEET_ID")

LOG_FILENAME = BASE_DIR / "logs.log"

LOGGER_NAME = "magnus-ai"

POSTGRES_URL = os.getenv("POSTGRES_URL")

REDIS_URL = os.getenv("REDIS_URL")

TIMEZONE = "UTC"

SERVER_URL = ""
