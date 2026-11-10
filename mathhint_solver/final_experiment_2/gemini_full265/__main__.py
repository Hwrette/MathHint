"""전체265 실행과 저장 결과의 보고서·검증을 명시적으로 분리한다."""

import argparse

from .common import ROOT, OUTPUT, execution_lock


def main():
    parser = argparse.ArgumentParser(description="독립 폴더의 전체265 Gemini A/B/C/D 비교")
    parser.add_argument("action", choices=("prepare", "preflight", "generate", "report", "verify"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--max-new-requests", type=int, default=None)
    parser.add_argument("--max-run-seconds", type=float, default=None)
    parser.add_argument("--max-wait-seconds", type=float, default=None)
    parser.add_argument("--clear-stop", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        from .run import prepare
        with execution_lock(ROOT, OUTPUT):
            _, _, result, _, _ = prepare(ROOT, OUTPUT)
        print(f"전체265 준비 · 성공 재사용 {result['state']['successful_requests']}/1060 · 신규 필요 {result['state']['pending_count']}")
    elif args.action == "preflight":
        from .run import preflight
        result = preflight(ROOT, OUTPUT, offline=args.offline)
        print(f"준비 {result['expected_requests']}개 · 성공 {result['successful_saved']}개 · 신규 필요 {result['new_requests_needed']}개 · 환경 {result['api_readiness']}")
    elif args.action == "generate":
        from .run import generate
        from .report import run as report
        policy = {name: value for name, value in (("max_new_requests", args.max_new_requests),
            ("max_run_seconds", args.max_run_seconds), ("max_wait_seconds", args.max_wait_seconds)) if value is not None}
        result = generate(ROOT, OUTPUT, policy=policy, clear_stop=args.clear_stop, render_callback=report)
        print(f"상태 {result['status']} · 성공 {result['successful_requests']}/{result['expected_requests']} · 미완료 {result['pending_count']}")
    elif args.action == "report":
        from .report import run as report
        with execution_lock(ROOT, OUTPUT):
            report(ROOT, OUTPUT)
        print(f"저장 자료의 전체265 비교 화면: {OUTPUT / 'report.html'} · 재학습/API 호출 없음")
    else:
        from .verify import run as verify
        with execution_lock(ROOT, OUTPUT):
            result = verify(ROOT, OUTPUT)
        print(f"검증 {result['passed']}통과/{result['failed']}실패 · 실험 완료 {result.get('experiment_complete')}")
        if result["failed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
