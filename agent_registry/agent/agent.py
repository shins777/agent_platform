"""
🤖 GCP Agent Registry No-Code Agent 연동 모듈 (No-Code Agent Client)
================================================================================

본 스크립트는 Google Cloud Platform (GCP)의 Agent Registry에 정식 등록되어 관리되는 
"No-Code Agent"(예: Vertex AI Agent Engine 기반 대화형 어시스턴트)를 자동으로 탐색하고,
보안 인증 게이트웨이(A2A)를 거쳐 실시간 스트리밍 답변을 수집하는 클라이언트 구현 예제입니다.

1. 아키텍처 흐름도 (Architectural Workflow)
------------------------------------------
[개발자 로컬 클라이언트]
       │
       │  1. Google Auth (ADC) 기반 서비스 계정 자격 증명 획득 및 OAuth Token 발급
       ▼
[GCP IAM & OAuth 2.0]
       │
       │  2. 특정 Display Name ("역사와 과학을 말해주는 에이전트")으로 에이전트 검색
       ▼
[GCP Agent Registry (디스커버리 서비스)]
       │
       │  3. 고유 리소스 식별 경로(Resource Path) 추출 및 Secure Client 바인딩
       ▼
[Agent-to-Agent (A2A) 보안 게이트웨이] ───► [실제 Vertex AI Agent Engine 에이전트]
                                                       │
                                                       │ 4. 대화 세션 생성 및 추론 수행
                                                       ▼
[터미널 콘솔 (사용자 화면)] ◄──────────────────── [Asynchronous Event Stream (UTF-8)]

2. 핵심 기술 개념 (Core Technology Concepts)
-------------------------------------------
- GCP Agent Registry: 
  엔터프라이즈 전반에 흩어져 있는 에이전트 서비스, API, Model Context Protocol(MCP) 서버를
  단일 포털에서 등록하고, 보안 및 검색을 단일화하여 접근할 수 있게 돕는 GCP의 핵심 관리 인프라입니다.
- ADK (Agent Development Kit):
  구글이 배포하는 파이썬 라이브러리로, 클라우드 자격 증명 인증부터 세션 및 실행 러너 추상화까지
  에이전트 연동의 복잡한 로직을 최소한의 코드로 구현할 수 있게 돕는 고수준 개발 도구입니다.
- A2A (Agent-to-Agent) 프로토콜:
  조직 내부 혹은 상호 다른 클라우드 테넌트 간의 에이전트들이 보안상 안전하게 상호 호출할 수 있도록
  구글의 고성능 게이트웨이가 토큰 검증, 호출 한도, 암호화 터널링을 처리해주는 기술입니다.
- InMemoryRunner:
  클라이언트의 메모리 컨텍스트 내부에서 단일/다중 대화 세션 상태(Session State)를 저장 및 추적하고,
  서버와의 비동기 통신을 담당하며, 실시간 텍스트 조각(Chunk)을 스트리밍 제너레이터 형태로 전달하는 러너 객체입니다.

3. 개발자 핵심 문제 해결 가이드 (Troubleshooting & Solutions)
--------------------------------------------------------------
- 한국어 에이전트 이름 에러 (Monkeypatch 적용 배경):
  ADK 내부 소스 코드는 리소스 이름을 영문, 숫자, 일부 특수문자로만 검증하려는 엄격한 정규식 필터가 적용되어 있습니다.
  이로 인해 한국어 이름(예: '역사와 과학을 말해주는 에이전트')을 가진 에이전트를 Registry에서 조회 시 
  ADK 내부 라이브러리 레벨에서 정규식 매칭 실패 예외(Assertion/ValueError)가 발생합니다.
  이 문제를 해결하기 위해 본 코드 상단에서 `AgentRegistry._clean_name` 클래스 메소드를 동적으로 재정의하여 
  한글 문자열을 온전히 보존하면서 안전하게 가공하도록 수정했습니다(런타임 원숭이 패치, Monkeypatch).
- GCP 403 Forbidden 권한 부족 에러:
  기본 인증인 Application Default Credentials (ADC)에 구글 클라우드 전체 권한 범위(`cloud-platform`)가
  누락되어 있을 경우 호출 권한 오류가 발생합니다. 이를 해결하려면 터미널에서 반드시 아래 명령어 스코프를 추가하여 
  다시 로그인해야 합니다.
  * 실행 명령어: gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform"
"""

