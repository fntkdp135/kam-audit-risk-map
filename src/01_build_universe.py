# -*- coding: utf-8 -*-
"""① 모집단 확정 + 사업보고서 접수번호 수집

- 주 대상: 2번 프로젝트의 엔터·미디어·콘텐츠 78개사 (universe_final.csv)
- 대조군: 게임 상장사 (업종코드 582x 접두)
- FY2019~2025 사업보고서 접수번호를 수집하되, 같은 사업연도에 여러 건이 있으면
  정정본 → 원본 순으로 후보를 모두 보관 (2번 프로젝트에서 확립한 폴백 패턴)
"""
import os, re, sys, csv, time, json
import requests
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
P2 = r"C:\Users\samsung-user\Desktop\삼일감사포트폴리오\02-콘텐츠무형자산손상징후"
OUT = os.path.join(ROOT, "data", "processed")

KEY = [l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env"), encoding="utf-8")
       if l.startswith("DART_API_KEY")][0]

FY_MIN, FY_MAX = 2019, 2025


def load_universe() -> pd.DataFrame:
    content = pd.read_csv(os.path.join(P2, "data/processed/universe_final.csv"),
                          dtype=str, encoding="utf-8-sig")
    content = content[["corp_code", "기업명", "종목코드", "업종코드", "업종"]].copy()
    content["군"] = "콘텐츠"

    ind = pd.read_csv(os.path.join(P2, "data/processed/corp_industry.csv"),
                      dtype=str, encoding="utf-8-sig")
    ind["induty_code"] = ind["induty_code"].fillna("")
    # 게임 소프트웨어 개발·공급업 = 5821 접두.
    # 3자리 '582'(71개사)는 게임/시스템응용SW 구분이 불가능해 원칙적으로 제외함
    # (대부분 보안·헬스케어SW이나 엔씨소프트·컴투스홀딩스·넥슨게임즈가 섞여 있음).
    # 수동 선별은 대조군 구성을 자의적으로 만들므로 규칙 기반만 사용하고 한계로 명시.
    game = ind[ind["induty_code"].str.startswith("5821")].copy()
    # 상장사만 (종목코드 있는 곳). status 000 = 정상
    game = game[game["stock_code"].notna() & (game["stock_code"].str.strip() != "")]
    game = game.rename(columns={"corp_name": "기업명", "stock_code": "종목코드",
                                "induty_code": "업종코드"})
    game["업종"] = "게임 소프트웨어"
    game["군"] = "게임"
    game = game[["corp_code", "기업명", "종목코드", "업종코드", "업종", "군"]]

    # 콘텐츠 모집단에 이미 있는 곳은 제외
    game = game[~game["corp_code"].isin(set(content["corp_code"]))]

    uni = pd.concat([content, game], ignore_index=True)
    uni = uni.drop_duplicates(subset=["corp_code"])
    return uni


def fetch_reports(corp_code: str) -> list:
    """해당 회사의 FY2019~2024 사업보고서 목록 (정정본 포함)"""
    out = []
    for page in range(1, 4):
        try:
            j = requests.get(
                "https://opendart.fss.or.kr/api/list.json",
                params=dict(crtfc_key=KEY, corp_code=corp_code,
                            bgn_de="20200101", end_de="20260831",
                            pblntf_ty="A", pblntf_detail_ty="A001",
                            page_no=page, page_count=100),
                timeout=30,
            ).json()
        except Exception as e:
            print(f"    ! {corp_code} page{page} {e}")
            break
        if j.get("status") != "000":
            break
        for it in j.get("list", []):
            nm = it["report_nm"]
            if "사업보고서" not in nm:
                continue
            m = re.search(r"\((\d{4})\.(\d{1,2})\)", nm)
            if not m:
                continue
            fy = int(m.group(1))
            if not (FY_MIN <= fy <= FY_MAX):
                continue
            out.append(dict(corp_code=corp_code, fy=fy, rcept_no=it["rcept_no"],
                            rcept_dt=it["rcept_dt"], report_nm=nm.strip(),
                            is_amend=int("정정" in nm)))
        if int(j.get("total_page", 1)) <= page:
            break
    return out


def main():
    uni = load_universe()
    n_c = (uni["군"] == "콘텐츠").sum()
    n_g = (uni["군"] == "게임").sum()
    print(f"모집단: 콘텐츠 {n_c}개사 + 게임(대조군) {n_g}개사 = {len(uni)}개사")
    uni.to_csv(os.path.join(OUT, "universe.csv"), index=False, encoding="utf-8-sig")

    rows = []
    for i, r in enumerate(uni.itertuples(), 1):
        rows.extend(fetch_reports(r.corp_code))
        if i % 20 == 0:
            print(f"  ...{i}/{len(uni)}개사 조회, 누적 보고서 {len(rows)}건")
        time.sleep(0.05)

    rep = pd.DataFrame(rows)
    if rep.empty:
        print("보고서 0건 — 중단"); return
    rep = rep.merge(uni[["corp_code", "기업명", "군", "업종코드"]], on="corp_code", how="left")
    # 같은 (회사, 사업연도)에서 정정본 우선 → 최신 접수 우선
    rep = rep.sort_values(["corp_code", "fy", "is_amend", "rcept_dt"],
                          ascending=[True, True, False, False])
    rep["cand_rank"] = rep.groupby(["corp_code", "fy"]).cumcount()
    rep.to_csv(os.path.join(OUT, "reports.csv"), index=False, encoding="utf-8-sig")

    fy_cov = rep[rep.cand_rank == 0].groupby(["군", "fy"]).size().unstack(fill_value=0)
    print("\n=== 사업연도별 firm-year (1순위 후보 기준)")
    print(fy_cov.to_string())
    print(f"\n총 보고서 후보 {len(rep):,}건 / firm-year {(rep.cand_rank==0).sum():,}건")
    print(f"정정본 보유 firm-year {rep[rep.is_amend==1].groupby(['corp_code','fy']).ngroups:,}건")
    covered = rep[rep.cand_rank == 0].groupby("군")["corp_code"].nunique()
    print(f"보고서가 실제로 있는 회사 수:\n{covered.to_string()}")


if __name__ == "__main__":
    main()
