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
UUID_REGEX = r'([a-f0-9\-]{36})'
REQUEST_ID_REGEX = r'Request ID:\s*([a-f0-9\-]{36})'

# =========================
# FUNCTIONS
# =========================
def extract_uuid(text):
    match = re.search(UUID_REGEX, text)
    return match.group(1) if match else None

def extract_request_id(text):
    match = re.search(REQUEST_ID_REGEX, text)
    return match.group(1) if match else None

def extract_response_json(text):
    if "Response:" not in text:
        return None
    try:
        json_part = text.split("Response:", 1)[1].strip()
        return json.loads(json_part)
    except:
        return None


def parse_vin_smart(df):
    rows = []

    # 🔥 GROUP ตาม UUID
    uuid_groups = {}

    for col in df.columns:
        for val in df[col]:
            if pd.isna(val):
                continue

            text = str(val)
            uuid = extract_uuid(text)

            if not uuid:
                continue

            if uuid not in uuid_groups:
                uuid_groups[uuid] = []

            uuid_groups[uuid].append(text)

    # 🔥 PROCESS ทีละ UUID
    for uuid, logs in uuid_groups.items():

        request_id = None
        response_data = None

        for log in logs:
            if not request_id:
                request_id = extract_request_id(log)

            if not response_data:
                response_data = extract_response_json(log)

        if response_data and "data" in response_data:
            vehicle_list = response_data["data"].get("vehicleList", [])

            for item in vehicle_list:
                rows.append({
                    "RequestID": request_id,
                    "VIN": item.get("vin"),
                    "Message": item.get("message"),
                    "Status": str(item.get("status"))
                })

    df_out = pd.DataFrame(rows)

    if not df_out.empty:
        df_out = df_out[df_out["VIN"].notna()]

        # =========================
        # ❌ ตัด 0008 ทิ้ง
        # =========================
        df_out = df_out[df_out["Status"] != "0008"]

        # =========================
        # 🔥 Latest ต่อ VIN
        # =========================
        df_out = df_out.iloc[::-1]
        df_out = df_out.drop_duplicates(subset=["VIN"], keep="first")
        df_out = df_out.iloc[::-1]

        df_out = df_out.reset_index(drop=True)
        df_out.insert(0, "No.", df_out.index + 1)

        return df_out

    return df_out


# =========================
# UPLOAD
# =========================
file1 = st.file_uploader("Upload FDFDataHub", type=["xlsx", "csv", "json"])

if file1:

    if file1.name.endswith(".json"):
        df_file1 = pd.read_json(file1)
        df_file1 = df_file1["@message"]
    else:
        df_file1 = pd.read_csv(file1) if file1.name.endswith(".csv") else pd.read_excel(file1)

    # =========================
    # PARSE
    # =========================
    df1 = parse_vin_smart(df_file1)

    # =========================
    # DISPLAY
    # =========================
    st.subheader("VIN (Latest per VIN | No 0008)")

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
