"""
🌐 Vertex AI Agent Engine 직접 HTTP/REST API Gateway 연동 모듈 (Direct HTTP Client)
================================================================================

본 스크립트는 구글 클라우드가 제공하는 별도의 에이전트 SDK나 전용 라이브러리를 경유하지 않고,
Vertex AI Agent Engine의 로우레벨 REST API 엔드포인트(`streamAssist`)로 직접 HTTP POST 스트리밍 호출을 수행하여 
실시간 청크 스트림을 획득하고 이를 단일 문자열로 완전 취합(Aggregate)해주는 경량 고성능 클라이언트 코드입니다.

1. 아키텍처 흐름도 (Architectural Workflow)
------------------------------------------
[개발자 로컬 클라이언트 (AuthorizedSession)]
       │
       │  1. HTTP POST Request (Accept: text/event-stream)
       ▼
[GCP Vertex AI Agent Engine Gateway]
       │
       │  2. Target Assistant Engine 검색 및 세션 초기화
       ▼
[Gemini Enterprise 백엔드] (답변 생성)
       │
       │  3. 실시간 JSON Chunk 스트리밍 반환 (TCP/IP 패킷 단위 전송)
       ▼
[개발자 로컬 클라이언트 (바이트 스트림 버퍼 수집)]
       │
       │  4. UTF-8 복원 (한글 깨짐/디코딩 방지) -> JSON 파싱 -> 최종 답변 완성
       ▼
[터미널 콘솔 (사용자 화면)]

2. 핵심 기술 개념 (Core Technology Concepts)
-------------------------------------------
- streamAssist API:
  구글 클라우드 어시스턴트 엔진의 실시간 스트리밍 대답 및 지식 검색(RAG) 인용 근거(Grounded Content)를 
  'text/event-stream'(Server-Sent Events) 프로토콜 기반으로 반환받는 핵심 로우레벨 API 메소드입니다.
- AuthorizedSession:
  Google Auth 라이브러리(`google-auth`)에서 지원하는 보안 HTTP 세션 객체입니다. 
  표준 Python `requests.Session`을 상속받아, Google OAuth 2.0 Bearer 인증 헤더를 자동으로 생성하고 
  토큰 만료 시 백엔드 단에서 자동으로 갱신(Refresh)하여 요청 누락을 영구 방지합니다.
- 멀티바이트 문자 경계 디코딩 문제 (UnicodeDecodeError & Broken Korean Chars):
  한국어나 중국어, 일본어와 같은 UTF-8 멀티바이트 문자는 한 문자당 3바이트를 차지합니다. 
  네트워크 소켓으로부터 수신되는 청크(Chunk) 데이터는 가변적인 TCP 패킷 크기로 나뉘어 전달되기 때문에, 
  재수가 없으면 한글 3바이트 중 1~2바이트가 첫 번째 청크 패킷의 끝에, 나머지 1바이트가 두 번째 청크 패킷의 
  시작에 잘려서 도착하게 됩니다. 
  만약 매 청크가 올 때마다 개별적으로 `.decode('utf-8')`을 시도하면 이렇게 잘린 부분에서 `UnicodeDecodeError`가 
  터지거나 문자열이 심각하게 깨져서 병합되는 고질적인 버그가 생깁니다.
  이를 해결하기 위해 본 코드에서는 수신되는 원시 청크를 디코딩하지 않고, `bytearray` 객체에 바이트 통째로 
  누적 축적(Buffer)한 다음 데이터가 완전히 종료되었을 때 한 번에 UTF-8 디코딩을 수행하여 문제를 완벽히 해결합니다.

3. 개발자 핵심 문제 해결 가이드 (Troubleshooting & Solutions)
--------------------------------------------------------------
- JSON 파싱 예외 발생 및 정규식(Regex) 보완:
  스트리밍 연결 도중 네트워크가 인위적으로 단절되거나 서버 측 오류로 인해 응답의 JSON 배열 구조가 완전히 닫히지 않고
  잘린 채 반환되는 경우가 생길 수 있습니다. 
  이 경우 `json.loads()`가 에러를 뿜으며 응답 전체를 유실할 위험이 있으므로, 예외 캐치 블록에서 
  정규식 패턴(Regex)인 `re.findall()`을 구동해 유효한 텍스트 데이터 조각만을 안전하게 뜯어내어 
  최종 문자열로 복구해 주는 이중 안전장치를 내장하고 있습니다.
"""

import re
import json
import google.auth
from google.auth.transport.requests import AuthorizedSession

# ==============================================================================
# GCP Vertex AI Agent Engine - 직접 HTTPS Gateway API Endpoint 주소
# ==============================================================================
# 이 URL은 GCP 글로벌 디스커버리 엔진에 상주하는 특정 컬렉션 하위의 어시스턴트 인스턴스로 경로가 이어집니다.
URL = "https://global-discoveryengine.googleapis.com/v1alpha/projects/721521243942/locations/global/collections/default_collection/engines/gemini-enterprise-20251128_1764121967638/assistants/default_assistant:streamAssist"

