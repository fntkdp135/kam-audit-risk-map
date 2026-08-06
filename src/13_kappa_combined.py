# -*- coding: utf-8 -*-
"""⑬ 통합 κ — 원표본(FY2019~2024 60건) + 추가표본(FY2025 15건).

원표본은 FY2019~2024 모집단에서 뽑은 것이라 FY2025 항목은 뽑힐 기회가 없었다.
FY2025 추가 표본을 합쳐 검증 범위를 모집단 전체(FY2019~2025)로 넓힌다.
"""
import os, sys
import pandas as pd
from sklearn.metrics import cohen_kappa_score

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")
RES = os.path.join(ROOT, "data", "results")


def load_current():
    k = pd.read_csv(os.path.join(OUT, "kam_typed.csv"), dtype={"corp_code": str},
                    encoding="utf-8-sig")
    k["corp_code"] = k.corp_code.str.zfill(8)
    return k.drop_duplicates(["corp_code", "fy", "kam_title"])


def part_original(cur):
    """원표본 60건 중 현재 파이프라인에도 존속하는 건."""
    r = pd.read_csv(os.path.join(RES, "kappa_result.csv"), dtype={"corp_code": str},
                    encoding="utf-8-sig")
    r["corp_code"] = r.corp_code.str.zfill(8)
    m = r.merge(cur[["corp_code", "fy", "kam_title", "kam_type"]]
                .rename(columns={"kam_type": "machine"}),
                on=["corp_code", "fy", "kam_title"], how="left", suffixes=("_old", ""))
    m = m[m["machine"].notna()].copy()
    m["구간"] = "FY2019~2024"
    return m[["기업명", "fy", "kam_title", "human", "machine", "구간"]]


def part_fy2025():
    x = pd.read_excel(os.path.join(RES, "KAM분류_사람검증_FY2025_15건.xlsx"), sheet_name="분류")
    x = x.rename(columns={x.columns[0]: "번호", x.columns[-1]: "human"})[["번호", "human"]]
    key = pd.read_csv(os.path.join(OUT, "kappa_machine_key_fy2025.csv"),
                      dtype={"corp_code": str}, encoding="utf-8-sig")
    d = key.merge(x, on="번호", how="left").rename(columns={"kam_type": "machine"})
    d["구간"] = "FY2025"
    return d[["기업명", "fy", "kam_title", "human", "machine", "구간"]]


def kappa(df, label):
    df = df.copy()
    df["human"] = df.human.fillna("").astype(str).str.strip()
    core = df[(df.machine != "미분류") & (df.human != "판단 불가") & (df.human != "")]
    if len(core) < 2:
        print(f"{label}: 계산 불가(유효 {len(core)}건)")
        return None
    agr = (core.machine == core.human).mean()
    k = cohen_kappa_score(core.human, core.machine)
    excl = len(df) - len(core)
    print(f"{label:<22} n={len(core):>2}  일치율 {agr*100:5.1f}%  κ={k:.3f}"
          f"   (제외 {excl}건: 사람 '판단 불가'·기계 '미분류')")
    return k


def main():
    cur = load_current()
    a = part_original(cur)
    b = part_fy2025()
    allx = pd.concat([a, b], ignore_index=True)

    print("=== 구간별")
    kappa(a, "FY2019~2024 (원표본)")
    kappa(b, "FY2025 (추가표본)")
    print()
    print("=== 통합")
    kappa(allx, "FY2019~2025 (통합)")

    print("\n=== FY2025 표본 불일치 내역")
    bb = b.copy()
    bb["human"] = bb.human.fillna("").astype(str).str.strip()
    dis = bb[(bb.machine != bb.human)]
    if dis.empty:
        print("  없음")
    for r in dis.itertuples():
        print(f"  {r.기업명} FY{r.fy} | {str(r.kam_title)[:40]}")
        print(f"     기계={r.machine} / 사람={r.human}")

    allx.to_csv(os.path.join(RES, "kappa_combined.csv"), index=False, encoding="utf-8-sig")
    print(f"\n저장: {os.path.join(RES,'kappa_combined.csv')} ({len(allx)}건)")


if __name__ == "__main__":
    main()
