import streamlit as st
import pandas as pd
import plotly.express as px
import io
from fpdf import FPDF
import xlsxwriter

# -----------------------------------------------------------------------------
# YARDIMCI FONKSİYONLAR
# -----------------------------------------------------------------------------
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        worksheet = writer.sheets['Sheet1']
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, max_len)
    return output.getvalue()

def create_pdf(df, title):
    class PDF(FPDF):
        def header(self):
            try: self.image('logo.png', 10, 8, 33)
            except: pass
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, clean_text(title), 0, 1, 'C')
            self.ln(15)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

    def clean_text(text):
        if not isinstance(text, str): return str(text)
        replacements = {'ğ':'g','Ğ':'G','ş':'s','Ş':'S','ı':'i','İ':'I','ü':'u','Ü':'U','ö':'o','Ö':'O','ç':'c','Ç':'C'}
        for tr, eng in replacements.items(): text = text.replace(tr, eng)
        return text.encode('latin-1', 'replace').decode('latin-1')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    col_width = 190 / (len(df.columns) if len(df.columns) > 0 else 1)
    
    pdf.set_font("Arial", 'B', 10)
    for col in df.columns: pdf.cell(col_width, 10, clean_text(col), 1, 0, 'C')
    pdf.ln()
    
    pdf.set_font("Arial", size=9)
    for _, row in df.iterrows():
        for item in row: pdf.cell(col_width, 10, clean_text(str(item)), 1, 0, 'C')
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# -----------------------------------------------------------------------------
# SAYFA AYARLARI
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Aşı Performans Sistemi", layout="wide")

with st.sidebar:
    try: st.image("logo.png", width=150)
    except: pass

st.title("📊 Aşı Takip & Performans Dashboard")
st.markdown("---")

# -----------------------------------------------------------------------------
# 1. VERİ YÜKLEME (Form Dışında)
# -----------------------------------------------------------------------------
st.sidebar.header("1. Veri Yükleme")
uploaded_file = st.sidebar.file_uploader("Excel veya CSV Yükleyin", type=["xlsx", "csv"])

# Global değişkenler (Analiz sonuçları için)
df_filtered = pd.DataFrame()
run_analysis = False