import asyncio
import google.auth
import google.auth.transport.requests
import httpx
from google.adk.integrations.agent_registry.agent_registry import AgentRegistry
from google.adk.runners import InMemoryRunner
from google.genai import types

# ==============================================================================
# [필수 해결책] ADK SDK 한글 지원 원숭이 패치 (Monkeypatch)
# ==============================================================================
# ADK 내부 라이브러리의 `_clean_name` 로직이 가진 문자열 검증 한계를 런타임에 보완하여,
# 한글 명칭의 노코드 에이전트도 정상적으로 로딩 및 바인딩될 수 있도록 재정의합니다.
def _clean_name_patch(self, name_str: str) -> str:
    r"""
    한글 등 다국어 문자가 포함된 에이전트 이름을 리소스 식별용 안전 문자열로 변환합니다.
    \w 패턴은 Python 3에서 유니코드 문자(한글 포함)를 기본적으로 매칭하므로 안전하게 치환됩니다.
    """
    import re
    # 알파벳, 숫자, 언더바(_), 그리고 한국어를 포함한 단어 캐릭터가 아닌 모든 특수기호를 언더바로 변환합니다.
    clean = re.sub(r"[^\w]", "_", name_str).strip("_")
    return clean if clean else "resolved_gcp_agent"

# 원본 클래스 메소드를 당사 패치 함수로 덮어씁니다.
AgentRegistry._clean_name = _clean_name_patch


# ==============================================================================
# GCP 프로젝트 및 레지스트리 연동 설정 정보
# ==============================================================================
# PROJECT_ID: GCP 프로젝트 번호(Project Number) 혹은 고유 ID
PROJECT_ID = "721521243942"  

# LOCATION: Agent Registry가 배포된 서비스 리전. 글로벌 에이전트의 경우 'global'로 통칭됩니다.
LOCATION = "global"          

# TARGET_DISPLAY_NAME: 구글 클라우드 콘솔에 표시되는 에이전트 고유 이름
TARGET_DISPLAY_NAME = "역사와 과학을 말해주는 에이전트"  


