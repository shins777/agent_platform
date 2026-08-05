"""
🤖 Google Search ADK Agent (Agent Gateway)
================================================================================
Step 1: Create an ADK Agent which searches and analyzes user requests using Google Search.
"""

from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.a2a.utils.agent_to_a2a import to_a2a

root_agent = Agent(
    model='gemini-2.5-flash',
    name='search_agent_0805',
    description='An agent that searches and analyzes user requests using Google Search.',
    instruction=(
        "Search for and analyze the user's request using Google Search. "
        "Always use the Google Search tool to find up-to-date and accurate information when answering user questions."
    ),
    tools=[google_search],
)

# A2A protocol compliant Starlette/ASGI application wrapper for the ADK Agent
a2a_app = to_a2a(root_agent)

