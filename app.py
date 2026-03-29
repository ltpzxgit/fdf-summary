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
# FUNCTIONS FDFDataHub
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


def parse_fdf_datahub(df):
    rows = []
    uuid_groups = {}

    for col in df.columns:
        for val in df[col]:
            if pd.isna(val):
                continue

            text = str(val)
            uuid = extract_uuid(text)

            if not uuid:
                continue

            uuid_groups.setdefault(uuid, []).append(text)

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

        # ❌ ตัด 0008
        df_out = df_out[df_out["Status"] != "0008"]

        # 🔥 Latest ต่อ VIN
        df_out = df_out.iloc[::-1]
        df_out = df_out.drop_duplicates(subset=["VIN"], keep="first")
        df_out = df_out.iloc[::-1]

        df_out = df_out.reset_index(drop=True)
        df_out.insert(0, "No.", df_out.index + 1)

    return df_out


# =========================
# FUNCTIONS FDFTCAP
# =========================
def parse_fdf_tcap(df):
    df.columns = [c.strip() for c in df.columns]

    # 🔥 หา column ที่เกี่ยวกับ status
    status_col = None
    for col in df.columns:
        if "status" in col.lower():
            status_col = col
            break

    if not status_col:
        return pd.DataFrame()

    # 🔥 filter 000
    df = df[df[status_col].astype(str).str.contains("000")]

    df = df.reset_index(drop=True)
    df.insert(0, "No.", df.index + 1)

    return df


# =========================
# UPLOAD
# =========================
col1, col2 = st.columns(2)

with col1:
    file1 = st.file_uploader("Upload FDFDataHub", type=["xlsx", "csv", "json"])

with col2:
    file2 = st.file_uploader("Upload FDFTCAP", type=["xlsx", "csv"])


# =========================
# PROCESS FDFDataHub
# =========================
if file1:
    if file1.name.endswith(".json"):
        df_file1 = pd.read_json(file1)
        df_file1 = df_file1["@message"]
    else:
        df_file1 = pd.read_csv(file1) if file1.name.endswith(".csv") else pd.read_excel(file1)

    df1 = parse_fdf_datahub(df_file1)

    st.subheader("FDFDataHub (Latest per VIN | No 0008)")

    if df1.empty:
        st.warning("⚠️ ไม่เจอข้อมูล")
    else:
        st.dataframe(df1, use_container_width=True)
        st.markdown(f"### 🔢 Total Rows: {len(df1)}")


# =========================
# PROCESS FDFTCAP
# =========================
if file2:
    df_file2 = pd.read_csv(file2) if file2.name.endswith(".csv") else pd.read_excel(file2)

    df2 = parse_fdf_tcap(df_file2)

    st.subheader("FDFTCAP (StatusCode = 000)")

    if df2.empty:
        st.warning("⚠️ ไม่เจอ StatusCode = 000")
    else:
        st.dataframe(df2, use_container_width=True)
        st.markdown(f"### 🔢 Total Rows: {len(df2)}")


# =========================
# EXPORT (optional รวม)
# =========================
if file1 or file2:
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if file1 and not df1.empty:
            df1.to_excel(writer, index=False, sheet_name='FDFDataHub')

        if file2 and not df2.empty:
            df2.to_excel(writer, index=False, sheet_name='FDFTCAP')

    output.seek(0)

    st.download_button(
        "Download Excel (All)",
        data=output,
        file_name="fdf-summary.xlsx"
    )
