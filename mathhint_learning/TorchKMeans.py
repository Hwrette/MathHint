"""저장된 빈도벡터 JSON을 읽어 PyTorch로 K-means 군집화를 합니다.

설치: python -m pip install torch
실행: python mathhint_learning/TorchKMeans.py
모듈 실행: python -m mathhint_learning.TorchKMeans
옵션 예: python mathhint_learning/TorchKMeans.py --vectors outputs/bow/frequency_vectors.json --clusters 3

텍스트를 다시 분석하거나 빈도벡터를 생성하지 않습니다.
현재는 저장된 원시 횟수와 유클리드 거리를 그대로 사용합니다.
"""

import argparse
import json
import math
from pathlib import Path

import torch

if __package__:
    from .TorchData import load_frequency_matrix
else:
    # VS Code의 ▶ 버튼으로 이 파일을 직접 실행할 때 사용합니다.
    from TorchData import load_frequency_matrix


# ▶ 버튼으로 실행할 때 사용할 설정입니다. 상대 경로는 MathHint 프로젝트 폴더를 기준으로 찾습니다.
VECTORS_FILE = "outputs/problem_vectors/frequency_vectors.json"
OUTPUT_FOLDER = "outputs/kmeans"
N_CLUSTERS = 3  # 로그·삼각함수·미분 문제가 비슷한 유형끼리 모이는지 보는 실험의 초기값입니다.
MAX_ITER = 100
TOLERANCE = 0.0001  # 중심 이동 거리가 이 값 이하이면 반복을 마칩니다.
SEED = 42  # 같은 데이터에서 초기 중심을 재현하기 위한 난수 설정입니다.


def _as_matrix(value: torch.Tensor, name: str) -> torch.Tensor:
    """행은 파일, 열은 토큰인 2차원 CPU 실수 텐서인지 확인합니다."""
    if not isinstance(value, torch.Tensor) or value.ndim != 2:
        raise ValueError(f"{name}는 2차원 PyTorch 텐서여야 합니다.")
    if value.shape[0] == 0 or value.shape[1] == 0:
        raise ValueError(f"{name}에는 행과 열이 각각 하나 이상 필요합니다.")
    matrix = value.detach().to(device="cpu", dtype=torch.float32)
    if not torch.isfinite(matrix).all():
        raise ValueError(f"{name}에 NaN이나 무한대가 있습니다.")
    return matrix


def _distances(matrix: torch.Tensor, centers: torch.Tensor) -> torch.Tensor:
    # 결과의 [i, j]는 i번째 파일과 j번째 중심 사이의 유클리드 거리입니다.
    distances = torch.cdist(matrix, centers)
    if not torch.isfinite(distances).all():
        raise ValueError("거리 계산이 실수 범위를 넘었습니다. 입력 벡터의 크기를 확인하세요.")
    return distances


def assign_clusters(matrix: torch.Tensor, centers: torch.Tensor) -> torch.Tensor:
    """각 벡터에 가장 가까운 중심의 번호를 돌려줍니다. 새 데이터에도 사용할 수 있습니다."""
    matrix = _as_matrix(matrix, "입력 행렬")
    centers = _as_matrix(centers, "중심 행렬")
    if matrix.shape[1] != centers.shape[1]:
        raise ValueError("입력 행렬과 중심 행렬의 토큰 열 수가 다릅니다.")
    return _distances(matrix, centers).argmin(dim=1)


