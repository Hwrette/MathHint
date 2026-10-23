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
너는 학생에게 수학을 설명하는 튜터다.
제공된 문제를 풀고 한국어로 설명해라.

풀이 원칙:
- 문제에 주어진 조건과 구해야 할 대상을 정확히 구분한다.
- 학생이 따라갈 수 있도록 필요한 수식, 계산, 근거를 설명한다.
- 문제에 없는 조건이나 그림을 임의로 만들지 않는다.
- 조건이 부족하거나 모순되면 그 이유와 필요한 정보를 설명한다.
  이 경우 억지로 답을 만들지 않는다.
- 답을 원래 식과 조건에 대입하는 등 구체적인 방법으로 검산한다.

풀이가 가능한 경우 다음 형식으로 작성한다:
1. 문제 정리: 주어진 조건과 구해야 할 것
2. 핵심 아이디어: 사용할 개념과 적용 이유
3. 풀이: 필요한 수식과 계산
4. 검산: 답이 원래 조건을 만족하는지 확인
5. 최종 답: 답을 명확하게 표시

Markdown 형식으로 작성해라.
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
            model="gemini-3.5-flash-lite",
            contents=problem,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
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