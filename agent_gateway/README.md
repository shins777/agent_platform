# 🤖 GCP Agent Gateway & ADK Search Agent 연동 개발자 가이드

본 문서는 Google Cloud Platform(GCP)의 **Agent Development Kit (ADK)**, **Vertex AI Agent Engine (Reasoning Engine)**, 그리고 **GCP Agent Registry**를 통합하여 실시간 Google Search 기반 검색 및 분석 에이전트를 개발, 배포, 검증하기 위한 상세 개발 가이드서입니다.

---

## 1. 아키텍처 및 시스템 개요 (System Architecture)

```text
                                [ GCP AGENT REGISTRY (Discovery & Binding) ]
                                                     │
                                                     │ (에이전트 메타데이터 및 리소스 주소 매핑)
                                                     ▼
 [ 개발자 로컬 환경 (CLI / SDK) ]  ◄── (A2A Gateway) ──►  [ Vertex AI Agent Engine ]
        │                                                              │
        │ 1. deploy.sh 실행 (3단계 배포 파이프라인)                          │ 2. 실시간 질의 전송 (test_agent.py)
        ▼                                                              ▼
 [ deploy_agent.py (자동 배포) ]                             [ Google Search Grounding ]
   ├─ Step 1: ADK Agent (gemini-2.5-flash + GoogleSearchTool)      │
   ├─ Step 2: 기존 인스턴스 자동 삭제 후 Agent Engine 배포                  │ (웹 실시간 검색 및 출처 그라운딩)
   └─ Step 3: Agent Registry에 리소스 식별 경로 등록                       ▼
                                                     [ 최종 응답 (Final Consolidated Response) ]
                                                       ├─ 요약 답변 (Markdown text)
                                                       ├─ 검색 질의어 목록 (web_search_queries)
                                                       └─ 출처 도메인 및 URL (sources)
```

### 핵심 인프라 구성 요소
1. **Google ADK (`google.adk.agents.Agent`)**:
   - 구글의 대화형 에이전트 개발 프레임워크로, 프롬프트 지시어(Instruction), LLM 모델(`gemini-2.5-flash`), 그리고 확장 도구(`GoogleSearchTool`)를 단일 파이썬 객체로 추상화합니다.
2. **Vertex AI Agent Engine (Reasoning Engine)**:
   - 작성된 ADK 에이전트를 Google Cloud의 완전 관리형 서버리스 런타임에 배포합니다. 로컬 에이전트 인스턴스를 `cloudpickle`로 직렬화하여 Cloud Storage 버킷(`gs://...`)에 스테이징한 후, Cloud Build를 통해 컨테이너화하여 고성능 비동기 스트리밍 세션 서버를 자동 호스팅합니다.
3. **GCP Agent Registry**:
   - 기업 조직 내에 배포된 여러 에이전트, API, MCP(Model Context Protocol) 서버들을 단일 포털에서 식별(Discovery)하고, A2A (Agent-to-Agent) 보안 게이트웨이와 바인딩할 수 있도록 관리하는 글로벌 레지스트리 서비스입니다.

---

## 2. 디렉토리 구조 및 구성 모듈 분석 (Directory Deep-Dive)

```text
agent_gateway/
├── README.md                  # 본 개발자 가이드 문서
└── agent/                     # ADK Agent 및 Agent Engine 연동 핵심 소스코드
    ├── __init__.py            # Python 패키지 인식 파일
    ├── .env                   # 환경변수 기본 설정 파일 (GCP 프로젝트 및 리전 정보)
    ├── agent.py               # Google Search 도구가 탑재된 ADK LlmAgent 정의 모듈
    ├── deploy.sh              # 어느 디렉토리에서나 실행 가능한 bash 배포 자동화 파이프라인
    ├── deploy_agent.py        # 3단계(생성 -> 배포/교체 -> 레지스트리 등록) 파이썬 자동화 스크립트
    └── test_agent.py          # 배포된 원격 Agent Engine을 Non-Streaming 방식으로 검증하는 테스트 스크립트
```

### 모듈별 상세 기능
*   **`agent/agent.py`**:
    *   `gemini-2.5-flash` 모델 기반으로 `root_agent` 객체를 인스턴스화합니다.
    *   `google.adk.tools.google_search` 도구를 주입하여 사용자의 질의가 입력되면 자체적인 판단 하에 구글 검색엔진을 활용하여 최신 웹 정보를 수집·종합하도록 프롬프트 지시어(`instruction`)를 구성했습니다.
*   **`agent/deploy_agent.py`**:
    *   **Step 1 (Agent 로드)**: `agent.py`에 정의된 `root_agent`를 로드합니다.
    *   **Step 2 (Agent Engine 배포 및 무중단 교체)**:
        *   표시 이름(`DISPLAY_NAME`: `"Google Search & Analysis Agent"`)으로 등록된 **기존 Reasoning Engine 인스턴스가 존재할 경우 자동 감지하여 삭제(`engine.delete(force=True)`)**함으로써 불필요한 클라우드 리소스 및 과금 누수를 원천 차단합니다.
        *   `vertexai.agent_engines.create(...)`를 호출하여 클라우드에 최신 에이전트 인스턴스를 새롭게 빌드 및 배포합니다.
    *   **Step 3 (Agent Registry 바인딩)**:
        *   배포된 Agent Engine의 리소스 이름(`projects/.../reasoningEngines/...`)을 GCP Agent Registry에 매핑하고 1.0.0 버전의 에이전트 메타데이터를 갱신합니다.