def fit_kmeans(
    matrix: torch.Tensor,
    n_clusters: int = 3,
    max_iter: int = 100,
    tol: float = 0.0001,
    seed: int = 42,
) -> dict:
    """가까운 중심에 배정 → 묶음의 평균으로 중심 갱신을 반복합니다.

    회귀와 달리 정답 라벨은 필요 없습니다. 군집 번호는 자동으로 붙은 번호이며,
    0번이 쉽고 1번이 어렵다는 뜻처럼 미리 정해진 의미가 있지는 않습니다.
    """
    matrix = _as_matrix(matrix, "입력 행렬")
    if isinstance(n_clusters, bool) or not isinstance(n_clusters, int) or n_clusters < 1:
        raise ValueError("군집 수는 1 이상의 정수여야 합니다.")
    if isinstance(max_iter, bool) or not isinstance(max_iter, int) or max_iter < 1:
        raise ValueError("반복 횟수는 1 이상의 정수여야 합니다.")
    if not math.isfinite(tol) or tol < 0:
        raise ValueError("수렴 기준은 0 이상의 유한한 숫자여야 합니다.")

    # 중복 벡터가 초기 중심으로 여러 번 선택되지 않도록 고유한 행에서 뽑습니다.
    unique_rows = torch.unique(matrix, dim=0)
    if n_clusters > len(unique_rows):
        raise ValueError("군집 수가 데이터의 서로 다른 벡터 수보다 많습니다.")
    generator = torch.Generator(device="cpu").manual_seed(seed)
    selected = torch.randperm(len(unique_rows), generator=generator)[:n_clusters]
    centers = unique_rows[selected].clone()

    for iteration in range(1, max_iter + 1):
        distances = _distances(matrix, centers)
        assignments = distances.argmin(dim=1)  # 각 행에서 거리가 가장 작은 중심 번호입니다.
        updated = centers.clone()
        nearest_distances = distances.min(dim=1).values.clone()

        for cluster in range(n_clusters):
            members = matrix[assignments == cluster]
            if len(members) > 0:
                updated[cluster] = members.mean(dim=0)
            else:
                # 빈 군집의 평균은 계산할 수 없으므로, 중심에서 가장 먼 점으로 옮깁니다.
                # 여러 군집이 비었을 때 같은 점을 반복 선택하지 않도록 표시합니다.
                farthest = nearest_distances.argmax()
                updated[cluster] = matrix[farthest]
                nearest_distances[farthest] = -1

        movement = torch.linalg.vector_norm(updated - centers, dim=1).max().item()
        centers = updated
        if movement <= tol:
            break

    # 마지막 중심을 갱신한 뒤 다시 배정해야 저장된 중심과 군집 번호가 일치합니다.
    assignments = assign_clusters(matrix, centers)
    inertia = ((matrix - centers[assignments]) ** 2).sum().item()
    if not math.isfinite(inertia):
        raise ValueError("군집 내 거리 합이 실수 범위를 넘었습니다.")
    return {"centers": centers, "assignments": assignments,
            "inertia": inertia, "iterations": iteration}


def main() -> None:
    """JSON을 행렬로 읽고 군집 번호와 중심을 파일로 저장합니다."""
    script_folder = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="PyTorch K-means 빈도벡터 군집화")
    parser.add_argument("--vectors", type=Path, help="기존 frequency_vectors.json 경로")
    parser.add_argument("-o", "--output", type=Path, help="결과 폴더")
    parser.add_argument("--clusters", type=int, default=N_CLUSTERS, help="군집 수")
    parser.add_argument("--max-iter", type=int, default=MAX_ITER)
    parser.add_argument("--tol", type=float, default=TOLERANCE)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    vectors_path = args.vectors if args.vectors is not None else script_folder / Path(VECTORS_FILE).expanduser()
    output_folder = args.output if args.output is not None else script_folder / Path(OUTPUT_FOLDER).expanduser()

    try:
        files, matrix, vocabulary = load_frequency_matrix(vectors_path)
        print(f"입력 행렬: {matrix.shape[0]}행 × {matrix.shape[1]}열", flush=True)
        result = fit_kmeans(matrix, args.clusters, args.max_iter, args.tol, args.seed)
        output_folder = output_folder.expanduser().resolve()
        output_folder.mkdir(parents=True, exist_ok=True)
        model_path = output_folder / "kmeans_model.pt"
        assignments_path = output_folder / "clusters.json"
        cluster_sizes = torch.bincount(result["assignments"], minlength=args.clusters).tolist()

        # 새 문제는 같은 어휘 순서로 벡터를 만든 후 저장된 중심과 거리를 비교합니다.
        torch.save({"centers": result["centers"], "vocabulary": vocabulary,
                    "n_clusters": args.clusters, "seed": args.seed,
                    "max_iter": args.max_iter, "tol": args.tol,
                    "feature_transform": "raw_counts"}, model_path)
        assignments_path.write_text(json.dumps({
            "n_clusters": args.clusters,
            "iterations": result["iterations"],
            "inertia": result["inertia"],
            "cluster_sizes": cluster_sizes,
            "documents": [{"file": file, "cluster": cluster}
                          for file, cluster in zip(files, result["assignments"].tolist())],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))

    print(f"반복 횟수: {result['iterations']}")
    print(f"군집별 파일 수: {cluster_sizes}")
    print(f"군집 내 제곱 거리 합: {result['inertia']:.6f}")
    print(f"군집 배정 저장: {assignments_path}")
    print(f"중심·어휘 저장: {model_path}")


if __name__ == "__main__":
    main()
