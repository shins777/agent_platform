# Google Cloud Agent Registry 및 Vertex AI Agent Engine 연동 플랫폼 개발 가이드

본 문서는 Google Cloud Agent Registry 및 Vertex AI Agent Engine의 주요 연동 규격(ADK, MCP, 직접 REST API 호출)을 검증하고 개발하기 위한 로컬 개발 환경 구성 및 실행 방법 안내서입니다.

---

## 1. 아키텍처 개요

본 프로젝트는 구글 클라우드 플랫폼의 에이전트 인프라와 외부 클라이언트를 연결하는 세 가지 기술적 연동 시나리오를 포함합니다.

```text
                                  [ GCP AGENT REGISTRY (Discovery) ]
                                                   │
                ┌──────────────────────────────────┼──────────────────────────────────┐
                │ (Scenario 1)                     │ (Scenario 2)                     │ (Scenario 3)
                ▼                                  ▼                                  ▼
      [ No-Code Agent Client ]            [ Gemini MCP Runner ]             [ Direct REST Client ]
                │                                  │                                  │
    (Agent-to-Agent Gateway)               (McpToolset & SDK)                (Direct REST HTTP POST)
                │                                  │                                  │
                ▼                                  ▼                                  ▼
     [ Remote No-Code Agent ]             [ FastMCP Cloud Run ]              [ streamAssist API ]
```

### 시나리오 1: No-Code 에이전트 연동 (ADK SDK)
*   **개요**: 구글 Vertex AI Agent Engine에 배포된 대화형 노코드 에이전트를 ADK SDK를 이용해 검색하고, Agent-to-Agent(A2A) 보안 게이트웨이를 경유하여 양방향 스트리밍 세션을 형성합니다.
*   **해결 과제**: ADK 라이브러리 내부의 `AgentRegistry._clean_name` 메소드는 ASCII 문자 검증 정규식 제한으로 인해 한글 자모가 포함된 에이전트명을 로드할 때 실행 예외(AssertionError)를 발생시킵니다. 본 프로젝트는 `re.sub(r"[^\w]", "_", name_str)` 형태의 런타임 Monkeypatch를 적용하여 한글 에이전트명을 정상 식별할 수 있도록 조치하였습니다.

### 시나리오 2: GCP Agent Registry MCP 도구 연동 (Gemini ADK Agent)
*   **개요**: 국가 수도 검색 API 기능을 처리하는 FastMCP 독립 서버를 개발하여 Cloud Run에 배포하고, 구글 에이전트 레지스트리에 등록합니다. 클라이언트 측 Gemini 2.5 Flash 모델은 ADK `McpToolset`을 통해 해당 도구 명세를 주입받아 필요 시 자동으로 구동합니다.
*   **해결 과제**: macOS 등 일부 로컬 파이썬 개발 환경에서 구글 보안 SDK 가동 시 로컬 mTLS(상호 TLS) 인증서 검증 오작동으로 인한 `SSLCertVerificationError`가 빈번히 보고됩니다. 이를 방지하기 위해 `google.auth.transport.mtls.should_use_client_cert` 탐지 기능을 `False`로 재정의하여 보안 등급 저하 없이 일반 SSL/TLS 소켓과 Bearer 토큰 인증으로 대체하도록 설계하였습니다.

### 시나리오 3: 직접 REST API 게이트웨이 호출 (streamAssist)
*   **개요**: 전용 ADK SDK를 사용하지 않고 구글 공인 세션 라이브러리(`AuthorizedSession`)를 직접 이용하여 Vertex AI Agent Engine의 로우레벨 HTTP POST `streamAssist` 엔드포인트를 호출하고 스트리밍 데이터 조각을 실시간으로 가공합니다.
*   **해결 과제**: 
    1.  **UTF-8 멀티바이트 문자 잘림 제어**: 한국어(UTF-8, 3바이트) 전송 시 네트워크 TCP 패킷 경계면에서 바이트가 분할 수신되면 즉각적인 `.decode('utf-8')` 수행 도중 `UnicodeDecodeError`가 발생하거나 문자가 깨집니다. 이 모듈은 원시 데이터를 `bytearray` 버퍼에 축적한 뒤 스트림이 완전히 종료되는 시점에 단 한 번 전체 디코딩을 처리합니다.
    2.  **불완전 JSON 응답 복구**: 통신 장애 등으로 응답 패킷의 JSON 포맷이 손상되어 유실될 경우를 대비해, 예외 처리 블록 내에 정규식 패턴(`re.findall()`) 및 `unicode_escape` 역환산을 적용하여 유효한 텍스트 데이터만을 추출해 내는 보완 엔진을 내장하고 있습니다.

---

## 2. 디렉토리 구조

