from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from agent import root_agent  # your existing ADK Agent

# Initialize session service and runner
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name="sql_agent_app",
    session_service=session_service
)
