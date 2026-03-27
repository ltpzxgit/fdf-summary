import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - FDF Single File", layout="wide")
st.title("ITOSE Tools - FDFDataHub")

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

    df_out = pd.DataFrame(rows)

    if not df_out.empty:
        # ❌ ตัด VIN ว่าง
        df_out = df_out[df_out["VIN"].notna()]

        # 🔥 รวมข้อมูลทุก record ต่อ VIN
        df_out = df_out.groupby("VIN", as_index=False).agg({
            "Message": lambda x: " | ".join(
                sorted(set(str(i) for i in x if pd.notna(i)))
            ),
            "Status": lambda x: " | ".join(
                sorted(set(str(i) for i in x if pd.notna(i)))
            )
        })

        df_out = df_out.reset_index(drop=True)
        df_out.insert(0, "No.", df_out.index + 1)

    return df_out


# =========================
# UPLOAD
# =========================
file1 = st.file_uploader("Upload FDFDataHub", type=["xlsx", "csv"])

if file1:

    df_file1 = pd.read_csv(file1) if file1.name.endswith(".csv") else pd.read_excel(file1)

    # =========================
    # PARSE
    # =========================
    df1 = parse_fdfdatahub(df_file1)

    # =========================
    # DISPLAY
    # =========================
    st.subheader("FDFDataHubLinkage")

    if df1.empty:
        st.warning("⚠️ ไม่เจอ JSON ที่มี vin / message / status ในไฟล์นี้")
    else:
        st.dataframe(df1)

        # 🔢 จำนวน VIN (ไม่ซ้ำ)
        st.markdown(f"### 🔢 Total Unique VIN: {len(df1)}")

    # =========================
    # EXPORT
    # =========================
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1.to_excel(writer, index=False, sheet_name='FDFDataHubLinkage')

    output.seek(0)

    st.download_button(
        "Download Excel",
        data=output,
        file_name="fdf-datahub.xlsx"
    )
