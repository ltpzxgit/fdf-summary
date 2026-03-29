import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - FDF", layout="wide")
st.title("ITOSE Tools - FDF Summary")

# =========================
# REGEX
# =========================
JSON_REGEX = r'\{.*?\}'
UUID_REGEX = r'([a-f0-9\-]{36})'   # 🔥 UUID

# =========================
# FUNCTIONS
# =========================
def extract_json_blocks(text):
    return re.findall(JSON_REGEX, text)

def extract_uuid(text):
    match = re.search(UUID_REGEX, text)
    return match.group(1) if match else None

def parse_vin_smart(df):
    rows = []

    for col in df.columns:
        for val in df[col]:
            if pd.isna(val):
                continue

            text = str(val)

            # 🔥 หา UUID จากบรรทัดเดียวกัน
            uuid = extract_uuid(text)

            for block in extract_json_blocks(text):
                try:
                    data = json.loads(block)

                    rows.append({
                        "RequestID": uuid,   # 🔥 เพิ่มตรงนี้
                        "VIN": data.get("vin"),
                        "Message": data.get("message"),
                        "Status": str(data.get("status"))
                    })

                except:
                    continue

    df_out = pd.DataFrame(rows)

    if not df_out.empty:
        df_out = df_out[df_out["VIN"].notna()]

        # 🔥 แยก 0008 กับ non-0008
        df_0008 = df_out[df_out["Status"] == "0008"]
        df_other = df_out[df_out["Status"] != "0008"]

        # 🔥 0008 → เอาแค่ 1 ต่อ VIN
        df_0008 = df_0008.drop_duplicates(subset=["VIN"], keep="last")

        # 🔥 รวมกลับ
        df_final = pd.concat([df_other, df_0008], ignore_index=True)

        df_final = df_final.reset_index(drop=True)
        df_final.insert(0, "No.", df_final.index + 1)

        return df_final

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
    df1 = parse_vin_smart(df_file1)

    # =========================
    # DISPLAY
    # =========================
    st.subheader("VIN (0008 No Duplicate)")

    if df1.empty:
        st.warning("⚠️ ไม่เจอข้อมูล")
    else:
        st.dataframe(df1, use_container_width=True)

        st.markdown(f"### 🔢 Total Rows: {len(df1)}")
        st.markdown(f"### 🧠 Unique VIN: {df1['VIN'].nunique()}")

    # =========================
    # EXPORT
    # =========================
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1.to_excel(writer, index=False, sheet_name='VIN_Smart')

    output.seek(0)

    st.download_button(
        "Download Excel",
        data=output,
        file_name="fdf-summary.xlsx"
    )
