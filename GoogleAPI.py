import os
import re
from pathlib import Path

from google import genai
from google.genai import errors, types

# 풀고 싶은 텍스트 파일명을 여기에서 지정한다.
# 상대 경로는 GoogleAPI.py가 있는 폴더를 기준으로 찾는다.
# 예: "problem.txt", "outputs/문제1.txt", "/Users/hwrette/Desktop/문제1.txt"
PROBLEM_FILE = "outputs/run01/로그계산_삼각함수각변환/problems/001.txt"
MODEL = "gemini-3.1-flash-lite"
THINKING_LEVEL = "minimal"

# 이 부분이 풀이 방식과 출력 형식을 정하는 프롬프트
SYSTEM_PROMPT = """
이 문제 풀어줘
"""


def format_token_count(usage, field):
    count = getattr(usage, field, None)
    return "미제공" if count is None else f"{count:,}"


def to_math_markdown(text):
    """보기용 복사본에서 LaTeX 수식 구분자를 VS Code 형식으로 맞춘다."""
    pattern = re.compile(
        r"(?P<code>```[\s\S]*?```|~~~[\s\S]*?~~~|(?P<ticks>`+)[^\n]*?(?P=ticks))"
        r"|(?P<existing_math>\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\$)(?:\\.|[^$\\\n])+\$)"
        r"|(?<!\\)\\\[(?P<display>[\s\S]*?)\\\]"
        r"|(?<!\\)\\\((?P<inline>[\s\S]*?)\\\)"
    )

    def replace(match):
        display = match.group("display")
        if display is not None and display.strip():
            return "\n\n$$\n" + display.strip() + "\n$$\n\n"
        inline = match.group("inline")
        if inline is not None and inline.strip():
            return "$" + inline.strip() + "$"
        # 코드와 이미 $...$ 또는 $$...$$로 감싼 수식은 그대로 둔다.
        return match.group(0)

    return pattern.sub(replace, text)


def main():
    script_dir = Path(__file__).resolve().parent
    problem_path = Path(PROBLEM_FILE).expanduser()
    if not problem_path.is_absolute():
        problem_path = script_dir / problem_path
    problem_path = problem_path.resolve()

    # 원본 텍스트와 수식 미리보기용 Markdown을 나란히 저장한다.
    output_dir = script_dir / "풀이생성"
    output_path = output_dir / f"{problem_path.stem}_문제와풀이.txt"
    markdown_path = output_path.with_suffix(".md")

    if not problem_path.is_file():
        raise SystemExit(f"문제 파일을 찾을 수 없어: {problem_path}")

    try:
        problem = problem_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as e:
        raise SystemExit(f"문제 파일을 UTF-8 텍스트로 읽을 수 없어: {e}")

    if not problem.strip():
        raise SystemExit(f"문제 파일이 비어 있어: {problem_path}")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY 환경변수를 설정해 줘.")

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
                model=MODEL,
                contents=problem,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=THINKING_LEVEL,
                    ),
                ),
            )

    except errors.APIError as e:
        raise SystemExit(f"API 오류 {e.code}: {e.message}")

    answer = response.text
    if not answer or not answer.strip():
        raise SystemExit("텍스트 응답이 없어. 풀이를 저장하지 않았어.")

    # API가 반환한 실제 사용량을 기록한다. 누락된 값은 0으로 추정하지 않는다.
    usage = getattr(response, "usage_metadata", None)
    separator = "=" * 60
    metadata = (
        f"모델: {MODEL} | 추론 수준: {THINKING_LEVEL}\n"
        f"입력 파일: {problem_path.name}\n"
        f"입력 토큰: {format_token_count(usage, 'prompt_token_count')}\n"
        f"추론 토큰: {format_token_count(usage, 'thoughts_token_count')}\n"
        f"생성 토큰(답변): {format_token_count(usage, 'candidates_token_count')}\n"
        f"전체 토큰: {format_token_count(usage, 'total_token_count')}\n"
    )
    result = (
        f"{metadata}\n"
        f"{separator}\n입력 문제\n{separator}\n"
        f"{problem}\n\n"
        f"{separator}\n출력 풀이\n{separator}\n"
        f"{answer}\n"
    )

    markdown_metadata = "\n".join(f"- {line}" for line in metadata.splitlines())
    markdown_result = (
        f"{markdown_metadata}\n\n"
        "---\n\n"
        "## 입력 문제\n\n"
        f"{to_math_markdown(problem).strip()}\n\n"
        "## 출력 풀이\n\n"
        f"{to_math_markdown(answer).strip()}\n"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8")
    markdown_path.write_text(markdown_result, encoding="utf-8")
    print("\n" + result)
    print(f"\n저장 완료: {output_path}")
    print(f"수식 미리보기: {markdown_path}")


if __name__ == "__main__":
    main()
