"""
🛠️ Model Context Protocol (MCP) Server & Vertex AI Gemini ADK Agent 결합 구동 모듈
================================================================================

본 스크립트는 구글 에이전트 레지스트리(Agent Registry)에 사전 연동되어 관리 중인 원격 MCP 서버 
인스턴스를 자동으로 디스커버리(수집)하고, 이에 소속된 실행용 기능들을 `McpToolset` 도구 모음 객체로 
추출하여 대형 언어 모델(Gemini 2.5 Flash) 기반의 ADK `LlmAgent`와 완벽하게 융합 구동하는 예제입니다.

1. 아키텍처 흐름도 (Architectural Workflow)
------------------------------------------
[로컬 에이전트 클라이언트 (LlmAgent)]
       │
       │  1. list_mcp_servers() 및 get_mcp_toolset() 요청 발생
       ▼
[GCP Agent Registry (인프라)]
       │
       │  2. 특정 등록 서버 ("Capital Finder Server")의 메타데이터 및 도구 정보 로드
       ▼
[Cloud Run (FastMCP 구동망)] ───► [Capital Finder API Server] (실제 연동 장비)
       │                                     │
       │  3. 제공 중인 도구 명세(get_capital) 및 스키마 회신  │
       ▼                                     │
[McpToolset 객체 빌드 (클라이언트)]            │
       │                                     │
       │  4. Gemini 추론 중 도구 필요 판단 발생  │
       ▼                                     │
[Gemini 2.5-Flash (Vertex AI)] <─────────────┘ 5. 도구 실행 및 결과를 기반으로 최종 답변 스트리밍

2. 핵심 기술 개념 (Core Technology Concepts)
-------------------------------------------
- Model Context Protocol (MCP):
  Anthropic사에서 최초 제안하고 업계 표준으로 자리매김 중인 개방형 프로토콜로, LLM과 외부 데이터 소스,
  로컬 및 원격 도구들 간의 연결 상태를 JSON-RPC 기반 스키마로 표준화하여 통일해 주는 통신 규약입니다.
- McpToolset:
  ADK SDK 내부에 포함된 어댑터 모듈로, 에이전트 레지스트리를 경유해 수신한 원격 MCP 서버 도구들을 
  Gemini 모델이 이해하고 스스로 분기 결정할 수 있도록 표준 Vertex AI Tool 선언 스키마로 번역하여 바인딩해 줍니다.
- LlmAgent:
  ADK 내부의 핵심 추론 에이전트 클래스로, 구글의 대형 언어 모델(Gemini)에 전용 프롬프트 지시어(Instruction)와 
  수집한 외부 도구들(Tools)을 함께 공급하여 대화 상태 및 도구 자동 호출 루프를 내부에서 직접 조율합니다.
- mTLS 대체 패치 (mTLS SSLCertVerificationError Patch):
  로컬 개발 환경(특히 macOS Python 환경)에서 구글 보안 SDK는 통신 보안을 높이기 위해 상호 TLS(mTLS) 연결을 
  기본적으로 활성화하려고 시도합니다.
  하지만 개발자 로컬 머신에 클라이언트 인증서 키체인 구조가 제대로 설치/세팅되지 않았을 경우, 
  통신 초기 단계에서 치명적인 `SSLCertVerificationError`가 발생하며 연결이 무조건 끊어지게 됩니다.
  이를 우회 및 극복하기 위해 `google.auth.transport.mtls.should_use_client_cert` 함수가 항상 `False`를 
  반환하도록 가로채는 영리한 솔루션(Monkeypatch)을 상단에 내장했습니다.
  이 조치는 mTLS를 비활성화하는 대신 일반 보안 TLS 채널과 구글 OAuth 토큰(Bearer)만을 사용하여 
  보안성을 손실하지 않으면서도 로컬 연결 오류를 원천 차단해 줍니다.

3. 개발자 핵심 문제 해결 가이드 (Troubleshooting & Solutions)
--------------------------------------------------------------
- 도구 목록 조회 오류 (get_tools() 실패):
  원격 Cloud Run 서비스가 비활성화 상태거나 Cold-Start 상태일 때 최초 목록 조회가 일시적으로 타임아웃 될 수 있습니다.
  본 예제에서는 이 예외를 안전하게 `try-except` 처리하고 trace를 인쇄하여 개발자가 서버 상태를 쉽게 검진하도록 설계했습니다.
- 모델 연동 실패:
  Vertex AI Gemini API 구동 시, 지정한 프로젝트 번호(`PROJECT_ID`)의 결제 상태가 활성화되어 있지 않거나 
  us-central1 리전에 해당 Gemini 모델 사용 권한이 승인되지 않았을 때 오류가 발생하므로 GCP IAM 권한을 확인해야 합니다.
"""

