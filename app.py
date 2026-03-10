import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re
from fpdf import FPDF
import xlsxwriter
import os

# -----------------------------------------------------------------------------
# 1. YARDIMCI FONKSİYONLAR (ASM EŞLEŞTİRME DAHİL)
# -----------------------------------------------------------------------------

def clean_turkish_chars(text):
    """Türkçe karakterleri İngilizce karşılıklarına çevirir ve büyütür."""
    if not isinstance(text, str): return str(text)
    text = text.replace("İ", "I").replace("ı", "I")
    text = text.replace("Ş", "S").replace("ş", "s")
    text = text.replace("Ğ", "G").replace("ğ", "g")
    text = text.replace("Ü", "U").replace("ü", "u")
    text = text.replace("Ö", "O").replace("ö", "o")
    text = text.replace("Ç", "C").replace("ç", "c")
    return text.upper()

def extract_key_from_unit_name(text):
    """Birim adından ortak bir anahtar (KADIKOY-5) üretir."""
    text = clean_turkish_chars(text)
    text = re.sub(r'^ISTANBUL\s+', '', text)
    match = re.search(r'(\d+)\s*NOLU', text)
    if match:
        number = int(match.group(1)) 
        district_part = text[:match.start()].strip()
        return f"{district_part}-{number}"
    return None

@st.cache_data
def load_asm_mapping():
    """Dizindeki ASM dosyasını arar ve eşleştirme sözlüğünü hazırlar."""
    possible_files = ["ASM.xlsx", "ASM.csv", "ASM.xlsx - Sayfa1.csv", "asm_listesi.xlsx"]
    df_asm = None
    
    for f in possible_files:
        if os.path.exists(f):
            try:
                if f.endswith('.xlsx'):
                    df_asm = pd.read_excel(f)
                else:
                    df_asm = pd.read_csv(f)
                break
            except:
                continue
    
    if df_asm is None:
        return None

    df_asm.columns = [c.strip() for c in df_asm.columns]
    col_birim = next((c for c in df_asm.columns if 'birim' in c.lower() and 'ad' in c.lower()), None)
    col_asm = next((c for c in df_asm.columns if 'aile' in c.lower() and 'merkez' in c.lower()), None)
    
    if not col_birim or not col_asm:
        return None
        
    mapping = {}
    for _, row in df_asm.iterrows():
        key = extract_key_from_unit_name(str(row[col_birim]))
        if key:
            mapping[key] = str(row[col_asm]).strip()
            
    return mapping

