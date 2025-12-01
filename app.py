import streamlit as st
import pandas as pd
import cv2
import pytesseract
from PIL import Image
from docx import Document
import re
import os
import numpy as np
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Pro Lazer Teklif", layout="wide", page_icon="🏭")

# --- BAŞLANGIÇ VERİLERİ ---
DEFAULT_MALZEME = {
    "S235JR (Siyah)": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
    "DKP": {"fiyat": 0.90, "birim": "USD", "yogunluk": 7.85},
    "Galvaniz": {"fiyat": 1.00, "birim": "USD", "yogunluk": 7.85},
    "Paslanmaz 304": {"fiyat": 3.50, "birim": "USD", "yogunluk": 7.9},
    "Paslanmaz 316": {"fiyat": 4.50, "birim": "USD", "yogunluk": 8.0},
    "Alüminyum": {"fiyat": 3.00, "birim": "USD", "yogunluk": 2.7},
    "ST37": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
}

# --- SESSION STATE (Hafıza) ---
if 'sepet' not in st.session_state: st.session_state.sepet = []
if 'malzeme_db' not in st.session_state: st.session_state.malzeme_db = DEFAULT_MALZEME
if 'dolar_kuru' not in st.session_state: st.session_state.dolar_kuru = 34.50
if 'lazer_dk_ucret' not in st.session_state: st.session_state.lazer_dk_ucret = 20.0

# --- FORM DOLUM DEĞİŞKENLERİ (Ara Kontrol İçin) ---
# Bu değişkenler, dosya yüklendiğinde otomatik dolacak, manuelde boş kalacak.
if 'form_x' not in st.session_state: st.session_state.form_x = 0.0
if 'form_y' not in st.session_state: st.session_state.form_y = 0.0
if 'form_sure' not in st.session_state: st.session_state.form_sure = 0.0
if 'form_kal' not in st.session_state: st.session_state.form_kal = 2.0
if 'form_fire' not in st.session_state: st.session_state.form_fire = 0.0
if 'form_malz' not in st.session_state: st.session_state.form_malz = "S235JR (Siyah)"

# --- FONKSİYONLAR ---

def sureyi_dakikaya_cevir(zaman_str):
    """00:05:30 gibi formatları dakikaya çevirir"""
    try:
        parts = list(map(int, str(zaman_str).strip().split(':')))
        if len(parts) == 3: return (parts[0] * 60) + parts[1] + (parts[2] / 60)
        elif len(parts) == 2: return parts[0] + (parts[1] / 60)
        return 0.0
    except: return 0.0

def word_analiz(file):
    """Word dosyasından veri çeker"""
    doc = Document(file)
    text = "\n".join([p.text for p in doc.paragraphs] + [" ".join([c.text for c in r.cells]) for t in doc.tables for r in t.rows])
    return regex_taramasi(text)

