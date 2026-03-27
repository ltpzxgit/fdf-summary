import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - VIN Raw", layout="wide")
st.title("ITOSE Tools - VIN Raw Extract")

# =========================
# REGEX
# =========================
JSON_REGEX = r'\{.*?\}'

# =========================
# FUNCTIONS
# =========================
def extract_json_blocks(text):
    return re.findall(JSON_REGEX, text)

def parse_vin_raw(df):
    rows = []

    for col in df.columns:
        for val in df[col]:
            if pd.isna(val):
                continue

            text = str(val)

            for block in extract_json_blocks(text):
                try:
                    data = json.loads(block)

                    # 🔥 ไม่ filter อะไรเลย เอามาหมด
                    rows.append({
                        "VIN": data.get("vin")
                    })

                except:
                    continue

    df_out = pd.DataFrame(rows)

    if not df_out.empty:
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
    df1 = parse_vin_raw(df_file1)

    # =========================
    # DISPLAY
    # =========================
    st.subheader("VIN Raw (No Filter)")

    if df1.empty:
        st.warning("⚠️ ไม่เจอ JSON ในไฟล์นี้")
    else:
        st.dataframe(df1, use_container_width=True)

        # 🔢 จำนวนทั้งหมด (รวมทุกอย่าง)
        st.markdown(f"### 🔢 Total Rows (Raw VIN): {len(df1)}")

        # 🧠 unique (แค่โชว์ ไม่ได้ใช้ตัด)
        st.markdown(f"### 🧠 Unique VIN (reference): {df1['VIN'].nunique()}")

    # =========================
    # EXPORT
    # =========================
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1.to_excel(writer, index=False, sheet_name='VIN_Raw')

    output.seek(0)

    st.download_button(
        "Download Excel",
        data=output,
        file_name="vin-raw.xlsx"
    )
