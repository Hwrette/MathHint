"""학습185/테스트80 고정 분리 군집화의 전용 실행 코드."""

from pathlib import Path


def preserve_navigation(path, generated):
    """보고서 재생성 때 명시적으로 추가한 군집 안내만 보존한다."""
    path = Path(path)
    start, end = "<!-- clustering-additions:start -->", "<!-- clustering-additions:end -->"
    saved = path.read_text(encoding="utf-8") if path.exists() else ""
    if start not in saved or end not in saved:
        return generated
    block = start + saved.split(start, 1)[1].split(end, 1)[0] + end
    heading, rest = generated.split("\n", 1)
    return heading + "\n\n" + block + "\n" + rest
