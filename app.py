import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - VIN Filter 0008", layout="wide")
st.title("ITOSE Tools - VIN + Message (Exclude Status 0008)")

# =========================
# REGEX
# =========================
JSON_REGEX = r'\{.*?\}'

# =========================
# FUNCTIONS
# =========================
def extract_json_blocks(text):
    return re.findall(JSON_REGEX, text)

def parse_vin_filter(df):
    rows = []

    for col in df.columns:
        for val in df[col]:
            if pd.isna(val):
                continue

            text = str(val)

            for block in extract_json_blocks(text):
                try:
                    data = json.loads(block)

                    vin = data.get("vin")
                    status = str(data.get("status"))
                    message = data.get("message")

                    # ❌ ตัดเฉพาะ 0008
                    if status == "0008":
                        continue

                    rows.append({
                        "VIN": vin,
                        "Message": message,
                        "Status": status
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
    df1 = parse_vin_filter(df_file1)

    # =========================
    # DISPLAY
    # =========================
    st.subheader("FDFDataHubLinkage")

    if df1.empty:
        st.warning("⚠️ ไม่เจอข้อมูลหลังจาก filter")
    else:
        st.dataframe(df1, use_container_width=True)

        # 🔢 จำนวนทั้งหมด (ยังซ้ำได้)
        st.markdown(f"### 🔢 Total Rows: {len(df1)}")

        # 🧠 unique VIN
        st.markdown(f"### 🧠 Unique VIN: {df1['VIN'].nunique()}")

    # =========================
    # EXPORT
    # =========================
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1.to_excel(writer, index=False, sheet_name='VIN_Filter_0008')

    output.seek(0)

    st.download_button(
        "Download Excel",
        data=output,
        file_name="vin-message-filter-0008.xlsx"
    )
