"""원문 재계수와 저장된 Gemini 요청으로 정보 손실·전송 토큰을 분석한다.

원본 토큰화와 직렬화 함수를 읽기 전용으로 재사용한다. 모델을 불러오거나
새 프롬프트를 전송하지 않으며, 불용어 선택·제거·재선정 기능은 포함하지 않는다.
"""

from collections import Counter, defaultdict
import json
import math
from pathlib import Path

from .common import dump_csv, dump_json, load_data, read_csv, read_json
from .roles import CATEGORIES, classify_token


ROLE_GROUPS = {
    "수학 개념 자연어": "수학 개념·명령·연산",
    "풀이 방법 자연어": "풀이 방법 자연어",
    "일반 조사·어미·연결어": "일반 조사·어미·연결어",
    "LaTeX 수학 명령어": "수학 개념·명령·연산",
    "LaTeX 변수명": "숫자·변수명",
    "LaTeX 숫자": "숫자·변수명",
    "연산·관계 기호": "수학 개념·명령·연산",
    "괄호·수식 구조 기호": "서식·수식 구조·고정 양식",
    "표시용 LaTeX 명령어": "서식·수식 구조·고정 양식",
    "해설지 고정 양식": "서식·수식 구조·고정 양식",
    "분류 불확실·검토 필요": "분류 불확실·검토 필요",
}


def restore_region(root, data, region, count_tokens):
    """모든 좌표·원래 총 토큰 수가 일치할 때만 OOV 복원으로 기록한다."""
    root = Path(root)
    vocabulary = data["vocabularies"][region]
    known = set(vocabulary)
    ignored = Counter()
    documents = defaultdict(list)
    split_summary = {}
    checks = []
    for part in ("train", "test"):
        saved = read_json(root / f"data/vectors/{region}/{part}_vectors.json")
        if [row["id"] for row in saved["documents"]] != data["ids"][part]:
            raise ValueError(f"{region}/{part}: 원래 벡터 문항 순서가 다릅니다.")
        original_total = represented_total = ignored_total = 0
        for row in saved["documents"]:
            text = (root / f"data/processed/{region}/{row['id']}.txt").read_text(encoding="utf-8-sig")
            counted = Counter(count_tokens(text))
            represented = [counted[token] for token in vocabulary]
            missing = {token: n for token, n in counted.items() if token not in known}
            total, outside = sum(counted.values()), sum(missing.values())
            if represented != row["vector"] or total != row["token_count"] or outside != row["ignored_token_count"]:
                raise ValueError(f"{region}/{part}/{row['id']}: 기존 좌표·총 토큰·제외 기록과 재계수가 다릅니다.")
            if part == "train" and outside:
                raise ValueError(f"{region}/{row['id']}: 학습 원문에 학습 어휘 밖 토큰이 있습니다.")
            original_total += total
            represented_total += sum(represented)
            ignored_total += outside
            checks.append({"region": region, "split": part, "id": row["id"],
                           "original_token_count": total, "represented_token_count": sum(represented),
                           "excluded_token_count": outside, "all_original_coordinates_match": True})
            if part == "test":
                ignored.update(missing)
                for token in missing:
                    documents[token].append(row["id"])
        split_summary[part] = {"n": len(saved["documents"]), "total_tokens": original_total,
                               "represented_tf": represented_total, "ignored_tf": ignored_total,
                               "ignored_fraction": ignored_total / original_total if original_total else None}
    rows = []
    for token, n in sorted(ignored.items(), key=lambda pair: (-pair[1], pair[0])):
        description = classify_token(token, region=region)
        rows.append({"region": region, "token": token, **description,
                     "total_tf": n, "total_df": len(documents[token]),
                     "document_ids": ",".join(documents[token]),
                     "absence_reason": "기존 학습185문항에는 등장하지 않고 테스트 원문에서 처음 등장; 학습 전용 고정 어휘에 포함되지 않음"})
    summary = {**split_summary["test"], "test_total_tokens": split_summary["test"]["total_tokens"],
               "unique_oov_tokens": len(ignored), "oov_documents": len({identifier for values in documents.values() for identifier in values}),
               "train": split_summary["train"], "test": split_summary["test"],
               "all_original_coordinates_match": True,
               "requested_examples": {token: {"in_existing_vocabulary": token in known,
                                               "oov_tf": ignored[token], "oov_df": len(documents[token])}
                                      for token in (r"latex:\gamma", r"latex:\log", r"latex:\circ")}}
    return rows, checks, summary