def resim_analiz(image):
    """Resimden veri çeker (İyileştirilmiş)"""
    img_np = np.array(image)
    if len(img_np.shape) == 3: img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else: img_gray = img_np
    _, img_thresh = cv2.threshold(img_gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(Image.fromarray(img_thresh))
    return regex_taramasi(text)

def regex_taramasi(text):
    """Metin içinden verileri bulur"""
    veriler = {}
    
    # 1. Süre (Kesim/Cut kelimesi zorunlu)
    zaman = re.search(r'(?:Kesim|Cut|Time).*?(\d{2}:\d{2}:\d{2})', text, re.IGNORECASE | re.DOTALL)
    if zaman: veriler["sure"] = sureyi_dakikaya_cevir(zaman.group(1))
    
    # 2. X ve Y (Daha esnek arama)
    # Word tablolarında bazen X ve sayı bitişik olabilir
    x_match = re.search(r'X\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
    y_match = re.search(r'Y\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
    if x_match: veriler["x"] = float(x_match.group(1).replace(',', '.'))
    if y_match: veriler["y"] = float(y_match.group(1).replace(',', '.'))
    
    # 3. Kalınlık
    kal = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
    if kal: veriler["kalinlik"] = float(kal.group(1).replace(',', '.'))
    
    # 4. Malzeme
    tl = text.lower()
    if "dkp" in tl: veriler["malzeme"] = "DKP"
    elif "galvaniz" in tl: veriler["malzeme"] = "Galvaniz"
    elif "paslanmaz" in tl or "304" in tl: veriler["malzeme"] = "Paslanmaz 304"
    elif "alu" in tl: veriler["malzeme"] = "Alüminyum"
    
    return veriler

def kayit_ekle(musteri, tutar, notlar):
    """CSV dosyasına kaydeder"""
    yeni_kayit = {
        "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Müşteri": musteri,
        "Tutar": tutar,
        "Notlar": notlar
    }
    df = pd.DataFrame([yeni_kayit])
    if os.path.exists("musteri_gecmisi.csv"):
        df.to_csv("musteri_gecmisi.csv", mode='a', header=False, index=False)
    else:
        df.to_csv("musteri_gecmisi.csv", index=False)

# --- ARAYÜZ BAŞLIYOR ---

# AYARLAR BUTONU (Sol Üst)
col_logo, col_settings = st.columns([6, 1])
with col_logo: st.title("🏭 Lazer Teklif Masası")
with col_settings:
    with st.popover("⚙️ Ayarlar"):
        st.write("**Birim Fiyatlar**")
        st.session_state.dolar_kuru = st.number_input("Dolar Kuru", value=st.session_state.dolar_kuru)
        st.session_state.lazer_dk_ucret = st.number_input("Lazer Kesim (TL/dk)", value=st.session_state.lazer_dk_ucret)
        st.markdown("---")
        if st.button("Sıfırla"):
            st.session_state.sepet = []
            st.rerun()

# SEKMELER
tab_islem, tab_musteri = st.tabs(["🛒 İşlem Masası (Hesaplama)", "🗂️ Müşteri Kayıtları"])

with tab_islem:
    row1_col1, row1_col2 = st.columns([1, 1.5])
    
    # --- SOL SÜTUN: VERİ GİRİŞİ VE DÜZENLEME (ARA KONTROL) ---
    with row1_col1:
        st.markdown("### 1. İş Ekle")
        st.info("Dosya yüklersen bilgiler otomatik dolar. Yüklemezsen elle girebilirsin.")
        
        # Dosya Yükleyici
        uploaded_file = st.file_uploader("Word veya Resim Raporu", type=['docx', 'jpg', 'png', 'jpeg'])
        
        # Dosya yüklendiğinde verileri state'e at (Sayfa yenilenince gitmesin diye)
        if uploaded_file and "dosya_islendi" not in st.session_state:
            try:
                if uploaded_file.name.endswith('.docx'):
                    veriler = word_analiz(uploaded_file)
                else:
                    veriler = resim_analiz(Image.open(uploaded_file))
                
                # Bulunanları kutucuklara doldur
                if "x" in veriler: st.session_state.form_x = veriler["x"]
                if "y" in veriler: st.session_state.form_y = veriler["y"]
                if "sure" in veriler: st.session_state.form_sure = veriler["sure"]
                if "kalinlik" in veriler: st.session_state.form_kal = veriler["kalinlik"]
                if "malzeme" in veriler: st.session_state.form_malz = veriler["malzeme"]
                
                st.session_state.dosya_islendi = True # Sürekli tekrar okumasın
                st.toast("Veriler okundu! Lütfen aşağıdan kontrol edin.", icon="✅")
            except Exception as e:
                st.error(f"Okuma hatası: {e}")

        # Eğer dosya silinirse flag'i kaldır
        if not uploaded_file and "dosya_islendi" in st.session_state:
            del st.session_state.dosya_islendi

        # --- DÜZENLEME FORMU (Manuel ve Otomatik Birleşimi) ---
        with st.form("ekleme_formu"):
            c1, c2 = st.columns(2)
            secilen_malzeme = c1.selectbox("Malzeme", list(st.session_state.malzeme_db.keys()), index=list(st.session_state.malzeme_db.keys()).index(st.session_state.form_malz) if st.session_state.form_malz in st.session_state.malzeme_db else 0)
            kalinlik = c2.number_input("Kalınlık (mm)", value=float(st.session_state.form_kal))
            
            c3, c4 = st.columns(2)
            # Birim Seçimi
            birim = st.radio("Ölçü Birimi", ["mm", "cm", "m"], horizontal=True)
            
            c5, c6 = st.columns(2)
            x_degeri = c5.number_input(f"X Boyutu", value=float(st.session_state.form_x))
            y_degeri = c6.number_input(f"Y Boyutu", value=float(st.session_state.form_y))
            
            c7, c8, c9 = st.columns(3)
            sure = c7.number_input("Süre (dk)", value=float(st.session_state.form_sure))
            adet = c8.number_input("Adet (Plaka)", value=1, min_value=1)
            fire = c9.number_input("Fire (%)", value=float(st.session_state.form_fire))
            
            ekle_btn = st.form_submit_button("Sepete Ekle ⬇️", type="primary", use_container_width=True)
            
            if ekle_btn:
                # Birim çevirme (Arka planda hep mm tutuyoruz)
                carpan = 1000 if birim == "m" else (10 if birim == "cm" else 1)
                
                st.session_state.sepet.append({
                    "Malzeme": secilen_malzeme,
                    "Kalınlık": kalinlik,
                    "X": x_degeri * carpan, # mm olarak kaydet
                    "Y": y_degeri * carpan, # mm olarak kaydet
                    "Süre": sure,
                    "Adet": adet,
                    "Fire": fire
                })
                st.toast("Ürün sepete eklendi!", icon="🛒")

    # --- SAĞ SÜTUN: SEPET VE FİYATLANDIRMA ---
    with row1_col2:
        st.markdown("### 2. Sepet & Fiyatlandırma")
        
        if len(st.session_state.sepet) > 0:
            # Sepeti Göster
            df_sepet = pd.DataFrame(st.session_state.sepet)
            
            # Tabloyu biraz daha okunabilir yapalım
            st.dataframe(
                df_sepet, 
                column_config={
                    "X": st.column_config.NumberColumn("X (mm)"),
                    "Y": st.column_config.NumberColumn("Y (mm)"),
                    "Süre": st.column_config.NumberColumn("Süre (dk)")
                },
                use_container_width=True
            )
            
            if st.button("🗑️ Sepeti Temizle"):
                st.session_state.sepet = []
                st.rerun()
            
            # --- HESAPLAMA MOTORU ---
            toplam_maliyet = 0
            toplam_kg = 0
            
            for urun in st.session_state.sepet:
                malz_bilgi = st.session_state.malzeme_db[urun["Malzeme"]]
                
                # Ağırlık (Hacim * Yoğunluk)
                hacim = urun["X"] * urun["Y"] * urun["Kalınlık"]
                agirlik = (hacim * malz_bilgi["yogunluk"]) / 1_000_000 * urun["Adet"]
                
                # Malzeme Fiyatı (Dolar -> TL)
                birim_fiyat = malz_bilgi["fiyat"] * st.session_state.dolar_kuru if malz_bilgi["birim"] == "USD" else malz_bilgi["fiyat"]
                
                # Fire Hesabı (Maliyet = Tutar / (1-fire))
                fire_orani = urun["Fire"] / 100
                if fire_orani >= 1: fire_orani = 0 # Hata önleyici
                fire_carpan = 1 / (1 - fire_orani)
                
                malzeme_tutari = agirlik * birim_fiyat * fire_carpan
                
                # İşçilik
                lazer_tutari = (urun["Süre"] * urun["Adet"]) * st.session_state.lazer_dk_ucret
                
                toplam_maliyet += malzeme_tutari + lazer_tutari
                toplam_kg += agirlik
            
            st.divider()
            
            # --- FİNAL TEKLİF EKRANI ---
            col_ozet1, col_ozet2 = st.columns(2)
            with col_ozet1:
                st.metric("Toplam Ağırlık", f"{toplam_kg:.2f} kg")
                st.metric("Ham Maliyet", f"{toplam_maliyet:.2f} TL")
            
            with col_ozet2:
                # KÂR ORANI BURADA
                st.write("#### 💰 Satış Ayarları")
                kar_orani = st.number_input("Kâr Oranı (%)", value=25, step=5)
                ekstra_gider = st.number_input("Ekstra (Nakliye vb.)", value=0)
                
                # Satış Fiyatı Formülü
                satis_fiyati = (toplam_maliyet * (1 + kar_orani/100)) + ekstra_gider
                
                st.success(f"### TEKLİF: {satis_fiyati:,.2f} TL")
            
            # KAYDETME
            st.divider()
            with st.expander("Müşteriye Kaydet", expanded=True):
                musteri_adi = st.text_input("Müşteri / Firma Adı")
                is_notu = st.text_input("İş Tanımı (Opsiyonel)")
                if st.button("💾 Kaydet"):
                    kayit_ekle(musteri_adi, satis_fiyati, f"{is_notu} - {len(st.session_state.sepet)} kalem ürün")
                    st.toast("Kayıt Başarılı!", icon="✅")
                    
        else:
            st.info("Sepetiniz boş. Soldan ürün ekleyin.")

with tab_musteri:
    st.header("Geçmiş Teklifler")
    if os.path.exists("musteri_gecmisi.csv"):
        df_gecmis = pd.read_csv("musteri_gecmisi.csv")
        st.dataframe(df_gecmis, use_container_width=True)
        
        with open("musteri_gecmisi.csv", "rb") as f:
            st.download_button("Excel Olarak İndir", f, "teklifler.csv")
    else:
        st.warning("Henüz hiç kayıt yok.")
