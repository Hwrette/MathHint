"""저장된 CSV를 읽어 η² 순위 Markdown 5개만 만든다. 통계를 다시 계산하지 않는다."""

import csv
from decimal import Decimal
from html import escape
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LEVELS = {"curriculum": "과목", "unit": "단원", "subunit": "세부단원", "type": "문제 유형"}


def _csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _eta(text):
    value = Decimal(text) if text.strip() else None
    if value is not None and not value.is_finite():
        raise ValueError("정의되지 않는 η²는 CSV의 빈 값으로 표시해야 합니다.")
    return value


def _same(a, b):
    # 두 기존 CSV에 남아 있는 부동소수점의 마지막 자리 차이만 허용한다.
    return a is None and b is None or a is not None and b is not None and abs(a - b) <= Decimal("1e-12")


def read_rankings(root=ROOT):
    base = Path(root) / "results/token_analysis"
    problem = base / "01_problem_tokens"
    tokens = _csv(problem / "all_tokens.csv")
    keys = {int(row["index"]): row for row in _csv(problem / "key_token_statistics.csv")}
    raw = _csv(problem / "variance_by_classification.csv")
    normalized = _csv(base / "04_distance_comparison/normalized_eta_comparison.csv")
    vocabulary = json.loads((Path(root) / "data/vectors/problems/vocabulary.json").read_text(encoding="utf-8"))
    expected = {(level, index) for level in LEVELS for index in range(346)}
    if ([int(row["index"]) for row in tokens] != list(range(346))
            or [row["token"] for row in tokens] != vocabulary or len(keys) != 346
            or len(raw) != 1384 or len(normalized) != 1384):
        raise ValueError("기존 346개 토큰·인덱스·4수준 CSV의 크기가 다릅니다.")
    raw_by_key = {(row["level"], int(row["index"])): row for row in raw}
    normalized_by_key = {(row["level"], int(row["index"])): row for row in normalized}
    if set(raw_by_key) != expected or set(normalized_by_key) != expected:
        raise ValueError("분류 수준·토큰 인덱스에 누락이나 중복이 있습니다.")
    result = {}
    for level in LEVELS:
        result[level] = []
        for index, token in enumerate(tokens):
            a, b, key = raw_by_key[level, index], normalized_by_key[level, index], keys[index]
            original, normal = _eta(a["eta_squared"]), _eta(b["normalized_eta_squared"])
            if (any(row["token"] != token["token"] for row in (a, b, key))
                    or any(int(row["n"]) != 185 or int(row["train_df"]) != int(token["train_df"]) for row in (a, b))
                    or not _same(original, _eta(b["original_eta_squared"]))
                    or not _same(original, _eta(key[level + "_eta_squared"]))
                    or token["meaning"] != b["meaning"] or token["meaning"] != key["meaning"]):
                raise ValueError(f"기존 CSV의 토큰·η²·DF·의미가 서로 다릅니다: {level}/{index}")
            result[level].append({"index": index, "token": token["token"], "raw": original,
                                  "normalized": normal, "df": int(token["train_df"]), "meaning": token["meaning"],
                                  "group_count": int(a["group_count"]), "singleton_groups": int(a["singleton_groups"])})
    return result


def sorted_rows(rows, field):
    return sorted(rows, key=lambda row: (row[field] is None, -row[field] if row[field] is not None else 0, row["index"]))


def _table(rows, *, df_label="학습 DF"):
    lines = [f"|순위|토큰|원시 η²|정규화 η²|{df_label}|의미|", "|---:|---|---:|---:|---:|---|"]
    for rank, row in enumerate(rows, 1):
        token = "`" + row["token"].replace("|", "\\|") + "`"
        meaning = escape(row["meaning"], quote=False).replace("|", "\\|").replace("\n", " ")
        raw, normal = ("—" if row[field] is None else f"{row[field]:.4f}" for field in ("raw", "normalized"))
        lines.append(f"|{rank}|{token}|{raw}|{normal}|{row['df']}|{meaning}|")
    return lines


def ranking_sections(rows, *, df_label="학습 DF"):
    lines = []
    for field, anchor, title in (("raw", "raw-ranking", "A. 원시 BoW η² 내림차순"),
                                 ("normalized", "normalized-ranking", "B. L2 정규화 BoW η² 내림차순")):
        ordered = sorted_rows(rows, field)
        lines += [f'<a name="{anchor}"></a>', "", f"## {title}", "", "### 상위 30개", "", *_table(ordered[:30], df_label=df_label), "",
                  "<details>", f"<summary>전체 {len(rows)}개 토큰 펼치기 — {title}</summary>", "", *_table(ordered, df_label=df_label), "", "</details>", "",
                  "[문서 처음으로](#top) · [원시 순위](#raw-ranking) · [정규화 순위](#normalized-ranking)", ""]
    return lines


