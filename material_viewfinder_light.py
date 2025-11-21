# ==========================================================
# MATERIAL VIEWFINDER — FINAL (AUTO-RESET SELECTION + EDITABLE CART)
# ==========================================================

import os
import re
import urllib.parse
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
    """Detect blocks whose header row contains both KEY_MAT and KEY_DESC."""
    A = df.copy()
    vals = A.astype(str).values
    mat_rows = np.where(vals == KEY_MAT)[0]
    desc_rows = np.where(vals == KEY_DESC)[0]
    headers = sorted(set(mat_rows).intersection(set(desc_rows)))

    blocks = []
    for i, r in enumerate(headers):
        header_vals = A.iloc[r].astype(str).tolist()
        cols = [c for c, v in enumerate(header_vals) if v.strip() not in ("", "nan", "None", "NaN")]
        if not cols:
            continue

        end = headers[i + 1] if i + 1 < len(headers) else len(A)
        block = A.iloc[r + 1 : end, cols].copy()
        block.columns = [header_vals[c] for c in cols]
        block = block.dropna(how="all")

        for c in block.columns:
            block[c] = block[c].astype(str).str.strip()

        if not block.empty:
            blocks.append(block)

    return blocks


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
                machine = "Winding" if sheet.lower() == "sheet1" else sheet
                T["Machine Type"] = machine
                rows.extend(T.to_dict(orient="records"))

    if not rows:
        return pd.DataFrame()

    df_all = pd.DataFrame(rows)

    for c in df_all.columns:
        df_all[c] = (
            df_all[c]
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

    df_all = df_all.replace({"nan": None, "NaN": None, "None": None, "": None})
    df_all = df_all[(df_all[KEY_MAT].notna()) | (df_all[KEY_DESC].notna())]

    return df_all.reset_index(drop=True)


def clean_display(df: pd.DataFrame) -> pd.DataFrame:
    """Replace nan/None with empty strings for nicer display."""
    return df.replace({"nan": "", "NaN": "", "None": "", None: ""}).fillna("")


# ==========================================================
# SEARCH HELPERS
# ==========================================================
def parse_keywords(q: str):
    q = q.lower().strip()
    if not q:
        return []
    parts = re.split(r"[,\s;|]+", q)
    seen = set()
    out = []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def hybrid_multi_search(df_sub: pd.DataFrame, q: str) -> pd.DataFrame:
    """Multi-keyword partial search on Material + Proposed Description."""
    keywords = parse_keywords(q)
    if not keywords:
        return df_sub.iloc[0:0].copy()

    df = df_sub.copy()
    combined = (
        df[[KEY_MAT, KEY_DESC]]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
    )

    masks_and = [combined.str.contains(k) for k in keywords]
    mask_and = np.logical_and.reduce(masks_and)
    masks_or = [combined.str.contains(k) for k in keywords]
    mask_or = np.logical_or.reduce(masks_or)

    if mask_and.any():
        cand = df[mask_and].copy()
    else:
        cand = df[mask_or].copy()

    if cand.empty:
        return cand

    first = keywords[0]
    desc = cand[KEY_DESC].fillna("").astype(str).str.lower()
    starts = desc.str.startswith(first)
    contains = desc.str.contains(first)

    cand = (
        cand.assign(_starts=starts.astype(int), _contains=contains.astype(int))
        .sort_values(by=["_starts", "_contains"], ascending=[False, False])
        .drop(columns=["_starts", "_contains"])
    )
    return cand.reset_index(drop=True)


# ==========================================================
# UI CSS
# ==========================================================
st.set_page_config(page_title="Material Viewfinder", layout="wide")
st.markdown(
    f"""
<style>
* {{ border-radius: 6px !important; }}

body, .stApp {{
    background:white !important;
    font-family:'Inter', sans-serif !important;
}}

/* MAIN BUTTON STYLE */
.stButton>button {{
    background:{BLUE} !important;
    color:white !important;
    font-weight:700 !important;
    padding:6px 18px !important;
    font-size:14px !important;
    border:none !important;
}}

/* RECENT SEARCH BUTTONS */
div[data-testid="column"] .stButton>button {{
    background:{BLUE} !important;
    padding:4px 14px !important;
    font-size:13px !important;
    font-weight:600 !important;
}}

/* TEXT INPUT */
.stTextInput input {{
    border:2px solid {BLUE} !important;
    color:{BLUE} !important;
    padding:6px !important;
    font-size:15px !important;
}}

/* LABELS */
.stSelectbox label p,
.stTextInput label p {{
    font-weight:800 !important;
    color:{DARK_BLUE} !important;
}}

/* TABLE HEADERS - BOLD */
[data-testid="stDataEditor"] thead th,
[data-testid="stDataEditor"] div[data-testid="column_header_content"] {{
    background-color: {DARK_GREEN} !important;
    color: white !important;
    font-size: 16px !important;
    font-weight: 900 !important; 
    font-family: 'Inter', sans-serif !important;
}}

h1,h2,h3 {{
    color:{DARK_BLUE} !important;
    font-weight:900 !important;
}}
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# SESSION STATE INIT
# ==========================================================
if "query" not in st.session_state:
    st.session_state["query"] = ""
if "clear_trigger" not in st.session_state:
    st.session_state["clear_trigger"] = False
if "trigger_search" not in st.session_state:
    st.session_state["trigger_search"] = False
if "recent_searches" not in st.session_state:
    st.session_state["recent_searches"] = []
if "cart" not in st.session_state:
    st.session_state["cart"] = {}

# Base table logic
if "table_df_base" not in st.session_state:
    st.session_state["table_df_base"] = None
if "table_label" not in st.session_state:
    st.session_state["table_label"] = ""

# Current filter logic
if "current_dept" not in st.session_state:
    st.session_state["current_dept"] = None
if "current_machine" not in st.session_state:
    st.session_state["current_machine"] = None

# TABLE RESET KEY (New for auto-clearing selections)
if "editor_key" not in st.session_state:
    st.session_state["editor_key"] = 0

# Apply clear logic
if st.session_state["clear_trigger"]:
    st.session_state["query"] = ""
    st.session_state["table_df_base"] = None
    st.session_state["table_label"] = ""
    st.session_state["clear_trigger"] = False
    st.session_state["editor_key"] += 1  # Ensure clean slate

# ==========================================================
# LOAD DATA
# ==========================================================
df = load_all()
if df.empty:
    st.error("❌ Excel material files missing.")
    st.stop()

# ==========================================================
# HEADER & FILTERS
# ==========================================================
st.markdown("<h1>🔍 Material Viewfinder</h1>", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
plant = c1.selectbox("Plant", ["SHJM", "MIJM", "SGJM", "SSKT"])
department = c2.selectbox("Department", sorted(df["Department"].unique()))
machine = c3.selectbox(
    "Machine Type",
    sorted(df[df["Department"] == department]["Machine Type"].unique()),
)

subset = df[(df["Department"] == department) & (df["Machine Type"] == machine)]

# Clear table if filters change
if (
    st.session_state["current_dept"] != department
    or st.session_state["current_machine"] != machine
):
    st.session_state["table_df_base"] = None
    st.session_state["table_label"] = ""
    st.session_state["current_dept"] = department
    st.session_state["current_machine"] = machine
    st.session_state["editor_key"] += 1  # Force reset table

# ==========================================================
# SEARCH BAR
# ==========================================================
c_s, c_btn, c_clr = st.columns([5, 1, 1])

with c_s:
    q = st.text_input(
        "Search by description or material code",
        key="query",
        placeholder="e.g., disc, stud, bearing, 13000..."
    )

with c_btn:
    st.write("")
    submit = st.button("Submit")

with c_clr:
    st.write("")
    clear = st.button("Clear", key="clear_btn")

if clear:
    st.session_state["clear_trigger"] = True
    st.session_state["table_df_base"] = None
    st.session_state["table_label"] = ""
    st.session_state["editor_key"] += 1
    st.rerun()

# ==========================================================
# RECENT SEARCHES (CALLBACK METHOD)
# ==========================================================
def on_recent_click(search_text):
    st.session_state["query"] = search_text
    st.session_state["trigger_search"] = True

if st.session_state["recent_searches"]:
    st.markdown("### 🕘 Recent Searches")
    cols = st.columns(len(st.session_state["recent_searches"]))
    for i, item in enumerate(st.session_state["recent_searches"]):
        with cols[i]:
            st.button(item, key=f"recent_{i}", on_click=on_recent_click, args=(item,))

# ==========================================================
# SEARCH LOGIC
# ==========================================================
should_search = submit or st.session_state.get("trigger_search", False)

if should_search:
    st.session_state["trigger_search"] = False
    st.session_state["editor_key"] += 1  # Reset selection on new search

    q_stripped = st.session_state["query"].strip()

    if not q_stripped:
        base = clean_display(subset).reset_index(drop=True)
        st.session_state["table_df_base"] = base
        st.session_state["table_label"] = f"📄 SAP Record — All materials in {machine}"
    else:
        filtered_local = hybrid_multi_search(subset, q_stripped)

        # update recent
        recent = st.session_state["recent_searches"]
        if q_stripped in recent:
            recent.remove(q_stripped)
        recent.insert(0, q_stripped)
        st.session_state["recent_searches"] = recent[:5]

        if not filtered_local.empty:
            base = clean_display(filtered_local).reset_index(drop=True)
            st.session_state["table_df_base"] = base
            st.session_state["table_label"] = (
                f"📄 SAP Record — {len(base)} result(s) in {machine}"
            )
        else:
            filtered_global = hybrid_multi_search(df, q_stripped)
            st.session_state["table_df_base"] = None
            st.session_state["table_label"] = ""

            if filtered_global.empty:
                st.error("❌ Material not found anywhere.")
            else:
                st.warning("⚠ Material not found in this machine, but found elsewhere:")
                st.dataframe(clean_display(filtered_global), use_container_width=True)

# ==========================================================
# SHOW SAP TABLE (WITH AUTO RESET)
# ==========================================================
base = st.session_state["table_df_base"]
label = st.session_state["table_label"]

if base is not None and not base.empty:
    st.subheader(label)

    display_df = base.copy().reset_index(drop=True)

    # Pre-fill Select and Quantity
    if "Select" not in display_df.columns:
        display_df.insert(0, "Select", False)
    if "Quantity" not in display_df.columns:
        display_df.insert(1, "Quantity", 1)

    # Use dynamic key for auto-resetting checkboxes
    unique_key = f"sap_table_editor_{st.session_state['editor_key']}"

    edited = st.data_editor(
        display_df,
        key=unique_key,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "Select": st.column_config.CheckboxColumn("Select"),
            "Quantity": st.column_config.NumberColumn("Quantity", min_value=1, step=1),
        },
    )

    if st.button("Add Selected to Cart"):
        selected_rows = edited[edited["Select"] == True]

        if selected_rows.empty:
            st.warning("No items selected.")
        else:
            cart = st.session_state["cart"]
            count = 0
            for _, row in selected_rows.iterrows():
                code = str(row.get(KEY_MAT, "")).strip()
                if not code:
                    continue

                try:
                    qty = int(row.get("Quantity", 1))
                    if qty < 1: qty = 1
                except:
                    qty = 1

                # Add to cart dictionary
                cart[code] = {
                    "Material": code,
                    "Description": row.get(KEY_DESC, ""),
                    "Department": row.get("Department", ""),
                    "Machine Type": row.get("Machine Type", ""),
                    "Quantity": qty,
                }
                count += 1

            if count > 0:
                st.session_state["cart"] = cart
                st.success(f"✔ Added {count} item(s) to cart.")
                # Increment key to force table reset (uncheck boxes)
                st.session_state["editor_key"] += 1
                st.rerun()

# ==========================================================
# CART (NOW EDITABLE)
# ==========================================================
st.write("---")
st.subheader("🛒 Cart (Edit Quantity Here)")

if not st.session_state["cart"]:
    st.info("Cart is empty.")
else:
    # Convert cart dict to DataFrame
    cart_df = pd.DataFrame(st.session_state["cart"].values())
    
    # Ensure Quantity is first for better UX
    cols = ["Quantity", "Material", "Description", "Department", "Machine Type"]
    # Filter to exist columns only
    final_cols = [c for c in cols if c in cart_df.columns]
    cart_df = cart_df[final_cols]

    # EDITABLE CART TABLE
    edited_cart = st.data_editor(
        cart_df,
        key="cart_editor",
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic", # Allows deleting rows if needed
        disabled=["Material", "Description", "Department", "Machine Type"], # Lock details, open Quantity
        column_config={
            "Quantity": st.column_config.NumberColumn("Quantity", min_value=1, step=1, required=True)
        }
    )
    
    # SYNC CART CHANGES BACK TO STATE
    # If user edits quantity in this table, update the session state dictionary
    if not edited_cart.equals(cart_df):
        new_cart = {}
        for _, row in edited_cart.iterrows():
             code = str(row["Material"])
             new_cart[code] = row.to_dict()
        st.session_state["cart"] = new_cart


    if st.button("Clear Cart"):
        st.session_state["cart"] = {}
        st.rerun()

    # ======================================================
    # EMAIL
    # ======================================================
    st.write("---")
    st.subheader("✉ Send Materials via Gmail")

    to_email = st.text_input("Receiver Email")

    subject = "Material Requirement – Material Viewfinder"

    body_lines = [
        "Dear Sir/Madam,",
        "",
        "Please arrange the following materials:",
        "",
    ]

    # Read from the *latest* cart state (including edits)
    for item in st.session_state["cart"].values():
        body_lines.append(
            f"- {item['Material']} — {item['Description']} "
            f"(Dept: {item['Department']}, Machine: {item['Machine Type']}, Qty: {item['Quantity']})"
        )

    body_lines += ["", "Regards,", "Material Viewfinder Bot"]
    body = "\n".join(body_lines)

    st.text_area("Email Preview", body, height=200)

    if st.button("Send Email"):
        if not to_email.strip():
            st.warning("Please enter receiver email.")
        else:
            subject_encoded = urllib.parse.quote(subject)
            body_encoded = urllib.parse.quote(body)
            to_encoded = urllib.parse.quote(to_email)

            gmail_url = (
                "https://mail.google.com/mail/?view=cm&fs=1"
                f"&to={to_encoded}&su={subject_encoded}&body={body_encoded}"
            )

            st.markdown(
                f"""
                <script>
                    window.open("{gmail_url}", "_blank");
                </script>
                """,
                unsafe_allow_html=True,
            )