def build_oov(root, output, data):
    # This is the original tokenizer factory, with its original model and worker settings.
    from mathhint_analysis.PrepareDataset import _count_function
    counter = _count_function()
    expected = read_json(Path(root) / "data/vectors/report.json")["tokenizer"]
    if counter.tokenizer_info != expected:
        raise ValueError(f"OOV 복원 토큰화 버전·설정 불일치: 저장={expected}, 현재={counter.tokenizer_info}")
    rows, checks, regions = [], [], {}
    for region in ("problems", "solutions"):
        result, verified, summary = restore_region(root, data, region, counter)
        rows.extend(result)
        checks.extend(verified)
        regions[region] = summary
    output = Path(output) / "03_oov_analysis"
    dump_csv(output / "excluded_tokens.csv", rows,
             fields=["region", "token", "source", "category", "total_tf", "total_df", "document_ids",
                     "meaning", "absence_reason", "ambiguity_note", "information_loss_if_removed"])
    dump_csv(output / "recount_validation.csv", checks)
    summary = {"tokenizer": expected, "regions": regions,
               "recounted_documents": len(checks), "all_original_coordinates_and_counts_match": True,
               "fraction_denominator": "all test tokens before vocabulary filtering = represented TF + ignored TF",
               "vocabulary_extended": False, "tokenizer_changed": False}
    dump_json(output / "summary.json", summary)
    return summary


def positive_top_indices(values, k=20):
    """기존 벡터 상위20의 분석용 재구성: 양수·반올림 전·어휘 인덱스 동률."""
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in values):
        raise ValueError("상위 토큰 분석에는 유한 실수 벡터가 필요합니다.")
    return sorted((i for i, value in enumerate(values) if value > 0),
                  key=lambda i: (-values[i], i))[:k]


def check_request(root, data, identifier, condition, values):
    """기존 저장 요청의 전체 텍스트·해시·값을 원래 직렬화 규칙과 대조한다."""
    from mathhint_solver.CompareGeneration import digest
    from mathhint_solver.ThreeWayGeneration import serialize_vector
    vocabulary = data["vocabularies"]["solutions"]
    source = "regression_prediction" if condition == "B" else "actual_reference"
    method = "regression_hint" if condition == "B" else "oracle_hint"
    path = Path(root) / f"results/final_experiment/03_gemini/prompt_audit/requests/{identifier}/{condition}.json"
    request = read_json(path)
    text = (Path(root) / f"data/processed/problems/{identifier}.txt").read_text(encoding="utf-8-sig")
    suffix, hint = serialize_vector(vocabulary, values, source=source)
    user_text = text + suffix
    if (request["id"] != identifier or request["condition"] != condition or request["method"] != method
            or request["generation_id"] != data["generation_id"] or request["problem_text"] != text
            or request["hint"] != hint or request["user_message"] != user_text
            or request["input_sha256"] != digest(user_text)
            or request["sdk_request"]["contents"] != user_text
            or request["sdk_request"]["model"] != request["requested_model"]
            or request["sdk_request"]["config"]["system_instruction"] != request["system_instruction"]
            or request["sdk_request_sha256"] != digest(request["sdk_request"])
            or request["full_request_text"] != "[SYSTEM]\n" + request["system_instruction"] + "\n[USER]\n" + user_text):
        raise ValueError(f"{path}: 실제 요청·직렬화·ID·해시가 원본 벡터와 일치하지 않습니다.")
    if list(request["hint"]["mapping"]) != list(hint["mapping"]):
        raise ValueError(f"{path}: 실제 토큰 순서가 원래 전송 규칙과 다릅니다.")
    return request, path