async def main():
    print("=========================================================================")
    print(" 🤖 GCP Agent Registry - 등록된 No-Code Agent 연동 및 실행")
    print("=========================================================================\n")

    # --------------------------------------------------------------------------
    # 1단계: Agent Registry 클라이언트 인스턴스화 및 타겟 검색
    # --------------------------------------------------------------------------
    # 지정한 GCP 프로젝트와 리전을 기반으로 검색 클라이언트를 생성한 뒤,
    # 프로젝트 내 등록된 에이전트 중 표시 이름(displayName)이 일치하는 에이전트의 내부 경로를 찾아냅니다.
    print("1. Agent Registry 클라이언트 초기화 중...")
    registry = AgentRegistry(project_id=PROJECT_ID, location=LOCATION)
    
    print("등록된 에이전트 목록 조회 및 대상 에이전트 검색 중...")
    try:
        agents_list = registry.list_agents().get("agents", [])
    except Exception as e:
        print(f"❌ GCP Agent Registry로부터 목록을 조회하지 못했습니다: {e}")
        print("💡 원인 분석 및 해결책:")
        print("   - 사용 중인 GCP 계정이 해당 프로젝트의 'Agent Vacancy' 혹은 'Vertex AI Administrator' 권한을 갖고 있는지 확인하십시오.")
        print("   - API 호출 권한(ADC)이 터미널 세션에 로드되었는지 확인하십시오.")
        return

    # 표시 이름 기반 탐색
    agent_resource = next((a["name"] for a in agents_list if a.get("displayName") == TARGET_DISPLAY_NAME), None)
    
    if not agent_resource:
        print(f"❌ 에이전트 레지스트리에서 '{TARGET_DISPLAY_NAME}' 에이전트를 찾을 수 없습니다.")
        print("💡 해결책: GCP Vertex AI 콘솔의 Agent Registry 탭으로 이동하여 해당 이름으로 배포된 에이전트가 정상 활성화 상태인지 확인해 주십시오.")
        return
        
    print(f"🎯 검색 완료! 에이전트 리소스 경로: {agent_resource}\n")

    # --------------------------------------------------------------------------
    # 2단계: OAuth 2.0 및 로컬 ADC 인증 보안 토큰 생성
    # --------------------------------------------------------------------------
    # A2A 게이트웨이를 경유할 때 보안 상 신원과 호출 자격을 판단하는 강력한 Bearer 토큰이 헤더에 탑재되어야 합니다.
    # 이를 위해 로컬 gcloud에 바인딩된 자격 증명을 갱신하여 고유 토큰을 주입합니다.
    print("2. Google 서비스 계정 애플리케이션 기본 사용자 인증 정보(ADC) 로드 및 갱신 중...")
    try:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(google.auth.transport.requests.Request())
    except Exception as e:
        print(f"❌ GCP 인증 자격 증명을 로드할 수 없습니다: {e}")
        print("💡 해결책: 아래 명령어를 사용하여 클라우드 관리 권한 스코프를 명시적으로 부여해 재로그인 하십시오:")
        print("   gcloud auth application-default login --scopes=\"https://www.googleapis.com/auth/cloud-platform\"")
        return
    
    # HTTP 요청 헤더 정보 설계
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json"
    }
    # 할당량(Quota) 프로젝트 지정으로 호출 비용이 올바르게 기록되도록 연동합니다.
    if getattr(credentials, "quota_project_id", None):
        headers["x-goog-user-project"] = credentials.quota_project_id

    # --------------------------------------------------------------------------
    # 3단계: HTTP 비동기 세션 연결 및 Remote 에이전트 스트리밍 질의
    # --------------------------------------------------------------------------
    # 비동기 통신 클라이언트(httpx.AsyncClient) 컨텍스트 내에서 에이전트와 통신하는 Remote 객체를 바인딩합니다.
    # InMemoryRunner를 통해 실시간 스트림 파이프라인을 구동하여 텍스트 조각들을 화면에 출력합니다.
    print("3. A2A 게이트웨이를 통해 Remote Agent에 연결하는 중...")
    async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(120.0)) as client:
        try:
            remote_agent = registry.get_remote_a2a_agent(
                agent_name=agent_resource,
                httpx_client=client
            )
            
            # ADK 실행 세션 생성
            runner = InMemoryRunner(agent=remote_agent)
            runner.auto_create_session = True  # 세션 키가 없을 경우 자동으로 생성
            
            # 사용자 입력 메시지 포맷팅 (Vertex AI 표준 양식 채택)
            query = "조선시대 최고의 과학 발명품은?"
            message = types.Content(role="user", parts=[types.Part.from_text(text=query)])
            
            print(f"💬 에이전트 대상 사용자 질의 전송: '{query}'\n")
            print("--- 스트리밍 답변 시작 ---")
            
            # 비동기 루프를 사용하여 청크가 도착할 때마다 즉각적으로 터미널 화면에 flush 출력 수행
            async for event in runner.run_async(user_id="user_123", session_id="session_123", new_message=message):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            print(part.text, end="", flush=True)
                            
            print("\n--- 스트리밍 답변 종료 ---\n")
            
        except Exception as e:
            print(f"❌ 원격 에이전트 스트리밍 실행 중 장애 발생: {e}")
            print("💡 원인 분석: 클라우드 Run 게이트웨이 타임아웃, 인스턴스 Cold-Start에 따른 레이턴시 초과, 혹은 API 트래픽 초과 오류일 수 있습니다.")

if __name__ == "__main__":
    asyncio.run(main())
