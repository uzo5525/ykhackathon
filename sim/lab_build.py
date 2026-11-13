"""연구실 봇 빌더: 베이스 폴더의 코드 + (v19 챔피언 설정 위에) 추가 설정 -> bots/<name>.

python sim/lab_build.py <name> <base_dir> "<json overrides>" "<설명>"
  base_dir 의 *.py/*.json 을 복사(persona_cfg 제외), persona = v19 OVERRIDES + overrides.
  import 해서 build(name, base, overrides, label) 로도 사용.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def champion_overrides(src="v19"):
    cfg = open(os.path.join(ROOT, src, "persona_cfg.py"), encoding="utf-8").read()
    return eval(re.search(r"OVERRIDES = (\{.*\})", cfg).group(1))


def build(name, base, overrides, label, parent="v19"):
    d = os.path.join(ROOT, "bots", name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    src = os.path.join(ROOT, base)
    for f in os.listdir(src):
        if (f.endswith(".py") or f.endswith(".json")) and f != "persona_cfg.py":
            shutil.copy(os.path.join(src, f), os.path.join(d, f))
    ov = champion_overrides(parent)
    ov.update(overrides)
    with open(os.path.join(d, "persona_cfg.py"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f'"""{name}: {parent} + {label}."""\nOVERRIDES = {ov!r}\n')
    return "bots/" + name


if __name__ == "__main__":
    name, base, ov, label = sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), sys.argv[4]
    print(build(name, base, ov, label))
