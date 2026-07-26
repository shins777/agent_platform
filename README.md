# 🚀 GCP Agent Platform 통합 개발 플랫폼 (ADK & MCP Integration)

이 프로젝트는 **Google Cloud Agent Registry** 및 **Vertex AI Agent Engine**과의 동적 통합을 지원하는 No-Code 에이전트, Model Context Protocol (MCP) 서버 연동, 그리고 로우레벨 직접 API 게이트웨이 호출 기능을 하나로 통합한 고성능 클라이언트 개발 플랫폼입니다. 

클라우드 기반 에이전트 오케스트레이션에 익숙하지 않은 개발자들을 위해 설계되었으며, 아키텍처 원리부터 실제 로컬 실행 및 클라우드 배포까지의 모든 솔루션을 한국어로 친절히 제공합니다.

---

## 🏗️ 플랫폼 아키텍처 개요 (Architectural Overview)

이 플랫폼은 구글 클라우드의 강력한 에이전트 연동 아키텍처를 보여주기 위해 3가지 연동 시나리오를 한 곳에 모았습니다.

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

### 1. 🤖 No-Code 에이전트 연동 (ADK SDK 활용)
- **개념**: 구글 Vertex AI Agent Engine에 생성한 대화형 에이전트를 SDK를 사용하여 조회 및 동적으로 스트리밍 호출합니다.
- **주요 해결책**: ADK 라이브러리의 엄격한 영어 정규식 필터링 한계를 해결하기 위해 **한글 에이전트 이름 지원 런타임 Monkeypatch**가 탑재되어 있습니다.

### 2. 🛠️ GCP Agent Registry MCP 도구 연동 (Gemini ADK Agent)
- **개념**: Model Context Protocol(MCP) 기술을 사용하여 국가 수도 데이터 조회 기능을 독립형 FastMCP 서버로 구현 후 Cloud Run에 배포하고, 이를 Gemini 2.5 Flash 모델의 도구(Toolset)로 정식 연동하여 AI가 스스로 도구를 활용해 추론을 완수하게 돕습니다.
- **주요 해결책**: 로컬 macOS/Linux 환경에서 발생하는 치명적인 SSL 인증서 에러(`SSLCertVerificationError`)를 완벽히 해결하기 위한 **mTLS 대체 일반 보안 TLS 채널 전환 패치**가 내장되어 있습니다.

### 3. 🌐 직접 REST API 게이트웨이 호출 (streamAssist)
- **개념**: 특수한 SDK나 어댑터 라이브러리 없이도 구글의 공인인증 세션(`AuthorizedSession`)을 사용하여 HTTP POST JSON-RPC를 직접 질의하고, 청크 스트림을 한 번에 병합(Aggregate)해내는 초경량 직접 호출 모듈입니다.
- **주요 해결책**: 한글과 같은 다중 바이트 문자(UTF-8)가 네트워크 패킷 경계선에서 반절로 잘려 수신될 때 발생하는 한국어 깨짐 현상 및 `UnicodeDecodeError`를 방지하기 위해 **바이트 버퍼 누적 후 디코딩 기술**을 사용합니다. JSON 패킷 훼손 시 자동으로 문자열을 살려내는 **Regex(정규식) 기반 보완적 텍스트 복구 알고리즘**도 탑재되어 있습니다.

---

## 📁 디렉토리 구조 (Folder Structure)

```text
.
├── agent_registry/           # 플랫폼 핵심 연동 폴더 📁
│   ├── agent/                # 🤖 No-Code 에이전트 모듈
│   │   ├── agent.py          # GCP Agent Registry No-Code 에이전트 연동 스크립트 (한글 이름 패치 포함)
│   │   └── README.md         # No-Code Agent 연동 가이드 및 실행 명세
│   ├── api/                  # 🌐 직접 REST API 호출 모듈
│   │   ├── api.py            # streamAssist 직접 HTTP POST 및 파이싱 스크립트 (한국어 버퍼 깨짐 방지 장착)
│   │   └── README.md         # 직접 API 호출 가이드 및 페이로드 명세
│   └── mcp/                  # 🛠️ MCP 도구셋 연동 모듈
│       ├── build/            # MCP 서버 빌드 및 클라우드 배포 패키지 📁
│       │   ├── Dockerfile        # MCP 서버 컨테이너 빌드 파일
│       │   ├── capital_mcp_server.py # 국가 수도 조회 FastMCP 서버 소립 소스
│       │   ├── deploy.sh         # Cloud Run 배포 자동화 쉘 스크립트
│       │   └── test_capital_mcp.py # 로컬 stdio 통신 기능 검증용 단위 스크립트
│       ├── mcp.py            # Registry MCP 도구를 로드하여 구동하는 Gemini 러너 (mTLS 에러 회피 포함)
│       └── README.md         # MCP 구성 및 빌드 가이드
├── pyproject.toml            # uv 연동 및 패키지 의존성(google-adk, google-genai 등) 정의 파일
└── README.md                 # 통합 안내서 (본 파일)
```

