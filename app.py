import streamlit as st
import pandas as pd
import plotly.express as px
import io
from fpdf import FPDF
import xlsxwriter

# -----------------------------------------------------------------------------
# YARDIMCI FONKSİYONLAR (İndirme İşlemleri İçin)
# -----------------------------------------------------------------------------

# 1. Excel İndirme Fonksiyonu
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        # Sütun genişliklerini ayarla
        worksheet = writer.sheets['Sheet1']
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, max_len)
    processed_data = output.getvalue()
    return processed_data

# 2. PDF İndirme Fonksiyonu (Logolu ve Türkçe Karakter Destekli)
def create_pdf(df, title):
    class PDF(FPDF):
        def header(self):
            # Logoyu ekle (x=10, y=8, w=33 - Oran korunur)
            # Logo dosyasının 'logo.png' adıyla proje klasöründe olduğunu varsayıyoruz.
            try:
                self.image('logo.png', 10, 8, 33)
            except:
                pass # Logo dosyası yoksa hata verme
            
            self.set_font('Arial', 'B', 12)
            # Başlığı ortala ve logodan sonra boşluk bırak
            self.cell(0, 10, clean_text(title), 0, 1, 'C')
            self.ln(15) # Logodan sonra boşluk

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

    # Türkçe karakterleri İngilizce karşılıklarına çevir
    def clean_text(text):
        if not isinstance(text, str): return str(text)
        replacements = {
            'ğ': 'g', 'Ğ': 'G', 'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I', 
            'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
        }
        for tr, eng in replacements.items():
            text = text.replace(tr, eng)
        return text.encode('latin-1', 'replace').decode('latin-1')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    # Tablo Başlıkları
    col_width = 190 / len(df.columns)
    pdf.set_font("Arial", 'B', 10)
    for col in df.columns:
        pdf.cell(col_width, 10, clean_text(col), 1, 0, 'C')
    pdf.ln()

    # Tablo Verileri
    pdf.set_font("Arial", size=9)
    for _, row in df.iterrows():
        for item in row:
            pdf.cell(col_width, 10, clean_text(str(item)), 1, 0, 'C')
        pdf.ln()

    return pdf.output(dest='S').encode('latin-1')

# -----------------------------------------------------------------------------
# SAYFA AYARLARI VE LOGO
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Aşı Performans Sistemi", layout="wide")

# Yan Menüye Logo Ekleme (Tüm sayfalarda görünür)
with st.sidebar:
    try:
        # Genişlik 150px olarak ayarlandı, responsive davranır.
        st.image("logo.png", width=150)
    except:
        st.warning("Logo dosyası (logo.png) bulunamadı.")
    
st.title("📊 Aşı Takip & Performans Dashboard")
st.markdown("---")

# -----------------------------------------------------------------------------
# YAN MENÜ VE VERİ YÜKLEME
# -----------------------------------------------------------------------------
st.sidebar.header("1. Veri Yükleme")
uploaded_file = st.sidebar.file_uploader("Excel veya CSV Yükleyin", type=["xlsx", "csv"])

