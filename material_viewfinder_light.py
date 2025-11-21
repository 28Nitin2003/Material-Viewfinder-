# ==========================================================
# MATERIAL VIEWFINDER — HYBRID MULTI-KEYWORD SEARCH
# + SAP LIST + RECENT SEARCHES + GLOBAL SEARCH
# ==========================================================

import os
import re
import pandas as pd
import numpy as np
import streamlit as st

# ---------------- FILES ----------------
FILES = {
    "Spreader": "Spreader Material Master.xlsx",
    "Drawing": "Drawing Material Master.xlsx",
    "Carding": "Carding Material Master.xlsx",
    "Spinning": "Spinning Material Master.xlsx",
    "Spool Winding": "Spool Winding Material Master.xlsx",
}

KEY_MAT = "Material"
KEY_DESC = "Material Proposed Description"

# COLORS
BLUE = "#00B4D8"
DARK_BLUE = "#003566"
DARK_GREEN = "#064E3B"
LIGHT_GREEN = "#D1FAE5"
BORDER_GREEN = "#48BB78"

# ==========================================================
# DATA EXTRACTION
# ==========================================================
def extract_tables(df: pd.DataFrame):
    """Find each header row (where Material & Material Proposed Description sit)
    and slice the table below it."""
    A = df.copy()
    vals = A.astype(str).values

    mat_rows = np.where(vals == KEY_MAT)[0]
    desc_rows = np.where(vals == KEY_DESC)[0]
    headers = sorted(set(mat_rows).intersection(set(desc_rows)))

    tables = []
    for i, r in enumerate(headers):
        header_vals = A.iloc[r].astype(str).tolist()
        cols = [
            c for c, v in enumerate(header_vals)
            if v.strip() not in ("", "nan", "None", "NaN")
        ]
        if not cols:
            continue

        end = headers[i + 1] if i + 1 < len(headers) else len(A)
        block = A.iloc[r + 1:end, cols].copy()
        block.columns = [header_vals[c] for c in cols]
        block = block.dropna(how="all")

        for c in block.columns:
            block[c] = block[c].astype(str).str.strip()

        if not block.empty:
            tables.append(block)

    return tables