def _document(level, name, rows):
    lines = [f"# {name} 기준 · 전체 346개 문제 토큰의 η² 순위", "",
             "학습 **185문항·고정 문제 어휘346개**의 기존 CSV를 표시한 자료다. 새로운 통계 계산이나 토큰 선택은 하지 않았다.", "",
             "[A. 원시 η² 순위](#raw-ranking) · [B. 정규화 η² 순위](#normalized-ranking) · [다른 분류 선택](README.md)", "",
             "정렬은 **반올림 전 CSV 값**의 내림차순, 완전 동점은 기존 어휘 인덱스 순서다. 표시값이 같아도 실제 값은 다를 수 있다. 정의되지 않은 값은 —로 표시해 맨 아래에 둔다.", "",
             "DF는 토큰이 등장한 학습 문항 수다. η²는 불용어 판정·수학적 중요도·ARI·정답률이 아니며, 아래 [해석 주의사항](#interpretation)을 함께 읽는다.", ""]
    lines += ranking_sections(rows)
    lines += ['<a name="interpretation"></a>', "", "## 해석 주의사항", "",
              f"학습 집단은 **{rows[0]['group_count']}개**, 그중 문항1개인 집단은 **{rows[0]['singleton_groups']}개**다. DF는 해당 토큰이 한 번 이상 등장한 학습 문항 수이며, 총 등장 횟수(TF)가 아니다.", "",
              "η²는 이 자료에서 실제 분류와 토큰 빈도의 연관성을 나타낸다. 낮다고 불용어가 되거나 높다고 수학적으로 중요한 토큰이 되는 것은 아니다. 제거 시 잃는 정보는 사용자가 의미·문맥과 함께 판단한다. η²는 K-means ARI나 정답률도 아니다. 특히 유형70개에는 문항1개인 집단이 많아 높은 η²를 과대해석하지 않는다.", "",
              "소수점4자리는 표시용이며 CSV는 원본 정밀도를 그대로 보존한다. 표시값이 같아도 반올림 전 값이 다르면 인덱스 순서가 아닐 수 있다.", "",
              "## 원본 자료", "",
              "원시 η²의 기준은 [분산 분해 CSV](../variance_by_classification.csv)의 eta_squared이며, 정규화 η²는 [정규화 비교 CSV](../../04_distance_comparison/normalized_eta_comparison.csv)의 normalized_eta_squared다. 기존 CSV 간 원시 η²의 마지막 자리 차이는 검증 시 허용하되 정렬에는 기준 CSV의 값을 그대로 사용한다.", "",
              "[토큰 인덱스·학습 DF·의미](../all_tokens.csv) · [기존 핵심 토큰 표](../key_token_statistics.csv) · [조정η²·집단 크기 등의 해석](../README.md)", ""]
    return '<a name="top"></a>\n\n' + "\n".join(lines)


def build_rankings(root=ROOT):
    data = read_rankings(root)
    output = Path(root) / "results/token_analysis/01_problem_tokens/eta_rankings"
    output.mkdir(parents=True, exist_ok=True)
    for level, name in LEVELS.items():
        (output / f"{level}.md").write_text(_document(level, name, data[level]), encoding="utf-8")
    lines = ["# η² 순위표 · 전체 346개 문제 토큰", "",
             "**분류를 선택한 뒤 원시·정규화 순위를 비교하세요.** 각 문서에서 상위30개를 먼저 보고, 접힌 영역을 펼치면 전체346개를 확인할 수 있다. GitHub 파일 페이지에서 바로 읽으며, 별도 프로그램이나 CSV 다운로드가 필요 없다. 좁은 화면에서는 표를 좌우로 밀어 나머지 열을 읽는다.", "",
             "|분류 수준|원시 BoW η² 내림차순|L2 정규화 η² 내림차순|", "|---|---|---|"]
    for level, name in LEVELS.items():
        lines.append(f"|{name}|[원시 순위]({level}.md#raw-ranking)|[정규화 순위]({level}.md#normalized-ranking)|")
    lines += ["", "두 표 모두 **원시 η²·정규화 η²·학습 DF·의미**를 나란히 표시한다. 소수점4자리는 표시용이며, 저장된 CSV와 내부 정렬 값의 정밀도는 바꾸지 않았다. 같은 표시값이라도 반올림 전 값이 다르면 순서가 다를 수 있고, 완전 동점은 기존 어휘 인덱스 순서다. 정의되지 않은 η²는 —로 표시해 맨 아래에 둔다.", "",
              "분석 대상은 기존 학습185문항의 문제 어휘346개다. 과목은 curriculum이며, 단원·세부단원·유형은 기존 상위 분류를 포함한 계층 경로를 사용한 통계를 그대로 읽었다. subject 자료군과 혼동하지 않는다.", "",
              "η²가 낮다는 이유로 불용어를 자동 선정하지 않는다. 높은 값도 수학적 중요성을 확정하지 않으며, 유형70개 중43개는 학습 문항1개뿐이므로 소집단·희귀 토큰의 높은 값에 주의한다. 원시·정규화 η²는 분류 연관성이며 K-means ARI나 정답률이 아니다. [조정η²·DF·정보 손실을 함께 보는 안내](../README.md)를 참고한다.", "",
              "## 출처와 다시 만들기", "",
              "[전체 토큰·인덱스·DF·의미](../all_tokens.csv) · [원시 η²](../variance_by_classification.csv) · [핵심 통계표](../key_token_statistics.csv) · [정규화 η²](../../04_distance_comparison/normalized_eta_comparison.csv)", "",
              "저장소 루트에서 다음 명령은 기존 CSV를 읽어 이 Markdown5개만 재생성한다. 통계 재계산·모델 학습·API 호출·불용어 적용은 없다.", "",
              "```bash", "python -m mathhint_analysis.token_analysis.eta_rankings", "```", "",
              "[토큰 분석 처음으로](../../README.md) · [문제 토큰 안내](../README.md)", ""]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return output


if __name__ == "__main__":
    print(f"기존 CSV의 η² 순위표 Markdown5개 저장: {build_rankings()}")
