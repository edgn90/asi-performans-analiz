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
            try:
                # Sütun genişliğini içeriğe göre ayarla
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                if max_len > 50: max_len = 50
                worksheet.set_column(i, i, max_len)
            except:
                worksheet.set_column(i, i, 15)
    return output.getvalue()

def create_pdf(df, title, info):
    """
    Veriyi PDF formatına çevirir.
    - Yatay Mod (Landscape)
    - Dinamik Header
    - Akıllı Sütun Genişliği
    """
    class PDF(FPDF):
        def header(self):
            # --- LOGO ---
            try:
                self.image('logo.png', 10, 8, 33)
            except:
                pass
            
            # --- BAŞLIK ---
            self.set_y(10)
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, clean_text(title), 0, 1, 'C')
            
            # --- HEADER BİLGİLERİ ---
            self.set_font('Arial', '', 9)
            self.set_text_color(80, 80, 80)
            
            date_str = f"Tarih: {info.get('tarih_araligi', '-')}"
            ilce_txt = info.get('ilce', '-') if info.get('ilce') != "Tümü" else "Tum Ilceler"
            asm_txt = info.get('asm', '-') if info.get('asm') != "Tümü" else "Tum ASM'ler"
            doz_txt = info.get('doz', '-') if info.get('doz') else "Tum Dozlar"
            
            filter_str = f"Konum: {ilce_txt} / {asm_txt} | Asi: {doz_txt}"
            threshold_str = f"Hedef: %{info.get('hedef', 90)} | Alt Sinir: %{info.get('alt_sinir', 70)}"

            self.ln(2)
            self.cell(0, 5, clean_text(date_str), 0, 1, 'R')
            self.cell(0, 5, clean_text(filter_str), 0, 1, 'R')
            self.set_font('Arial', 'B', 9)
            self.set_text_color(0, 0, 0)
            self.cell(0, 5, clean_text(threshold_str), 0, 1, 'R')
            
            self.ln(5)
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y(), 287, self.get_y())
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

    def clean_text(text):
        """Türkçe karakter düzeltme."""
        if not isinstance(text, str): return str(text)
        text = text.replace("🔴", "!").replace("🟢", "").replace("🟠", "")
        replacements = {
            'ğ': 'g', 'Ğ': 'G', 'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I', 
            'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
        }
        for tr, eng in replacements.items():
            text = text.replace(tr, eng)
        return text.encode('latin-1', 'replace').decode('latin-1')

    # PDF Ayarları
    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Sütun Genişliği Hesapla
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
    if total_len > 0:
        for l in max_lens:
            w = (l / total_len) * available_width
            if w < 20: w = 20
            col_widths.append(w)
    else:
        col_widths = [available_width] # Eğer sütun yoksa

    # Genişlik Normalize Et
    final_total = sum(col_widths)
    if final_total > available_width:
        factor = available_width / final_total
        col_widths = [w * factor for w in col_widths]

    # Başlıklar
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(220, 230, 240)
    pdf.set_text_color(0, 0, 0)
    for i, col in enumerate(df.columns):
        pdf.cell(col_widths[i], 10, clean_text(col), 1, 0, 'C', fill=True)
    pdf.ln()

    # Veriler
    pdf.set_font("Arial", size=8)
    for _, row in df.iterrows():
        if pdf.get_y() > 175:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 9)
            pdf.set_fill_color(220, 230, 240)
            for i, col in enumerate(df.columns):
                pdf.cell(col_widths[i], 10, clean_text(col), 1, 0, 'C', fill=True)
            pdf.ln()
            pdf.set_font("Arial", size=8)

        for i, item in enumerate(row):
            text = clean_text(str(item))
            max_char = int(col_widths[i] / 1.8) 
            if len(text) > max_char: text = text[:max_char-2] + ".."
            pdf.cell(col_widths[i], 8, text, 1, 0, 'C')
        pdf.ln()

    return pdf.output(dest='S').encode('latin-1')

# -----------------------------------------------------------------------------
# 2. SAYFA AYARLARI
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Aşı Performans Sistemi", layout="wide")

with st.sidebar:
    try: st.image("logo.png", width=150)
    except: pass 

st.title("📊 Aşı Takip & Performans Dashboard")
st.markdown("---")