```text
.
├── agent_registry/           # 핵심 연동 소스 코드 폴더
│   ├── agent/                # No-Code 에이전트 연동 모듈
│   │   ├── agent.py          # ADK No-Code 에이전트 검색 및 실시간 호출 스크립트 (한글 명칭 Monkeypatch 적용)
│   │   └── README.md         # No-Code 에이전트 모듈 전용 안내서
│   ├── api/                  # 직접 REST API 연동 모듈
│   │   ├── api.py            # streamAssist 직접 호출 및 UTF-8 누적 바이트 버퍼 구현 스크립트
│   │   └── README.md         # 직접 REST API 연동 모듈 전용 안내서
│   └── mcp/                  # MCP 도구셋 연동 모듈
│       ├── build/            # MCP 서버 빌드 및 Cloud Run 배포 아티팩트
│       │   ├── Dockerfile        # 컨테이너 이미지 명세서
│       │   ├── capital_mcp_server.py # FastMCP 기반 수도 검색 도구 서버 코드
│       │   ├── deploy.sh         # GCP 서울 리전 배포 쉘 스크립트
│       │   └── test_capital_mcp.py # 로컬 stdio 통신 기능 검증용 단위 검사 스크립트
│       ├── connect_mcp.py    # Registry에 등록된 MCP 서버를 호출하여 Gemini 2.5와 결합 구동하는 스크립트
│       └── README.md         # MCP 모듈 배포 및 연동 전용 안내서
├── pyproject.toml            # uv 전용 가상환경 의존성 정의 파일 (google-adk, google-genai, mcp)
└── README.md                 # 전체 플랫폼 통합 안내서 (본 문서)
```

---

## 3. 가상환경 구성 가이드 (uv)

본 프로젝트는 의존성 격리와 패키지 통제를 위해 `uv` 도구를 활용합니다. 시스템 전역(site-packages)에 사전에 안전하게 설치되어 상속되는 구글 클라우드 관련 모듈들과의 호환 및 충돌 방지를 위해 `--system-site-packages` 옵션을 필수 적용하여 구성합니다.

### 가상환경 생성
```bash
uv venv --python /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 --system-site-packages --allow-existing
```

### 가상환경 활성화 방안
*   **macOS / Linux**:
    ```bash
    source .venv/bin/activate
    ```
*   **Windows**:
    ```bash
    .venv\Scripts\activate
    ```

---

## 4. 모듈별 실행 방법

가상환경이 활성화되었거나 `uv run` 명령어로 실행 환경이 잡힌 터미널에서 다음 스크립트들을 개별 실행합니다.

### 1. No-Code 에이전트 연동 테스트
```bash
uv run --no-sync python3 agent_registry/agent/agent.py
```

### 2. 직접 REST API streamAssist 연동 테스트
```bash
uv run --no-sync python3 agent_registry/api/api.py
```

### 3. 로컬 MCP 서버 Stdio 통신 기능 검증
GCP 클라우드 배포 전에 로컬 stdio 채널 상태에서 작동을 개별 테스트합니다.
```bash
cd agent_registry/mcp/build
uv run --no-sync python3 test_capital_mcp.py
cd ../../..
```

### 4. GCP Agent Registry 등록 MCP + Gemini 결합 구동 테스트
```bash
uv run --no-sync python3 agent_registry/mcp/connect_mcp.py
```

---

## 5. 구글 클라우드 환경 전제 조건 (Prerequisites)

이 예제들이 구글 클라우드 리소스와 올바르게 통신하려면 개발 환경 장비에 적절한 권한 및 세션이 초기화되어 있어야 합니다.

### 1. gcloud CLI 설정 및 프로젝트 연결
로컬 환경에 구글 클라우드 SDK(gcloud CLI)가 정상 설치되어 있어야 하며 아래 명령으로 세션을 바인딩합니다.
```bash
gcloud auth login
gcloud config set project ai-hangsik
```

### 2. 애플리케이션 기본 자격 증명(ADC) 및 권한 범위(Scopes) 추가 구성
ADK 에이전트 탐색 및 호출 보안 게이트웨이는 엄격한 OAuth 토큰 범위를 수반해야 합니다. 기본 로그인만 거칠 경우 `cloud-platform` 권한이 누락되므로 반드시 아래 명령을 수행하여 Scopes 옵션이 적용된 사용자 토큰 파일을 로컬에 재발행해야 합니다.
```bash
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform"
```

### 3. 계정별 필수 IAM 권한 역할
*   **No-Code 에이전트 조회 및 호출**: `Vertex AI Administrator` 또는 `Vertex AI User` 역할 필요.
*   **MCP 서버 빌드 및 Cloud Run 서비스 배포**: `Cloud Run Admin`, `Service Account User`, `Artifact Registry Writer` 역할 필요.