def main():
    print("=========================================================================")
    print(" 🌐 GCP Agent HTTP API Gateway - 직접 HTTP POST 호출 및 스트림 취합")
    print("=========================================================================\n")

    # --------------------------------------------------------------------------
    # 1단계: Google AuthorizedSession OAuth 보안 인증 세션 수립
    # --------------------------------------------------------------------------
    # 로컬 시스템 자격 증명(ADC)을 자동으로 수집하여 AuthorizedSession 객체로 주입합니다.
    # 이것은 일반 HTTP 클라이언트(requests, httpx)를 사용하여 GCP REST API를 손쉽게 다룰 수 있도록 돕습니다.
    print("1. Google 클라우드 IAM 권한 기반 인증 세션 생성 중...")
    try:
        credentials, _ = google.auth.default()
        session = AuthorizedSession(credentials)
    except Exception as e:
        print(f"❌ GCP 인증 자격 증명을 획득하지 못했습니다: {e}")
        print("💡 해결책: 터미널에서 'gcloud auth application-default login'을 구동하여 로컬 환경을 연동하십시오.")
        return
    
    # --------------------------------------------------------------------------
    # 2단계: 질의문 및 페이로드 데이터 생성
    # --------------------------------------------------------------------------
    # 어시스턴트에 전달할 쿼리 형식을 딕셔너리로 기술합니다.
    user_input = "조선시대 최고의 과학 발명품은?"
    print(f"2. 개발자 전송 질의: '{user_input}'")
    
    payload = {"query": {"text": user_input}}
    
    print("\nAgent HTTP API로부터 이벤트 스트림 데이터를 다운로드 및 취합 중...")
    
    # --------------------------------------------------------------------------
    # 3단계: HTTP POST 스트리밍 호출 및 멀티바이트 바이트 버퍼링 (핵심 해결책)
    # --------------------------------------------------------------------------
    # stream=True 옵션을 부여하여 세션을 실시간 다운로드 모드로 고정합니다.
    # 한국어가 네트워크 바이트 경계에서 깨지는 것을 극도로 정밀하게 방어하기 위하여
    # bytearray 버퍼에 데이터를 완전 원시 바이트(Raw Bytes)로 누적합산합니다.
    response_bytes = bytearray()
    
    try:
        with session.post(URL, json=payload, headers={"Accept": "text/event-stream"}, stream=True) as res:
            res.raise_for_status()  # 4xx / 5xx 계열 HTTP 에러 반환 시 예외 발발
            
            # 수신되는 각 데이터 블록(청크)을 순차적으로 읽어 버퍼에 삽입합니다.
            for chunk in res.iter_content(chunk_size=None):
                if chunk:
                    response_bytes.extend(chunk)
    except Exception as e:
        print(f"❌ HTTP 연결 또는 데이터 스트리밍 다운로드 중 에러 발생: {e}")
        print("💡 원인 분석: GCP 엔드포인트 URL 경로가 잘못되었거나, 서비스 계정의 Vertex AI 호출 권한(Discovery Engine Viewer 등)이 상실되었을 수 있습니다.")
        return
                
    # 데이터가 완전히 취합된 후 비로소 한꺼번에 UTF-8로 안전하게 디코딩을 수행합니다.
    response_text = response_bytes.decode('utf-8')

    print("\n--- AGGREGATED FINAL RESPONSE (취합 완료된 최종 답변) ---")
    
    # --------------------------------------------------------------------------
    # 4단계: JSON 파싱 및 구조적 답변 텍스트 병합과 Regex 이중 백업 필터링
    # --------------------------------------------------------------------------
    # 서버로부터 수집된 streamAssist의 전체 응답 텍스트는 하나의 큰 JSON 배열 형태를 갖춥니다.
    # 정상 상황에서는 `json.loads()`로 객체화하여 데이터 구조 트리를 파싱해 답변을 출력합니다.
    try:
        data = json.loads(response_text)
        full_text = []
        for item in data:
            # 패턴 1: 정상 완성형 스트리밍 답변 객체 (answer -> replies -> groundedContent)
            if 'answer' in item and 'replies' in item['answer']:
                for reply in item['answer']['replies']:
                    if 'groundedContent' in reply and 'content' in reply['groundedContent']:
                        text = reply['groundedContent']['content'].get('text', '')
                        if text:
                            full_text.append(text)
            # 패턴 2: 에이전트 생각 단계 및 멀티 턴 중간 추론 객체 (planStep -> parts)
            elif 'planStep' in item and 'parts' in item['planStep']:
                for part in item['planStep']['parts']:
                    text = part.get('text', '')
                    if text:
                        full_text.append(text)
        
        # 누적 수집된 문자열 리스트를 하나의 깔끔한 완성 마크다운형 대답으로 변환합니다.
        aggregated_response = "".join(full_text)
        print(aggregated_response)
        
    except Exception as e:
        # 응답 패킷의 꼬리가 통신 중단 등으로 짤려서 JSON 구조가 일그러졌을 때 구동되는 Regex 복구 솔루션입니다.
        print(f"⚠️ JSON 구조 완전성 검증 실패 (이유: {e})")
        print("정규식(Regex) 기반 보완적 텍스트 복원을 시도합니다...\n")
        
        # JSON 객체 내부의 "text": "값" 형태의 문자열들을 전수 패턴 검색합니다.
        parts = re.findall(r'"text":\s*"([^"]+)"', response_text)
        if parts:
            try:
                # 유니코드 에스케이핑 문자(\uXXXX)들을 표준적인 유니코드 문자열로 말끔하게 역환산 복구합니다.
                decoded_text = bytes("".join(parts), "utf-8").decode("unicode_escape")
                print(decoded_text)
            except Exception as decode_err:
                print("".join(parts))
        else:
            print("답변 텍스트를 추출할 수 없습니다. 수집된 원본 원시 청크 텍스트:")
            print(response_text)

    print("\n--- END OF RESPONSE (호출 완료) ---\n")

if __name__ == "__main__":
    main()
