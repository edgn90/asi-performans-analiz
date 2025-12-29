import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Sayfa Konfigürasyonu
st.set_page_config(page_title="Aşı Performans Sistemi", layout="wide")

st.title("📊 Aşı Takip & Performans Dashboard")
st.markdown("---")

# Yan Menü (Filtreler)
st.sidebar.header("1. Ayarlar & Veri")
uploaded_file = st.sidebar.file_uploader("Excel veya CSV Yükleyin", type=["xlsx", "csv"])

if uploaded_file:
    # Veriyi Oku
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file, encoding='cp1254')
    else:
        df = pd.read_excel(uploaded_file)

    # Sütunları Temizle ve Eşleştir
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={
        'ILCE': 'ilce', 'asm': 'asm', 'BIRIM_ADI': 'birim',
        'ASI_SON_TARIH': 'hedef_tarih', 'ASI_YAP_TARIH': 'yapilan_tarih', 'ASI_DOZU': 'doz'
    })

    # Tarih İşlemleri
    df['hedef_tarih'] = pd.to_datetime(df['hedef_tarih'], errors='coerce')
    df['yapilan_tarih'] = pd.to_datetime(df['yapilan_tarih'], errors='coerce')
    df = df.dropna(subset=['hedef_tarih'])

    # Tarih Aralığı Seçimi
    min_date = df['hedef_tarih'].min().date()
    max_date = df['hedef_tarih'].max().date()
    date_range = st.sidebar.date_input("Analiz Tarih Aralığı", [min_date, max_date])

    # Hedef Oranlar
    target_val = st.sidebar.number_input("Hedef Başarı (Yeşil %)", value=90)
    min_val = st.sidebar.number_input("Alt Sınır (Kırmızı %)", value=70)

    # Filtreleme Uygula
    mask = (df['hedef_tarih'].dt.date >= date_range[0]) & (df['hedef_tarih'].dt.date <= date_range[1])
    df_filtered = df[mask].copy()
    df_filtered['basari_durumu'] = df_filtered['yapilan_tarih'].notna().astype(int)

    # --- KPI KARTLARI ---
    total_target = len(df_filtered)
    total_done = df_filtered['basari_durumu'].sum()
    
    ozet = df_filtered.groupby(['ilce', 'asm', 'birim']).agg(
        toplam=('basari_durumu', 'count'),
        yapilan=('basari_durumu', 'sum')
    ).reset_index()
    ozet['oran'] = (ozet['yapilan'] / ozet['toplam'] * 100).round(2)
    
    riskli_birim_sayisi = len(ozet[ozet['oran'] < min_val])

    col1, col2, col3 = st.columns(3)
    col1.metric("🔵 Toplam Hedef", total_target)
    col2.metric("🟢 Toplam Yapılan", total_done)
    col3.metric("🔴 Riskli Birim (Alt Sınır Altı)", riskli_birim_sayisi)

    # --- GRAFİKLER ---
    st.markdown("### 📈 Analiz Grafikleri")
    g1, g2 = st.columns(2)

    # İlçe Bazlı Bar Grafik
    ilce_ozet = ozet.groupby('ilce').agg({'toplam':'sum', 'yapilan':'sum'}).reset_index()
    ilce_ozet['oran'] = (ilce_ozet['yapilan'] / ilce_ozet['toplam'] * 100).round(2)
    ilce_ozet['Renk'] = ilce_ozet['oran'].apply(lambda x: 'Yeşil' if x >= target_val else ('Sarı' if x >= min_val else 'Kırmızı'))
    
    fig_bar = px.bar(ilce_ozet, x='ilce', y='oran', color='Renk', 
                     color_discrete_map={'Yeşil':'#198754', 'Sarı':'#ffc107', 'Kırmızı':'#dc3545'},
                     title="İlçe Performans Oranları (%)")
    g1.plotly_chart(fig_bar, use_container_width=True)

    # Trend Grafiği
    df_filtered['AY'] = df_filtered['hedef_tarih'].dt.strftime('%Y-%m')
    trend = df_filtered.groupby('AY').agg({'basari_durumu':['sum','count']}).reset_index()
    trend.columns = ['AY', 'YAPILAN', 'HEDEF']
    trend['ORAN'] = (trend['YAPILAN'] / trend['HEDEF'] * 100).round(2)
    
    fig_line = px.line(trend, x='AY', y='ORAN', title="Zaman Serisi Başarı Trendi (%)", markers=True)
    g2.plotly_chart(fig_line, use_container_width=True)

    # --- TABLOLAR ---
    st.markdown("### 📋 Veri Detayları")
    tab1, tab2, tab3 = st.tabs(["Birim Performans", "Düşük Oranlılar", "Riskli ASM Listesi"])

    with tab1:
        st.dataframe(ozet.style.background_gradient(subset=['oran'], cmap='RdYlGn'), use_container_width=True)

    with tab2:
        low_units = ozet[ozet['oran'] < min_val]
        st.write(f"Alt sınır olan %{min_val} altında kalan {len(low_units)} birim bulundu.")
        st.table(low_units)

    with tab3:
        riskli_asmler = []
        for (ilce, asm), group in ozet.groupby(['ilce', 'asm']):
            kirmizi = group[group['oran'] < min_val]
            if not kirmizi.empty:
                riskli_asmler.append({"İlçe": ilce, "ASM": asm, "Kırmızı Birim Sayısı": len(kirmizi)})
        st.write(pd.DataFrame(riskli_asmler))

else:
    st.info("Lütfen analiz için bir Excel veya CSV dosyası yükleyin.")