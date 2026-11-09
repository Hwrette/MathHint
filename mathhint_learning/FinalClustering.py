"""고정 분리 군집화의 기존 import·실행 명령을 유지하는 호환 진입점.

실제 구현: mathhint_learning/holdout/run.py
새 명령: python -m mathhint_learning.holdout
기존 명령: python -m mathhint_learning.FinalClustering
"""

from .holdout.run import *  # 기존 공개 함수·상수의 import 경로를 유지한다.


if __name__ == "__main__":
    main()
