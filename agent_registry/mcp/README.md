# 🛠️ MCP Server & Agent Integration 통합 연동 가이드

이 디렉토리는 국가의 수도 이름을 즉각 검색해 주는 독창적인 **Model Context Protocol (MCP)** 서버를 구축하고, 이를 클라우드 컨테이너 환경(Cloud Run)에 호스팅하여, 구글 에이전트 레지스트리(Agent Registry)에 정식 등록해 Vertex AI Gemini ADK 에이전트 도구로 실시간 융합 활용하는 전체 소스 코드와 배포 사양을 담고 있습니다.

---

## 🏗️ 전체 연동 아키텍처 (MCP + Agent Registry Pipeline)

```text
[로컬 클라이언트 (Gemini LlmAgent)]
               │
               │ 1. get_mcp_toolset() 요청 (GCP OAuth 인증 수반)
               ▼
   [ GCP Agent Registry ] (GCP 등록 센터)
               │
               │ 2. "Capital Finder Server"의 Cloud Run Endpoint 정보 해석
               ▼
   [ GCP Cloud Run ] (FastMCP Server 실시간 소켓 연결)
               │
               │ 3. 도구 명세(get_capital) 및 호출 인풋 스키마 회신
               ▼
[로컬 클라이언트 (LlmAgent)] <---> [ Gemini 2.5-Flash (Vertex AI) ]
               │
               │ 4. 질문 검토 중 외부 데이터(수도) 필요 시 해당 도구 가동 결정
               ▼
   [ get_capital 도구 작동 ] (국가 수도 정보 실시간 반환)
               │
               │ 5. 최종 완성된 답변 사용자를 향해 스트리밍 출력
               ▼
[터미널 콘솔 (사용자 화면)]
```

---

## 📂 파일 및 디렉토리 요약 (Files & Folders)

*   **`connect_mcp.py`**: GCP Agent Registry에 등록 완료된 원격 MCP 서버를 동적으로 수집하고, `McpToolset`을 추출하여 `Vertex AI Gemini 2.5-flash` 모델 기반의 `LlmAgent`와 완벽히 결합하여 답변 프로세스를 완수하는 최종 비동기 시나리오 러너입니다. (mTLS 로컬 인증서 오류 차단을 위한 **mTLS 회피 패치 솔루션** 탑재)

### 📁 **`build/`** (MCP 서버 빌드 및 배포 패키지)
*   **`capital_mcp_server.py`**: FastMCP 프레임워크 기반으로 빌드된 국가 수도 조회 전용 MCP 도구입니다. 환경에 맞춰 Stdio 모드 또는 Streamable HTTP(구글 레지스트리 표준 포맷) 모드로 자동 실행 분기됩니다.
*   **`test_capital_mcp.py`**: 로컬 Stdio 서브프로세스 파이프 방식을 활용하여 원격 배포 전에 로컬에서 도구 탐색 및 수동 실행이 잘 동작하는지 검증하는 단위 테스트 스크립트입니다.
*   **`Dockerfile`**: Cloud Run 배포용 라이트웨이트 컨테이너 패키징 명세입니다.
*   **`deploy.sh`**: 로컬 소스 코드를 구글 클라우드 빌드를 통해 아시아-이스트(서울) 리전의 Cloud Run 서비스로 신속하게 컴파일 및 배포해주는 쉘 스크립트입니다.

---

## 🛠️ 개발자를 위한 사전 요구사항 (Prerequisites)

이 모듈을 성공적으로 컴파일하고 구동하려면 gcloud CLI 설치 및 애플리케이션 기본 자격 증명(ADC) 범위가 반드시 아래처럼 확보되어 있어야 합니다.

```bash
# 1. 구글 인증 로그인 및 프로젝트 할당
gcloud auth login
gcloud config set project ai-hangsik

# 2. [매우 중요] Agent Registry의 MCP 게이트웨이 인증을 위한 Scopes 강제 연동 ADC 가동
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform"
```

