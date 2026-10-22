import os
import time

import httpx
from google import genai
from google.genai import errors, types

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("GEMINI_API_KEY가 설정되지 않았어.")

# 민감한 값은 출력하지 않고 설정 여부만 확인
print("=== 접속 설정 ===")
for name in [
    "GOOGLE_API_KEY",
    "GOOGLE_GEMINI_BASE_URL",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
]:
    print(f"{name}: {'설정됨' if os.getenv(name) else '없음'}")


def show_host(request):
    # 키와 전체 URL 대신 요청 대상 호스트만 출력
    print(f"접속 서버: {request.url.host}", flush=True)


client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        timeout=30_000,
        retry_options=types.HttpRetryOptions(attempts=1),
        client_args={"event_hooks": {"request": [show_host]}},
    ),
)

# 네가 조회한 목록에 있는 모델만 사용
models = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
]

try:
    for model in models:
        print(f"\n=== {model} 테스트 ===", flush=True)
        started = time.monotonic()

        try:
            response = client.models.generate_content(
                model=model,
                contents="'안녕'이라고만 답해 줘.",
            )

            print(f"응답 수신: {time.monotonic() - started:.1f}초")

            if response.text:
                print(f"사용 성공 모델: {model}")
                print(f"답변: {response.text}")
                break

            print("API 응답은 받았지만 텍스트가 없어.")

        except errors.APIError as e:
            message = str(e.message).replace(api_key, "[키 숨김]")
            print(f"API 오류 {e.code}: {message}")

        except httpx.TimeoutException:
            print("시간 초과: 제한 시간 안에 응답을 받지 못했어.")

        except httpx.RequestError as e:
            print(f"네트워크 연결 오류: {type(e).__name__}")

    else:
        print("\n후보 모델 모두에서 텍스트 응답을 얻지 못했어.")

finally:
    client.close()