"""명시적 preflight/generate와 저장 자료 전용 report/verify를 구분한다."""

import argparse

from .common import ROOT, OUTPUT, safe_output, read_json


def main():
    parser = argparse.ArgumentParser(description="확정 선형/MLP 모델의 Gemini A/B/C/D 비교")
    parser.add_argument("action", choices=("preflight", "generate", "report", "verify"))
    parser.add_argument("--split", choices=("test", "train"), default="test")
    parser.add_argument("--offline", action="store_true", help="preflight 입력·모의 SDK 감사만, 네트워크 호출 없음")
    parser.add_argument("--max-new-requests", type=int, default=None)
    parser.add_argument("--max-run-seconds", type=float, default=None)
    parser.add_argument("--max-wait-seconds", type=float, default=None)
    parser.add_argument("--clear-stop", action="store_true", help="generate를 재개할 때 명시적으로 중단 파일 해제")
    args = parser.parse_args()
    output = safe_output(ROOT)
    if args.action == "preflight":
        from .run import preflight
        result = preflight(ROOT, output, split=args.split, offline=args.offline)
        print(f"요청 준비 {result['expected_requests']}개 · 저장 성공 {result['successful_saved']}개 · 신규 필요 {result['new_requests_needed']}개 · API 환경 {result['api_readiness']}")
    elif args.action == "generate":
        from .run import generate
        from .report import run as report
        policy = {field: value for field, value in (("max_new_requests", args.max_new_requests),
                   ("max_run_seconds", args.max_run_seconds), ("max_wait_seconds", args.max_wait_seconds)) if value is not None}
        result = generate(ROOT, output, split=args.split, policy=policy,
                          clear_stop=args.clear_stop, render_callback=report)
        print(f"상태 {result['status']} · 성공 {result['successful_requests']}/{result['expected_requests']} · 미완료 {result['pending_count']}")
    else:
        target = output / "extension_train185" if args.split == "train" else output
        if args.action == "report":
            from .report import run as report
            report(ROOT, target)
            print(f"저장된 결과의 읽기 화면: {target / 'report.html'} · 재학습/API 호출 없음")
        else:
            from .verify import run as verify
            result = verify(ROOT, target)
            print(f"검증 {result['passed']}개 통과 · {result['failed']}개 실패 · 성공 {result['successful_requests']}/{result['expected_requests']}")
            if result["failed"]:
                raise SystemExit(1)


if __name__ == "__main__":
    main()
