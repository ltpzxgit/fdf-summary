import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - FDF 3 Files", layout="wide")
st.title("ITOSE Tools - FDF (3 Files Version)")

# =========================
# REGEX
# =========================
JSON_REGEX = r'\{.*?\}'

# =========================
# FUNCTIONS
# =========================
def extract_json_blocks(text):
    return re.findall(JSON_REGEX, text)

def parse_fdfdatahub(df):
    rows = []

    for col in df.columns:
        for val in df[col]:
            if pd.isna(val): 
                continue

            text = str(val)

            for block in extract_json_blocks(text):
                try:
                    data = json.loads(block)

                    rows.append({
                        "VIN": data.get("vin"),
                        "Message": data.get("message"),
                        "Status": data.get("status")
                    })
                except:
                    continue

    df_out = pd.DataFrame(rows).drop_duplicates()
    df_out = df_out.reset_index(drop=True)
    df_out.insert(0, "No.", df_out.index + 1)

    return df_out


# =========================
# UPLOAD
# =========================
col1, col2, col3 = st.columns(3)

with col1:
    file1 = st.file_uploader("FDFDataHub", type=["xlsx", "csv"])
with col2:
    file2 = st.file_uploader("FDFTCAP", type=["xlsx", "csv"])
with col3:
    file3 = st.file_uploader("VehicleSettingRequester", type=["xlsx", "csv"])


if file1 and file2 and file3:

    df_file1 = pd.read_csv(file1) if file1.name.endswith(".csv") else pd.read_excel(file1)
    df_file2 = pd.read_csv(file2) if file2.name.endswith(".csv") else pd.read_excel(file2)
    df_file3 = pd.read_csv(file3) if file3.name.endswith(".csv") else pd.read_excel(file3)

    # =========================
    # SHEET 1: FDFDataHubLinkage
    # =========================
    df1 = parse_fdfdatahub(df_file1)

    # =========================
    # SHEET 2: FDFTCAPHubLinkage (ยังไม่ parse)
    # =========================
    df2 = df_file2.copy()
    df2 = df2.reset_index(drop=True)
    df2.insert(0, "No.", df2.index + 1)

    # =========================
    # SHEET 3: VehicleSettingRequester (ยังไม่ parse)
    # =========================
    df3 = df_file3.copy()
    df3 = df3.reset_index(drop=True)
    df3.insert(0, "No.", df3.index + 1)

    # =========================
    # SHOW TABLE
    # =========================
    st.subheader("FDFDataHubLinkage")
    st.dataframe(df1)

    st.subheader("FDFTCAPHubLinkage")
    st.dataframe(df2)

    st.subheader("VehicleSettingRequester")
    st.dataframe(df3)

    # =========================
    # EXPORT
    # =========================
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1.to_excel(writer, index=False, sheet_name='FDFDataHubLinkage')
        df2.to_excel(writer, index=False, sheet_name='FDFTCAPHubLinkage')
        df3.to_excel(writer, index=False, sheet_name='VehicleSettingRequester')

    output.seek(0)

    st.download_button(
        "Download Excel",
        data=output,
        file_name="fdf-3files.xlsx"
    )
