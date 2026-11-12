"""준비·신규 생성·저장 결과 보고/검증을 명시적으로 분리한다."""

import argparse

from .common import ROOT, OUTPUT, execution_lock


def main():
    parser = argparse.ArgumentParser(description="5문항6조건 대조군과11오답4조건의3회 신규 반복 · 중복제거186요청")
    parser.add_argument("action", choices=("prepare", "preflight", "generate", "report", "verify"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--max-new-requests", type=int)
    parser.add_argument("--max-run-seconds", type=float)
    parser.add_argument("--max-wait-seconds", type=float)
    parser.add_argument("--clear-stop", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        from .run import prepare
        with execution_lock(ROOT, OUTPUT):
            _, _, result, _, _ = prepare(ROOT, OUTPUT)
        print(f"186개 신규 반복 준비 · API응답 {result['state']['completed_requests']} · 정상 STOP {result['state']['successful_requests']} · 미완료 {result['state']['pending_count']}")
    elif args.action == "preflight":
        from .run import preflight
        result = preflight(ROOT, OUTPUT, offline=args.offline)
        print(f"신규 계획186 · API응답 {result['completed_saved']} · 정상 STOP {result['successful_saved']} · 미완료 {result['new_requests_needed']} · 환경 {result['api_readiness']}")
    elif args.action == "generate":
        from .run import generate
        from .report import run as report
        policy = {name: value for name, value in (("max_new_requests", args.max_new_requests),
            ("max_run_seconds", args.max_run_seconds), ("max_wait_seconds", args.max_wait_seconds)) if value is not None}
        result = generate(ROOT, OUTPUT, policy=policy, clear_stop=args.clear_stop, render_callback=report)
        print(f"상태 {result['status']} · 신규 API응답 {result['completed_requests']}/186 · 정상 STOP {result['successful_requests']} · 비정상 응답 {result['incomplete_response_count']} · 미완료 {result['pending_count']}")
    elif args.action == "report":
        from .report import run as report
        with execution_lock(ROOT, OUTPUT):
            report(ROOT, OUTPUT)
        print(f"저장된 반복 결과 화면: {OUTPUT / 'report.html'} · API/학습 없음")
    else:
        from .verify import run as verify
        with execution_lock(ROOT, OUTPUT):
            result = verify(ROOT, OUTPUT)
        print(f"검증 {result['passed']}통과/{result['failed']}실패 · API완료 {result.get('experiment_complete')}")
        if result["failed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
