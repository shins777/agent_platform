# 🌐 Direct REST/HTTPS API Gateway Connection Module

이 디렉토리는 별도의 에이전트 SDK나 라이브러리를 경유하지 않고, Google Cloud Vertex AI Agent Engine의 로우레벨 REST API 엔드포인트(`streamAssist`)로 직접 HTTP POST 스트리밍 호출을 수행하여 고성능 다중 청크 스트림을 획득하고 이를 단일 문자열로 완전 취합(Aggregate)해주는 클라이언트 코드를 포함합니다.

---

## 📂 파일 요약 (Files)

*   **`connect_api.py`**: 구글 AuthorizedSession 자격 증명을 이용해 어시스턴트 게이트웨이 엔드포인트에 `text/event-stream` 양식으로 원격 API 호출을 발생시켜 실시간 바이트 리스트로 누적 취합(Aggregate)한 뒤 깨끗한 마크다운 및 텍스트 형태로 최종 출력해 주는 직접 API 통신 스크립트입니다.

---

## 🛠️ 사전 요구사항 (Prerequisites)

1.  **Google Cloud CLI (gcloud) 로그인**:
    ```bash
    gcloud auth login
    ```
2.  **기본 로컬 인증 자격 증명 (ADC) 설정**:
    ```bash
    gcloud auth application-default login
    ```

---

## 🚀 실행 방법 (How to Run)

프로젝트 루트 디렉토리(`/Users/hangsik/Documents/Antigravity/agentplatform`)에서 아래 명령어를 실행합니다.

```bash
python3 api/connect_api.py
```

### 실행 결과 예시:
```text
=========================================================================
 🌐 GCP Agent HTTP API Gateway - 직접 HTTP POST 호출 및 스트림 취합
=========================================================================

1. Google 클라우드 IAM 권한 기반 인증 세션 생성 중...
2. 개발자 전송 질의: '조선시대 최고의 과학 발명품은?'

Agent HTTP API로부터 이벤트 스트림 데이터를 다운로드 및 취합 중...

--- AGGREGATED FINAL RESPONSE (취합 완료된 최종 답변) ---
조선시대는 뛰어난 과학 기술과 실용적인 발명품들이 대거 등장한 황금기였습니다. 
그중에서도 역사적 가치와 독창성 면에서 최고로 손꼽히는 3대 과학 발명품은 다음과 같습니다.
... (완전히 파싱되어 깔끔하게 병합된 답변 한 번에 출력) ...

--- END OF RESPONSE (호출 완료) ---
```
