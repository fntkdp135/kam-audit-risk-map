# -*- coding: utf-8 -*-
"""② 사업보고서 원문(document.xml ZIP) 수집.

정정본 폴백을 위해 후보 전부를 받아 둔다(692건). 파일은 압축 상태 그대로 캐시.
"""
import os, sys, time
import requests
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, "data", "raw", "docs")
KEY = [l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env"), encoding="utf-8")
       if l.startswith("DART_API_KEY")][0]

rep = pd.read_csv(os.path.join(ROOT, "data/processed/reports.csv"),
                  dtype=str, encoding="utf-8-sig")
rep["cand_rank"] = rep["cand_rank"].astype(int)
todo = rep.sort_values("cand_rank")["rcept_no"].drop_duplicates().tolist()

os.makedirs(DOCS, exist_ok=True)
ok = skip = fail = 0
t0 = time.time()

for i, rc in enumerate(todo, 1):
    path = os.path.join(DOCS, f"{rc}.zip")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        skip += 1
        continue
    try:
        r = requests.get("https://opendart.fss.or.kr/api/document.xml",
                         params=dict(crtfc_key=KEY, rcept_no=rc), timeout=120)
        if r.content[:2] != b"PK":
            fail += 1
            print(f"  ! {rc} ZIP 아님 ({r.content[:80]!r})")
        else:
            with open(path, "wb") as f:
                f.write(r.content)
            ok += 1
    except Exception as e:
        fail += 1
        print(f"  ! {rc} {e}")
    time.sleep(0.25)
    if i % 25 == 0:
        el = time.time() - t0
        print(f"  {i}/{len(todo)}  신규{ok} 스킵{skip} 실패{fail}  "
              f"경과{el/60:.1f}분 예상총{el/i*len(todo)/60:.1f}분")

print(f"\n완료: 신규 {ok} / 스킵 {skip} / 실패 {fail} / 총 {len(todo)}건, "
      f"{(time.time()-t0)/60:.1f}분")
