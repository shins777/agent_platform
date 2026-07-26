import asyncio
import google.auth
import google.auth.transport.requests
import httpx
from google.adk.integrations.agent_registry.agent_registry import AgentRegistry
from google.adk.agents import LlmAgent, Context
from google.adk.runners import InMemoryRunner
from google.genai import types

# [Critical ADK/mTLS Patch] mTLS 대체 방지용 패치
# 로컬 개발/디버깅 환경(예: macOS Python 환경)에서 구글 보안 SDK는 기본적으로 상호 TLS(mTLS) 연결을 활성화하려 시도합니다.
# 하지만 로컬 시스템의 SSL 인증서 누락 등으로 'SSLCertVerificationError' 에러가 발생하는 경우가 많으므로,
# `google.auth.transport.mtls.should_use_client_cert` 함수가 항상 False를 반환하도록 재정의하여 
# 일반 보안 TLS 채널(us-central1-aiplatform.googleapis.com)을 사용하도록 유도합니다.
import google.auth.transport.mtls as auth_mtls
auth_mtls.should_use_client_cert = lambda: False

# GCP 설정 정보
PROJECT_ID = "721521243942"  # GCP 프로젝트 번호/ID
LOCATION = "global"          # 에이전트 레지스트리 리전 설정

# 레지스트리로부터 동적으로 획득하고자 하는 타겟 MCP 서버의 표시 이름 (displayName)
TARGET_MCP_SERVER_DISPLAY_NAME = "Capital Finder Server"

async def main():
    print("=========================================================================")
    print(" 🛠️  GCP Agent Registry - 등록된 MCP Server 연동 및 에이전트 실행")
    print("=========================================================================\n")

    # 1. 에이전트 레지스트리 클라이언트 초기화
    print("1. Agent Registry 클라이언트 초기화 중...")
    registry = AgentRegistry(project_id=PROJECT_ID, location=LOCATION)

    # 2. 에이전트 레지스트리에 등록된 모든 MCP 서버 목록 검색 및 타겟 서버 조회
    print("Agent Registry 내부의 등록된 MCP 서버 검색 중...")
    mcp_response = registry.list_mcp_servers()
    registered_servers = mcp_response.get("mcpServers", [])

    if not registered_servers:
        print("❌ GCP Agent Registry에서 등록된 MCP 서버를 찾을 수 없습니다.")
        return

    print(f"\n📂 검색 완료! 총 {len(registered_servers)}개의 등록된 MCP 서버 발견:")
    for srv in registered_servers:
        print(f" - Display Name: {srv.get('displayName')} | Resource ID: {srv.get('mcpServerId')} | Path: {srv.get('name')}")
    print()

    # 표시 이름을 바탕으로 타겟 MCP 서버 리소스를 필터링합니다.
    target_server = next(
        (srv for srv in registered_servers if srv.get("displayName") == TARGET_MCP_SERVER_DISPLAY_NAME), 
        None
    )

    # 대상을 찾지 못한 경우 목록의 첫 번째 서버로 대체합니다.
    if not target_server:
        target_server = registered_servers[0]
        print(f"⚠️ 타겟 MCP 서버 '{TARGET_MCP_SERVER_DISPLAY_NAME}'를 검색하지 못했습니다. 첫 번째 서버로 자동 대체합니다.")
    
    mcp_server_path = target_server["name"]
    print(f"🎯 선택된 MCP 서버: '{target_server.get('displayName')}'")
    print(f"   리소스 식별 경로: {mcp_server_path}\n")

    # 3. Google Cloud Platform (cloud-platform) 권한 범위 적용 토큰 갱신
    print("3. 구글 서비스 계정 OAuth 보안 토큰 권한 갱신 중...")
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(google.auth.transport.requests.Request())
    
    # 4. Agent Registry를 통한 비동기 McpToolset 결합 객체 빌드
    # 이 과정에서 내부적으로 GCP 레지스트리 정보를 해독하여, Cloud Run 상의 Streamable HTTP 엔드포인트에 
    # 자동으로 인증 헤더를 보강하고 실시간 JSON-RPC 통신 게이트웨이를 연결합니다.
    print("4. 원격 MCP 서버와 게이트웨이 보안 연결 수립 및 McpToolset 빌드 중...")
    toolset = registry.get_mcp_toolset(mcp_server_name=mcp_server_path)

    # 5. MCP 서버가 노출 중인 도구 목록 획득 및 진단
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

    # 6. Gemini LLM 에이전트와 수집한 MCP 도구셋 통합 후 실행
    # LlmAgent 생성자에 수집 완료된 toolset 객체를 그대로 입력하면, LLM이 필요 시 자동으로 해당 도구를 스스로 호출합니다.
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
        
        # 에이전트 비동기 세션 실행용 InMemoryRunner 선언
        runner = InMemoryRunner(agent=agent)
        runner.auto_create_session = True
        
        # MCP 도구 호출을 유도하는 질문 설정
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

    # 7. 세션 클린업 및 소켓 연결 안전하게 제거
    print("\nMCP Toolset 네트워크 세션 해제 및 연결 종료 중...")
    await toolset.close()
    print("Done!\n")

if __name__ == "__main__":
    asyncio.run(main())
