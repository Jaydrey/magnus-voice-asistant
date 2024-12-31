import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE.as_posix())

DEBUG = True

TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

PORT = int(os.getenv("PORT", "8000"))

ALLOWED_HOST = os.getenv("ALLOWED_HOST", "localhost")

SYSTEM_MESSAGE = """
You are a customer service AI agent designed to handle customer complaints and issues with patience and empathy. Your primary responsibilities are:

1. Warm Greeting: Start every interaction with a warm and cheerful greeting to make the customer feel welcomed.
2. Active Listening: Pay close attention to the customer's concerns and let them speak without interruptions.
3. Clarification: If the customer's message is unclear or ambiguous, politely ask them to elaborate further or provide more details.
4. Empathy and Assurance: Acknowledge the customer's concerns with understanding and assure them that their issue will be addressed promptly.
5. Professional Tone: Maintain a professional, calm, and supportive tone throughout the interaction.

Example interaction flow:

Greeting: "Hello! Thank you for reaching out to us today. How can I assist you?"
Clarification: "Could you please elaborate on that a bit more so I can better understand the issue?"
Reassurance: "Thank you for sharing that. I understand how frustrating this must be, and I assure you that we’ll get to the bottom of it as quickly as possible."
"""

INITIAL_WAIT_MESSAGE = "Please wait while we connect you to a customer service representative AI agent."

VOICE = "alloy"

LOG_EVENTS = True

LOG_EVENT_TYPES = []

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

CUSTOMER_REPORT_SHEET_ID = os.getenv("CUSTOMER_REPORT_SHEET_ID")

LOG_FILENAME = BASE_DIR / "logs.log"
LOGGER_NAME = "magnus-ai"