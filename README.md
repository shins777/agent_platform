# 🚀 GCP Agent Platform (ADK & MCP Integration)

이 프로젝트는 Google Cloud Agent Registry 및 Vertex AI Agent Engine과의 동적 통합을 지원하는 No-Code 에이전트, Model Context Protocol (MCP) 서버 및 직접 API 게이트웨이 호출 기능이 하나로 통합된 고성능 개발 플랫폼입니다.

 Astral사에서 제작한 초고속 파이썬 패키지 및 가상환경 관리 도구인 **`uv`**를 활용하여 로컬 개발 환경을 쉽고 안정적으로 구성할 수 있습니다.

---

## 📁 디렉토리 구조 (Folder Structure)

```text
.
├── agent/
│   ├── connect_agent.py      # GCP Agent Registry No-Code 에이전트 연동 스크립트
│   └── README.md             # No-Code Agent 연동 가이드
├── api/
│   ├── connect_api.py        # streamAssist 직접 HTTP POST 및 파이싱 스크립트
│   └── README.md             # 직접 API 호출 가이드
├── mcp/
│   ├── build/                # MCP 서버 빌드 및 클라우드 배포 패키지 📁
│   │   ├── Dockerfile        # MCP 서버 컨테이너 빌드 파일
│   │   ├── capital_mcp_server.py # 국가 수도 조회 FastMCP 서버 소스
│   │   ├── deploy.sh         # Cloud Run 배포 자동화 쉘 스크립트
│   │   └── test_capital_mcp.py # 로컬 stdio 통신 기능 검증용 단위 스크립트
│   ├── connect_mcp.py        # Registry MCP 도구를 로드하여 구동하는 Gemini 러너
│   └── README.md             # MCP 구성 및 빌드 가이드
├── pyproject.toml            # uv 연동 및 패키지 의존성 정의 파일
└── README.md                 # 통합 안내서 (본 파일)
```

---

## 🛠️ 가상환경 설정 및 실행 가이드 (Virtual Environment with `uv`)

구글 클라우드 전용 프라이빗 패키지(`google-adk`)가 시스템/전역(Library site-packages)에 사전에 안전하게 바인딩되어 있으므로, `uv` 가상환경 구성 시 **`--system-site-packages`** 옵션을 부여하여 충돌 없이 초고속으로 환경을 생성하고 사용합니다.

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

### 🤖 No-Code 에이전트 연동 실행
```bash
uv run --no-sync python3 agent/connect_agent.py
```

### 🌐 직접 API streamAssist 취합 호출 실행
```bash
uv run --no-sync python3 api/connect_api.py
```

### 🛠️ 로컬 MCP 서버 stdio 기능 수동 검증
```bash
cd mcp/build
uv run --no-sync python3 test_capital_mcp.py
cd ../..
```

### 🎯 GCP Agent Registry 등록 MCP + Gemini 연동 실행
```bash
uv run --no-sync python3 mcp/connect_mcp.py
```
