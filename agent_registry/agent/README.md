# 🤖 No-Code 에이전트 연동 가이드 (GCP Agent Registry Client)

이 디렉토리는 Google Cloud Agent Registry에 정식 등록되어 호스팅되는 No-Code 에이전트(예: Vertex AI Agent Engine 기반 대화형 에이전트 "역사와 과학을 말해주는 에이전트")를 탐색하고, 구글의 보안 에이전트 게이트웨이(A2A) 인증망을 통해 연동 및 비동기 스트리밍 방식으로 호출하는 핵심 클라이언트 기술 가이드를 포함하고 있습니다.

---

## 🏗️ 전체 연동 아키텍처 개요 (Connection Architecture)

```text
[로컬 클라이언트 (agent.py)]
            │
            │ 1. list_agents() 요청 (ADC Credentials 탑재)
            ▼
   [ GCP Agent Registry ] (디스커버리 서비스)
            │
            │ 2. "역사와 과학을 말해주는 에이전트" 리소스 식별 경로 탐색
            ▼
[ Agent-to-Agent (A2A) Gateway ] (A2A 인증 및 터널링)
            │
            │ 3. Secure Session 형성 & 실시간 추론 스트리밍 이벤트 전달
            ▼
[로컬 클라이언트 (agent.py)] -> (터미널 콘솔 화면에 즉시 flush 출력)
```

---

## 📂 파일 요약 (Files)

*   **`agent.py`**: GCP Agent Registry에서 특정 한글 이름의 No-Code 에이전트 리소스 ID를 동적으로 탐색하고, 클라우드 권한 자격 증명 기반으로 보안 게이트웨이를 경유하여 실시간 세션을 형성, 비동기 스트리밍 응답을 수집 및 모니터링하는 완성형 검증 스크립트입니다. (한글 이름 오류 극복을 위한 **Monkeypatch 패치 솔루션** 탑재)

---

## 🛠️ 개발자를 위한 사전 요구사항 (Prerequisites)

이 에이전트 연동 모듈을 구동하기 위해서는 로컬 환경에 아래의 구글 클라우드 보안 환경 설정이 반드시 수행되어 있어야 합니다.

### 1. Google Cloud CLI (gcloud) 로그인 및 프로젝트 바인딩
개발자 컴퓨터의 터미널에 gcloud CLI가 설치되어 있어야 하며, GCP AI 프로젝트가 바인딩되어야 합니다.
```bash
gcloud auth login
gcloud config set project ai-hangsik
```

### 2. 에이전트 호출용 특수 권한 범위 (Scopes) 적용 ADC 구성
노코드 에이전트 연동을 위한 보안 게이트웨이는 매우 엄격한 사용자 토큰을 요구합니다. 
단순히 `gcloud auth application-default login`만 수행하면 `cloud-platform` 권한이 누락되어 연결 과정에서 **403 Forbidden 및 권한 차단 예외**가 발생하므로, 반드시 아래와 같이 스코프 범위를 지정하여 토큰을 다시 활성화해 주십시오:
```bash
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform"
```

---

## 🚀 실행 방법 (How to Run)

프로젝트 루트 디렉토리(`/Users/hangsik/Documents/Antigravity/agentplatform`)에서 아래 명령어를 실행합니다.

```bash
# 가상환경 활성화 상태에서 실행
python3 agent_registry/agent/agent.py
```

### 🎯 실행 프로세스 및 터미널 출력 로그 시뮬레이션:
```text
=========================================================================
 🤖 GCP Agent Registry - 등록된 No-Code Agent 연동 및 실행
=========================================================================

1. Agent Registry 클라이언트 초기화 중...
등록된 에이전트 목록 조회 및 대상 에이전트 검색 중...
🎯 검색 완료! 에이전트 리소스 경로: projects/721521243942/locations/global/agents/agentregistry-00000000-0000-0000-xxxx-xxxxxxxxxxxx

2. Google 서비스 계정 애플리케이션 기본 사용자 인증 정보(ADC) 로드 및 갱신 중...
3. A2A 게이트웨이를 통해 Remote Agent에 연결하는 중...
💬 에이전트 대상 사용자 질의 전송: '조선시대 최고의 과학 발명품은?'

--- 스트리밍 답변 시작 ---
조선시대 최고의 과학 발명품으로 손꼽히는 것 중 하나는 세종대왕 시대에 장영실 등이 발명한 '측우기'입니다. 
측우기는 세계 최초의 강우량 측정기로서, 실용적이고 체계적인 농업 국가 형성에 지대한 영향을 끼쳤습니다. 
또한 해시계인 '앙부일구', 물시계인 '자격루' 역시 고도의 천문 기상학 기술력을 증명해 주는 명작들입니다... (실시간으로 글자가 빠르게 flush 인쇄됩니다)
--- 스트리밍 답변 종료 ---
```

---

## 💡 주요 기술적 솔루션 설명 (Technical Deep-Dive)

### 한글 에이전트 표시 이름(Display Name) 정규식 예외 완벽 해결
구글 ADK 파이썬 패키지의 내부 검증 메소드인 `AgentRegistry._clean_name` 함수는 인자로 전달받은 에이전트 이름을 영문, 숫자, 언더바 수준으로만 매칭하도록 가혹하게 설계되어 있습니다. 
만약 우리가 호출하려는 에이전트 이름이 한글 자모로 이루어져 있을 경우(`역사와 과학을 말해주는 에이전트`), 정규식 패턴 분석 실패에 따른 에러를 터트려 스크립트 실행이 중단됩니다.

이를 위해 `agent.py` 소스 상단부에서는 아래와 같은 **Monkeypatch 솔루션**을 동적 바인딩해 두고 있습니다:
```python
def _clean_name_patch(self, name_str: str) -> str:
    import re
    # \w는 정규식에서 한국어 유니코드를 포함한 단어 문자 전체를 지원합니다.
    clean = re.sub(r"[^\w]", "_", name_str).strip("_")
    return clean if clean else "resolved_gcp_agent"

# ADK 라이브러리의 클래스 원본 메소드를 런타임에 커스텀 패치 함수로 덮어씌움 (Monkeypatch)
AgentRegistry._clean_name = _clean_name_patch
```
이로 인해 SDK 소스 코드를 해킹하여 직접 수정하지 않고도 한국어 에이전트를 안정적이고 유연하게 로드할 수 있게 됩니다.
