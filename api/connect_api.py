import re
import json
import google.auth
from google.auth.transport.requests import AuthorizedSession

# GCP Vertex AI Agent Engine - 직접 HTTPS Gateway API Endpoint 주소
# 해당 URL은 구글 어시스턴트 엔진의 streamAssist 메소드를 직접 호출하여 대화형 답변 및 근거가 포함된 이벤트 스트림을 제공받습니다.
URL = "https://global-discoveryengine.googleapis.com/v1alpha/projects/721521243942/locations/global/collections/default_collection/engines/gemini-enterprise-20251128_1764121967638/assistants/default_assistant:streamAssist"

def main():
    print("=========================================================================")
    print(" 🌐 GCP Agent HTTP API Gateway - 직접 HTTP POST 호출 및 스트림 취합")
    print("=========================================================================\n")

    # 1. Google OAuth 인증 세션 초기화
    # 구글 서비스 계정(또는 기본 로컬 자격 증명) 정보를 로드하여 AuthorizedSession 객체를 생성합니다.
    # AuthorizedSession은 API 호출 시 Google OAuth 2.0 Bearer 인증 헤더를 자동으로 관리하고 갱신해줍니다.
    print("1. Google 클라우드 IAM 권한 기반 인증 세션 생성 중...")
    credentials, _ = google.auth.default()
    session = AuthorizedSession(credentials)
    
    # 2. 전송할 사용자 질의 및 Payload 작성
    user_input = "조선시대 최고의 과학 발명품은?"
    print(f"2. 개발자 전송 질의: '{user_input}'")
    
    payload = {"query": {"text": user_input}}
    
    print("\nAgent HTTP API로부터 이벤트 스트림 데이터를 다운로드 및 취합 중...")
    
    # 3. HTTP POST 요청 전송 및 원바이트 청크 버퍼 수집
    # Accept 헤더에 'text/event-stream'을 지정하여 어시스턴트로부터 실시간 스트리밍 형태로 전송받습니다.
    # [UnicodeDecodeError 해결책]: 한국어 등의 다중 바이트 문자열이 청크 경계에서 끊기지 않도록, 
    # 먼저 원시 바이트 목록(bytearray)으로 합친 후에 최종적으로 한 번에 utf-8 디코딩을 수행합니다.
    response_bytes = bytearray()
    with session.post(URL, json=payload, headers={"Accept": "text/event-stream"}, stream=True) as res:
        res.raise_for_status()  # 요청 에러 시 예외를 발생시킵니다.
        for chunk in res.iter_content(chunk_size=None):
            if chunk:
                response_bytes.extend(chunk)
                
    # 전체 응답 바이트를 UTF-8 텍스트로 복원합니다.
    response_text = response_bytes.decode('utf-8')

    print("\n--- AGGREGATED FINAL RESPONSE (취합 완료된 최종 답변) ---")
    
    # 4. JSON Array 파싱 및 답변 텍스트 필드 병합
    # 서버로부터 수집한 streamAssist 원본 데이터는 단일 큰 JSON 배열 형태([ ... 청크객체들 ... ])를 띄고 있습니다.
    try:
        data = json.loads(response_text)
        full_text = []
        for item in data:
            # 스키마 패턴 1: 일반 대화형 답변 객체 (answer -> replies -> groundedContent)
            if 'answer' in item and 'replies' in item['answer']:
                for reply in item['answer']['replies']:
                    if 'groundedContent' in reply and 'content' in reply['groundedContent']:
                        text = reply['groundedContent']['content'].get('text', '')
                        if text:
                            full_text.append(text)
            # 스키마 패턴 2: 플래너의 추론 단계 답변 객체 (planStep -> parts)
            elif 'planStep' in item and 'parts' in item['planStep']:
                for part in item['planStep']['parts']:
                    text = part.get('text', '')
                    if text:
                        full_text.append(text)
        
        # 청크 조각들을 하나의 문자열로 결합하여 깨끗하게 출력합니다.
        aggregated_response = "".join(full_text)
        print(aggregated_response)
        
    except Exception as e:
        # 응답 형식이 온전하지 않거나 네트워크 중간 중단 등으로 JSON 파싱 실패 시, 정규식을 사용하여 텍스트 부분을 보존적으로 추출합니다.
        print(f"⚠️ JSON 파싱 실패 (이유: {e})")
        print("정규식(Regex) 기반 보완적 텍스트 복원을 시도합니다...\n")
        
        parts = re.findall(r'"text":\s*"([^"]+)"', response_text)
        if parts:
            try:
                # 유니코드 이스케이프 문자열(\uXXXX)을 디코딩하여 문자열로 조합합니다.
                decoded_text = bytes("".join(parts), "utf-8").decode("unicode_escape")
                print(decoded_text)
            except Exception as decode_err:
                print("".join(parts))
        else:
            print("답변 텍스트를 추출할 수 없습니다. 원본 청크 텍스트:")
            print(response_text)

    print("\n--- END OF RESPONSE (호출 완료) ---\n")

if __name__ == "__main__":
    main()
