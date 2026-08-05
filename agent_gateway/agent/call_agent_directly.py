#!/usr/bin/env python3
"""
🧪 Test Script for Deployed Agent Engine (Non-Streaming / Final Response)
================================================================================
Queries the deployed Vertex AI Agent Engine and waits for the complete final response.
"""

import os
import vertexai
from vertexai import agent_engines

PROJECT_ID = os.environ.get("PROJECT_ID", "ai-hangsik")
LOCATION = os.environ.get("LOCATION", "us-central1")
DISPLAY_NAME = os.environ.get("DISPLAY_NAME", "Search_Agent-0805")


def get_final_response(engine, user_id, session_id, message):
    """스트리밍 응답들을 수집하여 최종 통합 답변 및 검색 근거(Grounding) 정보를 추출합니다."""
    # 전체 응답을 리스트로 수집하여 완료될 때까지 대기합니다 (Non-Streaming 방식)
    responses = list(
        engine.stream_query(
            user_id=user_id,
            session_id=session_id,
            message=message
        )
    )
    
    if not responses:
        return {"text": "No response received.", "search_queries": [], "sources": []}
    
    final_text_parts = []
    search_queries = []
    sources = []
    
    for resp in responses:
        # 1. 텍스트 추출
        if isinstance(resp, dict):
            content = resp.get("content", {})
            parts = content.get("parts", [])
            for p in parts:
                if isinstance(p, dict) and p.get("text"):
                    final_text_parts.append(p["text"])
                elif hasattr(p, "text") and p.text:
                    final_text_parts.append(p.text)
            
            # 2. Google Search Grounding 정보 추출
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
            
    final_text = "\n".join(final_text_parts) if final_text_parts else str(responses[-1])
    return {
        "text": final_text,
        "search_queries": list(dict.fromkeys(search_queries)),
        "sources": list(dict.fromkeys(sources)),
        "total_chunks": len(responses)
    }


def main():
    print("=========================================================================")
    print(" 🧪 Vertex AI Agent Engine 연동 검증 (Final Response 모드)")
    print("=========================================================================\n")
    
    print(f"1. Vertex AI SDK 초기화 (Project: {PROJECT_ID}, Location: {LOCATION})...")
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    
    print(f"2. 배포된 AgentEngine('{DISPLAY_NAME}') 인스턴스 검색 중...")
    target_engine = None
    for engine in agent_engines.list():
        if getattr(engine, "display_name", "") == DISPLAY_NAME:
            target_engine = engine
            break
            
    if not target_engine:
        print(f"❌ Error: Could not find an Agent Engine with display name '{DISPLAY_NAME}'")
        return

    resource_name = getattr(target_engine, "resource_name", str(target_engine))
    print(f"   🎯 선택된 Agent Engine Resource: {resource_name}")
    
    print("3. 대화 세션 (Session) 생성 중...")
    session = target_engine.create_session(user_id="user_test_final")
    session_id = session.get("id") if isinstance(session, dict) else getattr(session, "id", "session_test_final")
    print(f"   Session ID: {session_id}")
    
    query = "Google의 최근 발표된 Gemini AI 최신 모델 및 핵심 기능 요약해줘."
    print(f"\n💬 사용자 질의 전송: '{query}'")
    print("⏳ 전체 답변이 생성될 때까지 대기 중... (Non-Streaming)")
    
    try:
        result = get_final_response(
            engine=target_engine,
            user_id="user_test_final",
            session_id=session_id,
            message=query
        )
        
        print("\n=========================================================================")
        print(" 🎯 최종 답변 (Final Response)")
        print("=========================================================================\n")
        print(result["text"])
        
        if result["search_queries"]:
            print("\n---------------------------------------------------------")
            print(f"🔍 Google Search 질의어 ({len(result['search_queries'])}건):")
            for q in result["search_queries"]:
                print(f"  - {q}")
                
        if result["sources"]:
            print("\n---------------------------------------------------------")
            print(f"🌐 검색 근거 출처 (Sources, {len(result['sources'])}건):")
            for idx, src in enumerate(result["sources"][:5], 1):
                print(f"  [{idx}] {src}")
            if len(result["sources"]) > 5:
                print(f"  ... 외 {len(result['sources']) - 5}건")
        print("\n=========================================================================\n")
        
    except Exception as e:
        print(f"\n❌ Error querying Agent Engine: {e}")


if __name__ == "__main__":
    main()
