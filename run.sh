#!/usr/bin/env bash
# ARBOR 실행 스크립트 — move / objc 데이터셋을 차례로 풀고 점수를 출력한다.
#   사용: ./run.sh            # move, objc 둘 다
#         ./run.sh move       # 하나만
#         ./run.sh objc
set -euo pipefail
cd "$(dirname "$0")"

run() {
  echo "==================== dataset: $1 ===================="
  python -m arbor --dataset "$1"
  echo
}

if [ $# -eq 0 ]; then
  run move
  run objc
else
  for ds in "$@"; do run "$ds"; done
fi
