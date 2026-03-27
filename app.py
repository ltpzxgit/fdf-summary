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

    # ✅ ลบ VIN ที่ซ้ำ (เอาแค่ตัวแรก)
    if not df_out.empty:
        df_out = df_out.drop_duplicates(subset=["VIN"])

        df_out = df_out.reset_index(drop=True)
        df_out.insert(0, "No.", df_out.index + 1)

    return df_out
