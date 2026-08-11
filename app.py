# -*- coding: utf-8 -*-
"""감사위험 지도 — 핵심감사사항(KAM)·계속기업 불확실성·의견변형 실증분석."""
import os, re
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="감사위험 지도", page_icon="◧", layout="wide")

BASE = os.path.dirname(os.path.abspath(__file__))
BG, SURF, LINE = "#0E1013", "#171A21", "#272D3A"
MINT, CORAL, AMBER = "#6FD3C2", "#E8705A", "#D9A25F"
TXT, MUTE = "#E8EAEE", "#868E9E"

st.markdown(f"""<style>
.stApp {{ background:{BG}; color:{TXT}; }}
section[data-testid="stSidebar"] {{ background:#0A0C0F; border-right:1px solid {LINE}; }}
h1,h2,h3,h4 {{ color:{TXT} !important; letter-spacing:-.025em; font-weight:650; }}
b, strong {{ color:{MINT}; font-weight:600; }}

.eyebrow {{ color:{MUTE}; font-size:.72rem; letter-spacing:.22em; text-transform:uppercase;
           margin-bottom:.5rem; }}
.secttl {{ font-size:1.85rem; font-weight:680; letter-spacing:-.03em; line-height:1.25;
          margin:0 0 1.1rem 0; }}
.lead {{ font-size:1.06rem; line-height:1.85; color:#CDD3DE; border-left:2px solid {MINT};
        padding-left:1.1rem; margin:0 0 2rem 0; }}
.lead.warn {{ border-left-color:{CORAL}; }}

.figrow {{ display:flex; gap:0; border-top:1px solid {LINE}; border-bottom:1px solid {LINE};
          margin:0 0 2rem 0; }}
.fig {{ flex:1; padding:1.1rem 1.3rem; border-right:1px solid {LINE}; }}
.fig:last-child {{ border-right:none; }}
.fig .lbl {{ color:#C3CAD8; font-size:.78rem; font-weight:600; margin-bottom:.42rem;
            letter-spacing:.01em; }}
.fig .n {{ font-size:1.62rem; font-weight:700; letter-spacing:-.035em; color:{MINT};
          line-height:1.3; font-variant-numeric:tabular-nums; }}
.fig .n.sm {{ font-size:1.18rem; line-height:1.45; }}
.fig .pct {{ color:#C3CAD8; font-weight:600; font-size:.92rem; margin-left:.3rem; }}
.fig.neg .n {{ color:{CORAL}; }}
.fig.amb .n {{ color:{AMBER}; }}
.fig .k {{ color:#A7AFBE; font-size:.76rem; margin-top:.35rem; line-height:1.55; }}

/* 다크 배경에서 회색 기본색이 거의 안 보이므로 위젯·내비 글자를 흰색 볼드로 올림 */
section[data-testid="stSidebar"] [role="radiogroup"] label p {{
  color:#FFFFFF !important; font-weight:700 !important; font-size:.92rem !important; }}
section[data-testid="stSidebar"] [role="radiogroup"] label {{ padding:.15rem 0; }}
/* 04(방법론·한계점)는 본문 섹션과 성격이 달라 회색으로 눈에 덜 띄게 둠 */
section[data-testid="stSidebar"] [role="radiogroup"] label:last-of-type p {{
  color:{MUTE} !important; font-weight:600 !important; }}
div[data-testid="stWidgetLabel"] p, .stMultiSelect label p, .stSlider label p,
.stSelectbox label p {{ color:#FFFFFF !important; font-weight:700 !important; }}
div[data-testid="stSliderTickBarMin"], div[data-testid="stSliderTickBarMax"] {{
  color:#A7AFBE !important; }}

.body {{ color:#B8BFCC; font-size:.93rem; line-height:1.85; }}
.panel {{ background:{SURF}; border:1px solid {LINE}; border-radius:4px;
         padding:1rem 1.25rem; color:#AAB2C0; font-size:.88rem; line-height:1.8;
         margin:1.2rem 0; }}
.panel .h {{ color:{TXT}; font-weight:620; font-size:.9rem; display:block; margin-bottom:.45rem; }}
.src {{ color:#98A0AF; font-size:.87rem; line-height:1.85; white-space:pre-wrap; }}
.chip {{ display:inline-block; border:1px solid {LINE}; color:{MUTE}; border-radius:3px;
        padding:1px 7px; font-size:.72rem; margin-right:5px; }}
.rule {{ border-top:1px solid {LINE}; margin:2.4rem 0 1.6rem 0; }}
div[data-testid="stExpander"] {{ background:{SURF}; border:1px solid {LINE}; border-radius:4px; }}
div[data-testid="stExpander"] summary {{ font-size:.9rem; }}
.sbnum {{ color:{MINT}; font-variant-numeric:tabular-nums; font-weight:640; }}
.sbrow {{ color:{MUTE}; font-size:.78rem; padding:.28rem 0; border-bottom:1px solid #14171D; }}
</style>""", unsafe_allow_html=True)