# -----------------------------------------------------------------------------
# 3. VERİ YÜKLEME VE İŞLEME
# -----------------------------------------------------------------------------
st.sidebar.header("1. Veri Yükleme")

# Key parametresi eklenerek dosyanın kaybolması önlendi
uploaded_file = st.sidebar.file_uploader("Excel veya CSV Yükleyin", type=["xlsx", "csv"], key="loader_main")

# Session State
if 'filtered_df' not in st.session_state: st.session_state.filtered_df = pd.DataFrame()
if 'has_run' not in st.session_state: st.session_state.has_run = False

if uploaded_file:
    # Dosya değişti mi kontrolü
    if 'raw_data' not in st.session_state or st.session_state.get('file_name') != uploaded_file.name:
        try:
            # Dosya Okuma
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
            
            # Doz Sayısallaştırma
            if 'doz' in df.columns:
                df['doz'] = pd.to_numeric(df['doz'], errors='coerce').fillna(0).astype(int)
            else:
                df['doz'] = 1
            
            # --- KRİTİK TARİH DÜZELTMESİ ---
            # 1. Otomatik çevirmeyi dene
            df['hedef_tarih'] = pd.to_datetime(df['hedef_tarih'], errors='coerce')
            df['yapilan_tarih'] = pd.to_datetime(df['yapilan_tarih'], errors='coerce')
            
            # 2. Eğer otomatik çevirme başarısız olduysa ve hala nesne tipindeyse (CSV kaynaklı sorunlar için)
            # Özellikle YYYY-MM-DD formatını zorla tanıtmaya çalışabiliriz, ancak 'coerce' genelde çözer.
            # Boş tarihleri temizle (Sadece hedef tarihi olmayanlar)
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
        # İlçe
        ilce_list = ["Tümü"] + sorted(df['ilce'].astype(str).unique().tolist())
        selected_ilce = st.selectbox("İlçe Seç", ilce_list)
        
        # ASM (Kaynak filtreli)
        if selected_ilce != "Tümü":
            asm_source = df[df['ilce'] == selected_ilce]
        else:
            asm_source = df
        asm_list = ["Tümü"] + sorted(asm_source['asm'].astype(str).unique().tolist())
        selected_asm = st.selectbox("ASM Seç", asm_list)

        # Doz
        dose_options = list(range(1, 10))
        selected_doses = st.multiselect("Aşı Dozu Seçin", options=dose_options, default=[])

        # Tarih Aralığı (En kritik kısım)
        if not df.empty:
            min_date = df['hedef_tarih'].min().date()
            max_date = df['hedef_tarih'].max().date()
            date_range = st.date_input("Tarih Aralığı", [min_date, max_date])
        else:
            st.error("Veri boş veya tarihler okunamadı.")
            st.stop()

        # Eşik Değerler
        target_val = st.number_input("Hedef Başarı (%)", value=90)
        min_val = st.number_input("Alt Sınır (%)", value=70)
        
        st.markdown("---")
        submit_button = st.form_submit_button(label='🚀 Filtreleri Uygula')

    # -----------------------------------------------------------------------------
    # 5. ANALİZ MOTORU
    # -----------------------------------------------------------------------------
    if submit_button:
        with st.spinner('Veriler analiz ediliyor...'):
            temp_df = df.copy()
            
            # Filtreler
            if selected_ilce != "Tümü":
                temp_df = temp_df[temp_df['ilce'] == selected_ilce]
            if selected_asm != "Tümü":
                temp_df = temp_df[temp_df['asm'] == selected_asm]
            if selected_doses:
                temp_df = temp_df[temp_df['doz'].isin(selected_doses)]
            
            # Tarih Filtresi (ASI_SON_TARIH'e göre)
            if isinstance(date_range, list) and len(date_range) == 2:
                mask = (temp_df['hedef_tarih'].dt.date >= date_range[0]) & (temp_df['hedef_tarih'].dt.date <= date_range[1])
                temp_df = temp_df[mask]
            
            # Başarı Hesaplama (Yapılan tarih varsa 1, yoksa 0)
            temp_df['basari_durumu'] = temp_df['yapilan_tarih'].notna().astype(int)
            
            # Metadata Kaydı (PDF için)
            date_str = "Tumu"
            if isinstance(date_range, list) and len(date_range) == 2:
                date_str = f"{date_range[0].strftime('%d.%m.%Y')} - {date_range[1].strftime('%d.%m.%Y')}"
            
            dose_str = ", ".join(map(str, selected_doses)) if selected_doses else ""
            
            st.session_state.filtered_df = temp_df
            st.session_state.filter_info = f"{selected_ilce} / {selected_asm}"
            st.session_state.target_val = target_val
            st.session_state.min_val = min_val
            
            st.session_state.report_meta = {
                "tarih_araligi": date_str,
                "ilce": selected_ilce,
                "asm": selected_asm,
                "doz": dose_str,
                "hedef": target_val,
                "alt_sinir": min_val
            }
            
            st.session_state.has_run = True

    # -----------------------------------------------------------------------------
    # 6. SONUÇ EKRANI
    # -----------------------------------------------------------------------------
    if st.session_state.has_run:
        df_res = st.session_state.filtered_df
        t_val = st.session_state.target_val
        m_val = st.session_state.min_val
        meta = st.session_state.report_meta
        
        if df_res.empty:
            st.warning("⚠️ Seçilen kriterlere (özellikle tarih aralığına) uygun veri bulunamadı.")
            st.info("İpucu: 'Tarih Aralığı' kısmında aşıların 'Son Tarihi'ne göre seçim yaptığınızdan emin olun.")
        else:
            # Özet Tablo
            ozet = df_res.groupby(['ilce', 'asm', 'birim']).agg(
                toplam=('basari_durumu', 'count'),
                yapilan=('basari_durumu', 'sum')
            ).reset_index()
            
            ozet['oran'] = 0.0
            if not ozet.empty:
                ozet['oran'] = (ozet['yapilan'] / ozet['toplam'] * 100).round(2)
            
            # KPI 1: Düşük Oranlı Birim Sayısı
            dusuk_oranli_birim_sayisi = len(ozet[ozet['oran'] < m_val])
            
            # KPI 2: Riskli ASM Listesi
            riskli_asm_listesi = []
            for (ilce, asm), grup in ozet.groupby(['ilce', 'asm']):
                kirmizi_sayisi = len(grup[grup['oran'] < m_val])
                if kirmizi_sayisi > 0:
                    yesil_sayisi = len(grup[grup['oran'] >= t_val])
                    sari_sayisi = len(grup) - kirmizi_sayisi - yesil_sayisi
                    riskli_asm_listesi.append({
                        "İlçe": ilce, "ASM Adı": asm,
                        "Kırmızı Birim": kirmizi_sayisi,
                        "Sarı Birim": sari_sayisi,
                        "Yeşil Birim": yesil_sayisi,
                        "Toplam Birim": len(grup)
                    })
            
            riskli_asm_sayisi = len(riskli_asm_listesi)
            total_target = len(df_res)
            total_done = df_res['basari_durumu'].sum()
            
            # --- KPI Kartları ---
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🔵 Toplam Hedef", f"{total_target:,}".replace(",", "."))
            c2.metric("🟢 Toplam Yapılan", f"{total_done:,}".replace(",", "."))
            c3.metric("🟠 Düşük Oranlı Birim", f"{dusuk_oranli_birim_sayisi}", help=f"%{m_val} altı")
            c4.metric("🔴 Riskli ASM Sayısı", f"{riskli_asm_sayisi}", help="İçinde en az 1 kırmızı birim var")
            
            st.caption(f"📍 Aktif Filtre: {st.session_state.filter_info}")
            st.markdown("---")

            # --- Grafikler ---
            g1, g2 = st.columns(2)
            
            # Bar Grafik
            group_col = 'ilce' if st.session_state.filter_info.startswith("Tümü") else 'asm'
            chart_data = df_res.groupby(group_col).agg(
                toplam=('basari_durumu','count'), 
                yapilan=('basari_durumu','sum')
            ).reset_index()
            
            if not chart_data.empty:
                chart_data['oran'] = (chart_data['yapilan'] / chart_data['toplam'] * 100).round(2)
                chart_data['Renk'] = chart_data['oran'].apply(lambda x: 'Yeşil' if x >= t_val else ('Sarı' if x >= m_val else 'Kırmızı'))
                fig_bar = px.bar(chart_data, x=group_col, y='oran', color='Renk', 
                                 color_discrete_map={'Yeşil':'#198754', 'Sarı':'#ffc107', 'Kırmızı':'#dc3545'},
                                 text='oran', title="Performans Grafiği")
                fig_bar.update_traces(textposition='outside')
                g1.plotly_chart(fig_bar, use_container_width=True)

            # Trend Grafik
            trend = df_res.copy()
            trend['AY'] = trend['hedef_tarih'].dt.strftime('%Y-%m')
            trend_data = trend.groupby('AY').agg({'basari_durumu':['sum','count']}).reset_index()
            trend_data.columns = ['AY', 'YAPILAN', 'HEDEF']
            trend_data['ORAN'] = (trend_data['YAPILAN'] / trend_data['HEDEF'] * 100).round(2)
            fig_line = px.line(trend_data, x='AY', y='ORAN', title="Zaman Serisi Trendi", markers=True)
            g2.plotly_chart(fig_line, use_container_width=True)
            
            # Isı Haritası
            st.subheader("🌡️ İlçe Bazlı Dönemsel Isı Haritası")
            heatmap_data = df_res.copy()
            heatmap_data['AY'] = heatmap_data['hedef_tarih'].dt.strftime('%Y-%m')
            pivot_table = heatmap_data.pivot_table(index='ilce', columns='AY', values='basari_durumu', aggfunc='mean') * 100
            
            if not pivot_table.empty:
                fig_heat = px.imshow(pivot_table, labels=dict(x="Ay", y="İlçe", color="Başarı (%)"),
                                     color_continuous_scale='RdYlGn', text_auto='.1f', aspect="auto")
                st.plotly_chart(fig_heat, use_container_width=True)

            # --- Raporlar ---
            st.subheader("📋 Detaylı Raporlar")
            tab1, tab2, tab3 = st.tabs(["📊 Birim Performans", "⚠️ Düşük Oranlılar", "🚨 Riskli ASM Listesi (Özet)"])

            with tab1:
                c_d1, c_d2 = st.columns([1,1])
                c_d1.download_button("📥 Excel İndir", data=to_excel(ozet), file_name='birim_perf.xlsx')
                c_d2.download_button("📄 PDF İndir", data=create_pdf(ozet, "Birim Performans Raporu", meta), file_name='birim_perf.pdf')
                st.dataframe(ozet, column_config={"oran": st.column_config.ProgressColumn("Başarı", format="%.2f%%", min_value=0, max_value=100)}, use_container_width=True, hide_index=True)

            with tab2:
                low_units = ozet[ozet['oran'] < m_val].sort_values(by='oran')
                c_d1, c_d2 = st.columns([1,1])
                c_d1.download_button("📥 Excel İndir", data=to_excel(low_units), file_name='dusuk_oran.xlsx', key='dl1')
                c_d2.download_button("📄 PDF İndir", data=create_pdf(low_units, "Dusuk Oranli Birimler", meta), file_name='dusuk_oran.pdf', key='dp1')
                st.dataframe(low_units, column_config={"oran": st.column_config.NumberColumn("Başarı", format="%.2f%%")}, use_container_width=True, hide_index=True)

            with tab3:
                rdf = pd.DataFrame(riskli_asm_listesi)
                if not rdf.empty:
                    rdf = rdf.sort_values(by="Kırmızı Birim", ascending=False)
                    c_d1, c_d2 = st.columns([1,1])
                    c_d1.download_button("📥 Excel İndir", data=to_excel(rdf), file_name='riskli_asm_ozet.xlsx', key='dl2')
                    c_d2.download_button("📄 PDF İndir", data=create_pdf(rdf, "Riskli ASM Ozet Listesi", meta), file_name='riskli_asm_ozet.pdf', key='dp2')
                    st.dataframe(rdf, column_config={
                        "Kırmızı Birim": st.column_config.NumberColumn(help=f"Alt Sınırın (%{m_val}) altı"),
                        "Yeşil Birim": st.column_config.NumberColumn(help=f"Hedefin (%{t_val}) üstü")
                    }, use_container_width=True, hide_index=True)
                else:
                    st.success("Tebrikler! Riskli ASM bulunamadı.")
    else:
        st.info("👈 Analizi başlatmak için soldaki menüden **'Filtreleri Uygula'** butonuna basınız.")
else:
    st.info("⬅️ Lütfen sol menüden Excel dosyanızı yükleyerek başlayın.")