*   **`agent/deploy.sh`**:
    *   실행 환경의 현재 경로를 자동 계산하여, 프로젝트 루트(`../../`)에서 호출하든 폴더 내부에서 호출하든 오류 없이 `deploy_agent.py`를 실행하도록 구현된 셸 스크립트입니다.
*   **`agent/test_agent.py`**:
    *   스트리밍 단편 조각을 터미널에 흘려보내는 대신, **Non-Streaming(최종 응답 수집) 모드**인 `get_final_response()` 함수를 통해 전체 스트림(`stream_query`) 완료 후 **1) 최종 텍스트 본문**, **2) Google Search 질의어 키워드**, **3) 검색 출처 도메인 및 URL**을 깔끔한 형태로 요약 출력합니다.

---

## 3. 개발자 사전 준비 사항 (Prerequisites & GCP IAM Configuration)

> [!IMPORTANT]
> 본 모듈을 정상 배포하고 테스트하려면 로컬 개발 환경에 Google Cloud SDK(`gcloud`) 인증 및 권한이 올바르게 설정되어 있어야 합니다.

### 1. gcloud CLI 프로젝트 연결 및 계정 로그인
```bash
gcloud auth login
gcloud config set project ai-hangsik
```

### 2. Application Default Credentials (ADC) 및 OAuth 스코프 부여
Vertex AI Agent Engine 및 Agent Registry API는 높은 수준의 OAuth 스코프 권한을 요구합니다. 기본 ADC 로그인 시 `cloud-platform` 스코프가 누락되어 `403 Forbidden` 에러가 발생할 수 있으므로 아래 명령을 통해 권한 스코프가 명시된 인증 토큰을 발급받아야 합니다.
```bash
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform"
```

### 3. 필수 GCP IAM 권한 역할
*   **`Vertex AI Administrator`** 또는 **`Vertex AI User`**: Reasoning Engine 리소스 생성, 조회, 삭제 및 추론 API 호출 권한.
*   **`Storage Admin`** 또는 **`Storage Object Admin`**: 스테이징 버킷(`gs://ai-hangsik-adk-staging`) 내 직렬화 파일 및 요구사항 파일 업로드/읽기 권한.
*   **`Cloud Build Service Account`**: 원격 컨테이너 빌드 및 Artifact Registry 이미지 생성 권한.

---

## 4. 실행 및 배포 지침 (Step-by-Step Usage Guide)

### 1) 환경 변수 커스텀 (옵션)
필요에 따라 아래 환경 변수를 셸에 덮어써서 타겟 프로젝트나 리전을 유연하게 변경할 수 있습니다. 기본값은 아래와 같습니다:
*   `PROJECT_ID`: `"ai-hangsik"`
*   `LOCATION`: `"us-central1"` (Vertex AI Agent Engine 기본 서비스 리전)
*   `STAGING_BUCKET`: `"gs://ai-hangsik-adk-staging"`
*   `DISPLAY_NAME`: `"Google Search & Analysis Agent"`

### 2) 배포 자동화 스크립트 실행
프로젝트 루트 폴더 또는 `agent_gateway/agent/` 디렉토리 안에서 배포 스크립트를 실행합니다.

```bash
# 디렉토리 내부에서 실행 시
cd agent_gateway/agent
./deploy.sh

# 또는 프로젝트 루트에서 직접 실행 시
./agent_gateway/agent/deploy.sh
```

**실행 프로세스 요약:**
1. gcloud CLI 설정 프로젝트를 `ai-hangsik`으로 설정합니다.
2. `deploy_agent.py`를 호출하여 로컬 ADK 에이전트를 초기화합니다.
3. 동일한 이름의 구 에이전트 인스턴스가 존재할 경우 안전하게 제거합니다.
4. 원격 Storage 버킷에 패키지를 업로드하고 Reasoning Engine 컨테이너를 빌드·배포합니다.
5. GCP Agent Registry 메타데이터에 리소스 경로를 바인딩합니다.

---

## 5. 실시간 질의 및 Grounding 검증 테스트 (How to Test)

배포가 완료되면 `test_agent.py` 스크립트를 사용하여 원격 Vertex AI Agent Engine을 직접 호출하고 Google Search Grounding 동작을 검증할 수 있습니다.

```bash
uv run python3 agent_gateway/agent/test_agent.py
```

