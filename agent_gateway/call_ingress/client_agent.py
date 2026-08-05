#!/usr/bin/env python3
"""
🤖 ADK Client Agent (Ingress -> Agent Gateway -> A2A Gateway)
================================================================================
An ADK client agent that discovers the recently deployed agent in Agent Gateway
(GCP Agent Registry) and invokes it via the Agent-to-Agent (A2A) Gateway.

Workflow:
1. Initialize GCP Agent Registry client (project: ai-hangsik, location: global)
2. Locate the recently deployed agent by display name ("Google Search & Analysis Agent")
3. Securely authenticate using Application Default Credentials (ADC) & OAuth 2.0
4. Bind to the remote agent via A2A Gateway (AgentRegistry.get_remote_a2a_agent)
5. Execute an interactive/streaming query using ADK's InMemoryRunner
"""

import os
import sys
import asyncio
import google.auth
import google.auth.transport.requests
import google.auth.transport.mtls as auth_mtls
import httpx
from google.adk.integrations.agent_registry.agent_registry import AgentRegistry
from google.adk.runners import InMemoryRunner
from google.genai import types

# Disable mTLS client cert requirement for local dev environments (prevents SSLCertVerificationError on macOS)
auth_mtls.should_use_client_cert = lambda: False


# ==============================================================================
# [Essential Monkeypatch] ADK SDK _clean_name patch for non-alphanumeric / multi-word names
# ==============================================================================
def _clean_name_patch(self, name_str: str) -> str:
    """
    Converts agent names containing spaces, symbols (like '&'), or Unicode characters
    into an ASCII/word-safe identifier required by ADK internal naming rules.
    """
    import re
    clean = re.sub(r"[^\w]", "_", name_str).strip("_")
    return clean if clean else "resolved_gcp_agent"


AgentRegistry._clean_name = _clean_name_patch


# ==============================================================================
# Configuration Defaults (matching agent_gateway/build_agent/deploy_agent.py)
# ==============================================================================
PROJECT_ID = os.environ.get("PROJECT_ID", "ai-hangsik")
LOCATION = os.environ.get("LOCATION", "global")
TARGET_DISPLAY_NAME = os.environ.get("TARGET_DISPLAY_NAME", "Google Search & Analysis Agent")
DEFAULT_QUERY = os.environ.get(
    "DEFAULT_QUERY",
    "Google의 최근 발표된 Gemini AI 최신 모델 및 핵심 기능 요약해줘."
)


async def main(query: str = DEFAULT_QUERY):
    print("=========================================================================")
    print(" 🌐 ADK Client Agent - Calling Agent Gateway (A2A Gateway)")
    print("=========================================================================\n")

    # Step 1: Initialize Agent Registry client & find target agent
    print(f"1. Initializing Agent Registry client (Project: {PROJECT_ID}, Location: {LOCATION})...")
    registry = AgentRegistry(project_id=PROJECT_ID, location=LOCATION)

    print(f"   Searching for deployed agent with Display Name: '{TARGET_DISPLAY_NAME}'...")
    try:
        agents_list = registry.list_agents().get("agents", [])
    except Exception as e:
        print(f"❌ Error listing agents from GCP Agent Registry: {e}")
        print("💡 Hint: Ensure your GCP credentials have 'Vertex AI User/Administrator' permissions")
        print("   and run: gcloud auth application-default login --scopes=\"https://www.googleapis.com/auth/cloud-platform\"")
        return

    agent_resource = next((a["name"] for a in agents_list if a.get("displayName") == TARGET_DISPLAY_NAME), None)

    if not agent_resource:
        print(f"❌ Error: Could not find an agent with display name '{TARGET_DISPLAY_NAME}' in Agent Registry.")
        print("💡 Hint: Please ensure the agent has been deployed via 'agent_gateway/build_agent/deploy.sh'.")
        return

    print(f"   🎯 Found Agent Resource in Registry: {agent_resource}\n")

    # Step 2: Load and refresh ADC credentials for Bearer Token auth
    print("2. Loading and refreshing Google Cloud credentials (ADC)...")
    try:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(google.auth.transport.requests.Request())
    except Exception as e:
        print(f"❌ Error loading GCP credentials: {e}")
        print("💡 Hint: Run 'gcloud auth application-default login --scopes=\"https://www.googleapis.com/auth/cloud-platform\"'")
        return

    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json"
    }
    if getattr(credentials, "quota_project_id", None):
        headers["x-goog-user-project"] = credentials.quota_project_id

    # Step 3: Connect to remote A2A Agent & run streaming session
    print("3. Connecting to Remote Agent via Agent-to-Agent (A2A) Gateway...")
    async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(120.0)) as client:
        try:
            remote_agent = registry.get_remote_a2a_agent(
                agent_name=agent_resource,
                httpx_client=client
            )

            runner = InMemoryRunner(agent=remote_agent)
            runner.auto_create_session = True

            message = types.Content(role="user", parts=[types.Part.from_text(text=query)])

            print(f"\n💬 Sending User Query via A2A Gateway: '{query}'\n")
            print("=========================================================================")
            print(" 🎯 Streaming Response from Remote Agent")
            print("=========================================================================\n")

            async for event in runner.run_async(
                user_id="ingress_client_user",
                session_id="ingress_client_session",
                new_message=message
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            print(part.text, end="", flush=True)

            print("\n\n=========================================================================")
            print(" ✅ Stream completed successfully.")
            print("=========================================================================\n")

        except Exception as e:
            print(f"\n❌ Error during streaming from remote A2A agent: {e}")


if __name__ == "__main__":
    user_query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY
    asyncio.run(main(user_query))