import asyncio
import google.auth
import google.auth.transport.requests
import httpx
from google.adk.integrations.agent_registry.agent_registry import AgentRegistry
from google.adk.agents import LlmAgent, Context
from google.adk.runners import InMemoryRunner
from google.genai import types

# ==============================================================================
# [필수 해결책] ADK/mTLS 로컬 인증서 검증 회피 및 보안 패치 (Monkeypatch)
# ==============================================================================
# 로컬 개발 환경에서 불필요한 SSL 클라이언트 인증서(mTLS) 호출에 의한 오동작 및 
# 'SSLCertVerificationError'를 완전히 해결하고 일반 보안 TLS 채널을 활용하도록 유도합니다.
import google.auth.transport.mtls as auth_mtls
auth_mtls.should_use_client_cert = lambda: False

# GCP 및 에이전트 설정 정보
PROJECT_ID = "721521243942"  # 사용 중인 GCP 프로젝트 ID 또는 번호
LOCATION = "global"          # 에이전트 레지스트리가 운영되는 리전

# 레지스트리로부터 동적으로 획득하고자 하는 타겟 MCP 서버의 표시 이름 (displayName)
TARGET_MCP_SERVER_DISPLAY_NAME = "Capital Finder Server"

async def main():
    print("=========================================================================")
    print(" 🛠️  GCP Agent Registry - 등록된 MCP Server 연동 및 에이전트 실행")
    print("=========================================================================\n")

    # --------------------------------------------------------------------------
    # 1단계: Agent Registry 클라이언트 초기화 및 MCP 디스커버리 서비스 가동
    # --------------------------------------------------------------------------
    print("1. Agent Registry 클라이언트 초기화 중...")
    registry = AgentRegistry(project_id=PROJECT_ID, location=LOCATION)

    # --------------------------------------------------------------------------
    # 2단계: 에이전트 레지스트리에 배포 및 등록된 모든 원격 MCP 서버 목록 검색
    # --------------------------------------------------------------------------
    print("Agent Registry 내부의 등록된 MCP 서버 검색 중...")
    try:
        mcp_response = registry.list_mcp_servers()
        registered_servers = mcp_response.get("mcpServers", [])
    except Exception as e:
        print(f"❌ MCP 서버 목록을 레지스트리로부터 가져오지 못했습니다: {e}")
        print("💡 해결책: 'gcloud auth application-default login'을 사용하여 활성 클라우드 프로젝트 인증을 수행했는지 확인해 주십시오.")
        return

    if not registered_servers:
        print("❌ GCP Agent Registry에서 등록된 MCP 서버를 찾을 수 없습니다.")
        print("💡 해결책: GCP 콘솔에서 MCP 서버 및 Cloud Run 서비스 배포 상태를 점검하십시오.")
        return

    print(f"\n📂 검색 완료! 총 {len(registered_servers)}개의 등록된 MCP 서버 발견:")
    for srv in registered_servers:
        print(f" - Display Name: {srv.get('displayName')} | Resource ID: {srv.get('mcpServerId')} | Path: {srv.get('name')}")
    print()

    # 우리가 연동하고자 하는 TARGET_MCP_SERVER_DISPLAY_NAME ("Capital Finder Server")을 필터링해 냅니다.
    target_server = next(
        (srv for srv in registered_servers if srv.get("displayName") == TARGET_MCP_SERVER_DISPLAY_NAME), 
        None
    )

    # 만약 이름으로 찾지 못했다면 오동작 방지를 위해 첫 번째 서버 리소스를 기본 대체 타겟으로 선정합니다.
    if not target_server:
        target_server = registered_servers[0]
        print(f"⚠️ 타겟 MCP 서버 '{TARGET_MCP_SERVER_DISPLAY_NAME}'를 검색하지 못했습니다. 첫 번째 서버로 자동 대체합니다.")
    
    mcp_server_path = target_server["name"]
    print(f"🎯 선택된 MCP 서버: '{target_server.get('displayName')}'")
    print(f"   리소스 식별 경로: {mcp_server_path}\n")

    # --------------------------------------------------------------------------
    # 3단계: 구글 서비스 계정 OAuth 2.0 보안 자격 증명 획득
    # --------------------------------------------------------------------------
    # 원격 Cloud Run으로 향하는 JSON-RPC 엔드포인트 연동 게이트웨이 인증을 통과하기 위하여
    # 필수적인 cloud-platform 보안 토큰 갱신 작업을 진행합니다.
    print("3. 구글 서비스 계정 OAuth 보안 토큰 권한 갱신 중...")
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(google.auth.transport.requests.Request())
    
    # --------------------------------------------------------------------------
    # 4단계: Registry를 통한 비동기 McpToolset 결합 및 도구 인벤토리 추출
    # --------------------------------------------------------------------------
    # ADK의 AgentRegistry가 내부적으로 게이트웨이 핸들러를 바인딩하여 
    # 원격 리소스를 내 로컬 머신의 도구 모음(McpToolset) 형태로 완벽히 패키징해 줍니다.
    print("4. 원격 MCP 서버와 게이트웨이 보안 연결 수립 및 McpToolset 빌드 중...")
    toolset = registry.get_mcp_toolset(mcp_server_name=mcp_server_path)

    # --------------------------------------------------------------------------
    # 5단계: 수집된 원격 도구(Tools) 실시간 진단 및 메타데이터 모니터링
    # --------------------------------------------------------------------------
    # 원격 서버가 외부에 오픈하고 있는 도구 기능들의 이름 및 설명을 출력하여 정상 작동 상태인지 분석합니다.
    print("MCP 서버가 제공하는 도구 목록 조회 중...")
    try:
        tools = await toolset.get_tools()
        if not tools:
            print("⚠️ 선택한 MCP 서버에서 사용 가능한 도구 목록이 노출되지 않았습니다.")
        else:
            print(f"\n🔧 수집 완료! 총 {len(tools)}개의 도구가 노출 중입니다:")
            for index, tool in enumerate(tools, 1):
                print(f"  [{index}] 도구 이름(Tool Name):  {tool.name}")
                print(f"      도구 설명: {tool.description}")
                print(f"      긴 실행 여부(Is Long Run): {tool.is_long_running}")
                print("      ---------------------------------------------------------")
    except Exception as e:
        import traceback
        print("❌ MCP 서버로부터 도구 목록 조회 실패:")
        traceback.print_exc()
        await toolset.close()
        return

    # --------------------------------------------------------------------------
    # 6단계: Gemini LLM 에이전트와 수집한 MCP 도구셋 통합 및 비동기 추론 구동
    # --------------------------------------------------------------------------
    # LlmAgent 생성 시 tools 파라미터 리스트에 우리가 빌드한 `toolset`을 전달합니다.
    # LLM은 질의문을 평가한 뒤 도구가 필요한 타이밍에 이 Toolset을 호출하여 국가 수도 정보를 획득합니다.
    print("\n5. 수집된 MCP 도구셋을 활용하여 Vertex AI Gemini LLM 에이전트 결합 중...")
    try:
        # 모델명은 구글 서비스 계정 자격 증명(ADC)과 정상 매칭되도록 Vertex AI 전용 정규화 리소스 형식을 채택합니다.
        agent = LlmAgent(
            model=f"projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/gemini-2.5-flash",
            name="mcp_assistant",
            instruction="You are a helpful assistant. You have access to registered tools from the GCP Agent Registry.",
            tools=[toolset]
        )
        print(f"✅ Gemini LLM 에이전트 '{agent.name}' 초기화 완료!")
        
        # 비동기 실행 루프 구동을 담당하는 InMemoryRunner 구성
        runner = InMemoryRunner(agent=agent)
        runner.auto_create_session = True
        
        # MCP 서버의 get_capital 도구 호출을 명백히 유도하는 영어 질문 배치
        query = "What is the capital city of South Korea?"
        print(f"\n💬 에이전트 전송 질문: '{query}'\n")
        print("--- 스트리밍 답변 시작 ---")
        
        message = types.Content(role="user", parts=[types.Part.from_text(text=query)])
        async for event in runner.run_async(user_id="user_123", session_id="session_123", new_message=message):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text, end="", flush=True)
        print("\n--- 스트리밍 답변 완료 ---\n")
        
    except Exception as e:
        print(f"⚠️ Gemini 에이전트 비동기 실행 과정에서 오류 발생: {e}")
        print("💡 해결책: GCP Vertex AI 플랫폼 활성화 상황 및 us-central1 리전에 대한 접근 권한(IAM)을 재조정하십시오.")

    # --------------------------------------------------------------------------
    # 7단계: 네트워크 리소스 반환 및 세션 클린업
    # --------------------------------------------------------------------------
    # 열려 있는 백엔드 소켓 포트 및 HTTP 게이트웨이 파이프라인을 안전하게 닫아 메모리 릭(Leak)을 방지합니다.
    print("\nMCP Toolset 네트워크 세션 해제 및 연결 종료 중...")
    await toolset.close()
    print("Done!\n")

if __name__ == "__main__":
    asyncio.run(main())