---

## 🛠️ 가상환경 설정 및 실행 가이드 (Virtual Environment with `uv`)

이 프로젝트는 Astral사에서 제작한 초고속 파이썬 패키지 및 가상환경 관리 도구인 **`uv`**를 활용하여 로컬 개발 환경을 쉽고 안정적으로 구성할 수 있습니다.

구글 클라우드 전용 프라이빗 패키지(`google-adk`)가 시스템/전역(Library site-packages)에 사전에 안전하게 바인딩되어 있으므로, `uv` 가상환경 구성 시 **`--system-site-packages`** 옵션을 부여하여 충돌 없이 초고속으로 글로벌 패키지를 연동 상속하여 사용합니다.

### 1. 가상환경 생성 (venv Setup)
시스템에 바인딩된 글로벌 Python 3.13 및 패키지를 연계 상속하는 가상환경을 생성합니다.
```bash
uv venv --python /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 --system-site-packages --allow-existing
```

### 2. 가상환경 활성화 (Activation)
*   **macOS / Linux**:
    ```bash
    source .venv/bin/activate
    ```
*   **Windows**:
    ```bash
    .venv\Scripts\activate
    ```

---

## 🚀 에이전트 및 API 실행 커맨드 (Execution Commands)

가상환경을 활성화한 상태에서 혹은 `uv run` 접두사를 붙여 언제든지 스크립트를 독립적이고 신속하게 실행할 수 있습니다.

### 🤖 1. No-Code 에이전트 연동 실행
```bash
uv run --no-sync python3 agent_registry/agent/agent.py
```

### 🌐 2. 직접 API streamAssist 취합 호출 실행
```bash
uv run --no-sync python3 agent_registry/api/api.py
```

### 🛠️ 3. 로컬 MCP 서버 stdio 기능 수동 검증
GCP에 배포하기 전에 로컬 소프로세스 통신(Stdio)을 통하여 서버가 도구를 정상 반환하는지 탐색합니다.
```bash
cd agent_registry/mcp/build
uv run --no-sync python3 test_capital_mcp.py
cd ../../..
```

### 🎯 4. GCP Agent Registry 등록 MCP + Gemini 연동 실행
```bash
uv run --no-sync python3 agent_registry/mcp/mcp.py
```

---

## 💡 개발자를 위한 필수 클라우드 환경 가이드 (Prerequisites)

이 코드가 실제 클라우드 인프라와 정상 통신하기 위해서는 GCP 인증 환경 및 권한 수립이 올바르게 완료되어 있어야 합니다.

### 1. Google Cloud CLI (gcloud) 로그인 및 프로젝트 바인딩
터미널 환경에서 아래 명령어를 사용하여 대상 Google 계정으로 로그인하고 개발 프로젝트 ID를 할당합니다.
```bash
gcloud auth login
gcloud config set project ai-hangsik
```

### 2. 애플리케이션 기본 자격 증명 (Application Default Credentials, ADC) 활성화
로컬 파이썬 스크립트가 로컬 파일에 상주하는 사용자 토큰을 읽어서 자동으로 GCP API를 타격할 수 있도록 보안 터널을 뚫어 줍니다.
```bash
# 기본 ADC 로그인
gcloud auth application-default login

# [필독] ADK 및 에이전트 A2A 게이트웨이 연동 시 cloud-platform 권한 범위(scope) 강제 연동 명령어
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform"
```

### 3. 클라우드 필수 IAM 권한 요구사항
- **에이전트 검색 및 게이트웨이 호출**: 연동 계정이 `Vertex AI Administrator` 또는 `Vertex AI User` 역할을 가지고 있어야 합니다.
- **MCP Cloud Run 배포**: 배포 쉘 스크립트 수행을 위해 `Cloud Run Admin`, `Service Account User`, `Artifact Registry Writer` 권한이 요구됩니다.
