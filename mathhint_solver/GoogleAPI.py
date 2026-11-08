"""한 문제를 Gemini에 보내고 입력·풀이·실제 토큰 사용량을 저장한다.

상단의 문제 경로와 모델 설정을 바꾼 뒤 실행한다. 실행하면 API를 호출한다.
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
import re
from uuid import uuid4

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types


ROOT = Path(__file__).resolve().parents[1]
PROBLEM_FILE = "data/processed/problems/diff_1_005.txt"
OUTPUT = ROOT / "outputs/solutions"
MODEL = "gemini-3.1-flash-lite"
THINKING_LEVEL = "minimal"
SYSTEM_PROMPT = """
이 문제 풀어줘
"""
USAGE_LABELS = {
    "prompt_token_count": "입력 토큰",
    "thoughts_token_count": "추론 토큰",
    "candidates_token_count": "생성 토큰(답변)",
    "total_token_count": "전체 토큰",
}


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
    # 1. 문제와 로컬 API 키 읽기
    load_dotenv(ROOT / ".env", override=False)
    problem_path = Path(PROBLEM_FILE).expanduser()
    if not problem_path.is_absolute():
        problem_path = ROOT / problem_path
    problem_bytes = problem_path.read_bytes()
    problem = problem_bytes.decode("utf-8-sig")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise SystemExit(".env 또는 환경변수에 GEMINI_API_KEY를 설정해 줘.")
    if not problem.strip():
        raise SystemExit("문제 파일이 비어 있어.")

    # 2. 풀이 생성 — SDK 내부 재시도 없이 요청 한 번의 사용량을 기록한다.
    print(f"문제 파일: {problem_path}", flush=True)
    try:
        with genai.Client(api_key=key, http_options=types.HttpOptions(
                timeout=90_000, retry_options=types.HttpRetryOptions(attempts=1))) as client:
            response = client.models.generate_content(
                model=MODEL, contents=problem,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL)))
    except errors.APIError as error:
        raise SystemExit(f"API 오류 {error.code}: {error.message}".replace(key, "[REDACTED]")) from None
    answer = response.text
    if not answer or not answer.strip():
        raise SystemExit("텍스트 응답이 없어. 풀이를 저장하지 않았어.")

    # 3. 미제공 사용량은 null로 남긴다.
    usage = {field: getattr(response.usage_metadata, field, None) for field in USAGE_LABELS}
    lines = [f"모델: {MODEL} | 추론 수준: {THINKING_LEVEL}", f"입력 파일: {problem_path.name}"]
    for field, label in USAGE_LABELS.items():
        count = "미제공" if usage[field] is None else f"{usage[field]:,}"
        lines.append(f"{label}: {count}")
    metadata = "\n".join(lines)
    plain = f"{metadata}\n\n입력 문제\n{problem}\n\n출력 풀이\n{answer}\n"
    markdown = "\n".join("- " + line for line in lines)
    markdown += f"\n\n## 입력 문제\n\n{to_math_markdown(problem).strip()}"
    markdown += f"\n\n## 출력 풀이\n\n{to_math_markdown(answer).strip()}\n"

    # 같은 번호를 가진 다른 자료와 여러 실행을 별도 폴더로 보존한다.
    created_at = datetime.now().astimezone()
    source_id = hashlib.sha256(str(problem_path.parent.resolve()).encode()).hexdigest()[:8]
    run_id = f"{created_at:%Y%m%d_%H%M%S_%f}_{uuid4().hex[:8]}"
    output = OUTPUT / source_id / problem_path.stem / run_id
    output.mkdir(parents=True)
    record = {
        "created_at": created_at.isoformat(), "input_file": str(problem_path),
        "input_sha256": hashlib.sha256(problem_bytes).hexdigest(),
        "model": MODEL, "model_version": getattr(response, "model_version", None),
        "thinking_level": THINKING_LEVEL, "system_prompt": SYSTEM_PROMPT, "usage": usage,
        "files": {"input": "input.txt", "text": "solution.txt", "markdown": "solution.md"},
    }
    (output / "input.txt").write_bytes(problem_bytes)
    (output / "solution.txt").write_text(plain, encoding="utf-8")
    (output / "solution.md").write_text(markdown, encoding="utf-8")
    (output / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"저장 완료: {output}")


if __name__ == "__main__":
    main()
