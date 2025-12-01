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
st.set_page_config(page_title="Lazer CRM & Teklif", layout="wide", page_icon="🏭")

# --- DATABASE & AYARLAR ---
DEFAULT_MALZEME = {
    "S235JR (Siyah)": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
    "DKP": {"fiyat": 0.90, "birim": "USD", "yogunluk": 7.85},
    "Galvaniz": {"fiyat": 1.00, "birim": "USD", "yogunluk": 7.85},
    "Paslanmaz 304": {"fiyat": 3.50, "birim": "USD", "yogunluk": 7.9},
    "Paslanmaz 316": {"fiyat": 4.50, "birim": "USD", "yogunluk": 8.0},
    "Alüminyum": {"fiyat": 3.00, "birim": "USD", "yogunluk": 2.7},
    "ST37": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
}

# Session State
if 'sepet' not in st.session_state: st.session_state.sepet = []
if 'malzeme_db' not in st.session_state: st.session_state.malzeme_db = DEFAULT_MALZEME
if 'dolar_kuru' not in st.session_state: st.session_state.dolar_kuru = 34.50
if 'lazer_dk_ucret' not in st.session_state: st.session_state.lazer_dk_ucret = 20.0
# Form verileri
if 'form_x' not in st.session_state: st.session_state.form_x = 0.0
if 'form_y' not in st.session_state: st.session_state.form_y = 0.0
if 'form_sure' not in st.session_state: st.session_state.form_sure = 0.0
if 'form_kal' not in st.session_state: st.session_state.form_kal = 2.0
if 'form_fire' not in st.session_state: st.session_state.form_fire = 0.0
if 'form_malz' not in st.session_state: st.session_state.form_malz = "S235JR (Siyah)"

# --- YARDIMCI FONKSİYONLAR ---

def musteri_listesi_getir():
    """CSV'den benzersiz müşteri isimlerini çeker"""
    if os.path.exists("musteri_gecmisi.csv"):
        df = pd.read_csv("musteri_gecmisi.csv")
        # Benzersiz isimleri al ve sırala
        isimler = df["Müşteri"].unique().tolist()
        isimler.sort()
        return isimler
    return []

def kayit_ekle(musteri, is_adi, tutar, detay):
    """Müşteriye iş kaydeder"""
    yeni_kayit = {
        "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Müşteri": musteri,
        "İş Adı": is_adi,
        "Tutar (TL)": round(tutar, 2),
        "Detay": detay
    }
    df = pd.DataFrame([yeni_kayit])
    if os.path.exists("musteri_gecmisi.csv"):
        df.to_csv("musteri_gecmisi.csv", mode='a', header=False, index=False)
    else:
        df.to_csv("musteri_gecmisi.csv", index=False)

def sureyi_dakikaya_cevir(zaman_str):
    try:
        parts = list(map(int, str(zaman_str).strip().split(':')))
        if len(parts) == 3: return (parts[0] * 60) + parts[1] + (parts[2] / 60)
        elif len(parts) == 2: return parts[0] + (parts[1] / 60)
        return 0.0
    except: return 0.0