---

## 🚀 실행 및 배포 방법 (How to Run & Deploy)

### 1. 로컬 기능 독립 테스트 (Stdio Pipeline)
GCP에 올리기 전, 로컬 터미널에서 stdio 기반으로 도구 검색 및 반환값을 수동으로 검증합니다.
```bash
# 디렉토리 진입 및 테스트 스크립트 가동
cd agent_registry/mcp/build
uv run --no-sync python3 test_capital_mcp.py
cd ../../..
```

### 2. 구글 클라우드 런 배포 (Cloud Run Deploy)
작성한 MCP 서버를 클라우드 환경에 호스팅합니다. (Cloud Run 배포 성공 후 GCP Console의 Agent Registry 페이지에서 해당 Cloud Run 주소를 사용하여 MCP Server를 등록해야 합니다.)
```bash
cd agent_registry/mcp/build
./deploy.sh
cd ../../..
```

### 3. 클라우드 에이전트 레지스트리 연동 실행 (Gemini Agent)
Agent Registry에 호스트 등록된 `"Capital Finder Server"`의 도구를 로드하여 `Gemini` 비동기 루프에서 자동 호출되도록 시뮬레이션합니다.
```bash
uv run --no-sync python3 agent_registry/mcp/connect_mcp.py
```

#### 에이전트 추론 및 도구 호출 결과 예시:
```text
🎯 Selected MCP Server: 'Capital Finder Server'
   Resource Name: projects/721521243942/locations/global/mcpServers/agentregistry-00000000-0000-0000-73e9-2f1fc38bf9c0

Refreshing Google Service Account OAuth token with cloud-platform scopes...
Connecting to the MCP Server and building the McpToolset...
Fetching tools exposed by the MCP Server...

🔧 Exponentiated 1 Tool(s) from MCP Server:
  [1] Tool Name:  get_capital
      Description: Find the capital city of a given country.

💡 Integrating the MCP Toolset with an LLM Agent (Gemini)...
✅ Successfully initialized LlmAgent 'mcp_assistant' with the MCP Toolset!

💬 Querying Agent: 'What is the capital city of South Korea?'

--- STREAMING RESPONSE ---
The capital of South Korea is Seoul. (Gemini가 수동으로 입력 정보를 get_capital에 질의하여 알아낸 뒤 최종 문장으로 해독해 출력합니다.)
--- END OF STREAM ---
```

---

## 💡 주요 기술적 솔루션 설명 (Technical Deep-Dive)

### macOS 로컬 개발 SSLCertVerificationError 해결 (mTLS bypass)
로컬 Python 가상환경 등에서 구글 ADK 및 Cloud SDK 연동 시, 라이브러리 내부에서 상호 TLS(mTLS) 연결을 위한 인증 파일 검색을 격렬히 시도하게 됩니다. 
이 과정에서 로컬 SSL 핸드셰이크 프로토콜이 충돌해 **`SSLCertVerificationError`** 또는 **`SSLError`**가 발생하며 소켓 연결 전체가 다운되는 결함이 자주 보고됩니다.

`connect_mcp.py` 소스 상단부에서는 이러한 결함을 해결하기 위해 구글 모듈의 인증 판단을 차단하는 **인증 필터 Monkeypatch**를 적용해 두었습니다:
```python
import google.auth.transport.mtls as auth_mtls
# 클라이언트 mTLS 인증서 자동 사용 판단 함수가 항상 False를 응답하도록 재정의
auth_mtls.should_use_client_cert = lambda: False
```
mTLS를 해제하더라도, API 연동 시 일반 암호화 TLS 포트를 경유하고 구글 클라우드의 고유 Bearer OAuth 토큰을 철저히 인증 헤더에 태워 전송하므로, **동작 유연성은 확보하면서 보안성은 최고 수준으로 엄격하게 그대로 유지**됩니다.
