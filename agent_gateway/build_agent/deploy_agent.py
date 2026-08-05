#!/usr/bin/env python3
"""
🤖 ADK Search Agent Deployment (Agent Gateway)
================================================================================
1. Load ADK agent from agent_gateway.build_agent.agent (root_agent)
2. Deploy the ADK agent to Vertex AI Agent Engine
"""

import os
import sys
import google.auth
import google.auth.transport.requests
import httpx
import vertexai
from vertexai import agent_engines

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent_gateway.build_agent.agent import root_agent, a2a_app

PROJECT_ID = os.environ.get("PROJECT_ID", "ai-hangsik")
LOCATION = os.environ.get("LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET", "gs://ai-hangsik-adk-staging")
DISPLAY_NAME = os.environ.get("DISPLAY_NAME", "Search_Agent-0805")
DESCRIPTION = os.environ.get("DESCRIPTION", "ADK agent that searches and analyzes user requests using Google Search.")


def step1_get_adk_agent():
    """Step 1: agent_gateway/build_agent/agent.py에서 준비된 ADK 에이전트 및 A2A 래퍼를 로드합니다."""
    print("=========================================================================")
    print(" 🛠️  Step 1: ADK Agent 및 A2A Protocol 래퍼 로드 (agent_gateway/build_agent/agent.py)")
    print("=========================================================================")
    print(f"✅ ADK Agent 로드 완료: {root_agent.name}")
    print(f"   - Model: {root_agent.model}")
    print(f"   - Tools: {[t.__class__.__name__ for t in root_agent.tools]}")
    print(f"   - A2A Compliance: Enabled ({a2a_app.__class__.__name__})")
    return root_agent


def step2_create_agent_engine(adk_agent):
    """Step 2: Vertex AI Agent Engine을 생성하고 ADK Agent를 배포합니다."""
    print("\n=========================================================================")
    print(" 🚀 Step 2: Vertex AI Agent Engine 생성 및 ADK Agent 배포")
    print("=========================================================================")

    print(f"Vertex AI SDK 초기화 (Project: {PROJECT_ID}, Location: {LOCATION}, Staging Bucket: {STAGING_BUCKET})...")
    vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

    # 기존에 동일한 Display Name으로 배포된 Agent Engine을 교체(삭제)합니다.
    print(f"기존 배포된 Agent Engine ('{DISPLAY_NAME}') 확인 및 교체 준비 중...")
    try:
        for engine in agent_engines.list():
            if getattr(engine, "display_name", "") == DISPLAY_NAME:
                old_res = getattr(engine, "resource_name", str(engine))
                print(f"⚠️ 기존 Agent Engine 발견 -> 교체를 위해 삭제 진행: {old_res}")
                try:
                    engine.delete(force=True)
                    print("   ✅ 기존 Agent Engine 삭제 완료.")
                except Exception as del_err:
                    print(f"   ⚠️ 기존 Agent Engine 삭제 중 경고: {del_err}")
    except Exception as list_err:
        print(f"   ⚠️ 기존 Agent Engine 목록 조회 경고: {list_err}")

    requirements = [
        "google-cloud-aiplatform[agent-engines]>=1.70.0",
        "cloudpickle>=3.0.0",
        "google-adk[agent-identity,a2a]>=1.31.0",
        "google-genai>=1.0.0",
        "httpx>=0.20.0"
    ]

    print("Vertex AI Agent Engine 배포 진행 중 (원격 아티팩트 빌드)...")
    remote_agent_engine = agent_engines.create(
        agent_engine=adk_agent,
        display_name=DISPLAY_NAME,
        description=DESCRIPTION,
        requirements=requirements
    )

    resource_name = getattr(remote_agent_engine, "resource_name", str(remote_agent_engine))
    print(f"✅ Agent Engine 배포 완료!")
    print(f"   - Resource Name: {resource_name}")
    return remote_agent_engine, resource_name


def step3_register_in_agent_registry(resource_name):
    """Step 3: Update Agent Registry service entry with the new deployed Agent Engine resource URL."""
    print("\n=========================================================================")
    print(" 📋 Step 3: GCP Agent Registry A2A 서비스 Target URL 갱신")
    print("=========================================================================")

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())

    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
        "x-goog-user-project": PROJECT_ID
    }

    agent_url = f"https://{LOCATION}-aiplatform.googleapis.com/v1/{resource_name}"
    payload = {
        "displayName": DISPLAY_NAME,
        "description": DESCRIPTION,
        "agentSpec": {
            "type": "A2A_AGENT_CARD",
            "content": {
                "name": DISPLAY_NAME,
                "description": DESCRIPTION,
                "version": "1.0.0",
                "protocolVersion": "0.3.0",
                "url": agent_url,
                "defaultInputModes": ["text/plain"],
                "defaultOutputModes": ["application/json"],
                "capabilities": {},
                "skills": [
                    {
                        "id": "google_search",
                        "name": "Google Search Integration",
                        "description": "Performs Google searches to retrieve highly accurate, real-time web results for grounding.",
                        "tags": ["search", "google-search", "grounding", "web-search"]
                    }
                ]
            }
        }
    }

    url = f"https://agentregistry.googleapis.com/v1/projects/{PROJECT_ID}/locations/global/services"

    try:
        resp = httpx.get(url, headers=headers)
        if resp.status_code == 200:
            existing = resp.json().get("services", [])
            matched = next((s for s in existing if s.get("displayName") in (DISPLAY_NAME, "search_agent_0805")), None)
            if matched:
                print(f"기존 Agent Registry 서비스 발견 ('{matched.get('name')}') -> 신규 URL로 갱신 중: {agent_url}")
                patch_url = f"https://agentregistry.googleapis.com/v1/{matched['name']}?updateMask=displayName,description,agentSpec"
                res = httpx.patch(patch_url, json=payload, headers=headers)
                if res.status_code in (200, 201, 202):
                    print(f"✅ Agent Registry Target URL 갱신 완료!")
                    return matched
    except Exception as e:
        print(f"⚠️ Agent Registry 조회/갱신 중 경고: {e}")

    try:
        service_id = "google-search-analysis-agent"
        post_url = f"{url}?serviceId={service_id}"
        res = httpx.post(post_url, json=payload, headers=headers)
        if res.status_code in (200, 201, 202):
            print(f"✅ GCP Agent Registry에 신규 서비스 등록 완료!")
    except Exception as e:
        print(f"⚠️ Agent Registry 신규 등록 오류: {e}")


def main():
    adk_agent = step1_get_adk_agent()
    remote_engine, resource_name = step2_create_agent_engine(adk_agent)
    step3_register_in_agent_registry(resource_name)
    print("\n🎉 Vertex AI Agent Engine 배포 및 Agent Registry 갱신이 완료되었습니다!")


if __name__ == "__main__":
    main()
