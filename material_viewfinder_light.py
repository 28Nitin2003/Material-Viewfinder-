# ==========================================================
# MATERIAL VIEWFINDER — FINAL STRICT PARTIAL SEARCH + SAP LIST
# ==========================================================

import os
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

# ---------------- DATA EXTRACTION ----------------
def extract_tables(df):
    """Find all table blocks that start with headers containing Material + Material Proposed Description."""
    A = df.copy()
    vals = A.astype(str).values
    mat = set(np.where(vals == KEY_MAT)[0])
    desc = set(np.where(vals == KEY_DESC)[0])
    headers = sorted(mat.intersection(desc))

    out = []
    for i, r in enumerate(headers):
        header_vals = A.iloc[r].astype(str).tolist()
        cols = [c for c, v in enumerate(header_vals)
                if v.strip() not in ("", "nan", "NaN", "None")]
        if not cols:
            continue

        end = headers[i + 1] if i + 1 < len(headers) else len(A)
        block = A.iloc[r + 1:end, cols].copy()
        block.columns = [header_vals[c].strip() for c in cols]
        block = block.dropna(how="all")

        for c in block.columns:
            if block[c].dtype == object:
                block[c] = block[c].astype(str).str.strip()

        if not block.empty:
            out.append(block)
    return out


@st.cache_data(show_spinner=True)
def load_all():
    rows = []
    base = os.path.dirname(os.path.abspath(__file__))

    for dept, fname in FILES.items():
        path = os.path.join(base, fname)
        if not os.path.exists(path):
            continue

        sheets = pd.read_excel(path, sheet_name=None, header=None)

        for sheet, df in sheets.items():
            for tbl in extract_tables(df):
                T = tbl.copy()
                T["Department"] = dept

                m = sheet.strip()
                if m.lower() == "sheet1":
                    m = "Winding"
                T["Machine Type"] = m

                rows.extend(T.to_dict(orient="records"))

    if not rows:
        return pd.DataFrame()

    df_all = pd.DataFrame(rows)

    # Strip and normalise all string columns
    for c in df_all.columns:
        if df_all[c].dtype == object:
            df_all[c] = (
                df_all[c]
                .astype(str)
                .str.replace(r"\s+", " ", regex=True)
                .str.strip()
            )

    # Treat placeholder strings as NULL
    df_all = df_all.replace(
        {"nan": np.nan, "NaN": np.nan, "None": np.nan, "": np.nan}
    )

    # Keep only rows with some description or material code
    df_all = df_all[
        df_all[KEY_MAT].notna() | df_all[KEY_DESC].notna()
    ].reset_index(drop=True)

    return df_all


# ---------------- SMALL HELPERS ----------------
def clean_display(df: pd.DataFrame) -> pd.DataFrame:
    """Remove NaN / placeholder strings for display."""
    if df is None or df.empty:
        return df
    return (
        df.replace({"nan": "", "NaN": "", "None": "", np.nan: ""})
        .fillna("")
    )


def strict_partial_filter(df_sub: pd.DataFrame, q: str) -> pd.DataFrame:
    """
    Partial match, but STRICT:
    Only rows where query actually appears in:
    - Material code
    - Material Proposed Description
    - Material description (if present)
    - Material Long Description (if present)
    """
    if not q.strip():
        return pd.DataFrame()

    q = q.lower().strip()
    df = df_sub.copy()

    # Columns to search in
    search_cols = [KEY_MAT, KEY_DESC]
    for extra in ["Material description", "Material Long Description"]:
        if extra in df.columns:
            search_cols.append(extra)

    mask = False
    for col in search_cols:
        s = df[col].fillna("").astype(str).str.lower()
        mask = mask | s.str.contains(q)

    filtered = df[mask].copy()

    # Sort with a simple priority: description contains at beginning first, then general
    if KEY_DESC in filtered.columns:
        desc_series = filtered[KEY_DESC].fillna("").astype(str).str.lower()
        starts = desc_series.str.startswith(q)
        contains = desc_series.str.contains(q)
        # priority key: (-starts, -contains)
        filtered = filtered.assign(
            _starts=starts.astype(int),
            _contains=contains.astype(int),
        ).sort_values(
            by=["_starts", "_contains"], ascending=[False, False]
        ).drop(columns=["_starts", "_contains"])

    return filtered.reset_index(drop=True)