def build_top20(root, output, data):
    root, output = Path(root), Path(output) / "02_solution_tokens"
    saved = read_json(root / "results/final_experiment/02_regression/vectors.json")
    vocabulary = data["vocabularies"]["solutions"]
    if saved["vocabulary"] != vocabulary or [r["id"] for r in saved["documents"]] != data["ids"]["test"]:
        raise ValueError("저장된 회귀 해설 벡터의 어휘·테스트 행 순서가 다릅니다.")
    existing = {row["id"]: row for row in read_csv(root / "results/final_experiment/02_regression/question_comparison.csv")}
    # Link the saved prompt to the successful response, and to contemporaneous C
    # boundary captures where available. Historical B has no retroactive capture.
    response_path = root / "results/final_experiment/03_gemini/responses.jsonl"
    responses, captures = {}, defaultdict(list)
    if response_path.exists():
        for line in response_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("status") == "success":
                responses[(row["id"], row["method"])] = row
        for path in (response_path.parent / "prompt_audit/sdk_calls").glob("*.json"):
            capture = read_json(path)
            captures[(capture["id"], capture["condition"])].append(capture)
    elif len(data["ids"]["test"]) == 80:
        raise FileNotFoundError(f"실제80문항의 원본 전송·응답 연결 근거가 없습니다: {response_path}")
    tokens, comparisons = [], []
    token_docs, token_sums = defaultdict(set), Counter()
    categories, groups, category_docs = Counter(), Counter(), defaultdict(set)
    selected_before_rounding = []
    for number, document in enumerate(saved["documents"]):
        identifier = document["id"]
        actual, raw, clipped = document["actual_vector"], document["raw_predicted_vector"], document["predicted_vector"]
        if (actual != data["arrays"]["solutions"]["test"][number].tolist()
                or len(raw) != len(vocabulary) or clipped != [max(0., value) for value in raw]):
            raise ValueError(f"{identifier}: 원본 실제 벡터 또는 음수 보정 실수 예측과 다릅니다.")
        selections = {"B": positive_top_indices(clipped), "C": positive_top_indices(actual)}
        common = len(set(selections["B"]) & set(selections["C"]))
        source = existing[identifier]
        if (common != int(source["common_top20_count"]) or common / 20 != float(source["precision_at_20"])
                or len(selections["B"]) != int(source["predicted_top_count"])
                or len(selections["C"]) != int(source["actual_top_count"])):
            raise ValueError(f"{identifier}: 기존 상위20 일치도와 분석 재계산이 다릅니다.")
        requests, mappings = {}, {}
        for condition, values in (("B", clipped), ("C", actual)):
            request, path = check_request(root, data, identifier, condition, values)
            if responses:
                response = responses.get((identifier, request["method"]), {})
                old_hint = response.get("hint") or {}
                # Reconstructed B audit records add a provenance-only source field
                # that was absent from the original successful response metadata.
                hint_matches = (all(old_hint.get(key) == value for key, value in request["hint"].items() if key != "source")
                                and old_hint.get("source") in (None, request["hint"].get("source")))
                if (response.get("input_text") != request["user_message"]
                        or response.get("input_sha256") != request["input_sha256"]
                        or not hint_matches):
                    raise ValueError(f"{identifier}/{condition}: 저장 요청과 원본 성공 응답의 입력·토큰이 다릅니다.")
                if condition == "C" and not captures[(identifier, condition)]:
                    raise ValueError(f"{identifier}/C: 원래 실전송 직전 SDK 캡처가 없습니다.")
                for capture in captures[(identifier, condition)]:
                    if (capture["request"] != request["sdk_request"]
                            or capture["request_sha256"] != request["sdk_request_sha256"]):
                        raise ValueError(f"{identifier}/{condition}: 실전송 SDK 캡처가 저장 입력과 다릅니다.")
            requests[condition] = (request, path)
            mappings[condition] = request["hint"]["mapping"]
        transmitted_common = len(set(mappings["B"]) & set(mappings["C"]))
        for condition, values in (("B", clipped), ("C", actual)):
            request, path = requests[condition]
            mapping = mappings[condition]
            group_counts = Counter()
            for rank, (token, value) in enumerate(mapping.items(), 1):
                index = vocabulary.index(token)
                role = classify_token(token, region="solutions")
                group = ROLE_GROUPS[role["category"]]
                tokens.append({"id": identifier, "condition": condition, "rank": rank, "index": index,
                               "token": token, "transmitted_value": value, "unrounded_value": values[index],
                               **role, "role_group": group,
                               "request_path": path.relative_to(root).as_posix(), "input_sha256": request["input_sha256"]})
                token_docs[(condition, token)].add(identifier)
                token_sums[(condition, token)] += value
                categories[(condition, role["category"])] += 1
                groups[(condition, group)] += 1
                category_docs[(condition, role["category"])].add(identifier)
                group_counts[group] += 1
            for rank, index in enumerate(selections[condition], 1):
                token = vocabulary[index]
                selected_before_rounding.append({"id": identifier, "condition": condition, "rank": rank,
                    "index": index, "token": token, "unrounded_value": values[index],
                    "transmitted": token in mapping, "transmitted_value": mapping.get(token)})
            comparisons.append({"id": identifier, "condition": condition, "method": request["method"],
                "transmitted_count": len(mapping), "vector_top20_count": len(selections[condition]),
                "omitted_after_rounding": len(selections[condition]) - len(mapping),
                "common_bc_transmitted": transmitted_common, "common_vector_top20": common,
                "vector_precision_at_20": common / 20,
                "transmitted_bc_jaccard": transmitted_common / len(set(mappings["B"]) | set(mappings["C"]))
                    if mappings["B"] or mappings["C"] else None,
                **{f"{name}_coordinate_fraction": group_counts[name] / len(mapping) if mapping else None
                   for name in dict.fromkeys(ROLE_GROUPS.values())},
                "source_request": path.relative_to(root).as_posix(), "input_sha256": request["input_sha256"],
                "request_and_original_serialization_match": True,
                "original_success_response_input_verified": bool(responses),
                "contemporaneous_sdk_capture_count": len(captures[(identifier, condition)])})
    totals = {condition: sum(n for (code, _), n in categories.items() if code == condition) for condition in ("B", "C")}
    count = len(data["ids"]["test"])
    frequency = [{"condition": code, "index": vocabulary.index(token), "token": token,
                  **classify_token(token, region="solutions"), "document_count": len(identifiers),
                  "request_count": count, "document_fraction": len(identifiers) / count,
                  "coordinate_share": len(identifiers) / totals[code], "transmitted_value_sum": token_sums[(code, token)]}
                 for (code, token), identifiers in sorted(token_docs.items(), key=lambda item: (item[0][0], -len(item[1]), vocabulary.index(item[0][1])))]
    composition = [{"condition": code, "category": category, "role_group": ROLE_GROUPS[category],
                    "coordinate_count": categories[(code, category)], "total_coordinates": totals[code],
                    "coordinate_fraction": categories[(code, category)] / totals[code] if totals[code] else None,
                    "requests_with_category": len(category_docs[(code, category)]), "request_count": count}
                   for code in ("B", "C") for category in CATEGORIES]
    grouped = {code: {group: {"coordinates": groups[(code, group)],
                             "fraction": groups[(code, group)] / totals[code] if totals[code] else None}
                      for group in dict.fromkeys(ROLE_GROUPS.values())} for code in ("B", "C")}
    dump_csv(output / "top20_analysis.csv", comparisons)
    dump_csv(output / "transmitted_tokens.csv", tokens)
    dump_csv(output / "vector_top20.csv", selected_before_rounding)
    dump_csv(output / "top20_token_frequency.csv", frequency)
    dump_csv(output / "top20_category_composition.csv", composition)
    summary = {"request_count": len(comparisons), "questions_per_condition": count,
               "transmitted_coordinates": totals, "role_groups": grouped,
               "mean_common_vector_top20": sum(r["common_vector_top20"] for r in comparisons) / len(comparisons),
               "mean_vector_precision_at_20": sum(r["vector_precision_at_20"] for r in comparisons) / len(comparisons),
               "mean_common_transmitted_top20": sum(r["common_bc_transmitted"] for r in comparisons) / len(comparisons),
               "omitted_after_rounding": sum(r["omitted_after_rounding"] for r in comparisons),
               "all_original_requests_and_serialization_match": True,
               "all_original_regression_top20_overlap_matches": True,
               "successful_response_inputs_verified": len(comparisons) if responses else 0,
               "contemporaneous_sdk_capture_request_pairs": sum(bool(captures[(r["id"], r["condition"])]) for r in comparisons),
               "contemporaneous_sdk_capture_files_verified": sum(len(captures[(r["id"], r["condition"])]) for r in comparisons),
               "composition_denominator": "Number of actually transmitted token coordinates, not sum of frequency values or API tokens",
               "value_sum_note": "B is a rounded regression estimate and C is a true count. Value sums are not API token usage and do not measure information value.",
               "historical_audit_limit": "A/B requests were reconstructed and exact-input-verified; C also has contemporaneous SDK capture. No new SDK calls were made.",
               "interpretation_limit": "Role labels and coordinate proportions describe the old inputs; they do not establish causal hint usefulness or invalidate alternative correct solutions.",
               "new_api_calls": 0, "model_loads": 0, "stopword_filtered_reselection": False}
    dump_json(output / "top20_summary.json", summary)
    return summary


def build_evidence(root, output):
    """원본은 읽기만 하고 이번 분석 폴더의 표와 요약만 만든다."""
    data = load_data(root)
    return {"oov": build_oov(root, output, data), "top20": build_top20(root, output, data)}
