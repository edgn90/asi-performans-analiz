# 2. Gelişmiş PDF İndirme Fonksiyonu (Yatay Mod + Otomatik Genişlik)
def create_pdf(df, title):
    class PDF(FPDF):
        def header(self):
            try:
                # Logo genişliği ve konumu (Yatay mod için ayarlandı)
                self.image('logo.png', 10, 8, 33)
            except:
                pass
            
            self.set_font('Arial', 'B', 14)
            # Başlığı ortala
            self.cell(0, 10, clean_text(title), 0, 1, 'C')
            self.ln(12)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

    def clean_text(text):
        if not isinstance(text, str): return str(text)
        replacements = {
            'ğ': 'g', 'Ğ': 'G', 'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I', 
            'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
        }
        for tr, eng in replacements.items():
            text = text.replace(tr, eng)
        return text.encode('latin-1', 'replace').decode('latin-1')

    # YATAY (Landscape) Modu Başlatıyoruz ('L')
    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # --- AKILLI SÜTUN GENİŞLİĞİ HESAPLAMA ---
    # Sayfa genişliği (A4 Yatay = 297mm, kenar boşlukları düşünce ~275mm kullanılabilir)
    available_width = 275
    
    # Her sütundaki en uzun veriyi bul
    max_lens = []
    for col in df.columns:
        # Başlık uzunluğu
        max_l = len(str(col))
        # Veri uzunlukları (İlk 50 satırı kontrol etsek yeterli, performans için)
        for val in df[col].head(50):
            val_l = len(str(val))
            if val_l > max_l:
                max_l = val_l
        max_lens.append(max_l)
    
    total_len = sum(max_lens)
    
    # Her sütuna, içeriğinin uzunluğu oranında genişlik ver
    col_widths = []
    for l in max_lens:
        # Formül: (Sütun Max Uzunluk / Toplam Karakter) * Sayfa Genişliği
        w = (l / total_len) * available_width
        # Çok dar sütunları engellemek için minimum 15mm verelim
        if w < 15: w = 15
        col_widths.append(w)
        
    # Genişlikleri tekrar normalize et (Minimum eklemeler taşma yapmasın diye)
    final_total = sum(col_widths)
    if final_total > available_width:
        factor = available_width / final_total
        col_widths = [w * factor for w in col_widths]

    # --- TABLO BAŞLIKLARI ---
    pdf.set_font("Arial", 'B', 9) # Başlık fontu
    # Gri arka plan ekleyelim (görsellik için)
    pdf.set_fill_color(200, 220, 255) 
    
    for i, col in enumerate(df.columns):
        pdf.cell(col_widths[i], 10, clean_text(col), 1, 0, 'C', fill=True)
    pdf.ln()

    # --- TABLO VERİLERİ ---
    pdf.set_font("Arial", size=8) # Veri fontunu biraz küçültelim
    
    for _, row in df.iterrows():
        # Satır taşmasını önlemek için sayfa sonu kontrolü
        if pdf.get_y() > 180: # Sayfa sonuna yaklaştıysa
            pdf.add_page()
            # Başlıkları tekrar bas
            pdf.set_font("Arial", 'B', 9)
            pdf.set_fill_color(200, 220, 255)
            for i, col in enumerate(df.columns):
                pdf.cell(col_widths[i], 10, clean_text(col), 1, 0, 'C', fill=True)
            pdf.ln()
            pdf.set_font("Arial", size=8)

        # Hücreleri yaz
        for i, item in enumerate(row):
            # Hücre içeriğini kısalt (aşırı uzun metinler yine de taşmasın)
            text = clean_text(str(item))
            
            # Basit taşma önlemi: Eğer metin hücre genişliğinden çok fazlaysa kırp
            # Yaklaşık olarak 1mm = 2-3 karakter (fonta göre değişir)
            max_char = int(col_widths[i] / 2) + 2 
            if len(text) > max_char:
                text = text[:max_char-2] + ".."
                
            pdf.cell(col_widths[i], 8, text, 1, 0, 'C')
        pdf.ln()

    return pdf.output(dest='S').encode('latin-1')
