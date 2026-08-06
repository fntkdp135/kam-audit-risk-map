# -*- coding: utf-8 -*-
"""③ 감사보고서에서 핵심감사사항(KAM)·계속기업 불확실성(GC)·감사의견·감사인 추출.

설계 메모
- 인코딩: 선언(encoding="utf-8")이 거짓인 파일이 있음. strict utf-8 → cp949 순으로
  fallback하고 errors='replace'는 절대 쓰지 않음(조용히 깨져 0건으로 집계됨).
- 표제 변형이 많음: "결정된 이유"/"결정한 이유"/"선정한 이유",
  "핵심감사사항이 감사에서 다루어진 방법"/"감사에서 다루어진 방법"/"감사상 대응" 등.
- KAM 항목명은 '이유' 표제 바로 앞의 짧은 줄로 잡는다(관측된 구조).
"""
import os, re, sys, html, zipfile, glob
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, "data", "raw", "docs")
OUT = os.path.join(ROOT, "data", "processed")

# ---------------------------------------------------------------- 공통 유틸

def decode(raw: bytes) -> str:
    for enc in ("utf-8", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")  # 최후수단(집계 시 별도 표시)


def to_text(xml: str) -> str:
    """XML → 줄 구조를 보존한 평문.

    주의: DART XML은 서식 때문에 **단어 중간에서 <SPAN>을 끊는다.**
      <SPAN>가. 유</SPAN>\\n<SPAN>형자산의 실재성과 평가</SPAN>
      <SPAN>매출인식의 정</SPAN>\\n<SPAN>확성</SPAN>
    태그 사이의 원본 개행을 줄바꿈으로 취급하면 '형자산의 실재성과 평가', '확성' 같은
    잘린 제목이 만들어지고, 섹션 표제('연결재무제표감사에…'→'결재무제표감사에…')도
    판별에 실패해 KAM 섹션이 뒷 섹션을 삼킨다.

    해결: **인접한 동일 서식 SPAN을 먼저 병합**한다(역참조로 속성이 같을 때만).
    같은 서식이면 원래 한 덩어리 텍스트가 서식엔진 때문에 쪼개진 것이고,
    서식이 바뀌는 지점(볼드 표제 → 일반 본문)은 실제 구분이므로 줄바꿈은 유지해야 한다.
    (원본 개행을 전부 지우면 단어 분절은 고쳐지지만 표제 구분이 사라져
     섹션 검출이 426건 → 290건으로 무너진다. 실제로 겪은 실패.)
    """
    t = xml
    prev = None
    for _ in range(6):                      # 3조각 이상 쪼개진 경우가 있어 반복 적용
        if prev == t:
            break
        prev = t
        t = re.sub(r"<SPAN([^>]*)>((?:(?!</SPAN>).)*?)</SPAN>\s*<SPAN\1>",
                   r"<SPAN\1>\2", t, flags=re.S)
    t = re.sub(r"<(BR|br)\s*/?>", "\n", t)
    t = t.replace("&cr;", "\n")
    t = re.sub(r"</(P|SPAN|TD|TR|TITLE|TE)>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = t.replace("\xa0", " ").replace("　", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in t.split("\n")]
    return "\n".join(ln for ln in lines if ln)


# ---------------------------------------------------------------- 표제 사전

SECTION_PATTERNS = [
    r"핵심감사사항", r"강조사항", r"기타사항", r"기타\s*기재사항",
    r"계속기업\s*관련\s*중요한?\s*불확실성",
    r"(한정의견|부적정의견|의견거절|감사의견)\s*근거", r"의견근거",
    r"재무제표에\s*대한\s*경영진과\s*지배기구의\s*책임",
    r"재무제표감사에\s*대한\s*감사인의\s*책임",
    r"감사보고서\s*이용상의\s*유의사항",
    r"내부회계관리제도",
    r"(연결)?재무제표\s*및\s*감사보고서",
]
# 표제에 '연결' 접두가 붙는 보고서가 많다("연결재무제표감사에 대한 감사인의 책임").
# 이를 놓치면 KAM 섹션이 뒷 섹션을 통째로 삼켜 감사인의 책임 문단 끝의 정형 선언문
# ("...가장 유의적인 사항을 핵심감사사항으로 결정합니다")이 KAM 항목으로 잡힌다.
RE_SECTION = re.compile(r"^\s*(?:연결)?\s*(?:%s)\s*[:：]?\s*$" % "|".join(SECTION_PATTERNS))

RE_KAM_HEAD = re.compile(r"^\s*핵심감사사항\s*[:：]?\s*$")
RE_GC_HEAD = re.compile(r"계속기업\s*관련\s*중요한?\s*불확실성")

# 소제목은 회사·감사인마다 표현이 제각각이라 정규식 열거로는 못 따라간다.
# 실측된 변형: "핵심감사사항으로 결정한/결정된/선정한 이유", "해당 사항이 핵심감사사항으로 식별된 이유",
#              "핵심감사사항이 감사에서 다루어진 방법", "해당 사항이 감사에서 다루어진 방법",
#              "감사상 대응", "우리의 대응"
# → '짧은 줄 + 핵심어 조합' 휴리스틱으로 판별한다.
def is_reason_head(ln: str) -> bool:
    return (len(ln) <= 45 and "이유" in ln
            and any(k in ln for k in ("핵심감사사항", "식별", "결정", "선정", "판단")))


def is_proc_head(ln: str) -> bool:
    if len(ln) > 45:
        return False
    if any(k in ln for k in ("감사에서 다루어진", "감사상 대응", "감사에서의 대응", "우리의 대응")):
        return True
    return ("감사" in ln and ln.rstrip(" :：").endswith(("방법", "절차", "대응"))
            and not ln.endswith(("니다.", "습니다")))


class _RE:                       # 기존 호출부 호환용 얇은 래퍼
    def __init__(self, fn): self.fn = fn
    def match(self, s): return self.fn(s.strip())


RE_REASON = _RE(is_reason_head)
RE_PROC = _RE(is_proc_head)

RE_OPINION_MOD = re.compile(r"^\s*(한정의견|부적정의견|의견거절)\s*[:：]?\s*$")

# 감사의견 판정 — 표제가 아니라 '결정적 문구'로 판정한다.
# 표제만 보면 잡히지 않고(의견거절 표제는 실제로 거의 없음),
# 문서 앞부분 키워드로 폴백하면 **목차를 읽어버린다**(실제로 겪은 오류).
# 「독립된 감사인의 감사보고서」의 모든 출현 위치를 앞에서부터 훑되,
# 마지막 출현은 서명란("…근거가 된 감사를 실시한 업무수행이사는")이라 의견 문단을 지나침.
RE_AR_HEAD = re.compile(r"독립된\s*감사인의\s*감사보고서")
OPINION_PAT = [
    ("의견거절", re.compile(r"의견을?\s*표명하지\s*않습니다|감사의견을?\s*표명하지\s*아니"
                          r"|의견거절의?\s*근거|의견거절근거")),
    ("부적정의견", re.compile(r"공정하게\s*표시하고\s*있지\s*않습니다|부적정의견의?\s*근거|부적정의견근거")),
    ("한정의견", re.compile(r"한정의견의?\s*근거|한정의견근거")),
    ("적정", re.compile(r"중요성의\s*관점에서\s*공정하게\s*표시하고\s*있습니다")),
]
RE_BASIS_HEAD = re.compile(r"(한정의견|부적정의견|의견거절)\s*(?:의\s*)?근거")


def judge_opinion(text: str) -> str:
    for s in [m.start() for m in RE_AR_HEAD.finditer(text)] + [0]:
        body = text[s:s + 9000]
        for k, c in OPINION_PAT:
            if c.search(body):
                return k
    for k, c in OPINION_PAT:
        if c.search(text):
            return k
    return "미상"


def extract_basis(text: str, secs) -> str:
    """의견변형 근거 단락. 섹션 분할로 먼저 찾고, 없으면 표제 위치에서 잘라낸다."""
    for name, body in secs:
        if RE_BASIS_HEAD.search(name):
            return re.sub(r"\s+", " ", " ".join(body))[:3000]
    m = RE_BASIS_HEAD.search(text)
    if not m:
        return ""
    tail = text[m.start():m.start() + 4000]
    cut = re.search(r"\n\s*(?:연결)?\s*(?:재무제표에\s*대한\s*경영진|재무제표감사에\s*대한\s*감사인"
                    r"|기타사항|핵심감사사항|감사보고서\s*이용상)", tail)
    return re.sub(r"\s+", " ", tail[:cut.start()] if cut else tail)[:3000]
RE_AUDITOR = re.compile(r"([가-힣A-Za-z0-9\(\)\s]{2,20}?회계법인)")
RE_NO_KAM = re.compile(r"핵심감사사항[이가]?\s*(없|해당\s*사항\s*없)")

BOILER = re.compile(
    r"핵심감사사항은\s*우리의\s*전문가적\s*판단|별도의\s*의견을\s*제공하지는?\s*않"
    r"|재무제표\s*전체에\s*대한\s*감사의\s*관점"
    r"|지배기구와\s*커뮤니케이션|가장\s*유의적인\s*사항"
    r"|우리의\s*의견형성|의견을\s*표명하지\s*않")


def split_sections(text: str):
    """(표제, 본문) 리스트로 분할."""
    lines = text.split("\n")
    marks = [i for i, ln in enumerate(lines) if RE_SECTION.match(ln)]
    out = []
    for k, i in enumerate(marks):
        end = marks[k + 1] if k + 1 < len(marks) else len(lines)
        out.append((lines[i].strip(" :："), lines[i + 1:end]))
    return out


# --- 형식 편차 흡수용 ---------------------------------------------------
# 감사보고서 형식은 최소 3가지로 갈린다:
#   A) "핵심감사사항으로 결정한 이유"/"감사에서 다루어진 방법" 소제목이 있는 형식
#   B) "(핵심감사사항) 현금창출단위 손상 평가"처럼 괄호 표기만 있는 형식
#   C) 줄바꿈 없이 한 덩어리로 붙어 항목명과 본문이 분리되지 않는 형식
# 세 형식에 공통으로 존재하는 것은 "~을 핵심감사사항으로 결정/판단하였습니다" 선언문이므로
# 이를 1차 앵커로 쓰고, 소제목·괄호표기를 항목명 보강에 사용한다.
RE_DECL = re.compile(
    r"([^.。\n]{2,90}?)\s*(?:을|를)\s*(?:당기\s*)?핵심감사사항(?:으로|에|이라고)?\s*"
    r"(?:결정|판단|선정|식별|지정|포함)")
RE_PAREN_KAM = re.compile(r"^\s*[\(\[]\s*핵심감사사항\s*[\)\]]\s*(.+)$")
RE_LEAD = re.compile(
    r"^(?:그러므로|따라서|이에\s*따라|이에|그\s*결과|또한|그리고|우리는|본인은|본\s*감사인은"
    r"|이러한\s*(?:관점에서|이유로|점을?\s*고려하여)?|상기|위와\s*같이|이와\s*같이"
    r"|이상을?\s*종합하여|결과적으로)\s*[,·]?\s*")
PRONOUN = re.compile(r"^(이|이것|이를|해당\s*사항|동\s*사항|상기\s*사항|위\s*사항|이러한\s*사항)$")
RE_PROC_LEAD = re.compile(r"(감사절차는\s*다음과\s*같|다음과\s*같은\s*(?:주요\s*)?감사절차|"
                          r"우리가\s*수행한\s*(?:주요\s*)?감사절차)")


def clean_title(s: str) -> str:
    s = s.strip(" :：·ㆍ-–—()[]\t")
    s = re.sub(r"^(?:[가-힣]\.|\(?\d+[\.\)]|[①-⑳])\s*", "", s).strip()   # "1)", "가.", "(1)"
    s = re.sub(r"핵심감사사항(?:으로|에).*$", "", s).strip()   # 선언문 꼬리 제거
    prev = None
    while prev != s:                      # 선행 접속부사 반복 제거
        prev = s
        s = RE_LEAD.sub("", s).strip(" ,·ㆍ-")
    if "," in s and len(s) > 40:          # 긴 수식절이 앞에 붙은 경우 마지막 절만
        s = s.split(",")[-1].strip()
        s = RE_LEAD.sub("", s).strip()
    return s[:60].strip()


def parse_kam_decl(body: list) -> list:
    """선언문 기반 추출 (형식 A/B/C 공통)."""
    text = "\n".join(body)
    paren = {}                            # 괄호표기 항목명 (형식 B)
    for i, ln in enumerate(body):
        m = RE_PAREN_KAM.match(ln)
        if m:
            paren[text.find(ln)] = m.group(1).strip()

    # 줄별 시작 오프셋 (선언문 위치 → 직전 제목줄 역추적용)
    offs, pos = [], 0
    for ln in body:
        offs.append((pos, ln))
        pos += len(ln) + 1

    def title_before(p: int) -> str:
        """위치 p 직전의 '제목처럼 생긴 줄'. 본문 문장·정형문구·소제목은 제외."""
        for start, ln in reversed(offs):
            if start >= p:
                continue
            s = ln.strip()
            if not s or len(s) > 60 or BOILER.search(s):
                continue
            if is_reason_head(s) or is_proc_head(s):
                continue
            if s.endswith(("니다.", "습니다", "합니다.", "됩니다.", "입니다.")):
                continue
            pm = RE_PAREN_KAM.match(s)                            # "(핵심감사사항) 손상평가"
            if pm:
                s = pm.group(1)
            s = re.sub(r"^(?:[가-힣]\.|\(?\d+[\.\)])\s*", "", s)   # "가.", "(1)", "1)"
            t = clean_title(s)
            if t and len(t) >= 3 and not PRONOUN.match(t):
                return t
        return ""

    decls = list(RE_DECL.finditer(text))
    if not decls:
        return []
    items = []
    for k, m in enumerate(decls):
        # 항목명 출처 우선순위: 괄호표기 > 직전 제목줄 > 선언문 역추출(최후수단).
        # 선언문 역추출은 긴 수식절을 통째로 물고 오므로 짧을 때만 신뢰한다.
        cands = [v for p, v in paren.items() if p < m.start()]
        title, src = "", ""
        if cands:
            title, src = clean_title(cands[-1]), "paren"
        if not title:
            title, src = title_before(m.start()), "lookback"
        if not title:
            t = clean_title(m.group(1))
            if t and len(t) <= 35 and not PRONOUN.match(t) and not BOILER.search(t):
                title, src = t, "decl"
        if not title or len(title) < 4 or PRONOUN.match(title) or BOILER.search(title):
            continue
        start = decls[k - 1].end() if k else 0
        end = decls[k + 1].start() if k + 1 < len(decls) else len(text)
        blk = text[start:end]
        pm = RE_PROC_LEAD.search(blk, m.end() - start if m.end() > start else 0)
        items.append(dict(
            kam_title=title, title_source=src,
            reason_text=re.sub(r"\s+", " ", blk[:pm.start()] if pm else blk)[:2500],
            procedure_text=re.sub(r"\s+", " ", blk[pm.start():] if pm else "")[:2500],
        ))
    # 동일 항목명 중복 제거(같은 KAM을 두 번 선언하는 보고서가 있음)
    seen, out = set(), []
    for it in items:
        k = re.sub(r"[\s\W]", "", it["kam_title"])
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def parse_kam(body: list) -> list:
    """KAM 본문 줄 목록 → 항목 리스트. 소제목 방식 우선, 실패 시 선언문 방식."""
    items = []
    idx_reason = [i for i, ln in enumerate(body) if RE_REASON.match(ln)]
    idx_proc = [i for i, ln in enumerate(body) if RE_PROC.match(ln)]

    if idx_reason:
        for k, ri in enumerate(idx_reason):
            # 항목명 = 이유 표제 직전의 짧은 줄(정형문구·표제 제외)
            title = ""
            for j in range(ri - 1, max(-1, ri - 8), -1):
                ln = body[j]
                if not ln or BOILER.search(ln) or RE_PROC.match(ln) or RE_REASON.match(ln):
                    continue
                if len(ln) <= 90 and not ln.endswith(("니다.", "습니다", "합니다.")):
                    title = ln.strip(" :：·-")
                    break
            nxt = idx_reason[k + 1] if k + 1 < len(idx_reason) else len(body)
            pr = [p for p in idx_proc if ri < p < nxt]
            r_end = pr[0] if pr else nxt
            reason = " ".join(body[ri + 1:r_end])
            proc = " ".join(body[pr[0] + 1:nxt]) if pr else ""
            items.append(dict(kam_title=title, reason_text=reason, procedure_text=proc))
    else:
        # 폴백: '방법' 표제만 있는 형식
        for k, pi in enumerate(idx_proc):
            title = ""
            for j in range(pi - 1, max(-1, pi - 8), -1):
                ln = body[j]
                if ln and not BOILER.search(ln) and len(ln) <= 90 \
                        and not ln.endswith(("니다.", "습니다", "합니다.")):
                    title = ln.strip(" :：·-")
                    break
            nxt = idx_proc[k + 1] if k + 1 < len(idx_proc) else len(body)
            items.append(dict(kam_title=title, reason_text="",
                              procedure_text=" ".join(body[pi + 1:nxt])))

    items = [it for it in items if it["kam_title"]]
    for it in items:
        it["kam_title"] = clean_title(it["kam_title"])
        it["title_source"] = "subhead"
    items = [it for it in items if it["kam_title"] and not PRONOUN.match(it["kam_title"])]

    # 소제목 방식이 실패했거나 항목을 덜 잡았으면 선언문 방식으로 대체
    decl = parse_kam_decl(body)
    if len(decl) > len(items):
        return decl
    return items


def parse_report(text: str, doc_name: str) -> dict:
    secs = split_sections(text)
    sec_names = [s[0] for s in secs]
    kam_items, kam_found = [], False
    for name, body in secs:
        if RE_KAM_HEAD.match(name + " "):
            kam_found = True
            kam_items.extend(parse_kam(body))

    gc_text = ""
    for name, body in secs:
        if RE_GC_HEAD.search(name):
            gc_text = " ".join(body)[:2000]
            break
    if not gc_text and RE_GC_HEAD.search(text):
        i = RE_GC_HEAD.search(text).start()
        gc_text = re.sub(r"\s+", " ", text[i:i + 1200])

    opinion = judge_opinion(text)
    basis_text = extract_basis(text, secs) if opinion in (
        "한정의견", "부적정의견", "의견거절") else ""

    aud = RE_AUDITOR.findall(text)
    auditor = ""
    if aud:
        auditor = max(set(aud), key=aud.count).strip()
        auditor = re.sub(r"\s+", " ", auditor)

    return dict(
        doc_type="연결" if "연결" in doc_name else "별도",
        kam_section_found=int(kam_found),
        no_kam_stated=int(bool(RE_NO_KAM.search(text))),
        n_kam=len(kam_items),
        has_gc=int(bool(gc_text)),
        gc_text=gc_text,
        opinion=opinion,
        opinion_basis=basis_text,
        auditor=auditor,
        n_sections=len(secs),
        sections="|".join(sec_names[:20]),
        _items=kam_items,
    )


# ---------------------------------------------------------------- 메인

def main():
    rep = pd.read_csv(os.path.join(OUT, "reports.csv"), dtype=str, encoding="utf-8-sig")
    rep["cand_rank"] = rep["cand_rank"].astype(int)
    rep["fy"] = rep["fy"].astype(int)

    meta_rows, item_rows = [], []
    groups = list(rep.sort_values("cand_rank").groupby(["corp_code", "fy"]))

    for gi, ((cc, fy), g) in enumerate(groups, 1):
        info = g.iloc[0]
        got = False
        for r in g.itertuples():                       # 정정본 → 원본 폴백
            zp = os.path.join(DOCS, f"{r.rcept_no}.zip")
            if not os.path.exists(zp):
                continue
            try:
                z = zipfile.ZipFile(zp)
            except Exception:
                continue
            docs = []
            for n in z.namelist():
                raw = z.read(n)
                txt = decode(raw)
                dn = re.search(r"<DOCUMENT-NAME[^>]*>([^<]*)", txt)
                nm = dn.group(1).strip() if dn else ""
                if "감사보고서" in nm and "내부회계" not in nm:
                    docs.append((nm, txt))
            if not docs:
                continue
            # 연결 우선(2번 프로젝트의 CFS 우선 원칙 승계)
            docs.sort(key=lambda x: 0 if "연결" in x[0] else 1)
            for nm, txt in docs:
                p = parse_report(to_text(txt), nm)
                items = p.pop("_items")
                meta_rows.append(dict(corp_code=cc, fy=fy, 기업명=info.기업명, 군=info.군,
                                      업종코드=info.업종코드, rcept_no=r.rcept_no,
                                      is_amend=int(r.is_amend), doc_name=nm, **p))
                for si, it in enumerate(items, 1):
                    item_rows.append(dict(corp_code=cc, fy=fy, 기업명=info.기업명, 군=info.군,
                                          rcept_no=r.rcept_no, doc_type=p["doc_type"],
                                          kam_seq=si, **it))
            got = True
            break
        if not got:
            meta_rows.append(dict(corp_code=cc, fy=fy, 기업명=info.기업명, 군=info.군,
                                  업종코드=info.업종코드, rcept_no="", is_amend=0,
                                  doc_name="", doc_type="", kam_section_found=0,
                                  no_kam_stated=0, n_kam=0, has_gc=0, gc_text="",
                                  opinion="", opinion_basis="", auditor="",
                                  n_sections=0, sections=""))
        if gi % 100 == 0:
            print(f"  {gi}/{len(groups)} firm-year 처리")

    meta = pd.DataFrame(meta_rows)
    items = pd.DataFrame(item_rows)
    meta.to_csv(os.path.join(OUT, "report_meta.csv"), index=False, encoding="utf-8-sig")
    items.to_csv(os.path.join(OUT, "kam_items.csv"), index=False, encoding="utf-8-sig")

    prim = meta[(meta.doc_type == "연결") | (~meta.duplicated(["corp_code", "fy"], keep="first"))]
    prim = meta.sort_values("doc_type").drop_duplicates(["corp_code", "fy"], keep="first")
    print("\n=== 추출 결과")
    print(f"firm-year {len(groups):,}건 / 감사보고서 확보 {(prim.doc_name!='').sum():,}건 "
          f"({(prim.doc_name!='').mean()*100:.1f}%)")
    print(f"KAM 섹션 검출 {prim.kam_section_found.sum():,}건 / KAM 항목 {len(items):,}개")
    print(f"항목 0개인데 섹션은 있는 건 {((prim.kam_section_found==1)&(prim.n_kam==0)).sum():,}건")
    print(f"GC 기재 {prim.has_gc.sum():,}건")
    print(f"\n연도별 KAM 항목 수(1보고서 기준 중앙값):")
    print(prim[prim.n_kam > 0].groupby(["군", "fy"])["n_kam"].median().unstack().to_string())
    print(f"\n감사의견 분포:\n{prim.opinion.value_counts().to_string()}")
    print(f"\nGC 기재 firm-year:\n{prim[prim.has_gc==1].groupby(['군','fy']).size().to_string()}")


if __name__ == "__main__":
    main()
