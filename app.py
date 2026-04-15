import streamlit as st
import pandas as pd
from evds import evdsAPI
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="EVDS Veri Robotu", layout="wide")
st.title("📊 TCMB EVDS Veri Robotu")

DEFAULT_API_KEY = "SnWnU6PUDF"

with st.sidebar:
    st.header("⚙️ Ayarlar")
    override_key = st.text_input("API Key (opsiyonel)", type="password", placeholder="Hata alırsanız buraya girin")
    st.caption("TCMB EVDS Veri Robotu")

API_KEY = override_key.strip() if override_key.strip() else DEFAULT_API_KEY

@st.cache_data(show_spinner="Ana kategoriler yükleniyor...")
def load_main_categories(api_key):
    evds = evdsAPI(api_key)
    return evds.main_categories

@st.cache_data(show_spinner="Alt kategoriler yükleniyor...")
def load_sub_categories(api_key, cat_index):
    evds = evdsAPI(api_key)
    return evds.get_sub_categories(cat_index)

@st.cache_data(show_spinner="Seriler yükleniyor...")
def load_series(api_key, sub_code):
    evds = evdsAPI(api_key)
    return evds.get_series(sub_code)

# Ana kategoriler
try:
    main_cats = load_main_categories(API_KEY)
except Exception as e:
    st.error(f"Kategoriler yüklenemedi: {e}")
    st.warning("👈 Sol menüden API key girin. Key almak için: https://evds3.tcmb.gov.tr")
    st.stop()

cat_name_col = next((c for c in main_cats.columns if "TOPIC_TITLE" in c and "ENG" not in c), main_cats.columns[0])
cat_id_col   = next((c for c in main_cats.columns if "CATEGORY_ID" in c), main_cats.columns[0])

cat_options = ["— Seçin —"] + [
    f"{row[cat_name_col]}  [#{int(row[cat_id_col])}]"
    for _, row in main_cats.iterrows()
]

col1, col2 = st.columns([2, 1])

with col1:
    selected_cat = st.selectbox("1️⃣ Ana Kategori", cat_options)

sub_options = []
sub_cats_df = None

if selected_cat != "— Seçin —":
    cat_idx = int(selected_cat.split("[#")[-1].rstrip("]"))
    try:
        sub_cats_df = load_sub_categories(API_KEY, cat_idx)
        sub_name_col = next((c for c in sub_cats_df.columns if "DATAGROUP_NAME" in c and "ENG" not in c), sub_cats_df.columns[0])
        sub_code_col = next((c for c in sub_cats_df.columns if "DATAGROUP_CODE" in c), sub_cats_df.columns[0])
        sub_options = ["— Seçin —"] + [
            f"{row[sub_name_col]}  [{row[sub_code_col]}]"
            for _, row in sub_cats_df.iterrows()
        ]
    except Exception as e:
        st.warning(f"Alt kategoriler yüklenemedi: {e}")

with col1:
    selected_sub = st.selectbox(
        "2️⃣ Alt Kategori / Veri Grubu",
        sub_options if sub_options else ["— Önce ana kategori seçin —"]
    )

series_options = []
series_map = {}

if selected_sub and selected_sub not in ("— Seçin —", "— Önce ana kategori seçin —"):
    sub_code = selected_sub.split("[")[-1].rstrip("]")
    try:
        series_df = load_series(API_KEY, sub_code)
        serie_name_col = next((c for c in series_df.columns if "SERIE_NAME" in c and "ENG" not in c), series_df.columns[0])
        serie_code_col = next((c for c in series_df.columns if "SERIE_CODE" in c), series_df.columns[0])
        for _, row in series_df.iterrows():
            label = f"{row[serie_name_col]}  [{row[serie_code_col]}]"
            series_map[label] = str(row[serie_code_col])
        series_options = ["— Seçin —"] + list(series_map.keys())
    except Exception as e:
        st.warning(f"Seriler yüklenemedi: {e}")

with col1:
    selected_series = st.selectbox(
        "3️⃣ Seri Seç",
        series_options if series_options else ["— Önce alt kategori seçin —"]
    )
    manual_code = st.text_input("veya Manuel Ticker Kodu Gir", placeholder="örn: TP.DK.USD.A")

with col2:
    st.markdown("**Tarih Aralığı**")
    start_date = st.date_input("Başlangıç", value=datetime(2010, 1, 1))
    end_date   = st.date_input("Bitiş",     value=datetime.today())

# Aktif ticker
if manual_code.strip():
    active_ticker = manual_code.strip()
    active_name   = active_ticker
elif selected_series and selected_series not in ("— Seçin —", "— Önce alt kategori seçin —"):
    active_ticker = series_map.get(selected_series)
    active_name   = selected_series.split("  [")[0]
else:
    active_ticker = None
    active_name   = None

# Veri çekme
if active_ticker:
    try:
        evds_client = evdsAPI(API_KEY)
        fmt = "%d-%m-%Y"
        df = evds_client.get_data(
            [active_ticker],
            startdate=start_date.strftime(fmt),
            enddate=end_date.strftime(fmt)
        )

        if df is not None and not df.empty:
            date_col   = "Tarih" if "Tarih" in df.columns else df.columns[0]
            value_cols = [c for c in df.columns if c != date_col]
            df[date_col]   = pd.to_datetime(df[date_col], errors="coerce")
            df[value_cols] = df[value_cols].apply(pd.to_numeric, errors="coerce")
            df = df.dropna(subset=value_cols, how="all").sort_values(date_col)

            st.markdown("---")
            st.subheader(f"📌 {active_name}")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Ticker Kodu",     active_ticker)
            m2.metric("İlk Veri Tarihi", df[date_col].min().strftime("%d.%m.%Y"))
            m3.metric("Son Veri Tarihi", df[date_col].max().strftime("%d.%m.%Y"))
            m4.metric("Toplam Gözlem",   len(df))

            if len(df) > 1:
                delta  = (df[date_col].iloc[-1] - df[date_col].iloc[0]).days / len(df)
                period = ("Günlük" if delta < 2 else "Haftalık" if delta < 10
                          else "Aylık" if delta < 35 else "Çeyreklik" if delta < 100 else "Yıllık")
                st.info(f"📅 Tahmini Periyot: **{period}** (ortalama {delta:.1f} gün aralık)")

            st.line_chart(df.set_index(date_col)[value_cols[0]])

            with st.expander("📋 Veri Önizleme"):
                st.dataframe(df, use_container_width=True)

            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name=active_ticker[:30])
            output.seek(0)

            st.download_button(
                label="⬇️ Excel Olarak İndir",
                data=output,
                file_name=f"{active_ticker.replace('.', '_')}_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Bu tarih aralığında veri bulunamadı.")

    except Exception as e:
        err_msg = str(e).lower()
        if any(x in err_msg for x in ["401", "403", "unauthorized", "invalid key", "api key"]):
            st.error("❌ API key geçersiz veya süresi dolmuş.")
            st.warning("👈 Sol menüden yeni API key girin. Key almak için: https://evds3.tcmb.gov.tr")
        else:
            st.error(f"Hata: {e}")
else:
    st.info("Kategori → Alt Kategori → Seri seçin, veya manuel kod girin.")