GNAME = {"콘텐츠": "E&M", "게임": "Game"}
G1, G2 = "E&M", "Game"
MODIFIED = ["의견거절", "한정의견", "부적정의견"]


DATA_FILES = ["data/processed/kam_typed.csv", "data/processed/panel_outcomes.csv",
              "data/results/opinion_basis_typed.csv", "data/results/linkage.csv",
              "data/processed/report_meta.csv"]


def data_signature():
    """데이터 파일의 크기·수정시각을 캐시 키에 넣는다.

    이걸 넣지 않으면 CSV만 바뀌고 load() 본문이 그대로일 때 @st.cache_data가
    **옛 데이터를 계속 반환한다**. 로컬에서는 서버를 재시작하면 풀리지만, 배포본은
    재시작되지 않아 코드는 최신인데 수치만 옛것으로 남는 상태가 된다(실제로 겪음).
    """
    sig = []
    for rel in DATA_FILES:
        p = os.path.join(BASE, rel)
        try:
            st_ = os.stat(p)
            sig.append((rel, int(st_.st_size), int(st_.st_mtime)))
        except OSError:
            sig.append((rel, -1, -1))
    return tuple(sig)


@st.cache_data
def load(sig):   # ⚠️ 인자명에 밑줄을 붙이면 안 됨 — Streamlit은 '_'로 시작하는 인자를
                 # 캐시 키에서 제외하므로 시그니처를 넘겨도 무효화가 일어나지 않는다.
    k = pd.read_csv(f"{BASE}/data/processed/kam_typed.csv", dtype={"corp_code": str},
                    encoding="utf-8-sig")
    k["corp_code"] = k.corp_code.str.zfill(8)
    k = k.drop_duplicates(["corp_code", "fy", "kam_title"])
    k = k[k.kam_type != "미분류"]
    k["군"] = k["군"].map(GNAME).fillna(k["군"])
    p = pd.read_csv(f"{BASE}/data/processed/panel_outcomes.csv", dtype={"corp_code": str},
                    encoding="utf-8-sig")
    p["corp_code"] = p.corp_code.str.zfill(8)
    p["군"] = p["군"].map(GNAME).fillna(p["군"])
    b = pd.read_csv(f"{BASE}/data/results/opinion_basis_typed.csv", dtype={"corp_code": str},
                    encoding="utf-8-sig")
    b["corp_code"] = b.corp_code.str.zfill(8)
    b["군"] = b["군"].map(GNAME).fillna(b["군"])
    return k, p, b


@st.cache_data
def load_linkage(sig):
    d = pd.read_csv(f"{BASE}/data/results/linkage.csv", encoding="utf-8-sig")
    return d


@st.cache_data
def load_gc_text(sig):
    """계속기업 불확실성 단락 원문 (firm-year당 연결 우선 1행)."""
    m = pd.read_csv(f"{BASE}/data/processed/report_meta.csv",
                    dtype={"rcept_no": str, "corp_code": str}, encoding="utf-8-sig")
    m["corp_code"] = m.corp_code.str.zfill(8)
    m["_p"] = (m.doc_type != "연결").astype(int)
    m = m.sort_values(["corp_code", "fy", "_p"]).drop_duplicates(["corp_code", "fy"])
    return m[["corp_code", "fy", "gc_text"]]


kam, pan, bas = load(data_signature())

BAD = re.compile(r"^[\d,\.\s]+$|백만원|^\D{0,3}\d[\d,\.]*\s*(원|건)?$"
                 r"|(하였고|이며|하므로|고려하여|점을|바|이)$|참조\)")


def disp(t):
    t = str(t or "").strip()
    return "(항목명 추출 실패 — 원문 확인)" if (not t or len(t) < 4 or BAD.search(t)) else t


def txt_ok(x, n=30):
    """결측·공백·너무 짧은 조각을 걸러 화면에 'nan'이 찍히지 않도록 한다."""
    return isinstance(x, str) and len(x.strip()) >= n


# 한계 서술에 쓰는 값도 화면과 같은 판정으로 계산한다(하드코딩하면 데이터가 바뀔 때 어긋남)
n_bad = int(kam.kam_title.apply(lambda t: disp(t).startswith("(항목명")).sum())
n_noreason = int((~kam.reason_text.apply(txt_ok)).sum())
n_noproc = int((~kam.procedure_text.apply(txt_ok)).sum())


