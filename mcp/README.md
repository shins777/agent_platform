# 🛠️ MCP (Model Context Protocol) Server & Agent Integration Module

이 디렉토리는 국가의 수도 이름을 즉각 검색해 주는 독창적인 Model Context Protocol (MCP) 서버를 구축, 클라우드 가상 환경(Cloud Run)에 호스팅하고, 구글 에이전트 레지스트리(Agent Registry)에 정식 등록하여 Vertex AI Gemini ADK 에이전트 도구로 활용하는 전체 소스 코드와 배포 사양을 담고 있습니다.

---

## 📂 파일 및 디렉토리 요약 (Files & Folders)

*   **`connect_mcp.py`**: GCP Agent Registry에 등록 완료된 원격 MCP 서버를 동적으로 수집하고, `McpToolset`을 추출하여 `Vertex AI Gemini 2.5-flash` 모델 기반의 `LlmAgent`와 완벽히 결합하여 답변 프로세스를 완수하는 최종 비동기 시나리오 러너입니다. (mTLS 로컬 인증 회피 패치 탑재)

### 📁 **`build/`** (MCP 서버 빌드 및 배포 패키지)
*   **`capital_mcp_server.py`**: FastMCP 프레임워크 기반으로 빌드된 국가 수도 조회 전용 MCP 도구입니다. 환경에 맞춰 Stdio 모드 또는 Streamable HTTP(구글 레지스트리 표준 포맷) 모드로 자동 실행 분기됩니다.
*   **`test_capital_mcp.py`**: 로컬 Stdio 서브프로세스 파이프 방식을 활용하여 원격 배포 전에 로컬에서 도구 탐색 및 수동 실행이 잘 동작하는지 검증하는 단위 테스트 스크립트입니다.
*   **`Dockerfile`**: Cloud Run 배포용 라이트웨이트 컨테이너 패키징 명세입니다.
*   **`deploy.sh`**: 로컬 소스 코드를 구글 클라우드 빌드를 통해 아시아-이스트(서울) 리전의 Cloud Run 서비스로 신속하게 컴파일 및 배포해주는 쉘 스크립트입니다.

---

## 🛠️ 사전 요구사항 (Prerequisites)

1.  **Google Cloud CLI (gcloud) 구성 및 ADC**:
    ```bash
    gcloud auth login
    gcloud config set project ai-hangsik
    gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform"
    ```

---

## 🚀 실행 및 배포 방법 (How to Run & Deploy)

### 1. 로컬 기능 독립 테스트
GCP에 올리기 전, 로컬 터미널에서 stdio 기반으로 도구 검색 및 반환값을 수동으로 검증합니다.
```bash
cd mcp/build
uv run --no-sync python3 test_capital_mcp.py
cd ../..
```

### 2. 구글 클라우드 런 배포 (Cloud Run Deploy)
작성한 MCP 서버를 클라우드 환경에 호스팅합니다.
```bash
cd mcp/build
./deploy.sh
cd ../..
```

### 3. 클라우드 에이전트 레지스트리 연동 실행
Agent Registry에 호스트된 `"Capital Finder Server"`의 도구를 로드하여 `Gemini` 비동기 루프에서 자동 호출되도록 시뮬레이션합니다.
```bash
uv run --no-sync python3 mcp/connect_mcp.py
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
The capital of South Korea is Seoul.
--- END OF STREAM ---
```