def analiz_motoru(kaynak, text):
    veriler = {}
    # Süre
    zaman = re.search(r'(?:Kesim|Cut|Time).*?(\d{2}:\d{2}:\d{2})', text, re.IGNORECASE | re.DOTALL)
    if zaman: veriler["sure"] = sureyi_dakikaya_cevir(zaman.group(1))
    
    # X - Y
    x_match = re.search(r'X\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
    y_match = re.search(r'Y\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
    if x_match: veriler["x"] = float(x_match.group(1).replace(',', '.'))
    if y_match: veriler["y"] = float(y_match.group(1).replace(',', '.'))
    
    # Kalınlık
    kal = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
    if kal: veriler["kalinlik"] = float(kal.group(1).replace(',', '.'))
    
    # Malzeme
    tl = text.lower()
    if "dkp" in tl: veriler["malzeme"] = "DKP"
    elif "galvaniz" in tl: veriler["malzeme"] = "Galvaniz"
    elif "paslanmaz" in tl or "304" in tl: veriler["malzeme"] = "Paslanmaz 304"
    elif "alu" in tl: veriler["malzeme"] = "Alüminyum"
    else: veriler["malzeme"] = "S235JR (Siyah)"
    
    return veriler

def word_oku(file):
    doc = Document(file)
    text = "\n".join([p.text for p in doc.paragraphs] + [" ".join([c.text for c in r.cells]) for t in doc.tables for r in t.rows])
    return analiz_motoru("word", text)

def resim_oku(image):
    img_np = np.array(image)
    if len(img_np.shape) == 3: img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else: img_gray = img_np
    _, img_thresh = cv2.threshold(img_gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(Image.fromarray(img_thresh))
    return analiz_motoru("ocr", text)

# --- ARAYÜZ ---

# 1. BÖLÜM: MÜŞTERİ SEÇİMİ (EN ÜSTTE)
st.title("🏭 Lazer Yönetim Paneli")

# Müşteri veritabanını yükle
kayitli_musteriler = musteri_listesi_getir()

st.markdown("### 👤 Müşteri Seçimi")
col_mus1, col_mus2 = st.columns([3, 1])

with col_mus1:
    # Arama özellikli kutu (yazınca filtreler)
    secenekler = ["➕ Yeni Müşteri Ekle"] + kayitli_musteriler
    secim = st.selectbox("Müşteri Ara veya Seç", secenekler, index=0)

with col_mus2:
    if secim == "➕ Yeni Müşteri Ekle":
        aktif_musteri = st.text_input("Yeni Firma Adı Girin", placeholder="Örn: Yılmaz Makina")
    else:
        aktif_musteri = secim
        st.success(f"Seçili: **{aktif_musteri}**")

# Eğer müşteri seçilmediyse aşağıyı gösterme
if not aktif_musteri:
    st.warning("Lütfen işlem yapmak için bir müşteri seçin veya yeni oluşturun.")
    st.stop()

st.divider()

# 2. BÖLÜM: SEKMELER
tab_is, tab_gecmis, tab_ayar = st.tabs([f"📝 {aktif_musteri} - Yeni İş", f"🗂️ {aktif_musteri} - Geçmişi", "⚙️ Ayarlar"])

# --- TAB 1: YENİ İŞ OLUŞTURMA ---
with tab_is:
    col_sol, col_sag = st.columns([1, 1.2])
    
    # SOL: ÜRÜN GİRİŞİ (ARA KONTROL)
    with col_sol:
        st.markdown("#### 1. Veri Girişi")
        uploaded_file = st.file_uploader("Dosya Yükle (Word/Resim)", type=['docx', 'jpg', 'png'])
        
        # Dosya Okuma
        if uploaded_file and "dosya_token" not in st.session_state:
            try:
                if uploaded_file.name.endswith('.docx'): vals = word_oku(uploaded_file)
                else: vals = resim_oku(Image.open(uploaded_file))
                
                if "x" in vals: st.session_state.form_x = vals["x"]
                if "y" in vals: st.session_state.form_y = vals["y"]
                if "sure" in vals: st.session_state.form_sure = vals["sure"]
                if "kalinlik" in vals: st.session_state.form_kal = vals["kalinlik"]
                if "malzeme" in vals: st.session_state.form_malz = vals["malzeme"]
                st.session_state.dosya_token = True
                st.toast("Veriler çekildi, lütfen onaylayın.", icon="✅")
            except: st.error("Okuma hatası.")
        
        if not uploaded_file and "dosya_token" in st.session_state: del st.session_state.dosya_token

        # Form
        with st.form("veri_onay"):
            c1, c2 = st.columns(2)
            f_malz = c1.selectbox("Malzeme", list(st.session_state.malzeme_db.keys()), index=list(st.session_state.malzeme_db.keys()).index(st.session_state.form_malz) if st.session_state.form_malz in st.session_state.malzeme_db else 0)
            f_kal = c2.number_input("Kalınlık (mm)", value=float(st.session_state.form_kal))
            
            c3, c4 = st.columns(2)
            f_birim = c3.radio("Birim", ["mm", "cm", "m"], horizontal=True)
            f_adet = c4.number_input("Adet", 1, min_value=1)
            
            c5, c6 = st.columns(2)
            f_x = c5.number_input("X Boyutu", value=float(st.session_state.form_x))
            f_y = c6.number_input("Y Boyutu", value=float(st.session_state.form_y))
            
            c7, c8 = st.columns(2)
            f_sure = c7.number_input("Süre (dk)", value=float(st.session_state.form_sure))
            f_fire = c8.number_input("Fire (%)", value=float(st.session_state.form_fire))
            
            if st.form_submit_button("Sepete Ekle ⬇️", type="primary", use_container_width=True):
                # Birim çevirip sepete at
                carpan = 1000 if f_birim == "m" else (10 if f_birim == "cm" else 1)
                st.session_state.sepet.append({
                    "Malzeme": f_malz, "K": f_kal, "X": f_x*carpan, "Y": f_y*carpan, 
                    "Süre": f_sure, "Adet": f_adet, "Fire": f_fire, "Birim": f_birim
                })
                st.rerun()

    # SAĞ: SEPET VE HESAP
    with col_sag:
        st.markdown(f"#### 2. Sepet ({len(st.session_state.sepet)} Parça)")
        
        if st.session_state.sepet:
            df_sepet = pd.DataFrame(st.session_state.sepet)
            st.dataframe(df_sepet[["Malzeme", "K", "X", "Y", "Süre", "Adet"]], use_container_width=True, height=150)
            
            if st.button("🗑️ Sepeti Boşalt"):
                st.session_state.sepet = []
                st.rerun()
            
            # HESAP
            toplam_tl = 0
            toplam_kg = 0
            
            for p in st.session_state.sepet:
                db = st.session_state.malzeme_db[p["Malzeme"]]
                hacim = p["X"] * p["Y"] * p["K"]
                kg = (hacim * db["yogunluk"]) / 1_000_000 * p["Adet"]
                
                fiyat = db["fiyat"] * st.session_state.dolar_kuru if db["birim"] == "USD" else db["fiyat"]
                fire_kat = 1 / (1 - p["Fire"]/100) if p["Fire"] < 100 else 1
                
                malzeme_tutari = kg * fiyat * fire_kat
                lazer_tutari = (p["Süre"] * p["Adet"]) * st.session_state.lazer_dk_ucret
                
                toplam_tl += malzeme_tutari + lazer_tutari
                toplam_kg += kg
            
            st.divider()
            c_res1, c_res2 = st.columns(2)
            c_res1.metric("Toplam KG", f"{toplam_kg:.2f}")
            c_res2.metric("Ham Maliyet", f"{toplam_tl:.2f} TL")
            
            st.write("#### 💰 Satış & Kayıt")
            
            # Kâr ve İş Adı
            kc1, kc2 = st.columns(2)
            kar = kc1.number_input("Kâr (%)", 25, step=5)
            ekstra = kc2.number_input("Ekstra (TL)", 0)
            
            final_fiyat = (toplam_tl * (1 + kar/100)) + ekstra
            st.success(f"### TEKLİF: {final_fiyat:,.2f} TL")
            
            is_adi = st.text_input("İşin Adı / Açıklama", placeholder="Örn: 2mm Flanş Kesimi")
            
            if st.button("💾 Müşteriye Kaydet", type="primary", use_container_width=True):
                if not is_adi: is_adi = "Genel Kesim"
                kayit_ekle(aktif_musteri, is_adi, final_fiyat, f"{len(st.session_state.sepet)} parça, {toplam_kg:.1f}kg")
                st.session_state.sepet = [] # Kayıttan sonra sepeti temizle
                st.balloons()
                st.success(f"İşlem {aktif_musteri} hesabına işlendi!")
                
        else:
            st.info("Sepet boş. Yandaki formdan ürün ekleyin.")

# --- TAB 2: GEÇMİŞ (FİLTRELİ) ---
with tab_gecmis:
    st.header(f"🗂️ {aktif_musteri} - İş Geçmişi")
    
    if os.path.exists("musteri_gecmisi.csv"):
        df_all = pd.read_csv("musteri_gecmisi.csv")
        
        # Sadece seçili müşteriyi filtrele
        df_musteri = df_all[df_all["Müşteri"] == aktif_musteri]
        
        if not df_musteri.empty:
            st.dataframe(df_musteri, use_container_width=True)
            
            toplam_is = df_musteri["Tutar (TL)"].sum()
            st.info(f"Bu müşteriye yapılan toplam iş hacmi: **{toplam_is:,.2f} TL**")
        else:
            st.warning(f"{aktif_musteri} için henüz kayıt bulunamadı.")
    else:
        st.write("Veritabanı boş.")

# --- TAB 3: AYARLAR ---
with tab_ayar:
    st.write("### Genel Ayarlar")
    c1, c2 = st.columns(2)
    st.session_state.dolar_kuru = c1.number_input("Dolar Kuru", value=st.session_state.dolar_kuru)
    st.session_state.lazer_dk_ucret = c2.number_input("Lazer DK Ücreti", value=st.session_state.lazer_dk_ucret)
    
    if st.button("Ayarları Kaydet"):
        st.toast("Ayarlar güncellendi.")
