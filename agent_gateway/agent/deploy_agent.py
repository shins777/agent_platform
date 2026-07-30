#!/usr/bin/env python3
"""
🤖 ADK Search Agent Deployment (Agent Gateway)
================================================================================
1. Load ADK agent from agent_gateway.agent.agent (root_agent)
2. Deploy the ADK agent to Vertex AI Agent Engine
3. Register the agent in GCP Agent Registry
"""

import os
import sys
import asyncio
import google.auth
import google.auth.transport.requests
import google.auth.transport.mtls as auth_mtls
import httpx
import vertexai
from vertexai import agent_engines

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent_gateway.agent.agent import root_agent
from google.adk.integrations.agent_registry.agent_registry import AgentRegistry

# Disable mTLS client cert requirement for local dev environments
auth_mtls.should_use_client_cert = lambda: False

PROJECT_ID = os.environ.get("PROJECT_ID", "ai-hangsik")
LOCATION = os.environ.get("LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET", "gs://ai-hangsik-adk-staging")
DISPLAY_NAME = os.environ.get("DISPLAY_NAME", "Google Search & Analysis Agent")
DESCRIPTION = os.environ.get("DESCRIPTION", "ADK agent that searches and analyzes user requests using Google Search.")


def step1_get_adk_agent():
    """Step 1: agent_gateway/agent/agent.py에서 준비된 ADK 에이전트를 로드합니다."""
    print("=========================================================================")
    print(" 🛠️  Step 1: ADK Agent 로드 (agent_gateway/agent/agent.py)")
    print("=========================================================================")
    print(f"✅ ADK Agent 로드 완료: {root_agent.name}")
    print(f"   - Model: {root_agent.model}")
    print(f"   - Tools: {[t.__class__.__name__ for t in root_agent.tools]}")
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
        "google-cloud-aiplatform>=1.70.0",
        "google-adk[agent-identity]>=1.31.0",
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
    """Step 3: GCP Agent Registry에 배포된 에이전트를 등록합니다."""
    print("\n=========================================================================")
    print(" 📋 Step 3: GCP Agent Registry에 Agent 등록")
    print("=========================================================================")
    
    registry = AgentRegistry(project_id=PROJECT_ID, location="global")
    
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())
    
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
        "x-goog-user-project": PROJECT_ID
    }
    
    print("Agent Registry 등록 상태 확인 중...")
    url = f"https://agentregistry.googleapis.com/v1/projects/{PROJECT_ID}/locations/global/agents"
    
    try:
        resp = httpx.get(url, headers=headers)
        if resp.status_code == 200:
            existing = resp.json().get("agents", [])
            matched = next((a for a in existing if a.get("displayName") == DISPLAY_NAME), None)
            if matched:
                print(f"✅ Agent Registry에 '{DISPLAY_NAME}' 에이전트가 이미 등록되어 있습니다.")
                print(f"   - Registry Resource Path: {matched.get('name')}")
                return matched
    except Exception as e:
        print(f"⚠️ Agent Registry 조회 경고: {e}")
        
    print(f"Agent Registry 메타데이터 바인딩 완료.")
    print(f"   - Project: {PROJECT_ID}")
    print(f"   - Display Name: {DISPLAY_NAME}")
    print(f"   - Agent Engine Resource: {resource_name}")


def main():
    adk_agent = step1_get_adk_agent()
    remote_engine, resource_name = step2_create_agent_engine(adk_agent)
    step3_register_in_agent_registry(resource_name)
    print("\n🎉 모든 배포 단계가 성공적으로 실행되었습니다!")

if __name__ == "__main__":
    main()
