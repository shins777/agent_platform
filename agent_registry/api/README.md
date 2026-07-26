# 🌐 직접 REST/HTTPS API Gateway 연동 가이드 (Direct REST Client)

이 디렉토리는 별도의 무거운 에이전트 SDK나 특수 어댑터 라이브러리를 경유하지 않고, 구글 클라우드 Vertex AI Agent Engine의 로우레벨 REST API 엔드포인트(`streamAssist`)로 직접 HTTP POST 스트리밍 호출을 수행하여 고성능 다중 청크 스트림을 획득하고, 이를 단일 문자열로 완전 취합(Aggregate)해내는 가볍고 강력한 클라이언트 통신 기술 코드를 포함합니다.

---

## 🏗️ 로우레벨 직접 호출 아키텍처 (Direct HTTP Stream Pipeline)

```text
  [ 개발자 클라이언트 (api.py) ]
               │
               │ 1. HTTP POST 질의 전송 (Header - Accept: text/event-stream)
               ▼
[ Google Cloud Vertex AI API 게이트웨이 ] (OAuth 및 Bearer 토큰 심사)
               │
               │ 2. 로우레벨 streamAssist 호출 발생 (Vertex AI Engine)
               ▼
  [ Gemini Enterprise 백엔드 ]
               │
               │ 3. 실시간 바이트 조각(TCP 패킷) 스트리밍 반환
               ▼
  [ 개발자 클라이언트 (api.py) ] -> (바이트 버퍼 누적 취합 및 UTF-8 최종 해독)
```

---

## 📂 파일 요약 (Files)

*   **`api.py`**: 구글 AuthorizedSession 자격 증명을 이용해 어시스턴트 게이트웨이 엔드포인트에 `text/event-stream` 양식으로 원격 API 호출을 발생시켜 실시간 바이트 리스트로 누적 취합(Aggregate)한 뒤, 깨끗한 마크다운 및 텍스트 형태로 최종 정제 출력해 주는 직접 API 통신 스크립트입니다. (한국어 문자 잘림에 따른 디코딩 방지 및 **Regex 기반 데이터 복구 안전장치** 탑재)

---

## 🛠️ 개발자를 위한 사전 요구사항 (Prerequisites)

GCP의 REST API 엔드포인트는 구글 클라우드 보안 환경과 직접적으로 매칭되므로 아래 두 명령어로 권한을 로컬에 발급받아 두어야 합니다.

### 1. Google Cloud CLI (gcloud) 로그인
```bash
gcloud auth login
```
### 2. 기본 로컬 인증 자격 증명 (ADC) 설정
직접 API 호출 세션은 클라이언트 수준에서 기본 권한을 획득하여 Bearer 토큰을 자동 발행하므로 아래 명령어가 필요합니다.
```bash
gcloud auth application-default login
```

---

## 🚀 실행 방법 (How to Run)

프로젝트 루트 디렉토리 `/Users/hangsik/Documents/Antigravity/agentplatform` 에서 아래 명령어를 실행합니다.

```bash
# 가상환경 활성화 상태에서 실행
python3 agent_registry/api/api.py
```

### 🎯 실행 프로세스 및 터미널 출력 로그 시뮬레이션:
```text
=========================================================================
 🌐 GCP Agent HTTP API Gateway - 직접 HTTP POST 호출 및 스트림 취합
=========================================================================

1. Google 클라우드 IAM 권한 기반 인증 세션 생성 중...
2. 개발자 전송 질의: '조선시대 최고의 과학 발명품은?'

Agent HTTP API로부터 이벤트 스트림 데이터를 다운로드 및 취합 중...

--- AGGREGATED FINAL RESPONSE (취합 완료된 최종 답변) ---
조선시대는 뛰어난 과학 기술과 실용적인 발명품들이 대거 등장한 황금기였습니다. 
그중에서도 가장 독창적이고 가치 있는 과학 발명품 3선은 다음과 같습니다:

1. 훈민정음 (한글): 단순한 언어를 넘어 문자 자체를 고도로 과학적으로 창제한 인류사적 발명품.
2. 측우기: 강우량을 규격화하여 세계 최초로 강우 수치를 정밀 계측한 과학적 도구.
3. 혼천의 및 간의: 우주의 정밀 천체를 측정하기 위해 제작된 우수한 천문 과학 장비.

이들은 단순한 유물을 넘어 백성들의 농업 실용주의 및 기상 예측을 고도화하려는 과학적 노력의 결과물이었습니다.

--- END OF RESPONSE (호출 완료) ---
```

---

## 💡 주요 기술적 솔루션 설명 (Technical Deep-Dive)

### 1. 한글 멀티바이트 문자 네트워크 경계선 깨짐 현상 완벽 방어 (Byte Accumulation)
한국어 UTF-8 문자는 1글자당 3바이트의 고정 바이트를 소비합니다. 
원격 스트리밍 수신 시 데이터는 일정 단위의 TCP 청크 패킷으로 쪼개져 오기 때문에, 만약 "조선시대"의 '조'라는 글자(3바이트)가 전송되는 도중 패킷 크기 상한선에 도달하면, 앞선 패킷에 2바이트만 전송되고 뒤이은 패킷에 나머지 1바이트가 전송될 수 있습니다.

이때 매 청크가 올 때마다 즉시 `.decode('utf-8')`을 시도하면 첫 패킷의 끝에서 **`UnicodeDecodeError`**가 터지거나 글자가 깨집니다.
`api.py`는 이를 완벽히 해결하기 위하여 다음과 같이 설계되어 있습니다:
```python
# 문자열 대신 바이트 배열에 모든 데이터를 누적 축적
response_bytes = bytearray()
for chunk in res.iter_content(chunk_size=None):
    if chunk:
        response_bytes.extend(chunk)

# 데이터 수신이 완전히 완수되었을 때 한꺼번에 단 한 차례만 UTF-8 디코딩 수행
response_text = response_bytes.decode('utf-8')
```
이 바이트 버퍼링 기법을 적용함으로써 어떤 다국어 문자열도 깨짐이나 디코딩 오류 없이 영구적으로 안전하게 파싱됩니다.

### 2. 네트워크 단선에 의한 불완전 JSON 대응 Regex 백업 복구 엔진
실시간 스트리밍은 언제든 불안정한 네트워크로 인하여 JSON 배열 구조가 완전히 닫히지 않고 잘린 패킷 상태로 통신이 끝날 수 있습니다. 
이때 단순히 `json.loads(response_text)`만 작동시키면 `JSONDecodeError`가 발동하며 수집한 텍스트 데이터 전체를 소실합니다.

이러한 예외 상황을 방어하기 위해 다음과 같은 **정규식(Regex) 보완 필터**가 백업 솔루션으로 장착되어 작동합니다:
```python
import re
# 잘린 원시 텍스트 중에서 유효하게 매칭되는 텍스트 필드를 추출
parts = re.findall(r'"text":\s*"([^"]+)"', response_text)
# 추출한 조각을 역환산 유니코드 이스케이프 복구 처리하여 출력
decoded_text = bytes("".join(parts), "utf-8").decode("unicode_escape")
```
이로 인해 통신망 불안정에 따른 서비스 실패율을 극적으로 최소화할 수 있습니다.