if uploaded_file:
    # --- Veriyi Bir Kere Oku ve Session State'e At ---
    if 'raw_data' not in st.session_state or st.session_state.uploaded_file_name != uploaded_file.name:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, encoding='cp1254')
            else:
                df = pd.read_excel(uploaded_file)
            
            # Temizlik
            df.columns = [c.strip() for c in df.columns]
            rename_map = {'ILCE': 'ilce', 'asm': 'asm', 'BIRIM_ADI': 'birim', 'ASI_SON_TARIH': 'hedef_tarih', 'ASI_YAP_TARIH': 'yapilan_tarih', 'ASI_DOZU': 'doz'}
            df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
            
            if 'doz' in df.columns: df['doz'] = pd.to_numeric(df['doz'], errors='coerce').fillna(0).astype(int)
            else: df['doz'] = 1
            
            df['hedef_tarih'] = pd.to_datetime(df['hedef_tarih'], errors='coerce')
            df['yapilan_tarih'] = pd.to_datetime(df['yapilan_tarih'], errors='coerce')
            df = df.dropna(subset=['hedef_tarih'])
            
            st.session_state.raw_data = df
            st.session_state.uploaded_file_name = uploaded_file.name
            
        except Exception as e:
            st.error(f"Dosya okuma hatası: {e}")
            st.stop()

    df = st.session_state.raw_data

    # -----------------------------------------------------------------------------
    # 2. FİLTRELEME FORMU (Yan Menü)
    # -----------------------------------------------------------------------------
    st.sidebar.header("2. Filtre Ayarları")
    
    # --- FORM BAŞLANGICI ---
    with st.sidebar.form(key='filter_form'):
        
        # A. İlçe/ASM Seçimi
        ilce_list = ["Tümü"] + sorted(df['ilce'].astype(str).unique().tolist())
        selected_ilce = st.selectbox("İlçe Seç", ilce_list)
        
        # ASM listesini seçilen ilçeye göre dinamik daraltmak form içinde zordur.
        # Bu yüzden form içinde tüm ASM'leri gösterip mantıksal filtreleme yapacağız
        # veya basitlik adına kullanıcıya tüm listeyi sunacağız.
        # Kullanıcı deneyimi için önce tüm ASM'leri alıyoruz:
        if selected_ilce != "Tümü":
            current_asms = sorted(df[df['ilce'] == selected_ilce]['asm'].astype(str).unique().tolist())
        else:
            current_asms = sorted(df['asm'].astype(str).unique().tolist())
            
        asm_list = ["Tümü"] + current_asms
        selected_asm = st.selectbox("ASM Seç", asm_list)

        # B. Doz Seçimi
        dose_options = list(range(1, 10))
        selected_doses = st.multiselect("Aşı Dozu Seçin", options=dose_options, default=[], help="Boş bırakırsanız hepsi seçilir.")

        # C. Tarih Seçimi
        min_date = df['hedef_tarih'].min().date()
        max_date = df['hedef_tarih'].max().date()
        date_range = st.date_input("Tarih Aralığı", [min_date, max_date])

        # D. Hedefler
        target_val = st.number_input("Hedef Başarı (%)", value=90)
        min_val = st.number_input("Alt Sınır (%)", value=70)
        
        st.markdown("---")
        # --- BUTON ---
        submit_button = st.form_submit_button(label='🚀 Filtreleri Uygula')

    # -----------------------------------------------------------------------------
    # 3. ANALİZ MOTORU (Sadece Butona Basılınca veya İlk Yüklemede Çalışır)
    # -----------------------------------------------------------------------------
    
    # Sayfa ilk açıldığında boş kalmasın diye 'submit_button'a basılmış gibi davranabiliriz
    # Veya kullanıcı butona basana kadar beklemesini isteyebiliriz.
    # Burada kullanıcı butona basana kadar veya session state'de sonuç yoksa bekletiyoruz.
    
    if submit_button:
        with st.spinner('Veriler analiz ediliyor, lütfen bekleyin...'):
            # 1. Coğrafi Filtre
            temp_df = df.copy()
            if selected_ilce != "Tümü":
                temp_df = temp_df[temp_df['ilce'] == selected_ilce]
            if selected_asm != "Tümü":
                temp_df = temp_df[temp_df['asm'] == selected_asm]
            
            # 2. Doz Filtre
            if selected_doses:
                temp_df = temp_df[temp_df['doz'].isin(selected_doses)]
                
            # 3. Tarih Filtre
            if isinstance(date_range, list) and len(date_range) == 2:
                mask = (temp_df['hedef_tarih'].dt.date >= date_range[0]) & (temp_df['hedef_tarih'].dt.date <= date_range[1])
                temp_df = temp_df[mask]
            
            # 4. Hesaplamalar
            temp_df['basari_durumu'] = temp_df['yapilan_tarih'].notna().astype(int)
            
            # Sonuçları Session State'e kaydet (Ekran yenilendiğinde kaybolmasın)
            st.session_state.filtered_df = temp_df
            st.session_state.filter_info = f"{selected_ilce} / {selected_asm}"
            st.session_state.target_val = target_val
            st.session_state.min_val = min_val
            st.session_state.has_run = True

    # -----------------------------------------------------------------------------
    # 4. GÖSTERİM KATMANI
    # -----------------------------------------------------------------------------
    if 'has_run' in st.session_state and st.session_state.has_run:
        df_res = st.session_state.filtered_df
        t_val = st.session_state.target_val
        m_val = st.session_state.min_val

        if df_res.empty:
            st.warning("Seçilen kriterlere uygun veri bulunamadı.")
        else:
            # KPI
            total_target = len(df_res)
            total_done = df_res['basari_durumu'].sum()
            
            ozet = df_res.groupby(['ilce', 'asm', 'birim']).agg(
                toplam=('basari_durumu', 'count'),
                yapilan=('basari_durumu', 'sum')
            ).reset_index()
            ozet['oran'] = 0.0
            if not ozet.empty:
                ozet['oran'] = (ozet['yapilan'] / ozet['toplam'] * 100).round(2)
            
            riskli_sayisi = len(ozet[ozet['oran'] < m_val])

            c1, c2, c3 = st.columns(3)
            c1.metric("🔵 Toplam Hedef", f"{total_target:,}".replace(",", "."))
            c2.metric("🟢 Toplam Yapılan", f"{total_done:,}".replace(",", "."))
            c3.metric("🔴 Riskli Birim", riskli_sayisi)
            st.caption(f"📍 Filtre: {st.session_state.filter_info}")
            st.markdown("---")

            # Grafikler
            g1, g2 = st.columns(2)
            
            # Bar Grafik
            group_col = 'ilce' if st.session_state.filter_info.startswith("Tümü") else 'asm'
            chart_data = df_res.groupby(group_col).agg(toplam=('basari_durumu','count'), yapilan=('basari_durumu','sum')).reset_index()
            if not chart_data.empty:
                chart_data['oran'] = (chart_data['yapilan'] / chart_data['toplam'] * 100).round(2)
                chart_data['Renk'] = chart_data['oran'].apply(lambda x: 'Yeşil' if x >= t_val else ('Sarı' if x >= m_val else 'Kırmızı'))
                fig_bar = px.bar(chart_data, x=group_col, y='oran', color='Renk', color_discrete_map={'Yeşil':'#198754', 'Sarı':'#ffc107', 'Kırmızı':'#dc3545'}, text='oran', title="Performans Grafiği")
                fig_bar.update_traces(textposition='outside')
                g1.plotly_chart(fig_bar, use_container_width=True)

            # Trend Grafik
            df_res['AY'] = df_res['hedef_tarih'].dt.strftime('%Y-%m')
            trend = df_res.groupby('AY').agg({'basari_durumu':['sum','count']}).reset_index()
            trend.columns = ['AY', 'YAPILAN', 'HEDEF']
            trend['ORAN'] = (trend['YAPILAN'] / trend['HEDEF'] * 100).round(2)
            fig_line = px.line(trend, x='AY', y='ORAN', title="Zaman Serisi", markers=True)
            g2.plotly_chart(fig_line, use_container_width=True)

            # Sekmeler
            st.subheader("📋 Detaylı Raporlar")
            tab1, tab2, tab3 = st.tabs(["📊 Birim Performans", "⚠️ Düşük Oranlılar", "🚨 Riskli ASM'ler"])

            with tab1:
                c_d1, c_d2 = st.columns([1,1])
                c_d1.download_button("📥 Excel", data=to_excel(ozet), file_name='birim_perf.xlsx')
                c_d2.download_button("📄 PDF", data=create_pdf(ozet, "Birim Performans"), file_name='birim_perf.pdf')
                st.dataframe(ozet, column_config={"oran": st.column_config.ProgressColumn("Başarı", format="%.2f%%", min_value=0, max_value=100)}, use_container_width=True, hide_index=True)

            with tab2:
                low_units = ozet[ozet['oran'] < m_val].sort_values(by='oran')
                c_d1, c_d2 = st.columns([1,1])
                c_d1.download_button("📥 Excel", data=to_excel(low_units), file_name='dusuk_oran.xlsx', key='dl1')
                c_d2.download_button("📄 PDF", data=create_pdf(low_units, "Dusuk Oranlar"), file_name='dusuk_oran.pdf', key='dp1')
                st.dataframe(low_units, column_config={"oran": st.column_config.NumberColumn("Başarı", format="%.2f%%")}, use_container_width=True, hide_index=True)

            with tab3:
                riskli = []
                for (i, a), g in ozet.groupby(['ilce', 'asm']):
                    k = g[g['oran'] < m_val]
                    if not k.empty: riskli.append({"İlçe": i, "ASM": a, "Riskli Birim": len(k), "Toplam": len(g)})
                rdf = pd.DataFrame(riskli).sort_values(by="Riskli Birim", ascending=False) if riskli else pd.DataFrame()
                
                if not rdf.empty:
                    c_d1, c_d2 = st.columns([1,1])
                    c_d1.download_button("📥 Excel", data=to_excel(rdf), file_name='riskli_asm.xlsx', key='dl2')
                    c_d2.download_button("📄 PDF", data=create_pdf(rdf, "Riskli ASM"), file_name='riskli_asm.pdf', key='dp2')
                    st.dataframe(rdf, use_container_width=True, hide_index=True)
                else:
                    st.success("Riskli ASM yok.")
    else:
        st.info("👈 Analizi başlatmak için soldaki menüden 'Filtreleri Uygula' butonuna basınız.")

else:
    st.info("⬅️ Lütfen sol menüden Excel dosyanızı yükleyin.")