@st.cache_data(show_spinner=True)
def load_all():
    rows = []
    base = os.path.dirname(os.path.abspath(__file__))

    for dept, fname in FILES.items():
        path = os.path.join(base, fname)
        if not os.path.exists(path):
            continue

        xls = pd.ExcelFile(path)
        for sheet in xls.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet, header=None)
            for tbl in extract_tables(df):
                T = tbl.copy()
                T["Department"] = dept

                machine = sheet.strip()
                if machine.lower() == "sheet1":
                    machine = "Winding"

                T["Machine Type"] = machine
                rows.extend(T.to_dict(orient="records"))

    if not rows:
        return pd.DataFrame()

    df_all = pd.DataFrame(rows)

    # cleanup strings
    for c in df_all.columns:
        df_all[c] = (
            df_all[c].astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

    # normalise empties
    df_all = df_all.replace(
        {"nan": np.nan, "NaN": np.nan, "None": np.nan, "": np.nan}
    )

    # keep only rows having either code or description
    df_all = df_all[(df_all[KEY_MAT].notna()) | (df_all[KEY_DESC].notna())]

    return df_all.reset_index(drop=True)


# ==========================================================
# HELPERS
# ==========================================================
def clean_display(df: pd.DataFrame) -> pd.DataFrame:
    """Remove 'nan' text and show empty cells instead."""
    return df.replace(
        {"nan": "", "NaN": "", "None": "", np.nan: ""}
    ).fillna("")


def parse_keywords(q: str):
    """Split user query into keywords using spaces, comma, semicolon, pipe etc."""
    q = q.lower().strip()
    if not q:
        return []
    parts = re.split(r"[,\s;|]+", q)
    # keep order but remove empties and duplicates
    seen = set()
    keywords = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p not in seen:
            seen.add(p)
            keywords.append(p)
    return keywords


def hybrid_multi_search(df_sub: pd.DataFrame, q: str) -> pd.DataFrame:
    """
    Hybrid multi-keyword search:
    1) AND search (all keywords must appear)
    2) If no AND results -> OR search (any keyword)
    Ranking: based on first keyword in Material Proposed Description.
    """
    keywords = parse_keywords(q)
    if not keywords:
        return df_sub.iloc[0:0].copy()

    df = df_sub.copy()

    # columns to search in
    search_cols = [KEY_MAT, KEY_DESC]
    for extra in ["Material description", "Material Long Description"]:
        if extra in df.columns:
            search_cols.append(extra)

    # combine text for each row
    combined = (
        df[search_cols]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
    )

    # AND mask: all keywords must appear
    masks_and = [combined.str.contains(k) for k in keywords]
    mask_and = np.logical_and.reduce(masks_and) if masks_and else np.zeros(len(df), dtype=bool)

    # OR mask: any keyword appears
    masks_or = [combined.str.contains(k) for k in keywords]
    mask_or = np.logical_or.reduce(masks_or) if masks_or else np.zeros(len(df), dtype=bool)

    if mask_and.any():
        candidates = df[mask_and].copy()
    else:
        candidates = df[mask_or].copy()

    if candidates.empty:
        return candidates

    # Ranking based on FIRST keyword using description column
    first_kw = keywords[0]
    if KEY_DESC in candidates.columns:
        desc = candidates[KEY_DESC].fillna("").astype(str).str.lower()
        starts = desc.str.startswith(first_kw)
        contains = desc.str.contains(first_kw)
        candidates = (
            candidates.assign(
                _starts=starts.astype(int),
                _contains=contains.astype(int),
            )
            .sort_values(by=["_starts", "_contains"], ascending=[False, False])
            .drop(columns=["_starts", "_contains"])
        )

    return candidates.reset_index(drop=True)


# ==========================================================
# UI & CSS
# ==========================================================
st.set_page_config(page_title="Material Viewfinder", layout="wide")

st.markdown(
    f"""
<style>
* {{ border-radius:0px !important; }}

body, .stApp {{
    background:white !important;
    font-family: 'Inter', sans-serif !important;
}}

h1,h2,h3,h4 {{
    color:{DARK_BLUE} !important;
    font-weight:900 !important;
}}

.stSelectbox label p, .stTextInput label p {{
    font-weight:900 !important;
    color:{DARK_BLUE} !important;
}}

.stTextInput input {{
    border:2px solid {BLUE} !important;
    background:white !important;
    color:{BLUE} !important;
    caret-color:{BLUE} !important;
    font-weight:700 !important;
}}

.stButton>button {{
    background:{BLUE} !important;
    color:white !important;
    padding:10px 32px !important;
    font-weight:800 !important;
}}
.stButton>button:hover {{
    background:#0094B5 !important;
}}

[data-testid="dataframe"] th {{
    background:{DARK_GREEN} !important;
    color:white !important;
    font-weight:900 !important;
}}

[data-testid="stElementToolbar"] button {{
    background:white !important;
    border:1px solid #DDD !important;
    padding:6px !important;
}}

[data-testid="stElementToolbar"] button svg {{
    width:30px !important;
    height:30px !important;
    color:#111 !important;
}}

/* Suggestions dropdown */
li[data-baseweb="option"]:hover,
li[data-baseweb="option"][aria-selected="true"] {{
    background:{LIGHT_GREEN} !important;
    border-left:5px solid {BORDER_GREEN} !important;
    color:{DARK_GREEN} !important;
    font-weight:900 !important;
}}
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# LOAD DATA
# ==========================================================
df = load_all()
if df.empty:
    st.error("Material files missing.")
    st.stop()

# ==========================================================
# HEADER
# ==========================================================
st.markdown("<h1>🔍 Material Viewfinder</h1>", unsafe_allow_html=True)

# ==========================================================
# FILTERS
# ==========================================================
c1, c2, c3 = st.columns([1, 1, 1])

plant = c1.selectbox("Plant", ["SHJM", "MIJM", "SGJM", "SSKT"])
department = c2.selectbox("Department", sorted(df["Department"].unique()))
machine = c3.selectbox(
    "Machine Type",
    sorted(df[df["Department"] == department]["Machine Type"].unique()),
)

subset = df[(df["Department"] == department) & (df["Machine Type"] == machine)]

# ==========================================================
# SEARCH + CLEAR + RECENT
# ==========================================================
if "query" not in st.session_state:
    st.session_state["query"] = ""

if "trigger_clear" not in st.session_state:
    st.session_state["trigger_clear"] = False

if "recent_searches" not in st.session_state:
    st.session_state["recent_searches"] = []  # top 5 material codes


def add_recent(code: str):
    """Store last 5 material codes (no duplicates)."""
    code = code.strip()
    if not code:
        return

    recent = st.session_state["recent_searches"]
    if code in recent:
        recent.remove(code)
    recent.insert(0, code)
    st.session_state["recent_searches"] = recent[:5]


if st.session_state["trigger_clear"]:
    st.session_state["query"] = ""
    st.session_state["trigger_clear"] = False

c_search, c_btn, c_clear = st.columns([4, 1, 1])

with c_search:
    q = st.text_input(
        "Search by description or material code",
        key="query",
        placeholder="e.g., disc stud bolt, bearing; gear|pulley",
    )

with c_btn:
    st.write("")
    st.write("")
    submit = st.button("Submit")

with c_clear:
    st.write("")
    st.write("")
    clear = st.button("Clear")

if clear:
    st.session_state["trigger_clear"] = True
    st.rerun()

# Recent searches under search bar
if st.session_state["recent_searches"]:
    st.markdown("### 🕘 Recent Searches")
    cols_recent = st.columns(len(st.session_state["recent_searches"]))
    for i, code in enumerate(st.session_state["recent_searches"]):
        with cols_recent[i]:
            if st.button(code, key=f"recent_{code}"):
                st.session_state["query"] = code
                st.rerun()

# ==========================================================
# SEARCH ENGINE + GLOBAL FALLBACK
# ==========================================================
filtered_subset = pd.DataFrame()
global_matches = pd.DataFrame()
suggestions = []
chosen = None
status = "idle"  # idle / here / elsewhere / nowhere

if q.strip():
    # 1️⃣ Search in selected Department + Machine (hybrid multi-keyword)
    filtered_subset = hybrid_multi_search(subset, q)

    if not filtered_subset.empty:
        status = "here"
        suggestions = [
            f"【{str(row.get(KEY_MAT, ''))}】 {str(row.get(KEY_DESC, ''))}"
            for _, row in filtered_subset.iterrows()
        ]
        chosen = st.selectbox("Suggestions", suggestions)
    else:
        # 2️⃣ If nothing here → search entire DF (global)
        global_matches = hybrid_multi_search(df, q)

        if global_matches.empty:
            status = "nowhere"
            st.error("❌ Material not found anywhere in database")
        else:
            status = "elsewhere"
            st.warning(
                "⚠️ Material not found in selected machine — "
                "but exists in other Departments / Machines."
            )

            gm_clean = clean_display(global_matches)

            def highlight_global(x):
                return [
                    f"background-color:{LIGHT_GREEN};"
                    f"color:{DARK_GREEN};font-weight:bold"
                ] * len(x)

            st.subheader("🌍 Found in Other Departments / Machines")
            st.dataframe(
                gm_clean.style.apply(highlight_global, axis=1),
                use_container_width=True,
            )

# ==========================================================
# SAP RECORD TABLE (CURRENT MACHINE)
# ==========================================================
if submit and not q.strip():
    # Show all materials for that machine
    st.subheader("📄 SAP Record — All Materials in Selected Machine")
    st.dataframe(clean_display(subset), use_container_width=True)

elif status == "here" and not filtered_subset.empty:
    st.subheader(
        f"📄 SAP Record — {len(filtered_subset)} Result(s) in Selected Machine"
    )
    df_clean = clean_display(filtered_subset)

    def highlight_row(x):
        return [
            f"background-color:{LIGHT_GREEN};"
            f"color:{DARK_GREEN};font-weight:bold"
        ] * len(x)

    st.dataframe(
        df_clean.style.apply(highlight_row, axis=1),
        use_container_width=True,
    )

# ==========================================================
# SELECTED MATERIAL + RECENT SAVE
# ==========================================================
if chosen and status == "here" and not filtered_subset.empty:
    code = chosen.split("】")[0].replace("【", "").strip()
    if code:
        add_recent(code)
        st.write("")
        st.markdown(
            f"<h3 style='color:{BLUE};'>Selected: {code}</h3>",
            unsafe_allow_html=True,
        )
