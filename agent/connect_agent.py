import asyncio
import google.auth
import google.auth.transport.requests
import httpx
from google.adk.integrations.agent_registry.agent_registry import AgentRegistry
from google.adk.runners import InMemoryRunner
from google.genai import types

# [Critical ADK Monkeypatch] 한글 에이전트 이름 처리용 패치
# ADK 내부의 정규식 검증 과정에서 에이전트 이름에 한글이 포함되어 있을 경우 발생하는 정규식 오류를 방지하기 위해 
# AgentRegistry._clean_name 메서드를 오버라이드(원숭이 패치)하여 안전한 리소스 이름으로 정제합니다.
def _clean_name_patch(self, name_str: str) -> str:
    import re
    # 알파벳, 숫자, 언더바(_) 외의 특수문자나 한글 캐릭터를 모두 언더바로 치환합니다.
    clean = re.sub(r"[^\w]", "_", name_str).strip("_")
    return clean if clean else "resolved_gcp_agent"

# 원본 메서드를 커스텀 패치 함수로 동적 교체합니다.
AgentRegistry._clean_name = _clean_name_patch

# GCP 및 에이전트 설정 정보
PROJECT_ID = "721521243942"  # 구글 클라우드 프로젝트 번호/ID
LOCATION = "global"          # 에이전트 레지스트리가 등록된 GCP 리전 (글로벌 에이전트 등록의 경우 'global' 사용)
TARGET_DISPLAY_NAME = "역사와 과학을 말해주는 에이전트"  # 에이전트 레지스트리에 등록된 타겟 에이전트의 표시 이름

async def main():
    print("=========================================================================")
    print(" 🤖 GCP Agent Registry - 등록된 No-Code Agent 연동 및 실행")
    print("=========================================================================\n")

    # 1. 에이전트 레지스트리 클라이언트 초기화 및 등록된 에이전트 자동 검색
    # 지정한 GCP 프로젝트 및 위치에서 등록된 전체 에이전트 목록을 가져온 후, TARGET_DISPLAY_NAME과 일치하는 에이전트를 검색합니다.
    print("1. Agent Registry 클라이언트 초기화 중...")
    registry = AgentRegistry(project_id=PROJECT_ID, location=LOCATION)
    
    print("등록된 에이전트 목록 조회 및 대상 에이전트 검색 중...")
    agents_list = registry.list_agents().get("agents", [])
    agent_resource = next((a["name"] for a in agents_list if a.get("displayName") == TARGET_DISPLAY_NAME), None)
    
    if not agent_resource:
        print(f"❌ 에이전트 레지스트리에서 '{TARGET_DISPLAY_NAME}' 에이전트를 찾을 수 없습니다.")
        return
        
    print(f"🎯 검색 완료! 에이전트 리소스 경로: {agent_resource}\n")

    # 2. 보안 Gateway 인증을 위한 GCP 서비스 계정 OAuth 토큰 생성 및 갱신
    # 클라우드 플랫폼 범위(cloud-platform) 권한을 획득하여 에이전트 게이트웨이에 안전하게 요청을 보낼 준비를 합니다.
    print("2. Google 서비스 계정 애플리케이션 기본 사용자 인증 정보(ADC) 로드 및 갱신 중...")
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(google.auth.transport.requests.Request())
    
    # HTTP 요청 헤더에 Bearer 토큰 및 Quota 프로젝트 정보를 설정합니다.
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json"
    }
    if getattr(credentials, "quota_project_id", None):
        headers["x-goog-user-project"] = credentials.quota_project_id

    # 3. Agent-to-Agent (A2A) 게이트웨이를 사용하여 Gemini Enterprise 에이전트 연결 및 스트리밍 실행
    # httpx.AsyncClient 비동기 컨텍스트 내에서 에이전트를 원격 에이전트 객체(RemoteA2aAgent)로 해석합니다.
    print("3. A2A 게이트웨이를 통해 Remote Agent에 연결하는 중...")
    async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(120.0)) as client:
        remote_agent = registry.get_remote_a2a_agent(
            agent_name=agent_resource,
            httpx_client=client
        )
        
        # InMemoryRunner를 생성하여 메모리 상에서 원격 에이전트 세션을 안전하게 수행합니다.
        runner = InMemoryRunner(agent=remote_agent)
        runner.auto_create_session = True  # 세션 자동 생성 옵션 활성화
        
        # 실행할 사용자 쿼리 작성 및 메시지 구조 생성
        query = "조선시대 최고의 과학 발명품은?"
        message = types.Content(role="user", parts=[types.Part.from_text(text=query)])
        
        print(f"💬 에이전트 대상 사용자 질의 전송: '{query}'\n")
        print("--- 스트리밍 답변 시작 ---")
        
        # 비동기 실행 루프를 돌면서 원격 에이전트의 답변 이벤트를 실시간으로 화면에 출력합니다.
        async for event in runner.run_async(user_id="user_123", session_id="session_123", new_message=message):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text, end="", flush=True)
                        
        print("\n--- 스트리밍 답변 종료 ---\n")

if __name__ == "__main__":
    asyncio.run(main())