def to_excel(df):
    """Veriyi Excel formatına çevirir."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        worksheet = writer.sheets['Sheet1']
        for i, col in enumerate(df.columns):
            try:
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                if max_len > 50: max_len = 50
                worksheet.set_column(i, i, max_len)
            except:
                worksheet.set_column(i, i, 15)
    return output.getvalue()

def create_pdf(df, title, info):
    """PDF Oluşturucu"""
    class PDF(FPDF):
        def header(self):
            try: self.image('logo.png', 10, 8, 33)
            except: pass
            
            self.set_y(10)
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, clean_text(title), 0, 1, 'C')
            
            self.set_font('Arial', '', 9)
            self.set_text_color(80, 80, 80)
            
            date_str = f"Tarih: {info.get('tarih_araligi', '-')}"
            ilce_txt = info.get('ilce', '-') if info.get('ilce') != "Tümü" else "Tum Ilceler"
            asm_txt = info.get('asm', '-') if info.get('asm') != "Tümü" else "Tum ASM'ler"
            asi_txt = info.get('asi', 'Tümü')
            doz_txt = info.get('doz', '-') if info.get('doz') else "Tum Dozlar"
            
            filter_str = f"Konum: {ilce_txt} / {asm_txt} | Asi: {asi_txt} (Doz: {doz_txt})"
            threshold_str = f"Hedef: %{info.get('hedef', 90)} | Alt Sinir: %{info.get('alt_sinir', 70)}"

            self.ln(2)
            self.cell(0, 5, clean_text(date_str), 0, 1, 'R')
            self.cell(0, 5, clean_text(filter_str), 0, 1, 'R')
            self.cell(0, 5, clean_text(threshold_str), 0, 1, 'R')
            self.ln(3)

            dusuk_sayisi = info.get('dusuk_birim_sayisi', 0)
            
            if info.get('sadece_sayi_goster') == True:
                summary_text = f"ACIL MUDAHALE GEREKEN BIRIM SAYISI: {dusuk_sayisi}"
            else:
                if info.get('ilce') == "Tümü":
                    basari_etiket = "IL GENEL BASARI ORANI"
                else:
                    basari_etiket = f"{clean_text(info.get('ilce')).upper()} BASARI ORANI"
                
                genel_oran = info.get('genel_basari_orani', 0)
                summary_text = f"{basari_etiket}: %{genel_oran:.2f}   |   Acil Mudahale Gereken Birim: {dusuk_sayisi}"
            
            self.set_font('Arial', 'B', 11)
            self.set_text_color(0, 0, 0)
            self.set_fill_color(230, 230, 230)
            self.cell(0, 10, summary_text, 0, 1, 'C', fill=True)
            self.ln(5)
            self.set_draw_color(150, 150, 150)
            self.line(10, self.get_y(), 287, self.get_y())
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

    def clean_text(text):
        if not isinstance(text, str): return str(text)
        text = text.replace("🔴", "").replace("🟢", "").replace("🟠", "").replace("✅", "").replace("⚠️", "").replace("🚨", "")
        replacements = {
            'ğ': 'g', 'Ğ': 'G', 'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I', 
            'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
        }
        for tr, eng in replacements.items():
            text = text.replace(tr, eng)
        return text.encode('latin-1', 'replace').decode('latin-1')

    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.alias_nb_pages()
    pdf.add_page()
    
    available_width = 275 
    max_lens = []
    for col in df.columns:
        max_l = len(str(col))
        for val in df[col].head(50):
            val_l = len(str(val))
            if val_l > max_l: max_l = val_l
        if col in ['asm', 'birim', 'ASM Adı']:
            if max_l > 35: max_l = 35 
        if col in ['Başarı Durumu', 'Durum']:
            if max_l < 20: max_l = 25
        max_lens.append(max_l)
    
    total_len = sum(max_lens)
    col_widths = []
    if total_len > 0:
        for l in max_lens:
            w = (l / total_len) * available_width
            if w < 20: w = 20
            col_widths.append(w)
    else:
        col_widths = [available_width]

    final_total = sum(col_widths)
    if final_total > available_width:
        factor = available_width / final_total
        col_widths = [w * factor for w in col_widths]

    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(220, 230, 240)
    pdf.set_text_color(0, 0, 0)
    for i, col in enumerate(df.columns):
        pdf.cell(col_widths[i], 10, clean_text(col), 1, 0, 'C', fill=True)
    pdf.ln()

    pdf.set_font("Arial", '', 8)
    for _, row in df.iterrows():
        if pdf.get_y() > 175:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 9)
            pdf.set_fill_color(220, 230, 240)
            for i, col in enumerate(df.columns):
                pdf.cell(col_widths[i], 10, clean_text(col), 1, 0, 'C', fill=True)
            pdf.ln()
            pdf.set_font("Arial", '', 8)

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
# 3. VERİ YÜKLEME (ÇOKLU DOSYA DESTEĞİ)
# -----------------------------------------------------------------------------
st.sidebar.header("1. Veri Yükleme")
uploaded_files = st.sidebar.file_uploader("Excel veya CSV Yükleyin", type=["xlsx", "csv"], accept_multiple_files=True, key="loader_main")

if 'filtered_df' not in st.session_state: st.session_state.filtered_df = pd.DataFrame()
if 'has_run' not in st.session_state: st.session_state.has_run = False

if uploaded_files:
    current_file_names = [f.name for f in uploaded_files]
    
    if 'raw_data' not in st.session_state or st.session_state.get('file_names') != current_file_names:
        try:
            all_dfs = []
            for uploaded_file in uploaded_files:
                if uploaded_file.name.endswith('.csv'):
                    temp_df = pd.read_csv(uploaded_file, encoding='cp1254')
                else:
                    temp_df = pd.read_excel(uploaded_file)
                
                temp_df.columns = [c.strip() for c in temp_df.columns]
                
                # ASI_ADI eklendi
                rename_map = {
                    'ILCE': 'ilce', 'asm': 'asm', 'BIRIM_ADI': 'birim', 
                    'ASI_SON_TARIH': 'hedef_tarih', 'ASI_YAP_TARIH': 'yapilan_tarih', 
                    'ASI_DOZU': 'doz', 'ASI_ADI': 'asi'
                }
                temp_df = temp_df.rename(columns={k: v for k, v in rename_map.items() if k in temp_df.columns})
                all_dfs.append(temp_df)
            
            df = pd.concat(all_dfs, ignore_index=True)
            
            # --- EKSİK ASM EŞLEŞTİRME ---
            asm_map = load_asm_mapping()
            
            if asm_map and 'birim' in df.columns:
                df['temp_key'] = df['birim'].apply(lambda x: extract_key_from_unit_name(str(x)))
                df['mapped_asm'] = df['temp_key'].map(asm_map)
                
                if 'asm' not in df.columns:
                    df['asm'] = df['mapped_asm']
                else:
                    df['asm'] = df['asm'].fillna(df['mapped_asm'])
                
                df = df.drop(columns=['temp_key', 'mapped_asm'], errors='ignore')

            if 'asm' not in df.columns:
                st.warning("⚠️ Yüklenen dosyalarda ASM sütunu yok ve eşleştirme dosyası (ASM.xlsx) bulunamadı.")
                df['asm'] = "Belirtilmemiş"
            else:
                df['asm'] = df['asm'].fillna("Belirtilmemiş")

            if 'doz' in df.columns:
                df['doz'] = pd.to_numeric(df['doz'], errors='coerce').fillna(0).astype(int)
            else:
                df['doz'] = 1
            
            df['hedef_tarih'] = pd.to_datetime(df['hedef_tarih'], errors='coerce')
            df['yapilan_tarih'] = pd.to_datetime(df['yapilan_tarih'], errors='coerce')
            df = df.dropna(subset=['hedef_tarih'])
            
            st.session_state.raw_data = df
            st.session_state.file_names = current_file_names
        except Exception as e:
            st.error(f"Dosya okuma hatası: {e}")
            st.stop()

    df = st.session_state.raw_data

    # -----------------------------------------------------------------------------
    # 4. FİLTRELEME
    # -----------------------------------------------------------------------------
    st.sidebar.header("2. Filtre Ayarları")
    with st.sidebar.form(key='filter_form'):
        
        # İlçe Filtresi
        ilce_list = ["Tümü"] + sorted(df['ilce'].astype(str).unique().tolist())
        selected_ilce = st.selectbox("İlçe Seç", ilce_list)
        
        # ASM Filtresi
        if selected_ilce != "Tümü": asm_source = df[df['ilce'] == selected_ilce]
        else: asm_source = df
        
        asm_list = ["Tümü"] + sorted(asm_source['asm'].astype(str).unique().tolist())
        selected_asm = st.selectbox("ASM Seç", asm_list)

        # Aşı Filtresi (YENİ)
        if 'asi' in df.columns:
            asi_list = sorted(df['asi'].astype(str).unique().tolist())
            selected_asilar = st.multiselect("Aşı Seçin", options=asi_list, default=[])
        else:
            selected_asilar = []

        # Doz Filtresi
        dose_options = list(range(1, 10))
        selected_doses = st.multiselect("Aşı Dozu Seçin", options=dose_options, default=[])

        # Tarih Filtresi
        if not df.empty:
            min_date = df['hedef_tarih'].min().date()
            max_date = df['hedef_tarih'].max().date()
            date_range = st.date_input("Tarih Aralığı", [min_date, max_date])
        else:
            st.stop()

        target_val = st.number_input("Hedef Başarı (%)", value=90)
        min_val = st.number_input("Alt Sınır (%)", value=70)
        
        st.markdown("---")
        submit_button = st.form_submit_button(label='🚀 Filtreleri Uygula')

    # -----------------------------------------------------------------------------
    # 5. ANALİZ
    # -----------------------------------------------------------------------------
    if submit_button:
        with st.spinner('Analiz yapılıyor...'):
            temp_df = df.copy()
            if selected_ilce != "Tümü": temp_df = temp_df[temp_df['ilce'] == selected_ilce]
            if selected_asm != "Tümü": temp_df = temp_df[temp_df['asm'] == selected_asm]
            if selected_asilar: temp_df = temp_df[temp_df['asi'].isin(selected_asilar)] # AŞI FİLTRESİ
            if selected_doses: temp_df = temp_df[temp_df['doz'].isin(selected_doses)]
            
            if isinstance(date_range, list) and len(date_range) == 2:
                mask = (temp_df['hedef_tarih'].dt.date >= date_range[0]) & (temp_df['hedef_tarih'].dt.date <= date_range[1])
                temp_df = temp_df[mask]
            
            temp_df['basari_durumu'] = temp_df['yapilan_tarih'].notna().astype(int)
            
            date_str = "Tumu"
            if isinstance(date_range, list) and len(date_range) == 2:
                date_str = f"{date_range[0].strftime('%d.%m.%Y')} - {date_range[1].strftime('%d.%m.%Y')}"
            
            asi_str = ", ".join(map(str, selected_asilar)) if selected_asilar else "Tümü"
            dose_str = ", ".join(map(str, selected_doses)) if selected_doses else ""
            
            st.session_state.filtered_df = temp_df
            st.session_state.filter_info = f"{selected_ilce} / {selected_asm} | Aşı: {asi_str}"
            st.session_state.target_val = target_val
            st.session_state.min_val = min_val
            
            st.session_state.report_meta = {
                "tarih_araligi": date_str, "ilce": selected_ilce, "asm": selected_asm,
                "asi": asi_str, "doz": dose_str, "hedef": target_val, "alt_sinir": min_val
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
            st.warning("⚠️ Seçilen kriterlere uygun veri bulunamadı.")
        else:
            total_target = len(df_res)
            total_done = df_res['basari_durumu'].sum()
            genel_oran = (total_done / total_target * 100) if total_target > 0 else 0
            
            ozet = df_res.groupby(['ilce', 'asm', 'birim']).agg(
                toplam=('basari_durumu', 'count'), yapilan=('basari_durumu', 'sum')
            ).reset_index()
            ozet['oran'] = (ozet['yapilan'] / ozet['toplam'] * 100).round(2)
            
            dusuk_oranli_sayisi = len(ozet[ozet['oran'] < m_val])
            meta['genel_basari_orani'] = genel_oran
            meta['dusuk_birim_sayisi'] = dusuk_oranli_sayisi
            st.session_state.report_meta = meta 
            
            riskli_asm_listesi = []
            for (ilce, asm), grup in ozet.groupby(['ilce', 'asm']):
                kirmizi = len(grup[grup['oran'] < m_val])
                if kirmizi > 0:
                    yesil = len(grup[grup['oran'] >= t_val])
                    sari = len(grup) - kirmizi - yesil
                    riskli_asm_listesi.append({
                        "İlçe": ilce, "ASM Adı": asm, 
                        "Acil Müdahale": kirmizi, "Geliştirilmeli": sari, "Başarılı": yesil,        
                        "Toplam Birim": len(grup)
                    })
            riskli_asm_sayisi = len(riskli_asm_listesi)
            
            if meta['ilce'] != "Tümü":
                ana_baslik = f"{meta['ilce']} - BAŞARI ORANI"
            else:
                ana_baslik = "İL GENEL BAŞARI ORANI (Tüm İlçeler)"
            
            st.markdown(f"""
            <div style="text-align: center; background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 20px; border-radius: 12px; margin-bottom: 25px;">
                <h3 style="color: #6c757d; margin: 0; font-weight: 500; font-size: 1.5rem;">{ana_baslik}</h3>
                <h1 style="color: #0d6efd; font-size: 4rem; margin: 10px 0; font-weight: 700;">%{genel_oran:.2f}</h1>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🔵 Toplam Hedef", f"{total_target:,}".replace(",", "."))
            c2.metric("🟢 Toplam Yapılan", f"{total_done:,}".replace(",", "."))
            c3.metric("🟠 Acil Müdahale (Birim)", f"{dusuk_oranli_sayisi}")
            c4.metric("🔴 Acil Müdahale (ASM)", f"{riskli_asm_sayisi}")
            
            st.caption(f"📍 Filtre: {st.session_state.filter_info}")
            st.markdown("---")

            g1, g2 = st.columns(2)
            if st.session_state.filter_info.startswith("Tümü"):
                group_col = 'ilce'
                x_label = "İlçe"
                chart_height = 500
            else:
                group_col = 'birim'
                x_label = "Aile Hekimliği Birimi (AHB)"
                chart_height = 600
                
            chart_data = df_res.groupby(group_col).agg(toplam=('basari_durumu','count'), yapilan=('basari_durumu','sum')).reset_index()
            if not chart_data.empty:
                chart_data['oran'] = (chart_data['yapilan'] / chart_data['toplam'] * 100).round(2)
                chart_data = chart_data.sort_values(by='oran', ascending=False)
                
                def get_chart_status(x):
                    if x >= t_val: return 'Başarılı'
                    elif x >= m_val: return 'Geliştirilmeli'
                    else: return 'Acil Müdahale'

                chart_data['Durum'] = chart_data['oran'].apply(get_chart_status)
                
                fig_bar = px.bar(chart_data, x=group_col, y='oran', color='Durum', 
                                 color_discrete_map={'Başarılı':'#0d6efd', 'Geliştirilmeli':'#ffc107', 'Acil Müdahale':'#dc3545'},
                                 text='oran', title=f"Performans Dağılımı ({x_label})", height=chart_height)
                
                fig_bar.update_layout(xaxis_title=x_label, yaxis_title="Başarı Oranı (%)")
                fig_bar.update_traces(textposition='outside')
                g1.plotly_chart(fig_bar, use_container_width=True)

            trend = df_res.copy()
            trend['AY'] = trend['hedef_tarih'].dt.strftime('%Y-%m')
            trend_data = trend.groupby('AY').agg({'basari_durumu':['sum','count']}).reset_index()
            trend_data.columns = ['AY', 'YAPILAN', 'HEDEF']
            trend_data['ORAN'] = (trend_data['YAPILAN'] / trend_data['HEDEF'] * 100).round(2)
            fig_line = px.line(trend_data, x='AY', y='ORAN', title="Zaman Serisi Trendi", markers=True)
            g2.plotly_chart(fig_line, use_container_width=True)

            st.subheader("📋 Detaylı Raporlar")
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Birim Performans", "🚦 Birim Başarı Durumu", "⚠️ Acil Müdahale Gerekenler", "🚨 Riskli ASM Listesi"])

            with tab1:
                ozet_num = ozet.copy()
                if 'Durum' in ozet_num.columns: ozet_num = ozet_num.drop(columns=['Durum'])
                c_d1, c_d2 = st.columns([1,1])
                c_d1.download_button("📥 Excel İndir", data=to_excel(ozet_num), file_name='birim_perf_sayisal.xlsx')
                c_d2.download_button("📄 PDF İndir", data=create_pdf(ozet_num, "Birim Performans (Sayisal)", meta), file_name='birim_perf_sayisal.pdf')
                st.dataframe(ozet_num, column_config={"oran": st.column_config.ProgressColumn("Başarı Oranı", format="%.2f%%", min_value=0, max_value=100)}, use_container_width=True, hide_index=True)

            with tab2:
                def get_status_text(rate, target, minimum):
                    if rate >= target: return "Başarılı"
                    elif rate >= minimum: return "Geliştirilmeli"
                    else: return "Acil Müdahale"
                
                ozet_status = ozet.copy()
                ozet_status['Başarı Durumu'] = ozet_status['oran'].apply(lambda x: get_status_text(x, t_val, m_val))
                cols_to_keep = ['ilce', 'asm', 'birim', 'Başarı Durumu']
                ozet_status_final = ozet_status[cols_to_keep]
                
                def color_status(val):
                    if val == "Başarılı": return 'background-color: #cfe2ff; color: #084298'
                    elif val == "Geliştirilmeli": return 'background-color: #fff3cd; color: #856404'
                    elif val == "Acil Müdahale": return 'background-color: #f8d7da; color: #721c24'
                    return ''

                c_d1, c_d2 = st.columns([1,1])
                c_d1.download_button("📥 Excel İndir", data=to_excel(ozet_status_final), file_name='birim_basari_durumu.xlsx', key='bd_xls')
                
                meta_status = meta.copy()
                meta_status['sadece_sayi_goster'] = True
                c_d2.download_button("📄 PDF İndir", data=create_pdf(ozet_status_final, "Birim Basari Durumu", meta_status), file_name='birim_basari_durumu.pdf', key='bd_pdf')
                st.dataframe(ozet_status_final.style.map(color_status, subset=['Başarı Durumu']), use_container_width=True, hide_index=True)

            with tab3:
                low = ozet[ozet['oran'] < m_val].sort_values(by='oran')
                c_d1, c_d2 = st.columns([1,1])
                c_d1.download_button("📥 Excel İndir", data=to_excel(low), file_name='acil_mudahale_birimler.xlsx', key='dl1')
                c_d2.download_button("📄 PDF İndir", data=create_pdf(low, "Acil Mudahale Gereken Birimler", meta), file_name='acil_mudahale_birimler.pdf', key='dp1')
                st.dataframe(low, column_config={"oran": st.column_config.NumberColumn("Başarı", format="%.2f%%")}, use_container_width=True, hide_index=True)

            with tab4:
                rdf = pd.DataFrame(riskli_asm_listesi)
                if not rdf.empty:
                    rdf = rdf.sort_values(by="Acil Müdahale", ascending=False)
                    c_d1, c_d2 = st.columns([1,1])
                    c_d1.download_button("📥 Excel İndir", data=to_excel(rdf), file_name='riskli_asm_ozet.xlsx', key='dl2')
                    c_d2.download_button("📄 PDF İndir", data=create_pdf(rdf, "Riskli ASM Ozet Listesi", meta), file_name='riskli_asm_ozet.pdf', key='dp2')
                    st.dataframe(rdf, use_container_width=True, hide_index=True)
                else:
                    st.success("Tebrikler! Riskli ASM bulunamadı.")
    else:
        st.info("👈 Analizi başlatmak için soldaki menüden **'Filtreleri Uygula'** butonuna basınız.")
else:
    st.info("⬅️ Lütfen sol menüden Excel dosyanızı(veya dosyalarınızı) yükleyerek başlayın.")