# ---------------- UI & CSS ----------------
st.set_page_config(page_title="Material Viewfinder", layout="wide")

st.markdown(
    f"""
<style>
* {{ border-radius: 0px !important; }}

body, .stApp {{
    background: white !important;
    font-family: 'Inter', sans-serif !important;
}}

h1, h2, h3, h4 {{
    color: {DARK_BLUE} !important;
    font-weight: 900 !important;
}}

.stSelectbox label p, .stTextInput label p {{
    font-weight: 900 !important;
    color: {DARK_BLUE} !important;
}}

/* Search input text always visible */
.stTextInput input {{
    border: 2px solid {BLUE} !important;
    background:white !important;
    color:{BLUE} !important;
    caret-color:{BLUE} !important;
    font-weight:600 !important;
}}

/* Dropdowns */
.stSelectbox div[data-baseweb="select"] {{
    border: 2px solid #cccccc !important;
    background:white !important;
}}

/* Buttons */
.stButton>button {{
    background:{BLUE} !important;
    color:white !important;
    padding:10px 32px !important;
    font-weight:800 !important;
}}
.stButton>button:hover {{
    background:#0094B5 !important;
}}

/* SAP Record header */
[data-testid="dataframe"] th {{
    background:{DARK_GREEN} !important;
    color:white !important;
    font-weight:900 !important;
}}

/* Toolbar icons */
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

/* Suggest options */
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

# ---------------- LOAD DATA ----------------
df = load_all()

if df.empty:
    st.error("Material files not found.")
    st.stop()

# ---------------- HEADER ----------------
st.markdown("<h1>🔍 Material Viewfinder</h1>", unsafe_allow_html=True)

# ---------------- FILTERS ----------------
c1, c2, c3 = st.columns([1, 1, 1])

plant = c1.selectbox("Plant", ["SHJM", "MIJM", "SGJM", "SSKT"])
department = c2.selectbox("Department", sorted(df["Department"].unique()))
machine = c3.selectbox(
    "Machine Type",
    sorted(df[df["Department"] == department]["Machine Type"].unique()),
)

subset = df[
    (df["Department"] == department) & (df["Machine Type"] == machine)
]

# ---------------- SEARCH BAR + BUTTONS ----------------
st.write("---")
c_search, c_btn, c_clear = st.columns([4, 1, 1])

if "query" not in st.session_state:
    st.session_state["query"] = ""

with c_search:
    q = st.text_input(
        "Search by description or material code",
        placeholder="e.g., disc, stud, 13000...",
        key="query",
    )

with c_btn:
    st.write("")
    submit = st.button("Submit")

with c_clear:
    st.write("")
    clear = st.button("Clear")

if clear:
    st.session_state["query"] = ""
    st.experimental_rerun()

# ---------------- SEARCH ENGINE EXECUTION ----------------
filtered = pd.DataFrame()
suggestions = []
chosen = None

if q.strip():
    filtered = strict_partial_filter(subset, q)

    if filtered.empty:
        st.error("❌ Material not found")
    else:
        # Build suggestions from filtered data ONLY
        suggestions = [
            f"【{str(row.get(KEY_MAT, '')).strip()}】 "
            f"{str(row.get(KEY_DESC, '')).strip()}"
            for _, row in filtered.iterrows()
        ]
        chosen = st.selectbox("Suggestions", suggestions)

# ---------------- DISPLAY SAP RECORD ----------------

# CASE A – Submit with empty search: show all for that machine
if submit and not q.strip():
    st.subheader("📄 SAP Record — All Materials")
    st.dataframe(clean_display(subset), use_container_width=True)

# CASE B – query present and matches found: show ALL matched materials
elif not filtered.empty:
    st.subheader(f"📄 SAP Record — {len(filtered)} Result(s) Found")

    df_clean = clean_display(filtered)

    def highlight_all(s):
        return [
            f"background-color:{LIGHT_GREEN};color:{DARK_GREEN};font-weight:bold"
        ] * len(s)

    st.dataframe(
        df_clean.style.apply(highlight_all, axis=1),
        use_container_width=True,
    )

# CASE C – suggestion chosen: show selected code label (table already shows full list)
if chosen and not filtered.empty:
    code = chosen.split("】")[0].replace("【", "").strip()
    if code:
        st.write("")
        st.markdown(
            f"<h3 style='color:{BLUE};'>Selected: {code}</h3>",
            unsafe_allow_html=True,
        )