if uploaded_file:
    try:
        # ... (Veri Okuma ve İşleme Kodları Aynı Kalacak) ...
        # (Kısalık için burayı atlıyorum, önceki kodun aynısı)
        
        # Veri Okuma
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='cp1254')
        else:
            df = pd.read_excel(uploaded_file)
            
        # Sütun Temizliği
        df.columns = [c.strip() for c in df.columns]
        rename_map = {
            'ILCE': 'ilce', 'asm': 'asm', 'BIRIM_ADI': 'birim',
            'ASI_SON_TARIH': 'hedef_tarih', 'ASI_YAP_TARIH': 'yapilan_tarih', 'ASI_DOZU': 'doz'
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        # Tarih İşlemleri
        df['hedef_tarih'] = pd.to_datetime(df['hedef_tarih'], errors='coerce')
        df['yapilan_tarih'] = pd.to_datetime(df['yapilan_tarih'], errors='coerce')
        df = df.dropna(subset=['hedef_tarih'])

        # --- FİLTRELEME ALANI (YAN MENÜ) ---
        st.sidebar.header("2. Filtreler")
        
        # 1. İlçe Filtresi
        ilce_list = ["Tümü"] + sorted(df['ilce'].astype(str).unique().tolist())
        selected_ilce = st.sidebar.selectbox("İlçe Seç", ilce_list)

        # Veriyi İlçe'ye göre daralt
        if selected_ilce != "Tümü":
            df_ilce_filtered = df[df['ilce'] == selected_ilce]
        else:
            df_ilce_filtered = df

        # 2. ASM Filtresi (Seçilen ilçeye göre dolar)
        asm_list = ["Tümü"] + sorted(df_ilce_filtered['asm'].astype(str).unique().tolist())
        selected_asm = st.sidebar.selectbox("ASM Seç", asm_list)

        # Veriyi ASM'ye göre daralt (Final Filtre Öncesi)
        if selected_asm != "Tümü":
            df_final_geo = df_ilce_filtered[df_ilce_filtered['asm'] == selected_asm]
        else:
            df_final_geo = df_ilce_filtered

        # 3. Tarih Filtresi
        min_date = df['hedef_tarih'].min().date()
        max_date = df['hedef_tarih'].max().date()
        date_range = st.sidebar.date_input("Tarih Aralığı", [min_date, max_date])

        # 4. Hedefler
        target_val = st.sidebar.number_input("Hedef Başarı (%)", value=90)
        min_val = st.sidebar.number_input("Alt Sınır (%)", value=70)

        # --- ANA FİLTRELEME ---
        # Hem Coğrafi (İlçe/ASM) hem Tarih filtresini uygula
        if isinstance(date_range, list) and len(date_range) == 2:
            mask = (df_final_geo['hedef_tarih'].dt.date >= date_range[0]) & (df_final_geo['hedef_tarih'].dt.date <= date_range[1])
            df_filtered = df_final_geo[mask].copy()
        else:
            df_filtered = df_final_geo.copy()

        # Başarı Durumu Hesapla
        df_filtered['basari_durumu'] = df_filtered['yapilan_tarih'].notna().astype(int)

        # --- KPI HESAPLAMALARI ---
        total_target = len(df_filtered)
        total_done = df_filtered['basari_durumu'].sum()
        
        ozet = df_filtered.groupby(['ilce', 'asm', 'birim']).agg(
            toplam=('basari_durumu', 'count'),
            yapilan=('basari_durumu', 'sum')
        ).reset_index()
        ozet['oran'] = (ozet['yapilan'] / ozet['toplam'] * 100).round(2)
        
        riskli_sayisi = len(ozet[ozet['oran'] < min_val])

        # KPI Gösterimi
        c1, c2, c3 = st.columns(3)
        c1.metric("🔵 Toplam Hedef", f"{total_target:,}".replace(",", "."))
        c2.metric("🟢 Toplam Yapılan", f"{total_done:,}".replace(",", "."))
        c3.metric("🔴 Riskli Birim", riskli_sayisi)
        
        # Filtre Bilgisi Göster
        st.caption(f"📍 Gösterilen Veri: **{selected_ilce}** / **{selected_asm}**")

        st.markdown("---")

        # --- GRAFİKLER ---
        g1, g2 = st.columns(2)

        # Grafik 1: İlçe/Birim Performansı
        # Eğer tek bir ilçe seçiliyse ASM bazlı göster, hepsi seçiliyse İlçe bazlı göster
        if selected_ilce == "Tümü":
            group_col = 'ilce'
            title_text = "İlçe Bazlı Performans"
        else:
            group_col = 'asm'
            title_text = f"{selected_ilce} - ASM Bazlı Performans"

        chart_data = df_filtered.groupby(group_col).agg(
            toplam=('basari_durumu', 'count'), 
            yapilan=('basari_durumu', 'sum')
        ).reset_index()
        chart_data['oran'] = (chart_data['yapilan'] / chart_data['toplam'] * 100).round(2)
        
        # Renklendirme
        chart_data['Renk'] = chart_data['oran'].apply(lambda x: 'Yeşil' if x >= target_val else ('Sarı' if x >= min_val else 'Kırmızı'))
        color_map = {'Yeşil':'#198754', 'Sarı':'#ffc107', 'Kırmızı':'#dc3545'}

        fig_bar = px.bar(chart_data, x=group_col, y='oran', color='Renk',
                         color_discrete_map=color_map, title=title_text, text='oran')
        fig_bar.update_traces(textposition='outside')
        g1.plotly_chart(fig_bar, use_container_width=True)

        # Grafik 2: Trend
        df_filtered['AY'] = df_filtered['hedef_tarih'].dt.strftime('%Y-%m')
        trend = df_filtered.groupby('AY').agg({'basari_durumu':['sum','count']}).reset_index()
        trend.columns = ['AY', 'YAPILAN', 'HEDEF']
        trend['ORAN'] = (trend['YAPILAN'] / trend['HEDEF'] * 100).round(2)
        fig_line = px.line(trend, x='AY', y='ORAN', title="Zaman Serisi Trendi (%)", markers=True)
        g2.plotly_chart(fig_line, use_container_width=True)

        # --- SEKMELER VE İNDİRME BUTONLARI ---
        st.subheader("📋 Detaylı Raporlar")
        tab1, tab2, tab3 = st.tabs(["📊 Birim Performans", "⚠️ Düşük Oranlılar", "🚨 Riskli ASM'ler"])

        # Sekme 1: Birim Performans
        with tab1:
            col_d1, col_d2 = st.columns([1, 1])
            with col_d1:
                st.download_button("📥 Excel İndir", data=to_excel(ozet), file_name='birim_performans.xlsx', mime='application/vnd.ms-excel')
            with col_d2:
                st.download_button("📄 PDF İndir", data=create_pdf(ozet, "Birim Performans Raporu"), file_name='birim_performans.pdf', mime='application/pdf')

            st.dataframe(
                ozet,
                column_config={
                    "oran": st.column_config.ProgressColumn("Başarı Oranı", format="%.2f%%", min_value=0, max_value=100),
                },
                use_container_width=True, hide_index=True
            )

        # Sekme 2: Düşük Oranlılar
        with tab2:
            low_units = ozet[ozet['oran'] < min_val].sort_values(by='oran')
            
            col_d1, col_d2 = st.columns([1, 1])
            with col_d1:
                st.download_button("📥 Excel İndir", data=to_excel(low_units), file_name='dusuk_oranlilar.xlsx', mime='application/vnd.ms-excel', key='dlow_xls')
            with col_d2:
                st.download_button("📄 PDF İndir", data=create_pdf(low_units, "Dusuk Oranli Birimler"), file_name='dusuk_oranlilar.pdf', mime='application/pdf', key='dlow_pdf')

            st.write(f"Alt sınır **%{min_val}** altındaki **{len(low_units)}** birim:")
            st.dataframe(
                low_units,
                column_config={"oran": st.column_config.NumberColumn("Başarı Oranı", format="%.2f%%")},
                use_container_width=True, hide_index=True
            )

        # Sekme 3: Riskli ASM'ler
        with tab3:
            riskli_asmler = []
            for (ilce, asm), group in ozet.groupby(['ilce', 'asm']):
                kirmizi = group[group['oran'] < min_val]
                if not kirmizi.empty:
                    riskli_asmler.append({"İlçe": ilce, "ASM": asm, "Kırmızı Birim": len(kirmizi), "Toplam": len(group)})
            
            risk_df = pd.DataFrame(riskli_asmler).sort_values(by="Kırmızı Birim", ascending=False) if riskli_asmler else pd.DataFrame()

            if not risk_df.empty:
                col_d1, col_d2 = st.columns([1, 1])
                with col_d1:
                    st.download_button("📥 Excel İndir", data=to_excel(risk_df), file_name='riskli_asmler.xlsx', mime='application/vnd.ms-excel', key='drisk_xls')
                with col_d2:
                    st.download_button("📄 PDF İndir", data=create_pdf(risk_df, "Riskli ASM Listesi"), file_name='riskli_asmler.pdf', mime='application/pdf', key='drisk_pdf')
                
                st.dataframe(risk_df, use_container_width=True, hide_index=True)
            else:
                st.success("Tebrikler! Riskli kategorisine giren ASM bulunamadı.")

    except Exception as e:
        st.error(f"Hata oluştu: {e}")
else:
    st.info("⬅️ Lütfen sol menüden Excel dosyanızı yükleyin.")
