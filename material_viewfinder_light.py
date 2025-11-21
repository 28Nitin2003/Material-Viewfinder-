# ==========================================================
# MATERIAL VIEWFINDER — FINAL ADVANCED SEARCH ENGINE + SAP RECORD LIST
# ==========================================================

import os
import pandas as pd
import numpy as np
import streamlit as st

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SK_OK = True
except:
    SK_OK = False

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
    mat = set(np.where(vals == KEY_MAT)[0])
    desc = set(np.where(vals == KEY_DESC)[0])
    headers = sorted(mat.intersection(desc))

    out = []
    for i, r in enumerate(headers):
        header_vals = A.iloc[r].astype(str).tolist()
        cols = [c for c, v in enumerate(header_vals)
                if v.strip() not in ("","nan","None","NaN")]
        if not cols:
            continue

        end = headers[i+1] if i+1 < len(headers) else len(A)
        block = A.iloc[r+1:end, cols].copy()
        block.columns = [header_vals[c].strip() for c in cols]
        block = block.dropna(how='all')
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

    df_all = pd.DataFrame(rows)

    for c in df_all.columns:
        if df_all[c].dtype == object:
            df_all[c] = df_all[c].astype(str).str.replace(r"\s+"," ",regex=True).str.strip()

    return df_all[df_all[KEY_DESC].str.len() > 0].reset_index(drop=True)


# ---------------- UI & CSS ----------------
st.set_page_config(page_title="Material Viewfinder", layout="wide")

st.markdown(f"""
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

.stTextInput input {{
    border: 2px solid {BLUE} !important;
    background:white !important;
    color:{BLUE} !important;
    caret-color:{BLUE} !important;
    font-weight:600 !important;
}}

.stButton>button {{
    background:{BLUE} !important;
    color:white !important;
    padding:12px 42px !important;
    font-weight:800 !important;
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
c1, c2, c3 = st.columns([1,1,1])

plant = c1.selectbox("Plant", ["SHJM","MIJM","SGJM","SSKT"])
department = c2.selectbox("Department", sorted(df["Department"].unique()))
machine = c3.selectbox("Machine Type", sorted(df[df["Department"] == department]["Machine Type"].unique()))

subset = df[(df["Department"] == department) & (df["Machine Type"] == machine)]

# ---------------- SEARCH ----------------
st.write("---")
c_search, c_btn = st.columns([4,1])

with c_search:
    q = st.text_input("Search by description or material code", placeholder="e.g., disc, stud, 13000...")

with c_btn:
    st.write("")
    submit = st.button("Submit")


# ---------------- SEARCH ENGINE LOGIC ----------------
def advanced_filter(d, q):
    if not q.strip():
        return pd.DataFrame()

    q = q.lower().strip()
    d = d.copy()

    # Strict filter first
    strict = d[
        d[KEY_MAT].str.contains(q, case=False) |
        d[KEY_DESC].str.contains(q, case=False)
    ]
    if strict.empty:
        return pd.DataFrame()

    # TF-IDF ranking
    if SK_OK:
        vec = TfidfVectorizer(stop_words="english")
        X = vec.fit_transform(strict[KEY_DESC])
        score = cosine_similarity(vec.transform([q]), X).ravel()
        strict["score"] = score
    else:
        strict["score"] = 0

    strict = strict.sort_values("score", ascending=False)
    return strict


filtered = pd.DataFrame()
suggestions = []
chosen = None

if q.strip():
    filtered = advanced_filter(subset, q)

    if filtered.empty:
        st.error("❌ Material not found")
    else:
        suggestions = [f"【{r[KEY_MAT]}】 {r[KEY_DESC]}" for _, r in filtered.iterrows()]
        chosen = st.selectbox("Suggestions", suggestions)


# ---------------- DISPLAY LOGIC ----------------

# CASE A — Submit with empty search = show all
if submit and not q.strip():
    st.subheader("📄 SAP Record — All Materials")
    st.dataframe(subset, use_container_width=True)

# CASE B — Search typed → show ALL matched materials
elif not filtered.empty:
    st.subheader(f"📄 SAP Record — {len(filtered)} Result(s) Found")

    def highlight(s):
        return [f'background-color:{LIGHT_GREEN};color:{DARK_GREEN};font-weight:bold'] * len(s)

    st.dataframe(filtered.style.apply(highlight, axis=1), use_container_width=True)

# CASE C — clicking one suggestion DOES NOT remove others — full list stays
if chosen and filtered.shape[0] > 0:
    st.write("")   # spacing
    code = chosen.split("】")[0].replace("【","")
    st.markdown(f"<h3 style='color:{BLUE};'>Selected: {code}</h3>", unsafe_allow_html=True)
