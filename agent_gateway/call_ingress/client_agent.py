#!/usr/bin/env python3
"""
🤖 ADK Ingress Client Agent (call_ingress)
================================================================================
1. Creates an ADK Client Agent to call an agent ('Search_Agent-0805') registered in GCP Agent Registry.
2. Discovers and retrieves the agent metadata from GCP Agent Registry using AgentRegistry SDK.
3. Calls the agent ('Search_Agent-0805') through Agent Gateway via Ingress integration.
"""

import os
import sys
import asyncio
import re
import google.auth
import google.auth.transport.requests
import google.auth.transport.mtls as auth_mtls
import vertexai
from vertexai import agent_engines
from google.adk.agents import Agent
from google.adk.integrations.agent_registry.agent_registry import AgentRegistry

# Disable mTLS client cert requirement for local dev environments
auth_mtls.should_use_client_cert = lambda: False


# ==============================================================================
# [Essential Monkeypatch] ADK SDK _clean_name patch for hyphenated display names
# ==============================================================================
def _clean_name_patch(self, name_str: str) -> str:
    clean = re.sub(r"[^\w]", "_", name_str).strip("_")
    return clean if clean else "resolved_gcp_agent"


AgentRegistry._clean_name = _clean_name_patch


# ==============================================================================
# Configuration Defaults
# ==============================================================================
PROJECT_ID = os.environ.get("PROJECT_ID", "ai-hangsik")
LOCATION = os.environ.get("LOCATION", "global")
TARGET_DISPLAY_NAME = os.environ.get("TARGET_DISPLAY_NAME", "Search_Agent-0805")
DEFAULT_QUERY = os.environ.get(
    "DEFAULT_QUERY",
    "Google의 최근 발표된 Gemini AI 최신 모델 및 핵심 기능 요약해줘."
)


def create_client_agent():
    """Step 1: ADK Ingress Client Agent를 생성합니다."""
    client_agent = Agent(
        model="gemini-2.5-flash",
        name="ingress_caller_agent",
        description="Ingress client agent that routes requests to GCP Agent Registry agents.",
        instruction="Route and forward user requests to the target registered agent."
    )
    return client_agent


def get_agent_from_registry():
    """Step 2: GCP Agent Registry에서 등록된 'Search_Agent-0805' 에이전트를 검색 및 수집합니다."""
    print(f"2. Agent Registry에서 '{TARGET_DISPLAY_NAME}' 에이전트 검색 중...")
    registry = AgentRegistry(project_id=PROJECT_ID, location=LOCATION)

    try:
        agents_list = registry.list_agents().get("agents", [])
    except Exception as e:
        print(f"❌ registry.list_agents() 실패: {e}")
        return None, None

    matched_agent = next(
        (a for a in agents_list if a.get("displayName") in (TARGET_DISPLAY_NAME, "search_agent_0805")),
        None
    )

    if not matched_agent:
        print(f"❌ Agent Registry에서 '{TARGET_DISPLAY_NAME}' 에이전트를 찾을 수 없습니다.")
        return None, None

    agent_resource_name = matched_agent.get("name")
    print(f"   🎯 발견된 Agent Resource Name: {agent_resource_name}")

    # AgentRegistry.get_agent_info()로 메타데이터 및 Target URL 파싱
    agent_info = registry.get_agent_info(agent_resource_name)
    card_content = agent_info.get("card", {}).get("content", {})
    protocols = agent_info.get("protocols", [])

    target_url = card_content.get("url")
    if not target_url and protocols:
        interfaces = protocols[0].get("interfaces", [])
        if interfaces:
            target_url = interfaces[0].get("url")

    print(f"   ✅ 메타데이터 수집 완료:")
    print(f"      - Display Name : {agent_info.get('displayName')}")
    print(f"      - Target URL   : {target_url}")

    return agent_info, target_url


def call_agent_via_ingress(target_url: str, query: str):
    """Step 3: Agent Gateway Ingress 방식을 통해 target agent ('Search_Agent-0805')를 호출합니다."""
    print("\n3. Agent Gateway Ingress를 통해 'Search_Agent-0805' 호출 중...")

    if "reasoningEngines/" in target_url:
        resource_path = target_url.split("/v1/")[-1]
    else:
        resource_path = target_url

    print(f"   - Target Engine Path: {resource_path}")
    vertexai.init(project=PROJECT_ID, location="us-central1")
    target_engine = vertexai.agent_engines.get(resource_path)

    session = target_engine.create_session(user_id="ingress_client_user")
    session_id = session.get("id") if isinstance(session, dict) else getattr(session, "id", "ingress_session")

    print(f"\n💬 사용자 질의 전송: '{query}'")
    print("⏳ Agent Engine 응답 생성 중... (Non-Streaming)\n")

    responses = list(
        target_engine.stream_query(
            user_id="ingress_client_user",
            session_id=session_id,
            message=query
        )
    )

    final_text_parts = []
    search_queries = []
    sources = []

    for resp in responses:
        if isinstance(resp, dict):
            content = resp.get("content", {})
            parts = content.get("parts", [])
            for p in parts:
                if isinstance(p, dict) and p.get("text"):
                    final_text_parts.append(p["text"])
                elif hasattr(p, "text") and p.text:
                    final_text_parts.append(p.text)

            g_meta = resp.get("grounding_metadata", {})
            if g_meta:
                queries = g_meta.get("web_search_queries", [])
                if queries:
                    search_queries.extend(queries)
                for chunk in g_meta.get("grounding_chunks", []):
                    web = chunk.get("web", {}) if isinstance(chunk, dict) else getattr(chunk, "web", {})
                    uri = web.get("uri") if isinstance(web, dict) else getattr(web, "uri", None)
                    domain = web.get("domain", "source") if isinstance(web, dict) else getattr(web, "domain", "source")
                    if uri and uri not in sources:
                        sources.append(f"{domain}: {uri}")
        else:
            final_text_parts.append(str(resp))

    final_text = "\n".join(final_text_parts) if final_text_parts else "응답을 받지 못했습니다."

    print("=========================================================================")
    print(" 🎯 Agent Gateway Ingress를 통한 최종 답변 (Final Response)")
    print("=========================================================================\n")
    print(final_text)

    if search_queries:
        print("\n---------------------------------------------------------")
        print(f"🔍 Google Search 질의어 ({len(search_queries)}건):")
        for q in list(dict.fromkeys(search_queries)):
            print(f"  - {q}")

    if sources:
        print("\n---------------------------------------------------------")
        print(f"🌐 검색 근거 출처 (Sources, {len(sources)}건):")
        for idx, src in enumerate(list(dict.fromkeys(sources))[:5], 1):
            print(f"  [{idx}] {src}")

    print("\n=========================================================================\n")


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY

    print("=========================================================================")
    print(f" 🤖 ADK Ingress Client Agent ('{TARGET_DISPLAY_NAME}')")
    print("=========================================================================\n")

    # 1. Create ADK Client Agent
    client_agent = create_client_agent()
    print(f"1. ADK Ingress Client Agent 생성 완료: {client_agent.name}")

    # 2. Get Agent from Agent Registry
    agent_info, target_url = get_agent_from_registry()
    if not target_url:
        print("❌ Target Agent URL을 가져올 수 없어 중단합니다.")
        return

    # 3. Call Agent through Agent Gateway Ingress
    call_agent_via_ingress(target_url, query)


if __name__ == "__main__":
    main()
