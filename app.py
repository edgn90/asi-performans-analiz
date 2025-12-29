import streamlit as st
import pandas as pd
import plotly.express as px

# -----------------------------------------------------------------------------
# 1. SAYFA AYARLARI
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Aşı Performans Sistemi",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Aşı Takip & Performans Dashboard")
st.markdown("---")

# -----------------------------------------------------------------------------
# 2. YAN MENÜ VE DOSYA YÜKLEME
# -----------------------------------------------------------------------------
st.sidebar.header("1. Ayarlar & Veri")
uploaded_file = st.sidebar.file_uploader("Excel veya CSV Yükleyin", type=["xlsx", "csv"])

# -----------------------------------------------------------------------------
# 3. ANA MANTIK (Dosya yüklendiyse çalışır)
# -----------------------------------------------------------------------------
if uploaded_file:
    try:
        # --- A) Veri Okuma ---
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='cp1254')
        else:
            df = pd.read_excel(uploaded_file)
            
        # Sütun isimlerini temizle (boşlukları sil)
        df.columns = [c.strip() for c in df.columns]

        # Sütunları standart isimlere çevir
        rename_map = {
            'ILCE': 'ilce', 'asm': 'asm', 'BIRIM_ADI': 'birim',
            'ASI_SON_TARIH': 'hedef_tarih', 'ASI_YAP_TARIH': 'yapilan_tarih', 'ASI_DOZU': 'doz'
        }
        # Sadece dosyada var olan sütunları değiştir
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        # Tarih formatlama
        df['hedef_tarih'] = pd.to_datetime(df['hedef_tarih'], errors='coerce')
        df['yapilan_tarih'] = pd.to_datetime(df['yapilan_tarih'], errors='coerce')
        # Hedef tarihi olmayan (boş) satırları at
        df = df.dropna(subset=['hedef_tarih'])

        # --- B) Filtreler ---
        min_date = df['hedef_tarih'].min().date()
        max_date = df['hedef_tarih'].max().date()
        
        if pd.isnull(min_date) or pd.isnull(max_date):
             st.error("Dosyada geçerli tarih verisi bulunamadı.")
             st.stop()

        date_range = st.sidebar.date_input("Analiz Tarih Aralığı", [min_date, max_date])
        
        # Kullanıcı hedefleri
        target_val = st.sidebar.number_input("Hedef Başarı (Yeşil %)", value=90)
        min_val = st.sidebar.number_input("Alt Sınır (Kırmızı %)", value=70)

        # Tarih filtresini uygula
        if isinstance(date_range, list) and len(date_range) == 2:
            mask = (df['hedef_tarih'].dt.date >= date_range[0]) & (df['hedef_tarih'].dt.date <= date_range[1])
            df_filtered = df[mask].copy()
        else:
            df_filtered = df.copy()

        # Başarı durumu: Yapılan tarih doluysa 1, boşsa 0
        df_filtered['basari_durumu'] = df_filtered['yapilan_tarih'].notna().astype(int)

        # --- C) Hesaplamalar ---
        total_target = len(df_filtered)
        total_done = df_filtered['basari_durumu'].sum()
        
        # Birim bazlı özet tablo
        ozet = df_filtered.groupby(['ilce', 'asm', 'birim']).agg(
            toplam=('basari_durumu', 'count'),
            yapilan=('basari_durumu', 'sum')
        ).reset_index()
        
        # Oran hesabı
        ozet['oran'] = (ozet['yapilan'] / ozet['toplam'] * 100).round(2)
        
        # Riskli birim sayısı
        riskli_sayisi = len(ozet[ozet['oran'] < min_val])

        # --- D) KPI Kartları ---
        col1, col2, col3 = st.columns(3)
        col1.metric("🔵 Toplam Hedef", f"{total_target:,}".replace(",", "."))
        col2.metric("🟢 Toplam Yapılan", f"{total_done:,}".replace(",", "."))
        col3.metric("🔴 Riskli Birim", riskli_sayisi)

        st.markdown("---")

        # --- E) Grafikler ---
        g1, g2 = st.columns(2)

        # Grafik 1: İlçe Performansı
        ilce_ozet = ozet.groupby('ilce').agg({'toplam':'sum', 'yapilan':'sum'}).reset_index()
        ilce_ozet['oran'] = (ilce_ozet['yapilan'] / ilce_ozet['toplam'] * 100).round(2)
        
        # Renk koşulları
        ilce_ozet['Renk'] = ilce_ozet['oran'].apply(lambda x: 'Yeşil' if x >= target_val else ('Sarı' if x >= min_val else 'Kırmızı'))
        color_map = {'Yeşil':'#198754', 'Sarı':'#ffc107', 'Kırmızı':'#dc3545'}
        
        fig_bar = px.bar(ilce_ozet, x='ilce', y='oran', color='Renk', 
                         color_discrete_map=color_map,
                         title="İlçe Performans Oranları (%)",
                         text='oran')
        fig_bar.update_traces(textposition='outside')
        g1.plotly_chart(fig_bar, use_container_width=True)

        # Grafik 2: Trend
        df_filtered['AY'] = df_filtered['hedef_tarih'].dt.strftime('%Y-%m')
        trend = df_filtered.groupby('AY').agg({'basari_durumu':['sum','count']}).reset_index()
        trend.columns = ['AY', 'YAPILAN', 'HEDEF']
        trend['ORAN'] = (trend['YAPILAN'] / trend['HEDEF'] * 100).round(2)
        
        fig_line = px.line(trend, x='AY', y='ORAN', title="Zaman Serisi Başarı Trendi (%)", markers=True)
        g2.plotly_chart(fig_line, use_container_width=True)

        # --- F) Detaylı Tablolar ---
        st.subheader("📋 Detaylı Tablolar")
        tab1, tab2, tab3 = st.tabs(["📊 Birim Performans", "⚠️ Düşük Oranlılar", "🚨 Riskli ASM'ler"])

        with tab1:
            st.caption("Not: Tabloda başarı oranları doluluk çubuğu olarak gösterilmektedir.")
            # İŞTE HATA VERMEYEN YENİ YÖNTEM BURASI:
            st.dataframe(
                ozet,
                column_config={
                    "oran": st.column_config.ProgressColumn(
                        "Başarı Oranı",
                        format="%.2f%%",
                        min_value=0,
                        max_value=100,
                    ),
                    "toplam": st.column_config.NumberColumn("Hedef Nüfus"),
                    "yapilan": st.column_config.NumberColumn("Yapılan Aşı")
                },
                use_container_width=True,
                hide_index=True
            )

        with tab2:
            low_units = ozet[ozet['oran'] < min_val].sort_values(by='oran')
            st.write(f"Alt sınır olan **%{min_val}** altında kalan **{len(low_units)}** birim listeleniyor.")
            st.dataframe(
                low_units,
                column_config={
                    "oran": st.column_config.NumberColumn(
                        "Başarı Oranı (%)",
                        format="%.2f%%"
                    )
                },
                use_container_width=True,
                hide_index=True
            )

        with tab3:
            riskli_asmler = []
            for (ilce, asm), group in ozet.groupby(['ilce', 'asm']):
                kirmizi = group[group['oran'] < min_val]
                if not kirmizi.empty:
                    riskli_asmler.append({
                        "İlçe": ilce, 
                        "ASM": asm, 
                        "Kırmızı Birim Sayısı": len(kirmizi),
                        "Toplam Birim": len(group)
                    })
            
            if riskli_asmler:
                risk_df = pd.DataFrame(riskli_asmler).sort_values(by="Kırmızı Birim Sayısı", ascending=False)
                st.dataframe(risk_df, use_container_width=True, hide_index=True)
            else:
                st.success("Harika! Riskli kategorisine giren ASM bulunamadı.")

    except Exception as e:
        st.error(f"Bir hata oluştu: {e}")
        st.warning("Lütfen yüklediğiniz dosyanın formatının doğru olduğundan emin olun.")

else:
    st.info("⬅️ Lütfen sol menüden Excel veya CSV dosyanızı yükleyerek analizi başlatın.")
