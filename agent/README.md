# 🤖 Agent Integration Module (GCP Agent Registry No-Code Agent)

이 디렉토리는 Google Cloud Agent Registry에 등록되어 호스팅되는 No-Code 에이전트(예: "역사와 과학을 말해주는 에이전트")를 탐색하고, 구글의 보안 에이전트 게이트웨이(A2A) 인증망을 통해 연동 및 비동기 스트리밍 방식으로 호출하는 클라이언트 코드가 포함되어 있습니다.

---

## 📂 파일 요약 (Files)

*   **`connect_agent.py`**: GCP Agent Registry에서 특정 한글 이름의 No-Code 에이전트 리소스 ID를 검색하고, 클라우드 권한 자격 증명 기반으로 게이트웨이를 경유하여 실시간 세션을 형성, 비동기 스트리밍 응답을 수집 및 모니터링하는 검증 스크립트입니다.

---

## 🛠️ 사전 요구사항 (Prerequisites)

1.  **Google Cloud CLI (gcloud) 로그인 및 프로젝트 바인딩**:
    ```bash
    gcloud auth login
    gcloud config set project ai-hangsik
    ```
2.  **애플리케이션 기본 자격 증명 (Application Default Credentials, ADC) 설정**:
    에이전트 게이트웨이 및 레지스트리 보안 인증 처리를 위해 클라우드 플랫폼 권한 범위를 적용하여 인증을 수립합니다.
    ```bash
    gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform"
    ```

---

## 🚀 실행 방법 (How to Run)

프로젝트 루트 디렉토리(`/Users/hangsik/Documents/Antigravity/agentplatform`)에서 아래 명령어를 실행합니다.

```bash
python3 agent/connect_agent.py
```

### 실행 결과 예시:
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
조선시대는 뛰어난 과학 기술이 꽃피었던 시기... (에이전트 실시간 스트리밍 출력)
--- 스트리밍 답변 종료 ---
```
