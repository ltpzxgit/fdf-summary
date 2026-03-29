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
    """
    ดึง JSON หลังคำว่า Response:
    """
    if "Response:" not in text:
        return None

    try:
        json_part = text.split("Response:", 1)[1].strip()

        # 🔥 แก้ double quote "" → "
        json_part = json_part.replace('""', '"')

        return json.loads(json_part)
    except:
        return None

def parse_vin_smart(df):
    rows = []
    uuid_map = {}

    for col in df.columns:
        for val in df[col]:
            if pd.isna(val):
                continue

            text = str(val)

            uuid = extract_uuid(text)
            request_id = extract_request_id(text)

            # =========================
            # STEP 1: map RequestID
            # =========================
            if uuid and request_id:
                uuid_map[uuid] = request_id

            # =========================
            # STEP 2: parse RESPONSE JSON
            # =========================
            data = extract_response_json(text)

            if data and "data" in data:
                vehicle_list = data["data"].get("vehicleList", [])

                for item in vehicle_list:
                    rows.append({
                        "RequestID": uuid_map.get(uuid),
                        "VIN": item.get("vin"),
                        "Message": item.get("message"),
                        "Status": str(item.get("status"))
                    })

    df_out = pd.DataFrame(rows)

    if not df_out.empty:
        df_out = df_out[df_out["VIN"].notna()]

        # =========================
        # RULE: 0008 ไม่ซ้ำ
        # =========================
        df_0008 = df_out[df_out["Status"] == "0008"]
        df_other = df_out[df_out["Status"] != "0008"]

        df_0008 = df_0008.drop_duplicates(subset=["VIN"], keep="last")

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
