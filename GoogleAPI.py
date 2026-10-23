import os
from pathlib import Path

from google import genai
from google.genai import errors, types

# 실행하는 터미널 위치와 관계없이 이 파일의 폴더를 기준으로 읽기
import argparse

parser = argparse.ArgumentParser(description="텍스트 파일의 수학 문제 풀이")
parser.add_argument("problem_file", type=Path, help="문제가 들어 있는 텍스트 파일")
args = parser.parse_args()

problem_path = args.problem_file.expanduser().resolve()

# 문제1.txt → 문제1_solution.md
output_path = problem_path.with_name(
    f"{problem_path.stem}_solution.md"
)


if not problem_path.is_file():
    raise SystemExit(f"문제 파일을 찾을 수 없어: {problem_path}")

problem = problem_path.read_text(encoding="utf-8-sig").strip()

if not problem:
    raise SystemExit("problem.txt에 문제를 입력해 줘.")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("GEMINI_API_KEY 환경변수를 설정해 줘.")

# 이 부분이 풀이 방식과 출력 형식을 정하는 프롬프트
SYSTEM_PROMPT = """
이 문제 풀어줘
"""

print(f"문제 파일: {problem_path}")
print("풀이 요청 중...", flush=True)

try:
    with genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=90_000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    ) as client:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=problem,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                thinking_config=types.ThinkingConfig(
                    thinking_level="minimal",
                ),
            ),
        )

except errors.APIError as e:
    raise SystemExit(f"API 오류 {e.code}: {e.message}")

answer = response.text
if not answer:
    raise SystemExit("텍스트 응답이 없어. 풀이를 저장하지 않았어.")

print("\n" + answer)

output_path.write_text(answer, encoding="utf-8")
print(f"\n저장 완료: {output_path}")