def figs(items):
    """(라벨, 값, 보조설명, 클래스) — 라벨·값·보조설명이 한눈에 보이도록."""
    html = '<div class="figrow">'
    for lbl, val, sub, cls in items:
        small = " sm" if len(re.sub(r"<[^>]+>", "", str(val))) > 9 else ""
        html += (f'<div class="fig {cls}"><div class="lbl">{lbl}</div>'
                 f'<div class="n{small}">{val}</div>'
                 + (f'<div class="k">{sub}</div>' if sub else "") + "</div>")
    st.markdown(html + "</div>", unsafe_allow_html=True)


def head(eyebrow, title, lead, warn=False):
    html = f'<div class="eyebrow">{eyebrow}</div><div class="secttl">{title}</div>'
    if lead:  # 리드문 없이 제목만 쓰고 카드로 바로 들어가는 섹션을 위해 생략 가능하게 함
        html += f'<div class="lead {"warn" if warn else ""}">{lead}</div>'
    st.markdown(html, unsafe_allow_html=True)


def chart(fig, h=380):
    """제목과 범례가 겹치지 않도록 범례를 차트 아래로 내리고, 글자색을 밝게 유지."""
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", height=h + 46,
                      font=dict(color="#E2E6EE", size=12),
                      title=dict(font=dict(color=TXT, size=14), x=0, xanchor="left",
                                 y=0.98, yanchor="top"),
                      margin=dict(l=6, r=6, t=50, b=58),
                      legend=dict(orientation="h", yanchor="top", y=-0.10, x=0,
                                  font=dict(color="#E2E6EE", size=12),
                                  bgcolor="rgba(0,0,0,0)"),
                      xaxis=dict(gridcolor="#1D222C", zerolinecolor="#1D222C",
                                 tickfont=dict(color="#C7CEDA")),
                      yaxis=dict(gridcolor="#1D222C", zerolinecolor="#1D222C",
                                 tickfont=dict(color="#E2E6EE")))
    st.plotly_chart(fig, use_container_width=True)


def b(s):
    """플로틀리 축·범례 라벨을 볼드로."""
    return f"<b>{s}</b>"


