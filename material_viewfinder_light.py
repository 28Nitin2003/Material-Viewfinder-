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
    A = df.copy()
    vals = A.astype(str).values
    mat_rows = np.where(vals == KEY_MAT)[0]
    desc_rows = np.where(vals == KEY_DESC)[0]
    headers = sorted(set(mat_rows).intersection(set(desc_rows)))

    tables = []
    for i, r in enumerate(headers):
        header_vals = A.iloc[r].astype(str).tolist()
        cols = [c for c,v in enumerate(header_vals) if v.strip() not in ("","nan","None","NaN")]
        if not cols:
            continue

        end = headers[i+1] if i+1<len(headers) else len(A)
        block = A.iloc[r+1:end, cols].copy()
        block.columns = [header_vals[c] for c in cols]
        block = block.dropna(how='all')

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

        sheets = pd.read_excel(path, sheet_name=None, header=None)
        for sheet, df in sheets.items():
            for tbl in extract_tables(df):
                T = tbl.copy()
                T["Department"] = dept
                machine = sheet.strip()
                if machine.lower()=="sheet1":
                    machine="Winding"
                T["Machine Type"] = machine
                rows.extend(T.to_dict(orient="records"))

    if not rows:
        return pd.DataFrame()

    df_all = pd.DataFrame(rows)

    # cleanup strings
    for c in df_all.columns:
        df_all[c] = df_all[c].astype(str).str.replace(r"\s+"," ",regex=True).str.strip()

    # remove useless values
    df_all = df_all.replace(
        {"nan": np.nan, "NaN": np.nan, "None": np.nan, "": np.nan}
    )

    df_all = df_all[(df_all[KEY_MAT].notna()) | (df_all[KEY_DESC].notna())]

    return df_all.reset_index(drop=True)


# ---------------- HELPERS ----------------

def clean_display(df: pd.DataFrame) -> pd.DataFrame:
    return df.replace(
        {"nan":"", "NaN":"", "None":"", np.nan:""}
    ).fillna("")


def strict_partial_filter(df_sub, q):
    q = q.lower().strip()
    df = df_sub.copy()

    search_cols = [KEY_MAT, KEY_DESC]
    for extra in ["Material description", "Material Long Description"]:
        if extra in df.columns:
            search_cols.append(extra)

    mask = False
    for col in search_cols:
        coltext = df[col].fillna("").astype(str).str.lower()
        mask = mask | coltext.str.contains(q)

    filtered = df[mask].copy()

    if KEY_DESC in filtered.columns:
        desc = filtered[KEY_DESC].fillna("").astype(str).str.lower()
        starts = desc.str.startswith(q)
        contains = desc.str.contains(q)
        filtered = filtered.assign(
            _starts=starts.astype(int),
            _contains=contains.astype(int)
        ).sort_values(
            by=["_starts","_contains"],
            ascending=[False,False]
        ).drop(columns=["_starts","_contains"])

    return filtered.reset_index(drop=True)


# ---------------- UI & CSS ----------------
st.set_page_config(page_title="Material Viewfinder", layout="wide")

st.markdown(f"""
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

/* Suggestions */
li[data-baseweb="option"]:hover,
li[data-baseweb="option"][aria-selected="true"] {{
    background:{LIGHT_GREEN} !important;
    border-left:5px solid {BORDER_GREEN} !important;
    color:{DARK_GREEN} !important;
    font-weight:900 !important;
}}
</style>
""", unsafe_allow_html=True)


# ---------------- LOAD DATA ----------------
df = load_all()

if df.empty:
    st.error("Material files missing.")
    st.stop()


# ---------------- HEADER ----------------
st.markdown("<h1>🔍 Material Viewfinder</h1>", unsafe_allow_html=True)


# ---------------- FILTERS ----------------
c1,c2,c3 = st.columns([1,1,1])

plant = c1.selectbox("Plant", ["SHJM","MIJM","SGJM","SSKT"])
department = c2.selectbox("Department", sorted(df["Department"].unique()))
machine = c3.selectbox(
    "Machine Type",
    sorted(df[df["Department"]==department]["Machine Type"].unique())
)

subset = df[(df["Department"]==department)&(df["Machine Type"]==machine)]


# ---------------- SEARCH + CLEAR BUTTON ----------------

if "query" not in st.session_state:
    st.session_state["query"] = ""

if "trigger_clear" not in st.session_state:
    st.session_state["trigger_clear"] = False

if st.session_state["trigger_clear"]:
    st.session_state["query"] = ""
    st.session_state["trigger_clear"] = False

c_search, c_btn, c_clear = st.columns([4,1,1])

with c_search:
    q = st.text_input(
        "Search by description or material code",
        key="query",
        placeholder="e.g., disc, stud, bearing, 13000..."
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


# ---------------- SEARCH ENGINE ----------------

filtered = pd.DataFrame()
suggestions = []
chosen = None

if q.strip():
    filtered = strict_partial_filter(subset, q)

    if filtered.empty:
        st.error("❌ Material not found")
    else:
        suggestions = [
            f"【{str(row.get(KEY_MAT,''))}】 {str(row.get(KEY_DESC,''))}"
            for _, row in filtered.iterrows()
        ]
        chosen = st.selectbox("Suggestions", suggestions)


# ---------------- DISPLAY SAP RECORD ----------------

# Case A: Submit without search → show ALL items of machine
if submit and not q.strip():
    st.subheader("📄 SAP Record — All Materials")
    st.dataframe(clean_display(subset), use_container_width=True)

# Case B: Show all matched rows
elif not filtered.empty:
    st.subheader(f"📄 SAP Record — {len(filtered)} Result(s) Found")
    df_clean = clean_display(filtered)

    def highlight_row(x):
        return [
            f"background-color:{LIGHT_GREEN};color:{DARK_GREEN};font-weight:bold"
        ] * len(x)

    st.dataframe(df_clean.style.apply(highlight_row, axis=1), use_container_width=True)

# Case C: Show selected code label
if chosen and not filtered.empty:
    code = chosen.split("】")[0].replace("【","").strip()
    if code:
        st.write("")
        st.markdown(
            f"<h3 style='color:{BLUE};'>Selected: {code}</h3>",
            unsafe_allow_html=True
        )
