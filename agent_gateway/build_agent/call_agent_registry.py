#!/usr/bin/env python3
"""
🌐 Search and Call Agent using ADK AgentRegistry Client API
================================================================================
1. Uses ADK's `AgentRegistry` Client SDK (not direct REST API) to search for the agent.
2. Retrieves agent metadata and target URL using `registry.list_agents()` and `registry.get_agent_info()`.
3. Invokes the deployed agent and receives the response.
"""

import os
import sys
import re
import vertexai
from vertexai import agent_engines
from google.adk.integrations.agent_registry.agent_registry import AgentRegistry

# ==============================================================================
# Monkeypatch ADK SDK _clean_name for non-alphanumeric or hyphenated display names
# ==============================================================================
def _clean_name_patch(self, name_str: str) -> str:
    clean = re.sub(r"[^\w]", "_", name_str).strip("_")
    return clean if clean else "resolved_gcp_agent"

AgentRegistry._clean_name = _clean_name_patch


PROJECT_ID = os.environ.get("PROJECT_ID", "ai-hangsik")
LOCATION = os.environ.get("LOCATION", "global")
DISPLAY_NAME = os.environ.get("DISPLAY_NAME", "Search_Agent-0805")
DEFAULT_QUERY = os.environ.get(
    "DEFAULT_QUERY",
    "Google의 최근 발표된 Gemini AI 최신 모델 및 핵심 기능 요약해줘."
)


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY

    print("=========================================================================")
    print(f" 🤖 ADK AgentRegistry Client API - 에이전트 검색 및 호출 ('{DISPLAY_NAME}')")
    print("=========================================================================\n")

    # 1. ADK AgentRegistry Client SDK 초기화
    print(f"1. ADK AgentRegistry SDK 초기화 (Project: {PROJECT_ID}, Location: {LOCATION})...")
    registry = AgentRegistry(project_id=PROJECT_ID, location=LOCATION)

    # 2. AgentRegistry Client API로 등록된 에이전트 목록 검색
    print(f"2. AgentRegistry.list_agents() 호출하여 '{DISPLAY_NAME}' 탐색 중...")
    try:
        agents_list = registry.list_agents().get("agents", [])
    except Exception as e:
        print(f"❌ registry.list_agents() 실패: {e}")
        return

    matched_agent = next((a for a in agents_list if a.get("displayName") in (DISPLAY_NAME, "search_agent_0805")), None)

    if not matched_agent:
        print(f"❌ Error: Agent Registry에서 '{DISPLAY_NAME}' 에이전트를 찾을 수 없습니다.")
        return

    agent_resource_name = matched_agent.get("name")
    print(f"   🎯 발견된 Agent Resource Name: {agent_resource_name}")

    # 3. AgentRegistry.get_agent_info()로 상세 메타데이터 및 URL 조율
    print(f"3. AgentRegistry.get_agent_info()로 상세 메타데이터 조회 중...")
    agent_info = registry.get_agent_info(agent_resource_name)

    card_content = agent_info.get("card", {}).get("content", {})
    protocols = agent_info.get("protocols", [])

    target_url = card_content.get("url")
    if not target_url and protocols:
        interfaces = protocols[0].get("interfaces", [])
        if interfaces:
            target_url = interfaces[0].get("url")

    print(f"   ✅ 메타데이터 수집 완료!")
    print(f"      - Display Name : {agent_info.get('displayName')}")
    print(f"      - Description  : {agent_info.get('description')}")
    print(f"      - Target URL   : {target_url}\n")

    if not target_url:
        print("❌ Error: Target Agent URL을 확인할 수 없습니다.")
        return

    # 4. Target Agent URL에서 Reasoning Engine resource path 파싱 및 호출
    if "reasoningEngines/" in target_url:
        resource_path = target_url.split("/v1/")[-1]
    else:
        resource_path = target_url

    print(f"4. Vertex AI Agent Engine에 연결 중 ({resource_path})...")
    vertexai.init(project=PROJECT_ID, location="us-central1")
    target_engine = vertexai.agent_engines.get(resource_path)

    session = target_engine.create_session(user_id="registry_sdk_user")
    session_id = session.get("id") if isinstance(session, dict) else getattr(session, "id", "session_sdk")

    print(f"\n💬 사용자 질의: '{query}'")
    print("⏳ Agent Engine 응답 생성 중... (Non-Streaming)\n")

    responses = list(
        target_engine.stream_query(
            user_id="registry_sdk_user",
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
    print(" 🎯 AgentRegistry SDK를 통한 최종 답변 (Final Response)")
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


if __name__ == "__main__":
    main()
