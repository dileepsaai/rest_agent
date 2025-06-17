# whatsapp_integration.py

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from flask_cors import CORS
from dotenv import load_dotenv
import os

from agent import root_agent  # Your ADK agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types  # For Content and Part

load_dotenv()
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

app = Flask(__name__)
CORS(app)
validator = RequestValidator(TWILIO_TOKEN)

# Proper session service and runner instantiation
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    session_service=session_service,
    app_name="whatsapp_sql_agent"
)

@app.route("/webhook", methods=["POST"])
def webhook():
    # 1. Validate Twilio signature
    signature = request.headers.get("X-Twilio-Signature", "")
    if not validator.validate(request.url, request.form.to_dict(), signature) \
       and os.getenv("FLASK_ENV") != "development":
        return "Forbidden", 403

    # 2. Extract message and user/session ID
    incoming_msg = request.values.get("Body", "").strip()
    from_whatsapp = request.values.get("From", "").replace("whatsapp:", "")
    session_id = from_whatsapp

    # 3. **Create session properly** using the documented method
    session = session_service.create_session(
        app_name="whatsapp_sql_agent",
        user_id=session_id,
        session_id=session_id
    )

    # 4. Wrap user input as ADK Content
    content = types.Content(role="user", parts=[types.Part(text=incoming_msg)])

    # 5. Run the agent with proper parameters
    try:
        events = runner.run(
            user_id=session.user_id,
            session_id=session.id,
            new_message=content
        )

        response_text = ""
        for event in events:
            if event.is_final_response():
                response_text = event.content.parts[0].text
                break
        if not response_text:
            response_text = "⚠️ No response generated."

    except Exception as e:
        response_text = f"❌ {e}"

    # 6. Send Twilio WhatsApp message
    resp = MessagingResponse()
    resp.message(response_text)
    return str(resp), 200, {'Content-Type': 'application/xml'}


if __name__ == "__main__":
    print("WhatsApp agent listening on 5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
