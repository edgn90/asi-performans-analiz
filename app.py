import streamlit as st
import pandas as pd
import plotly.express as px
import io
from fpdf import FPDF
import xlsxwriter

# -----------------------------------------------------------------------------
# 1. YARDIMCI FONKSİYONLAR
# -----------------------------------------------------------------------------

def to_excel(df):
    """Veriyi Excel formatına çevirir."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        worksheet = writer.sheets['Sheet1']
        for i, col in enumerate(df.columns):
            # Sütun genişliğini içeriğe göre ayarla
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            # Excel'de çok uzun sütunları (Birim Detayları gibi) biraz sınırlayalım (max 50)
            if max_len > 50: max_len = 50
            worksheet.set_column(i, i, max_len)
    return output.getvalue()

def create_pdf(df, title):
    """
    Veriyi PDF formatına çevirir. Yatay Mod (Landscape).
    """
    class PDF(FPDF):
        def header(self):
            try:
                self.image('logo.png', 10, 8, 33)
            except:
                pass
            self.set_font('Arial', 'B', 14)
            self.cell(0, 10, clean_text(title), 0, 1, 'C')
            self.ln(12)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

    def clean_text(text):
        """Türkçe karakterleri Latin-1 uyumlu hale getirir."""
        if not isinstance(text, str): return str(text)
        # Emojileri temizle (PDF kütüphanesi hata vermesin diye)
        text = text.replace("🔴", "[!]").replace("🟢", "")
        
        replacements = {
            'ğ': 'g', 'Ğ': 'G', 'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I', 
            'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
        }
        for tr, eng in replacements.items():
            text = text.replace(tr, eng)
        return text.encode('latin-1', 'replace').decode('latin-1')

    # YATAY (Landscape) Modu Başlat ('L')
    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # --- AKILLI SÜTUN GENİŞLİĞİ ---
    available_width = 275 
    
    max_lens = []
    for col in df.columns:
        max_l = len(str(col))
        for val in df[col].head(50):
            val_l = len(str(val))
            if val_l > max_l: max_l = val_l
        max_lens.append(max_l)
    
    total_len = sum(max_lens)
    
    col_widths = []
    for l in max_lens:
        w = (l / total_len) * available_width
        if w < 20: w = 20 # Minimum genişliği biraz artırdık
        col_widths.append(w)
        
    final_total = sum(col_widths)
    if final_total > available_width:
        factor = available_width / final_total
        col_widths = [w * factor for w in col_widths]

    # --- BAŞLIKLAR ---
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(220, 230, 240)
    
    for i, col in enumerate(df.columns):
        pdf.cell(col_widths[i], 10, clean_text(col), 1, 0, 'C', fill=True)
    pdf.ln()

    # --- VERİLER ---
    pdf.set_font("Arial", size=8)
    
    for _, row in df.iterrows():
        # Sayfa sonu kontrolü
        if pdf.get_y() > 180:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 9)
            pdf.set_fill_color(220, 230, 240)
            for i, col in enumerate(df.columns):
                pdf.cell(col_widths[i], 10, clean_text(col), 1, 0, 'C', fill=True)
            pdf.ln()
            pdf.set_font("Arial", size=8)

        # Hücreleri yaz
        for i, item in enumerate(row):
            text = clean_text(str(item))
            # Metin çok uzunsa (Detay sütunu gibi) sığdırmaya çalış veya kırp
            max_char = int(col_widths[i] / 1.8) 
            if len(text) > max_char:
                text = text[:max_char-3] + "..."
                
            pdf.cell(col_widths[i], 8, text, 1, 0, 'C')
        pdf.ln()

    return pdf.output(dest='S').encode('latin-1')

# -----------------------------------------------------------------------------
# 2. SAYFA AYARLARI
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Aşı Performans Sistemi", layout="wide")

with st.sidebar:
    try:
        st.image("logo.png", width=150)
    except:
        pass 

st.title("📊 Aşı Takip & Performans Dashboard")
st.markdown("---")

# -----------------------------------------------------------------------------
# 3. VERİ YÜKLEME
# -----------------------------------------------------------------------------
st.sidebar.header("1. Veri Yükleme")
uploaded_file = st.sidebar.file_uploader("Excel veya CSV Yükleyin", type=["xlsx", "csv"])

# Session State
if 'filtered_df' not in st.session_state: st.session_state.filtered_df = pd.DataFrame()
if 'has_run' not in st.session_state: st.session_state.has_run = False

if uploaded_file:
    # Veriyi bir kez oku
    if 'raw_data' not in st.session_state or st.session_state.get('file_name') != uploaded_file.name:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, encoding='cp1254')
            else:
                df = pd.read_excel(uploaded_file)
            
            df.columns = [c.strip() for c in df.columns]
            rename_map = {'ILCE': 'ilce', 'asm': 'asm', 'BIRIM_ADI': 'birim', 
                          'ASI_SON_TARIH': 'hedef_tarih', 'ASI_YAP_TARIH': 'yapilan_tarih', 'ASI_DOZU': 'doz'}
            df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
            
            if 'doz' in df.columns:
                df['doz'] = pd.to_numeric(df['doz'], errors='coerce').fillna(0).astype(int)
            else:
                df['doz'] = 1
            
            df['hedef_tarih'] = pd.to_datetime(df['hedef_tarih'], errors='coerce')
            df['yapilan_tarih'] = pd.to_datetime(df['yapilan_tarih'], errors='coerce')
            df = df.dropna(subset=['hedef_tarih'])
            
            st.session_state.raw_data = df
            st.session_state.file_name = uploaded_file.name
            
        except Exception as e:
            st.error(f"Dosya okuma hatası: {e}")
            st.stop()

    df = st.session_state.raw_data

    # -----------------------------------------------------------------------------
    # 4. FİLTRELEME FORMU
    # -----------------------------------------------------------------------------
    st.sidebar.header("2. Filtre Ayarları")
    
    with st.sidebar.form(key='filter_form'):
        ilce_list = ["Tümü"] + sorted(df['ilce'].astype(str).unique().tolist())
        selected_ilce = st.selectbox("İlçe Seç", ilce_list)
        
        if selected_ilce != "Tümü": asm_source = df[df['ilce'] == selected_ilce]
        else: asm_source = df
        
        asm_list = ["Tümü"] + sorted(asm_source['asm'].astype(str).unique().tolist())
        selected_asm = st.selectbox("ASM Seç", asm_list)

        dose_options = list(range(1, 10))
        selected_doses = st.multiselect("Aşı Dozu Seçin", options=dose_options, default=[])

        min_date = df['hedef_tarih'].min().date()
        max_date = df['hedef_tarih'].max().date()
        date_range = st.date_input("Tarih Aralığı", [min_date, max_date])

        target_val = st.number_input("Hedef Başarı (%)", value=90)
        min_val = st.number_input("Alt Sınır (%)", value=70)
        
        st.markdown("---")
        submit_button = st.form_submit_button(label='🚀 Filtreleri Uygula')

    # -----------------------------------------------------------------------------
    # 5. ANALİZ İŞLEMİ
    # -----------------------------------------------------------------------------
    if submit_button:
        with st.spinner('Veriler analiz ediliyor...'):
            temp_df = df.copy()
            
            if selected_ilce != "Tümü": temp_df = temp_df[temp_df['ilce'] == selected_ilce]
            if selected_asm != "Tümü": temp_df = temp_df[temp_df['asm'] == selected_asm]
            if selected_doses: temp_df = temp_df[temp_df['doz'].isin(selected_doses)]
            if isinstance(date_range, list) and len(date_range) == 2:
                mask = (temp_df['hedef_tarih'].dt.date >= date_range[0]) & (temp_df['hedef_tarih'].dt.date <= date_range[1])
                temp_df = temp_df[mask]
                
            temp_df['basari_durumu'] = temp_df['yapilan_tarih'].notna().astype(int)
            
            st.session_state.filtered_df = temp_df
            st.session_state.filter_info = f"{selected_ilce} / {selected_asm}"
            st.session_state.target_val = target_val
            st.session_state.min_val = min_val
            st.session_state.has_run = True

    # -----------------------------------------------------------------------------
    # 6. SONUÇLAR
    # -----------------------------------------------------------------------------
    if st.session_state.has_run:
        df_res = st.session_state.filtered_df
        t_val = st.session_state.target_val
        m_val = st.session_state.min_val
        
        if df_res.empty:
            st.warning("Seçilen kriterlere uygun veri bulunamadı.")
        else:
            # Temel Hesaplama
            ozet = df_res.groupby(['ilce', 'asm', 'birim']).agg(
                toplam=('basari_durumu', 'count'),
                yapilan=('basari_durumu', 'sum')
            ).reset_index()
            
            ozet['oran'] = 0.0
            if not ozet.empty:
                ozet['oran'] = (ozet['yapilan'] / ozet['toplam'] * 100).round(2)
            
            # Riskli ASM Hesaplama Mantığı (GÜNCELLENDİ)
            riskli_asm_listesi = []
            
            # Her ASM'yi kendi içinde değerlendir
            for (ilce, asm), grup in ozet.groupby(['ilce', 'asm']):
                # Kırmızı (Riskli) olan birimleri bul
                kirmizi_birimler = grup[grup['oran'] < m_val]
                
                # Eğer en az 1 tane kırmızı varsa, bu ASM'yi listeye al
                if not kirmizi_birimler.empty:
                    # Detay Metni Oluşturma: "Ahmet (%60) 🔴, Mehmet (%95) 🟢"
                    birim_detaylari = []
                    for _, row in grup.iterrows():
                        durum_ikon = "🔴 (RISKLI)" if row['oran'] < m_val else "🟢"
                        # PDF çıktısında emoji sorun olabilir diye metin tabanlı da tutuyoruz
                        detay = f"{row['birim']}: %{row['oran']} {durum_ikon}"
                        birim_detaylari.append(detay)
                    
                    riskli_asm_listesi.append({
                        "İlçe": ilce,
                        "ASM Adı": asm,
                        "Hedef Başarı": f"%{t_val}",
                        "Alt Sınır": f"%{m_val}",
                        "Birim Detayları": " | ".join(birim_detaylari)
                    })
            
            riskli_sayisi = len(riskli_asm_listesi)

            # KPI
            total_target = len(df_res)
            total_done = df_res['basari_durumu'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("🔵 Toplam Hedef", f"{total_target:,}".replace(",", "."))
            c2.metric("🟢 Toplam Yapılan", f"{total_done:,}".replace(",", "."))
            c3.metric("🔴 Riskli ASM Sayısı", riskli_sayisi)
            st.caption(f"📍 Filtre: {st.session_state.filter_info}")
            st.markdown("---")

            # Grafikler
            g1, g2 = st.columns(2)
            group_col = 'ilce' if st.session_state.filter_info.startswith("Tümü") else 'asm'
            chart_data = df_res.groupby(group_col).agg(toplam=('basari_durumu','count'), yapilan=('basari_durumu','sum')).reset_index()
            if not chart_data.empty:
                chart_data['oran'] = (chart_data['yapilan'] / chart_data['toplam'] * 100).round(2)
                chart_data['Renk'] = chart_data['oran'].apply(lambda x: 'Yeşil' if x >= t_val else ('Sarı' if x >= m_val else 'Kırmızı'))
                fig_bar = px.bar(chart_data, x=group_col, y='oran', color='Renk', color_discrete_map={'Yeşil':'#198754', 'Sarı':'#ffc107', 'Kırmızı':'#dc3545'}, text='oran', title="Performans Grafiği")
                fig_bar.update_traces(textposition='outside')
                g1.plotly_chart(fig_bar, use_container_width=True)

            trend = df_res.copy()
            trend['AY'] = trend['hedef_tarih'].dt.strftime('%Y-%m')
            trend_data = trend.groupby('AY').agg({'basari_durumu':['sum','count']}).reset_index()
            trend_data.columns = ['AY', 'YAPILAN', 'HEDEF']
            trend_data['ORAN'] = (trend_data['YAPILAN'] / trend_data['HEDEF'] * 100).round(2)
            fig_line = px.line(trend_data, x='AY', y='ORAN', title="Zaman Serisi Trendi", markers=True)
            g2.plotly_chart(fig_line, use_container_width=True)

            # --- SEKMELER ---
            st.subheader("📋 Detaylı Raporlar")
            # Sekme isimleri güncellendi
            tab1, tab2, tab3 = st.tabs(["📊 Birim Performans", "⚠️ Düşük Oranlılar", "🚨 Riskli birim olan ASM Listesi"])

            with tab1:
                c_d1, c_d2 = st.columns([1,1])
                c_d1.download_button("📥 Excel İndir", data=to_excel(ozet), file_name='birim_perf.xlsx')
                c_d2.download_button("📄 PDF İndir", data=create_pdf(ozet, "Birim Performans"), file_name='birim_perf.pdf')
                st.dataframe(ozet, column_config={"oran": st.column_config.ProgressColumn("Başarı Oranı", format="%.2f%%", min_value=0, max_value=100)}, use_container_width=True, hide_index=True)

            with tab2:
                low_units = ozet[ozet['oran'] < m_val].sort_values(by='oran')
                c_d1, c_d2 = st.columns([1,1])
                c_d1.download_button("📥 Excel İndir", data=to_excel(low_units), file_name='dusuk_oran.xlsx', key='dl1')
                c_d2.download_button("📄 PDF İndir", data=create_pdf(low_units, "Dusuk Oranli Birimler"), file_name='dusuk_oran.pdf', key='dp1')
                st.dataframe(low_units, column_config={"oran": st.column_config.NumberColumn("Başarı Oranı", format="%.2f%%")}, use_container_width=True, hide_index=True)

            with tab3:
                # GÜNCELLENMİŞ RİSKLİ ASM TABLOSU
                rdf = pd.DataFrame(riskli_asm_listesi)
                
                if not rdf.empty:
                    c_d1, c_d2 = st.columns([1,1])
                    c_d1.download_button("📥 Excel İndir", data=to_excel(rdf), file_name='riskli_asm_listesi.xlsx', key='dl2')
                    c_d2.download_button("📄 PDF İndir", data=create_pdf(rdf, "Riskli Birim Olan ASM Listesi"), file_name='riskli_asm_listesi.pdf', key='dp2')
                    
                    # Tabloyu göster
                    st.dataframe(rdf, use_container_width=True, hide_index=True)
                else:
                    st.success("Tebrikler! Kriterlere uyan Riskli ASM bulunamadı.")
    else:
        st.info("👈 Analizi başlatmak için soldaki menüden **'Filtreleri Uygula'** butonuna basınız.")
else:
    st.info("⬅️ Lütfen sol menüden Excel dosyanızı yükleyerek başlayın.")