### 예상 터미널 출력 결과 (Non-Streaming 모드)
```text
=========================================================================
 🧪 Vertex AI Agent Engine 연동 검증 (Final Response 모드)
=========================================================================

1. Vertex AI SDK 초기화 (Project: ai-hangsik, Location: us-central1)...
2. 배포된 AgentEngine('Google Search & Analysis Agent') 인스턴스 검색 중...
   🎯 선택된 Agent Engine Resource: projects/721521243942/locations/us-central1/reasoningEngines/3615354211069329408
3. 대화 세션 (Session) 생성 중...
   Session ID: 8242140028839395328

💬 사용자 질의 전송: 'Google의 최근 발표된 Gemini AI 최신 모델 및 핵심 기능 요약해줘.'
⏳ 전체 답변이 생성될 때까지 대기 중... (Non-Streaming)

=========================================================================
 🎯 최종 답변 (Final Response)
=========================================================================

Google은 최근 Gemini AI 모델 제품군에에 대한 여러 업데이트를 발표하며...
(중략: Gemini 3.6 Flash, 3.5 Flash-Lite, 3.5 Flash Cyber, 3.1 Pro 및 멀티모달 에이전트 핵심 기능 요약 본문)

---------------------------------------------------------
🔍 Google Search 질의어 (6건):
  - Google Gemini AI 최신 모델 발표
  - Google Gemini AI 최신 모델 핵심 기능
  - Gemini 1.5 Pro 기능
  - Google Gemini Advanced
...

---------------------------------------------------------
🌐 검색 근거 출처 (Sources, 20건):
  [1] aitimes.com: https://...
  [2] hada.io: https://...
  [3] blog.google: https://...
=========================================================================
```

---

## 6. 개발자 핵심 트러블슈팅 및 아키텍처 FAQ (Engineering Troubleshooting)

> [!TIP]
> 배포 및 실행 과정에서 발생할 수 있는 주요 기술적 오류와 해결 원리를 정리했습니다.

### Q1. `Pickle load failed: Missing module 'vertexai'` 오류가 발생하는 경우
*   **증상**: Cloud Build 배포는 성공하지만, Reasoning Engine 인스턴스 기동 도중 로그에서 `ModuleNotFoundError: No module named 'vertexai'`가 출력되며 `InvalidArgument: 400 Reasoning Engine failed to start` 오류 발생.
*   **원인**: 로컬에서 `cloudpickle`로 직렬화된 ADK 에이전트 객체가 원격 클라우드 컨테이너 환경에서 역직렬화될 때 `vertexai` 및 `google-cloud-aiplatform` 패키지 클래스 참조가 필요하지만 원격 컨테이너 의존성에 누락된 경우입니다.
*   **해결 방법**: `deploy_agent.py` 내 `requirements` 리스트에 반드시 `"google-cloud-aiplatform>=1.70.0"`을 명시하여 Cloud Build가 컨테이너 내부에 해당 모듈을 사전에 설치하도록 해야 합니다. 본 프로젝트의 `deploy_agent.py`는 이를 이미 자동화하고 있습니다.

### Q2. `remote_agent.query()` 호출 시 `AttributeError: 'AgentEngine' object has no attribute 'query'` 오류 발생
*   **원인**: Vertex AI Agent Engine(`AdkApp` 래퍼)은 내부적으로 Server-Sent Events (SSE) 및 스트리밍 RPC 프로토콜을 사용하므로 동기식 단건 `query()` 메소드가 존재하지 않습니다.
*   **해결 방법**:
    *   표준 스트리밍 호출: `remote_agent.stream_query(user_id=..., session_id=..., message=...)` 제너레이터를 반복문으로 호출하여 이벤트 청크를 수신합니다.
    *   Non-Streaming(완결 텍스트) 사용: 본 프로젝트의 `test_agent.py`에 구현된 `get_final_response()` 함수처럼, `stream_query()`의 반환 청크들을 리스트로 모두 수집한 뒤 `content['parts'][0]['text']` 및 `grounding_metadata`를 종합하여 단일 응답 객체로 가공하면 됩니다.

### Q3. macOS 로컬 개발 시 `SSLCertVerificationError` (mTLS 통신 차단) 오류
*   **원인**: Google Auth SDK가 상호 TLS(mTLS) 연결을 기본 시도할 때 로컬 OS 키체인 클라이언트 인증서가 구성되지 않아 통신 핸드셰이크 단계에서 실패하는 현상입니다.
*   **해결 방법**: 모든 스크립트 최상단에 다음 원숭이 패치(Monkeypatch)를 주입하여 mTLS 대신 일반 안전 TLS 소켓과 Bearer 토큰 인증을 사용하도록 제어합니다:
    ```python
    import google.auth.transport.mtls as auth_mtls
    auth_mtls.should_use_client_cert = lambda: False
    ```

### Q4. 에이전트 배포 시 무한정 새로운 엔진 인스턴스가 생성되는 문제 (리소스 낭비 방지)
*   **원인**: `vertexai.agent_engines.create(...)`는 호출할 때마다 새로운 고유 ID(`reasoningEngines/xxx`)를 가진 인스턴스를 클라우드에 생성합니다.
*   **해결 방법**: `deploy_agent.py`의 `step2_create_agent_engine` 함수에 구현된 것처럼, 새 에이전트를 생성하기 직전에 `agent_engines.list()`를 조회하여 표시 이름(`DISPLAY_NAME`)이 일치하는 기존 엔진이 존재하면 `engine.delete(force=True)`를 수행해 릴리즈하도록 설계했습니다.