# ─────────────────────────────────────────────── 사이드바
with st.sidebar:
    st.markdown(f'<div class="eyebrow">Samil Audit Portfolio</div>'
                f'<div style="font-size:1.22rem;font-weight:800;letter-spacing:-.03em;'
                f'color:#FFFFFF;margin-bottom:1.3rem">감사위험 지도</div>',
                unsafe_allow_html=True)
    sec = st.radio("섹션", [
        "01  콘텐츠산업의 핵심감사사항(KAM)",
        "02  KAM은 실제로 핵심적인 위험이었는가 (KAM→의견변형)",
        "03  의견변형 사유",
        "04  방법론, 한계점",
    ], label_visibility="collapsed")
    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    n_mod = len(bas)
    for lab, val in [("분석 단위", "636 firm-year"), ("사업연도", "FY2019–2025"),
                     ("기업", "109개사"), ("핵심감사사항", f"{len(kam)}개"),
                     ("의견변형", f"{n_mod}건"), ("분류 검증 κ", "0.930")]:
        st.markdown(f'<div class="sbrow">{lab}<span style="float:right" class="sbnum">{val}</span></div>',
                    unsafe_allow_html=True)
    st.markdown(f'<div style="color:{MUTE};font-size:.72rem;line-height:1.7;margin-top:1.2rem">'
                f'DART 사업보고서에 첨부된 감사보고서 원문 기반. 감사의견의 적정성을 평가하지 않으며 '
                f'공시된 기재를 집계·대조한 것임.</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────── 01
if sec.startswith("01"):
    # 표시하는 비율은 전부 여기서 계산한다(하드코딩 금지).
    # 또한 **분모가 무엇인지**를 라벨에 반드시 적는다 — 전체 합산 비율을 각 부문의 비율인 것처럼
    # 쓰면 안 됨(전체 69.5% / E&M 67.6% / Game 75.2%로 서로 다른 값임).
    top = kam.kam_type.value_counts()
    T1, T2 = top.index[0], top.index[1]
    p1 = top.iloc[0] / len(kam) * 100
    p2 = (top.iloc[0] + top.iloc[1]) / len(kam) * 100

    def share(seg, types):
        s = kam[kam["군"] == seg]
        return s.kam_type.isin(types).sum() / len(s) * 100 if len(s) else float("nan")

    e2, g2 = share(G1, [T1, T2]), share(G2, [T1, T2])
    e1, g1 = share(G1, [T1]), share(G2, [T1])

    head("Section 01 · 콘텐츠산업의 핵심감사사항(KAM)",
         "콘텐츠 산업 기업의 핵심감사사항",
         f"<b>E&amp;M 부문</b>(음악·방송·영화·드라마·웹툰, 78개사)과 "
         f"<b>Game 부문</b>(31개사, 대조군)의 핵심감사사항 {len(kam)}개를 13개 유형으로 분류함. "
         f"전체의 <b>{p2:.1f}%</b>가 <b>{T1}·{T2}</b> 두 유형에 몰려 있고, 부문별로 나눠 봐도 "
         f"E&amp;M {e2:.1f}% · Game {g2:.1f}%로 비슷함. "
         f"<b>부문 간 유형 분포 차이는 유의하지 않음</b>(카이제곱 p=0.087).")
    figs([(f"최다 유형 · 전체 {len(kam)}건 기준",
           f"{T1}<span class='pct'>{p1:.1f}%</span>",
           f"{int(top.iloc[0])}건 · 부문별 E&M {e1:.1f}% / Game {g1:.1f}%", ""),
          (f"상위 2유형 · 전체 {len(kam)}건 기준",
           f"{T1} · {T2}<span class='pct'>{p2:.1f}%</span>",
           f"{int(top.iloc[0]+top.iloc[1])}건 · 부문별 E&M {e2:.1f}% / Game {g2:.1f}%", ""),
          ("분류 유형 수", "13", "감사인이 지목한 회계쟁점 기준", ""),
          ("부문 간 분포 차이", "없음", "카이제곱 p=0.087 · 유의하지 않음", "amb")])

    c1, c2, c3 = st.columns([1, 1, 2])
    grp = c1.multiselect("부문", [G1, G2], default=[G1, G2])
    # 연도 범위를 하드코딩하면 데이터가 늘어도 화면이 옛 범위에 갇힌다(FY2025 추가 때 실제로 겪음).
    FY0, FY1 = int(kam.fy.min()), int(kam.fy.max())
    yrs = c2.slider("사업연도", FY0, FY1, (FY0, FY1))
    tsel = c3.multiselect("유형", sorted(kam.kam_type.unique()), default=[])
    v = kam[kam["군"].isin(grp) & kam.fy.between(*yrs)]
    if tsel:
        v = v[v.kam_type.isin(tsel)]

    if v.empty:
        st.warning("조건에 맞는 항목이 없음")
    else:
        L, R = st.columns([1.15, 1])
        with L:
            ct = pd.crosstab(v.kam_type, v["군"], normalize="columns") * 100
            ct = ct.reindex(v.kam_type.value_counts().index).fillna(0).round(1)
            fig = go.Figure()
            for g, col in [(G1, MINT), (G2, AMBER)]:
                if g in ct.columns:
                    fig.add_bar(y=[b(x) for x in ct.index[::-1]], x=ct[g][::-1], name=b(g),
                                orientation="h", marker_color=col,
                                hovertemplate="%{y} %{x}%<extra></extra>")
            fig.update_layout(title="부문별 유형 구성비 (%)", barmode="group")
            chart(fig, h=max(360, 27 * len(ct) + 90))
        with R:
            tr = v.groupby(["fy", "kam_type"]).size().unstack(fill_value=0)
            keep = [c for c in v.kam_type.value_counts().head(5).index if c in tr.columns]
            fig = go.Figure()
            for i, c in enumerate(keep):
                fig.add_scatter(x=tr.index, y=tr[c], name=b(c), mode="lines+markers",
                                line=dict(color=[MINT, AMBER, "#7C9CE0", CORAL, "#9B8ACB"][i],
                                          width=2.2))
            fig.update_layout(title="연도별 추이 (상위 5유형, 건수)",
                              xaxis=dict(dtick=1, gridcolor="#1D222C"))
            chart(fig, h=max(360, 27 * len(ct) + 90))
        st.markdown(f'<div class="panel"><span class="h">한 firm-year에서 한 문서만 채택했음</span>'
                    f'연결·별도 감사보고서를 둘 다 세면 같은 사건이 두 번 계상됨. 예를 들어 한 게임사는 '
                    f'연결에서 「현금창출단위(영업권)의 회수가능액 측정」, 별도에서 「종속기업투자주식 '
                    f'손상검사」로 기재되는데 같은 사건을 두 재무제표에서 다르게 부른 것임. '
                    f'실제로 종속·관계기업투자 유형의 <b>85%가 별도보고서</b>에서 나와, 둘 다 세면 '
                    f'부문별 분포가 문서 구성에 따라 왜곡됨. <b>연결 우선, 연결 미작성 기간만 별도</b>를 '
                    f'적용함(연결 432 · 별도 34).</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="panel"><span class="h">FY2019는 다른 연도와 같은 선상에 놓을 수 없음</span>'
                    f'핵심감사사항 기재가 자산규모별로 단계 도입되던 시기라 소형사가 빠져 있음'
                    f'(검출률 45.7% vs 다른 해 60~81%).</div>', unsafe_allow_html=True)

        st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
        st.markdown("#### 감사보고서 원문")
        st.markdown('<div class="body">항목을 펼치면 감사보고서 내 '
                    '<b>[핵심감사사항] 단락의 원문 내용이 출력</b>됨.</div>',
                    unsafe_allow_html=True)
        st.caption("일부 항목은 DART 원문의 서식(단어 중간에서 분리되는 HTML 태그) 특성상 "
                   "항목명이나 본문 일부가 짧게 표시되거나 생략될 수 있음. 표시 로직의 한계이며 "
                   "원본 데이터는 보존됨.")
        f = st.selectbox("기업", ["(전체)"] + sorted(v.기업명.unique()))
        vv = (v if f == "(전체)" else v[v.기업명 == f]).sort_values(["fy", "기업명"],
                                                              ascending=[False, True])
        st.caption(f"{len(vv)}건 · 상위 60건 표시")
        for r in vv.head(60).itertuples():
            with st.expander(f"{r.fy} · {r.기업명} · {r.kam_type} — {disp(r.kam_title)[:56]}"):
                st.markdown(f'<span class="chip">{r.군}</span>'
                            f'<span class="chip">{r.doc_type}감사보고서</span>'
                            f'<span class="chip">분류 {"규칙" if r.type_source=="rule" else "LLM 보조"}</span>',
                            unsafe_allow_html=True)
                # 결측(NaN)을 그대로 찍으면 화면에 'nan'이 노출되므로 있는 구간만 출력함.
                # 보고서에 따라 '이유'와 '방법'이 소제목으로 나뉘지 않아 한쪽만 잡히는 경우가 있음.
                shown = False
                if txt_ok(r.reason_text):
                    st.markdown("**핵심감사사항으로 결정한 이유**")
                    st.markdown(f'<div class="src">{str(r.reason_text)[:2400]}</div>',
                                unsafe_allow_html=True)
                    shown = True
                if txt_ok(r.procedure_text):
                    st.markdown("**감사에서 다루어진 방법**")
                    st.markdown(f'<div class="src">{str(r.procedure_text)[:2400]}</div>',
                                unsafe_allow_html=True)
                    shown = True
                if not shown:
                    st.markdown('<div class="src">원문 구간을 분리하지 못한 항목임 '
                                '(감사보고서가 이유·방법을 소제목으로 나누지 않은 형식).</div>',
                                unsafe_allow_html=True)

# ─────────────────────────────────────────────── 02
elif sec.startswith("02"):
    lk = load_linkage(data_signature())
    n_mod = len(bas)
    s = lk[lk.경로 == "KAM → 의견변형"]
    n_link, n_match = len(s), int(s.일치.sum())
    firms_link, firms_match = s.기업명.nunique(), s[s.일치 == 1].기업명.nunique()
    gap = s.간격.median()

    head("Section 02 · KAM은 실제로 핵심적인 위험이었는가 (KAM→의견변형)",
         "지목된 핵심감사사항이 이후 연도에<br>의견변형으로 이어졌는가", "")
    figs([("KAM → 이후 의견변형", f"{n_link}건",
           f"의견변형 {n_mod}건 중 {n_link/n_mod*100:.0f}% · {firms_link}개사", "amb"),
          ("사유까지 일치", f"{n_match}건",
           f"연결 {n_link}건 중 {n_match/n_link*100:.0f}% · {firms_match}개사", "neg"),
          ("간격 중앙값", f"{gap:.0f}년", "핵심감사사항 지목 → 의견변형까지", ""),
          ("일치 사례 편중", f"{firms_match}개사", "레드로버·아이에이치큐 2개사에 집중", "amb")])

    st.markdown(f'<div class="panel"><span class="h">읽는 법</span>'
                f'"<b>{n_link}건</b>"은 이후 연도에 의견변형이 나타난 경우이고, "<b>{n_match}건</b>"은 '
                f'그중 <b>선행 핵심감사사항의 회계쟁점이 뒤의 의견변형 근거에 같은 사유로 다시 '
                f'등장한</b> 경우임. 예를 들어 아이에이치큐는 FY2021 영업권 손상을 핵심감사사항으로 '
                f'받았고 이후 FY2022 의견거절 근거가 "자산의 실재성·평가 증거 미확보"였음 — 그 '
                f'핵심감사사항은 경고로서 실제 의미가 있었던 것임.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="panel"><span class="h">읽어낸 것</span>'
                f'{n_link}건의 사례 역시 절반에 못 미치고({n_link}/{n_mod}건, '
                f'{n_link/n_mod*100:.0f}%), 그중 사유까지 일치한 것은 {n_match}건뿐임. '
                f'또한, <b style="color:{CORAL}">{firms_match}개사(레드로버·아이에이치큐)에 몰려 '
                f'있어 일반화할 수 없음</b>.<br><br>'
                f'실무적으로, 핵심감사사항은 수위가 조절될 수 있으며, 일반적으로 수익인식과 '
                f'회계추정치로 제시됨을 고려하면, <b style="color:{CORAL}">핵심감사사항을 '
                f'의견변형의 경보라고 볼 여지는 희박하다</b>고 볼 수 있음.</div>', unsafe_allow_html=True)

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.markdown("#### 실제로 이어진 사례")
    show = s.copy()
    show["사유 일치"] = show.일치.map({1: "일치", 0: "불일치"})
    show["선행"] = "FY" + show.선행연도.astype(str) + " · " + show.선행기재
    show["후행"] = "FY" + show.후행연도.astype(str) + " · " + show.후행기재
    show = show[["기업명", "군", "선행", "후행", "간격", "사유 일치", "사유일치"]].rename(
        columns={"사유일치": "일치한 사유", "간격": "간격(년)"})
    # width는 픽셀 정수로 직접 지정함 — "small"/"large" 같은 프리셋은 열 합이 컨테이너 폭을
    # 넘겨 왼쪽의 기업명이 스크롤 밖으로 밀려났었음(실제로 겪음). "일치한 사유"의 남는 여백을
    # 줄여 기업명 쪽에 폭을 더 준다.
    st.dataframe(show.sort_values("기업명"), use_container_width=True, hide_index=True,
                height=330, column_config={
                    "기업명": st.column_config.TextColumn(width=110),
                    "군": st.column_config.TextColumn(width=54),
                    "선행": st.column_config.TextColumn(width=210),
                    "후행": st.column_config.TextColumn(width=150),
                    "간격(년)": st.column_config.NumberColumn(width=70),
                    "사유 일치": st.column_config.TextColumn(width=64),
                    "일치한 사유": st.column_config.TextColumn(width=170),
                })

# ─────────────────────────────────────────────── 03
elif sec.startswith("03"):
    n = len(bas)
    n_firm = bas.기업명.nunique()
    key = set(zip(bas.corp_code, bas.fy))
    carry = sum(1 for c, f in key if (c, f - 1) in key)
    n_carryover = int(bas.사유.str.contains("기초잔액").sum())  # "읽어낸 것" 패널과 같은 계산 재사용
    head("Section 03 · 의견변형 사유",
         "콘텐츠 산업 기업의 의견변형 사유",
         f"FY2019~2025 동안 의견변형은 <b>{n}건</b>, 사유는 모두 감사범위 제한(부적정의견은 "
         f"0건).<br><br>의견변형 근거 단락을 전수 추출해 사유를 유형화한 결과, 절반에 가까운 "
         f"<b>{n_carryover}건({n_carryover/n*100:.0f}%)</b>이 전기 의견변형이 기초잔액 검증을 "
         f"막아 의견변형이 이월된 것이었음.", warn=True)
    figs([("의견변형", f"{n}건",
           f"의견거절 {int((bas.의견=='의견거절').sum())} · "
           f"한정 {int((bas.의견=='한정의견').sum())}", "neg"),
          ("해당 기업 수", f"{n_firm}개사", f"평균 {n/n_firm:.1f}년씩 연속됨", "amb"),
          ("부적정의견", "0건", "왜곡표시를 단정한 사례 없음", ""),
          ("직전 연도에도 의견변형", f"{carry/n*100:.0f}%", f"{carry}/{n}건", "neg")])

    cnt = {}
    for s in bas.사유.fillna(""):
        for x in [y for y in s.split("|") if y]:
            cnt[x] = cnt.get(x, 0) + 1
    # 표본이 34건뿐이라 %보다 건수가 왜곡 없이 읽힘
    freq = pd.Series(cnt).sort_values()
    fig = go.Figure(go.Bar(y=[b(x) for x in freq.index], x=freq,
                           orientation="h", marker_color=CORAL,
                           hovertemplate="%{y} %{x}건<extra></extra>"))
    fig.update_layout(title=f"의견변형 근거 단락의 사유 유형 (n={n}, 다중 집계, 건수)")
    chart(fig, h=max(360, 32 * len(freq) + 80))

    st.markdown(f'<div class="panel"><span class="h">의견변형은 스스로를 재생산한다</span>'
                f'근거 단락 {n_carryover}건에 '
                f'"전기 재무제표를 타감사인이 감사했고 의견을 표명하지 않았으므로 기초잔액에 대한 '
                f'충분하고 적합한 증거를 확보하지 못했다"는 취지가 명시돼 있음. '
                f'전기에 한 번 의견변형이 나면 당기 감사인은 기초잔액을 검증할 방법이 없어 '
                f'당기도 의견변형이 됨. 실제로 {n}건이 {n_firm}개사에서 나왔고 '
                f'평균 {n/n_firm:.1f}년씩 연속됨.</div>', unsafe_allow_html=True)

    L, R = st.columns([1.1, 1])
    with L:
        seq = bas.groupby(["기업명", "군"]).agg(
            연도수=("fy", "size"), 기간=("fy", lambda s: f"{s.min()}–{s.max()}"),
            의견=("의견", lambda s: "·".join(sorted(set(s))))).reset_index()
        st.markdown("**기업별 의견변형 지속 기간**")
        st.dataframe(seq.sort_values("연도수", ascending=False), use_container_width=True,
                     hide_index=True, height=330)
    with R:
        by = bas.groupby("군").size()
        st.markdown("**부문별**")
        st.dataframe(pd.DataFrame({"의견변형 건수": by,
                                   "기업 수": bas.groupby("군").기업명.nunique()}),
                     use_container_width=True)
        st.markdown(f'<div class="body">한정의견은 <b>3건</b>뿐이며 모두 한 기업'
                    f'(로아앤코홀딩스 FY2023–2025)임. 의견변형의 실질은 의견거절이므로 '
                    f'분석의 초점을 의견거절에 둠.</div>', unsafe_allow_html=True)

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.markdown("#### 의견변형 근거 단락 원문")
    pick = st.selectbox("건 선택", [f"{r.기업명} · FY{r.fy} · {r.의견}" for r in bas.itertuples()])
    row = bas.iloc[[f"{r.기업명} · FY{r.fy} · {r.의견}" for r in bas.itertuples()].index(pick)]
    st.markdown("".join(f'<span class="chip">{x}</span>'
                        for x in str(row.사유).split("|") if x), unsafe_allow_html=True)
    st.markdown(f'<div class="src">{row.근거단락}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────── 04
else:
    head("Section 04 · 방법론, 한계점",
         "공개 API가 주지 않는 데이터를<br>원문에서 꺼내 검증",
         "감사보고서 전문은 공시유형 검색으로 받을 수 없음(거래소 「감사보고서제출」 공시는 "
         "표지 3천여 자뿐). <b>사업보고서 원문 ZIP에 첨부된 별도·연결 감사보고서</b>를 통해서만 "
         "확보됨. 여기서 핵심감사사항·계속기업 불확실성·감사의견·의견근거를 추출함.")
    figs([("감사보고서 확보율", "98.4%", "626 / 636 firm-year", ""),
          ("규칙기반 분류", "93.8%", "코드가 처리", ""),
          ("LLM 보조 분류", "5.5%", "규칙이 놓친 잔여분만", "amb"),
          ("사람 표본검증", "κ 0.930", "무작위 75건 blind 재분류", "")])

    steps = pd.DataFrame([
        ("① 모집단", "E&M 78개사(59x·60x·90x + 웹툰·웹소설) + Game 대조군 31개사(5821)",
         "636 firm-year (FY2019~2025)"),
        ("② 원문 수집", "사업보고서 ZIP 806건 — 정정본→원본 순 폴백", "캐시 후 재사용"),
        ("③ 추출", "핵심감사사항 · 계속기업 · 감사의견 · 의견근거", "확보 98.4%"),
        ("④ 규칙 분류", "13개 유형, 키워드 규칙", "93.8%"),
        ("⑤ LLM 보조", "규칙 미분류분만. 판정을 코드에 고정해 재현 가능화", "5.5%"),
        ("⑥ 사람 표본검증", "무작위 75건 blind 재분류 (FY2019~2024 60 + FY2025 15)",
         "일치율 94.5% · κ=0.930"),
        ("⑦ 후속 결과", "t+1·t+2 의견변형 / 계속기업 재기재 / 제출 중단", "관측가능 541"),
    ], columns=["단계", "내용", "결과"])
    st.dataframe(steps, use_container_width=True, hide_index=True)

    st.markdown(f'<div class="panel"><span class="h">규칙·LLM·본인 검증의 3단 구조</span>'
                f'분류 기준을 먼저 규칙으로 세워 코드가 처리하게 했고(93.8%), 규칙이 잡지 못한 '
                f'잔여만 LLM이 원문을 읽어 분류한 뒤 <b>그 판정을 코드에 표로 고정</b>해 재현 '
                f'가능하게 만듦(5.5%, 자동 API 호출이 아님). 이 결과를 그대로 믿지 않기 위해 '
                f'<b>본인이 직접</b> 자동 분류 결과를 가린 채 무작위 75건을 blind 재분류해 대조함 '
                f'(일치율 94.5% · κ=0.930). 이 과정에서 <b>자동화가 조용히 만든 결함</b>을 찾아냄 — '
                f'감사보고서 XML이 서식 때문에 단어 중간에서 태그를 끊어 항목명과 섹션 표제가 잘리고 '
                f'있었음(예: 「유형자산의 실재성과 평가」→「형자산의…」). 인접한 같은 서식 조각만 '
                f'병합하도록 고쳐 해결함.</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="panel"><span class="h">1차 완성 이후의 수기검증</span>'
                f'완성 후 태그 병합·연결 우선 채택·FY2025 확장까지 <b>파이프라인을 세 차례 다시 '
                f'정리</b>하며 상당한 시간을 들여 오류를 잡아냄. 그때마다 원표본을 다시 대조한 결과 '
                f'60건 중 <b>43건이 존속했고 분류가 바뀐 건은 0건</b>이었음. 판단 불가로 표시했던 '
                f'3건도 분류 기준의 모호함이 아니라 원문 추출 한계(선정 이유 구간 누락)에서 나온 '
                f'것으로 확인됨.</div>', unsafe_allow_html=True)

    st.markdown("#### 한계")
    st.markdown(f'<div class="panel">'
                f'· <b>후속 결과는 프록시임.</b> 실제 부도·상장폐지 자료 대신 의견변형·사업보고서 제출 '
                f'중단·계속기업 재기재로 대체했으므로 M&amp;A로 인한 제출 중단이 섞일 수 있음<br>'
                f'· <b>부적정의견 0건은 이 표본에서의 관측</b>이며 일반 명제가 아님<br>'
                f'· <b>Game 부문은 업종코드 5821 접두로만 정의함.</b> 3자리 582는 게임과 시스템·응용 '
                f'소프트웨어를 구분할 수 없어 제외했고 그 안에 엔씨소프트·컴투스홀딩스·넥슨게임즈가 포함됨<br>'
                f'· <b>핵심감사사항은 기업 안에 중첩됨.</b> 항목 단위 검정은 독립성 가정을 어기므로 '
                f'기업 단위 재검정을 병기했고 결과가 갈리면 확정하지 않음<br>'
                f'· <b>κ 표본은 75건.</b> FY2019~2024에서 60건, FY2025에서 15건을 각각 무작위 '
                f'추출해 모집단 전 구간을 덮었으나, 표본 규모가 작아 추정치의 신뢰구간은 넓음 '
                f'(유효 55건 기준 κ=0.930)<br>'
                f'· <b>항목명 추출 실패 {n_bad}건</b>({n_bad/len(kam)*100:.1f}%)이 남아 있어 '
                f'화면에서는 대체 문구로 표시함<br>'
                f'· <b>원문 구간이 한쪽만 잡힌 항목이 있음.</b> 감사보고서가 이유·방법을 소제목으로 '
                f'나누지 않는 형식이면 한 구간만 분리됨 — 선정 이유 미확보 {n_noreason}건'
                f'({n_noreason/len(kam)*100:.1f}%), 감사절차 미확보 {n_noproc}건'
                f'({n_noproc/len(kam)*100:.1f}%). 유형 분류는 항목명과 확보된 구간으로 이뤄지므로 '
                f'분류 자체에는 영향이 적으나, 원문 열람에서는 해당 구간이 표시되지 않음<br>'
                f'· <b>FY2019는 다른 연도와 비교 불가</b> — 핵심감사사항 단계 도입기<br>'
                f'· <b>감사인별 성과 비교는 수행하지 않음.</b> 감사인마다 클라이언트 구성이 달라 '
                f'통제 없는 비교는 감사 품질이 아니라 클라이언트 구성을 재게 됨</div>',
                unsafe_allow_html=True)

    st.markdown(f'<div class="panel" style="border-left:3px solid {AMBER}">'
                f'<span class="h" style="color:{AMBER}">한계 — 계속기업 관련 중요한 불확실성은 '
                f'섹션 02에서 제외함</span>'
                f'초안에는 KAM↔계속기업 경로도 포함했으나, 계속기업 불확실성은 감사인 판단이 매개하는 '
                f'사건이라기보다 회사의 존속 상태라는 같은 원인이 매년 다른 단락에 반복 관찰되는 것에 '
                f'가까워 인과로 서술하기 어려웠음. 기재 원문은 아래에서 참고로만 열람할 수 있게 둠.</div>',
                unsafe_allow_html=True)

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.markdown("#### 참고 — 계속기업 관련 중요한 불확실성 단락 원문")
    gcrec = pan[pan.has_gc == 1]
    n_gc = len(gcrec)
    st.markdown(f'<div class="body">섹션 02의 연계 분석에는 포함하지 않았으나(위 한계 참고), '
                f'기재된 <b>{n_gc}건 전수</b>를 참고 자료로 열람할 수 있음.</div>',
                unsafe_allow_html=True)
    gtxt = load_gc_text(data_signature())
    g2 = gcrec.merge(gtxt, on=["corp_code", "fy"], how="left")
    labels = [f"{r.기업명} · FY{r.fy} · {r.opinion}" for r in g2.itertuples()]
    sel = st.selectbox("건 선택", labels, key="gc_ref_select")
    row = g2.iloc[labels.index(sel)]
    st.markdown(f'<span class="chip">{row.군}</span><span class="chip">감사의견 {row.opinion}</span>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="src">{str(row.gc_text)[:2600]}</div>', unsafe_allow_html=True)
