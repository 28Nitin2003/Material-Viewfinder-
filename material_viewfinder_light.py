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

# --- ENHANCED COLORS ---
BLUE = "#1F7A8C"        # Richer Teal/Corporate Blue
DARK_BLUE = "#003566"   # Deep Blue for Title and quantity text for visibility
DARK_GREEN = "#006D5B"  # Professional Dark Green for Headers
RED_DELETE = "#EF4444"
TEXT_DARK = "#1E293B"   # Very dark gray/almost black for all general text
TITLE_BACKGROUND = "#F1F5F9" # Light gray background for the title block

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

        end = headers[i + 1] if i i + 1 < len(headers) else len(A)
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
    # NOTE: In a real environment, the underlying Excel files must be present 
    # in the same directory for this application to function.
    base = os.path.dirname(os.path.abspath(__file__))

    for dept, fname in FILES.items():
        path = os.path.join(base, fname)
        if not os.path.exists(path):
            # In a deployed environment, you might log this or handle it differently
            # For this context, we just skip missing files
            continue

        try:
            xls = pd.ExcelFile(path)
            for sheet in xls.sheet_names:
                df = pd.read_excel(path, sheet_name=sheet, header=None)
                for tbl in extract_tables(df):
                    T = tbl.copy()
                    T["Department"] = dept
                    machine = "Winding" if sheet.lower() == "sheet1" else sheet
                    T["Machine Type"] = machine
                    rows.extend(T.to_dict(orient="records"))
        except Exception as e:
            # Handle potential errors during file reading/parsing
            st.error(f"Error processing file {fname}, sheet {sheet}: {e}")
            continue

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
    # Split by comma, space, semicolon, or pipe
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

    # --- AND Logic (Must contain ALL keywords) ---
    masks_and = [combined.str.contains(k) for k in keywords]
    mask_and = np.logical_and.reduce(masks_and)
    
    # --- OR Logic (Must contain AT LEAST ONE keyword) ---
    masks_or = [combined.str.contains(k) for k in keywords]
    mask_or = np.logical_or.reduce(masks_or)

    if mask_and.any():
        # If all keywords are found together, use that filtered subset
        cand = df[mask_and].copy()
    else:
        # Otherwise, use the results that contain at least one keyword
        cand = df[mask_or].copy()

    if cand.empty:
        return cand

    # --- Scoring/Sorting Logic (Prioritize starting matches) ---
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
# UI CSS (AESTHETIC STYLING)
# ==========================================================
st.set_page_config(page_title="Material Viewfinder", layout="wide")
st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

* {{ border-radius: 8px !important; }}

/* ============================================================ */
/* 0. DARK MODE FIX: Force Light Theme & Text Visibility        */
/* ============================================================ */
/* Force white background globally */
.stApp {{
    background: #FFFFFF !important;
    font-family: 'Inter', sans-serif !important;
}}

/* Force dark text color for specific elements only */
p, 
.stMarkdown,
.stCaption,
[data-testid^="stWidgetLabel"] p, /* Labels for selectboxes, textinputs */
.stText,
.stHeader,
.stSubheader,
[data-testid="stSidebar"] * /* Sidebar elements if present */
{{
    color: {TEXT_DARK} !important; 
}}

/* Ensure button text remains white for main app buttons (secondary) */
button[kind="secondary"] p {{
    color: white !important;
}}

/* Ensure button text remains RED for destructive actions (primary) */
/* This ensures the 'Clear Entire Cart' text is red on white background */
button[kind="primary"] p {{
    color: {RED_DELETE} !important;
}}


/* Ensure all input/select box labels are visible against the main background */
.stSelectbox label p,
.stTextInput label p {{
    color: {TEXT_DARK} !important;
    font-weight: 600; /* Make labels stand out */
}}

/* ============================================================ */
/* 0.1 TITLE FIX (SAP Record Header) - NEW STYLES */
/* ============================================================ */
/* Target the title header generated by st.header() or st.markdown() 
   and apply the background color and padding */
div[data-testid="stMarkdownContainer"]:has(.sap-record-title) {{
    background-color: {TITLE_BACKGROUND} !important; /* Light gray background */
    padding: 12px 16px !important; 
    border-radius: 8px 8px 0 0 !important; /* Rounded top corners */
    margin-top: 1.5rem; /* Add margin above the title block */
    box-shadow: 0 1px 3px rgba(0,0,0,0.05); /* subtle shadow */
}}

/* Force the actual text inside the title to be dark/black */
.sap-record-title {{
    color: {TEXT_DARK} !important;
    font-size: 1.25rem; /* Large text size */
    font-weight: 700;
}}

/* Fix for the icon, ensuring it uses dark color as well */
.sap-record-title [data-testid="stMarkdown"] > p > svg {{
    fill: {TEXT_DARK} !important;
}}

/* ============================================================ */
/* 1. BLUE BUTTONS (Search, Submit, Clear, Add to Cart, Recent) */
/* ============================================================ */
button[kind="secondary"] {{
    background-color: {BLUE} !important;
    border: none !important;
    font-weight: 700 !important;
    padding: 0.25rem 0.75rem !important; /* Adjusted padding for smaller recent search buttons */
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.06);
    transition: all 0.2s ease;
}}
button[kind="secondary"]:hover {{
    background-color: {DARK_BLUE} !important;
    transform: translateY(-2px); 
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
}}
button[kind="secondary"]:focus, button[kind="secondary"]:active {{
    background-color: {DARK_BLUE} !important;
    outline: none !important;
    box-shadow: none !important;
    transform: translateY(0);
}}

/* ============================================================ */
/* 2. DELETE BUTTON (Clean Red Icon & Clear All Cart Button)    */
/* ============================================================ */
button[kind="primary"] {{
    background-color: transparent !important;
    border: 1px solid {RED_DELETE} !important;
    color: {RED_DELETE} !important;
    font-weight: 700 !important;
    transition: all 0.2s ease !important;
    height: 100% !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}
button[kind="primary"]:hover {{
    background-color: {RED_DELETE} !important;
    color: white !important;
    border: 1px solid {RED_DELETE} !important;
    transform: scale(1.05);
    box-shadow: 0 4px 6px rgba(239, 68, 68, 0.3);
}}
button[kind="primary"]:focus {{
    box-shadow: none !important;
    border-color: {RED_DELETE} !important;
}}
/* Override the delete icon button to ensure height is minimal for the trashcan */
button[kind="primary"].stButton {{
    padding: 0;
}}
/* Specifically target the 'Clear Entire Cart' button which is type="primary" 
to give it more height and make it look like a regular button */
button[kind="primary"].stButton:not(.stColumns > div:nth-child(4) button) {{
    height: auto !important;
    padding: 0.25rem 0.75rem !important;
    transform: none; /* remove scale up on hover unless it's the trashcan */
}}
button[kind="primary"].stButton:not(.stColumns > div:nth-child(4) button):hover {{
    transform: translateY(-2px); /* Add slight lift on hover for the full button */
    color: white !important;
}}


/* ============================================================ */
/* 3. INPUTS & DROPDOWNS (Light Background, Blue Borders)       */
/* ============================================================ */

/* Text Input Styling (Search Box) */
.stTextInput input {{
    background-color: white !important; /* Force light background */
    border: 2px solid {BLUE} !important;
    color: {TEXT_DARK} !important; /* Ensure text is dark */
    padding: 8px 12px !important;
    font-weight: 500;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}
.stTextInput input:focus {{
    border-color: {DARK_BLUE} !important;
    box-shadow: 0 0 0 1px {DARK_BLUE} !important;
}}

/* Selectbox (Dropdown) Styling */
.stSelectbox div[data-baseweb="select"] > div {{
    background-color: white !important; /* Force light background */
    border: 2px solid {BLUE} !important;
    color: {TEXT_DARK} !important; /* Ensure selected value is dark */
    font-weight: 500;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}
/* Ensure all dropdown options (list items) are also dark text on light background */
[data-baseweb="menu"] li {{
    color: {TEXT_DARK} !important;
    background-color: white !important;
}}


/* ============================================================ */
/* 4. TABLE STYLING (SAP Record)                                */
/* ============================================================ */
[data-testid="stDataEditor"] {{
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.06);
    border-radius: 0 0 8px 8px !important; /* Rounded bottom corners only */
}}
[data-testid="stDataEditor"] thead th {{
    font-weight: 800 !important; 
    background-color: {TEXT_DARK} !important; /* Darkest color for background */
    color: white !important;
    border: 1px solid #334155 !important;
    font-size: 15px !important;
}}
/* Apply border to the right side of cells for a grid look */
[data-testid="stDataEditor"] tbody td {{
    border-right: 1px solid #E5E7EB; 
    color: {TEXT_DARK} !important; /* Ensure data text is dark */
}}

/* Hides the default colored bar at top */
header {{visibility: hidden;}}

/* ============================================================ */
/* 5. CART ITEM STYLING - ULTRA TIGHT PADDING (Final Compression)*/
/* ============================================================ */

/* Reduce vertical padding on all blocks within the st.columns for the cart */
div[data-testid="stColumn"] > div > div > div {{
    padding-top: 1px !important; 
    padding-bottom: 1px !important; 
    margin-top: 0px !important;
    margin-bottom: 0px !important;
}}

/* Tighter spacing for description/caption text */
div[data-testid="stColumn"] .stMarkdown p, div[data-testid="stColumn"] .stCaption {{
    margin: 0px 0px !important;
    line-height: 1.1;
    font-size: 0.875rem;
}}

div[data-testid="stColumn"] .stText {{
    margin: 0px !important;
    padding: 0px !important;
    line-height: 1.1;
    font-size: 0.875rem;
}}

/* Tighter spacing and smaller height for Quantity Input */
.stNumberInput {{
    margin: 0 !important;
    padding: 0 !important;
}}
.stNumberInput div[data-baseweb="input"] input {{
    height: 28px !important;
    padding-top: 4px !important;
    padding-bottom: 4px !important;
    font-size: 0.875rem;
    /* --- START FIX: Quantity Text Visibility --- */
    color: white !important; 
    background-color: {DARK_BLUE} !important;
    font-weight: 700 !important;
    /* --- END FIX: Quantity Text Visibility --- */
    border: 1px solid {DARK_BLUE} !important; 
    box-shadow: none !important;
    text-align: center; /* Center the quantity number */
}}
/* Adjust buttons inside number input (plus/minus) */
.stNumberInput button {{
    min-height: 28px !important;
    line-height: 1;
    padding: 0 4px; 
    color: {DARK_BLUE} !important; /* Ensure plus/minus buttons are dark blue */
    background-color: transparent !important; /* Keep button backgrounds transparent */
    border: none !important; /* Remove individual button borders */
}}
/* Target the overall container for the number input buttons to remove its background if any */
.stNumberInput div[data-baseweb="input"] {{
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
}}

/* Align delete button vertically */
.stColumns > div:nth-child(4) button {{
    margin-top: 4px; 
    height: 28px !important;
    min-width: 28px !important;
    padding: 0;
    display: flex;
    justify-content: center;
    align-items: center;
}}

/* Override the default margin on the Quantity label column to center content */
.stColumns > div:nth-child(1) .stMarkdown p {{
    margin-top: 8px !important;
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

# --- CART DELETE LOGIC STATES ---
if "undo_item" not in st.session_state:
    st.session_state["undo_item"] = None 

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

# TABLE RESET KEY
if "editor_key" not in st.session_state:
    st.session_state["editor_key"] = 0

# Apply clear logic
if st.session_state["clear_trigger"]:
    st.session_state["query"] = ""
    st.session_state["table_df_base"] = None
    st.session_state["table_label"] = ""
    st.session_state["clear_trigger"] = False
    st.session_state["editor_key"] += 1

# ==========================================================
# LOAD DATA
# ==========================================================
df = load_all()
if df.empty:
    st.error("❌ Material data could not be loaded. Ensure master files are present.")
    st.stop()

# ==========================================================
# AESTHETIC HEADER
# ==========================================================
st.markdown(
    f"""
<div style='text-align: center; margin-bottom: 2rem;'>
    <h1 style='color: {DARK_BLUE}; font-size: 2.5rem; margin-bottom: 0;'>
        MaterialViewfinder
    </h1>
    <p style='color: {BLUE}; font-size: 1.1rem; margin-top: 0;'>
        <span style='margin-right: 8px;'>&#x1F50E;</span> Smart Inventory & Procurement Assistant
    </p>
</div>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# FILTERS AND SEARCH FORM
# ==========================================================
dept_list = [""] + df["Department"].unique().tolist()
machine_list = [""] + df["Machine Type"].unique().tolist()
plant_list = ["SHJM"] # Placeholder for Plant

with st.form("search_form", clear_on_submit=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.selectbox("Plant", plant_list, index=0, key="plant_select", label_visibility="collapsed")
    
    with col2:
        current_dept_index = dept_list.index(st.session_state["current_dept"]) if st.session_state["current_dept"] in dept_list else 0
        selected_dept = st.selectbox(
            "Department", 
            dept_list, 
            index=current_dept_index, 
            key="dept_select",
            label_visibility="collapsed"
        )
        if selected_dept != st.session_state["current_dept"]:
            st.session_state["current_dept"] = selected_dept
            st.session_state["current_machine"] = "" # Reset machine when department changes

    with col3:
        filtered_machines = [""]
        if st.session_state["current_dept"]:
            filtered_machines.extend(
                df[df["Department"] == st.session_state["current_dept"]]["Machine Type"].unique().tolist()
            )
        
        current_machine_index = filtered_machines.index(st.session_state["current_machine"]) if st.session_state["current_machine"] in filtered_machines else 0

        selected_machine = st.selectbox(
            "Machine Type", 
            filtered_machines, 
            index=current_machine_index, 
            key="machine_select",
            label_visibility="collapsed"
        )
        st.session_state["current_machine"] = selected_machine

    col_q, col_s, col_c = st.columns([5, 1, 1])

    with col_q:
        query = st.text_input(
            "Search",
            key="query_input",
            value=st.session_state["query"],
            placeholder="Search by description or material code (e.g. bearing, 13000...)",
            label_visibility="collapsed",
        )
        # Store latest query in session state for cross-form use
        st.session_state["query"] = query
        
    with col_s:
        submitted = st.form_submit_button("Submit", use_container_width=True, type="secondary")
    
    with col_c:
        clear_clicked = st.form_submit_button("Clear", key="clear_btn_form", use_container_width=True, type="secondary")

    if submitted:
        # 1. Update Recent Searches
        search_term = st.session_state["query"].strip()
        if search_term and search_term not in st.session_state["recent_searches"]:
            st.session_state["recent_searches"].insert(0, search_term)
            st.session_state["recent_searches"] = st.session_state["recent_searches"][:5] # Keep max 5

        # 2. Trigger the main search logic
        st.session_state["trigger_search"] = True
    
    if clear_clicked:
        st.session_state["clear_trigger"] = True
        st.session_state["trigger_search"] = False
        st.session_state["query"] = ""
        st.rerun() # Rerun to apply clear_trigger logic outside the form

# ==========================================================
# RECENT SEARCHES
# ==========================================================
if st.session_state["recent_searches"]:
    st.markdown(f"<div style='margin-top: 1rem; margin-bottom: 0.5rem;'><span style='font-weight: 600; color: {TEXT_DARK};'>Recent</span> <span style='color: {BLUE}; font-size: 0.8em;'>&#x21BA;</span></div>", unsafe_allow_html=True)
    
    recent_cols = st.columns(len(st.session_state["recent_searches"]))
    for i, term in enumerate(st.session_state["recent_searches"]):
        with recent_cols[i]:
            if st.button(term, key=f"recent_search_{i}"):
                st.session_state["query"] = term
                st.session_state["trigger_search"] = True
                st.rerun()

# ==========================================================
# SEARCH LOGIC AND DISPLAY
# ==========================================================
if st.session_state["trigger_search"]:
    # Apply Department/Machine filters first
    df_filtered = df.copy()
    if st.session_state["current_dept"]:
        df_filtered = df_filtered[df_filtered["Department"] == st.session_state["current_dept"]]
    if st.session_state["current_machine"]:
        df_filtered = df_filtered[df_filtered["Machine Type"] == st.session_state["current_machine"]]

    # Build the label
    label_parts = []
    if st.session_state["current_dept"]:
        label_parts.append(st.session_state["current_dept"])
    if st.session_state["current_machine"]:
        label_parts.append(st.session_state["current_machine"])
    
    machine_label = f" in {' | '.join(label_parts)}" if label_parts else " (All Departments/Machines)"
    
    # Perform search if query is present
    if st.session_state["query"].strip():
        search_results = hybrid_multi_search(df_filtered, st.session_state["query"])
        st.session_state["table_df_base"] = search_results
        st.session_state["table_label"] = (
            f"Search Results for '{st.session_state['query']}'"
            f"{machine_label}"
        )
    else:
        # If no query, show all filtered results
        st.session_state["table_df_base"] = df_filtered.copy()
        st.session_state["table_label"] = f"All materials{machine_label}"

    st.session_state["trigger_search"] = False
    st.session_state["editor_key"] += 1 # Force key change to reset editor
    st.rerun()


if st.session_state["table_df_base"] is not None:
    display_df = clean_display(st.session_state["table_df_base"])
    
    # ------------------ ADDED FIX FOR TITLE CONTRAST ------------------
    # Use a custom CSS class 'sap-record-title' which is targeted in the <style> block
    st.markdown(
        f'<p class="sap-record-title"><span style="margin-right: 8px;">&#x1F4C4;</span>SAP Record — {st.session_state["table_label"]}</p>',
        unsafe_allow_html=True
    )
    # ------------------------------------------------------------------

    # --- DATAFRAME CONFIGURATION ---
    column_config = {
        "Select": st.column_config.CheckboxColumn(
            "Select", help="Select to add to cart", default=False
        ),
        "Quantity": st.column_config.NumberColumn(
            "Quantity", min_value=1, max_value=1000, step=1, default=1
        ),
        "Machine Type": st.column_config.TextColumn("Machine Type"),
        "Department": st.column_config.TextColumn("Department"),
        "Material": st.column_config.TextColumn("Material"),
        KEY_DESC: st.column_config.TextColumn("Material description"),
        "Material Proposed Description": st.column_config.TextColumn("Material Long Description"),
    }
    
    # Columns to show in the final table (in order)
    cols_to_show = [
        "Select",
        "Quantity",
        "Machine Type",
        "Department",
        "Material",
        KEY_DESC,
        "Material Proposed Description",
    ]

    try:
        edited_df = st.data_editor(
            display_df[cols_to_show],
            column_config=column_config,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            key=f"data_editor_{st.session_state['editor_key']}"
        )

        selected_rows = edited_df[edited_df["Select"]]

        if not selected_rows.empty:
            st.info(f"Adding {len(selected_rows)} selected item(s) to the cart.")

            # Process additions
            for index, row in selected_rows.iterrows():
                mat_code = row["Material"]
                quantity = int(row["Quantity"])
                
                item_key = mat_code
                
                # Create the full item object to store
                item_details = {
                    "code": mat_code,
                    "desc": row[KEY_DESC],
                    "long_desc": row["Material Proposed Description"],
                    "dept": row["Department"],
                    "machine": row["Machine Type"],
                    "qty": quantity, # Store the selected quantity
                }
                
                # Add/Update the cart item
                if item_key in st.session_state["cart"]:
                    # If item exists, update quantity (or overwrite with new quantity)
                    st.session_state["cart"][item_key]["qty"] = quantity
                else:
                    # New item, add to cart
                    st.session_state["cart"][item_key] = item_details
            
            # After processing, reset the table state to remove selections
            # by reloading the table data (which clears the 'Select' column)
            st.session_state["table_df_base"] = st.session_state["table_df_base"].copy() 
            st.session_state["editor_key"] += 1
            st.rerun()

    except Exception as e:
        st.error(f"An error occurred while displaying the table: {e}")
        st.session_state["table_df_base"] = None # Reset table to prevent looping error


# ==========================================================
# CART DISPLAY
# ==========================================================
st.markdown("<h2 style='margin-top: 2rem; color: #1E293B;'>&#x1F6D2; Cart</h2>", unsafe_allow_html=True)

if not st.session_state["cart"]:
    st.info("Your cart is empty.")
else:
    # 1. Cart Items Container
    cart_items = st.session_state["cart"].values()
    
    header_cols = st.columns([1, 4.5, 2, 0.5])
    header_cols[0].markdown(f"<p style='font-weight: 700; color: {DARK_BLUE};'>Qty</p>", unsafe_allow_html=True)
    header_cols[1].markdown(f"<p style='font-weight: 700; color: {DARK_BLUE};'>Material / Description</p>", unsafe_allow_html=True)
    header_cols[2].markdown(f"<p style='font-weight: 700; color: {DARK_BLUE};'>Machine</p>", unsafe_allow_html=True)
    # The last column is for the delete icon

    for i, item in enumerate(cart_items):
        key = item["code"]
        
        # Line separator
        st.markdown("<hr style='border-top: 1px solid #E5E7EB; margin: 2px 0 2px 0;'>", unsafe_allow_html=True)

        col_qty, col_desc, col_machine, col_del = st.columns([1, 4.5, 2, 0.5])

        with col_qty:
            new_qty = st.number_input(
                "Qty",
                min_value=1,
                max_value=1000,
                value=item["qty"],
                key=f"qty_{key}",
                label_visibility="collapsed",
                # on_change handler to update state immediately
                on_change=lambda k=key: st.session_state["cart"][k].update(qty=st.session_state[f"qty_{k}"])
            )
            # Update item quantity in state immediately if changed by user input
            if new_qty != item["qty"]:
                st.session_state["cart"][key]["qty"] = new_qty
                
        with col_desc:
            st.markdown(
                f"""
                <p style='font-weight: 600; color: {TEXT_DARK}; margin: 0;'>{item['desc']}</p>
                <p class='stCaption'>Code: {item['code']} | Dept: {item['dept']}</p>
                """, 
                unsafe_allow_html=True
            )
            
        with col_machine:
            st.text(item["machine"])
            
        with col_del:
            # Delete button (primary style for red color)
            if st.button("🗑️", key=f"delete_{key}", type="primary", use_container_width=True):
                # Save item for potential undo
                st.session_state["undo_item"] = (key, st.session_state["cart"][key])
                del st.session_state["cart"][key]
                st.rerun()

    # Final horizontal rule after the last item
    st.markdown("<hr style='border-top: 1px solid #E5E7EB; margin: 2px 0 2px 0;'>", unsafe_allow_html=True)

    # 2. Cart Actions (Clear All / Undo)
    col_clear, col_undo, col_fill = st.columns([1.5, 1.5, 5])
    
    with col_clear:
        if st.button("Clear Entire Cart", key="clear_all_cart", type="primary"):
            # Clear cart and reset undo
            st.session_state["cart"] = {}
            st.session_state["undo_item"] = None
            st.rerun()
            
    with col_undo:
        if st.session_state["undo_item"] is not None:
            undo_key, undo_item = st.session_state["undo_item"]
            if st.button("Undo Last Delete", key="undo_delete", type="secondary"):
                # Restore the item
                st.session_state["cart"][undo_key] = undo_item
                st.session_state["undo_item"] = None
                st.rerun()
                
    # 3. Email Preview/Export Section
    st.markdown("---", unsafe_allow_html=True)
    st.markdown("### Email Preview")
    
    email_body = "Dear Sir/Madam,\n\nPlease arrange the following materials:\n\n"
    for item in st.session_state["cart"].values():
        email_body += f"- {item['qty']} x {item['desc']} (Code: {item['code']}, Machine: {item['machine']})\n"
        
    email_body += "\nRegards,\nMaterial Viewfinder Bot"
    
    # Text area for email preview
    st.text_area(
        "Email Content",
        value=email_body,
        height=200,
        key="email_content",
        label_visibility="collapsed"
    )
    
    # Button to open mail client (using mailto link)
    mailto_url = f"mailto:procurement@example.com?subject={urllib.parse.quote('Material Request')}&body={urllib.parse.quote(email_body)}"
    
    st.markdown(
        f'<a href="{mailto_url}" target="_blank" style="text-decoration: none;">'
        f'<button class="stButton" kind="secondary" style="width: 100%;">'
        f'<p>Send Email</p>'
        f'</button>'
        f'</a>',
        unsafe_allow_html=True
    )
    
    st.markdown("")
    st.download_button(
        label="Download Material List (TXT)",
        data=email_body,
        file_name="material_request.txt",
        mime="text/plain",
        use_container_width=True
    )
