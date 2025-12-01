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
st.set_page_config(page_title="Lazer CRM & Metalix", layout="wide", page_icon="🏭")

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

# Session State Başlatma
if 'sepet' not in st.session_state: st.session_state.sepet = []
if 'malzeme_db' not in st.session_state: st.session_state.malzeme_db = DEFAULT_MALZEME
if 'dolar_kuru' not in st.session_state: st.session_state.dolar_kuru = 34.50
if 'lazer_dk_ucret' not in st.session_state: st.session_state.lazer_dk_ucret = 20.0

# Form verileri (Geçici Hafıza)
defaults = {"x": 0.0, "y": 0.0, "sure": 0.0, "kal": 2.0, "fire": 0.0, "malz": "S235JR (Siyah)"}
for key, val in defaults.items():
    if f'form_{key}' not in st.session_state: st.session_state[f'form_{key}'] = val

# --- YARDIMCI FONKSİYONLAR ---

def musteri_listesi_getir():
    if os.path.exists("musteri_gecmisi.csv"):
        try:
            df = pd.read_csv("musteri_gecmisi.csv")
            isimler = df["Müşteri"].dropna().unique().tolist()
            isimler.sort()
            return isimler
        except: return []
    return []

def kayit_ekle(musteri, is_adi, tutar, detay):
    yeni_kayit = {
        "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Müşteri": musteri,
        "İş Adı": is_adi,
        "Tutar (TL)": round(tutar, 2),
        "Detay": detay
    }
    df = pd.DataFrame([yeni_kayit])
    mode = 'a' if os.path.exists("musteri_gecmisi.csv") else 'w'
    header = not os.path.exists("musteri_gecmisi.csv")
    df.to_csv("musteri_gecmisi.csv", mode=mode, header=header, index=False)

def sureyi_dakikaya_cevir(zaman_str):
    try:
        parts = list(map(int, str(zaman_str).strip().split(':')))
        if len(parts) == 3: return (parts[0] * 60) + parts[1] + (parts[2] / 60)
        elif len(parts) == 2: return parts[0] + (parts[1] / 60)
        return 0.0
    except: return 0.0

# --- ANALİZ MOTORLARI ---

def regex_taramasi(text):
    veriler = {}
    zaman = re.search(r'(?:Kesim|Cut|Time).*?(\d{2}:\d{2}:\d{2})', text, re.IGNORECASE | re.DOTALL)
    if zaman: veriler["sure"] = sureyi_dakikaya_cevir(zaman.group(1))
    
    x_match = re.search(r'X\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
    y_match = re.search(r'Y\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
    if x_match: veriler["x"] = float(x_match.group(1).replace(',', '.'))
    if y_match: veriler["y"] = float(y_match.group(1).replace(',', '.'))
    
    kal = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
    if kal: veriler["kal"] = float(kal.group(1).replace(',', '.'))
    
    tl = text.lower()
    if "dkp" in tl: veriler["malz"] = "DKP"
    elif "galvaniz" in tl: veriler["malz"] = "Galvaniz"
    elif "paslanmaz" in tl: veriler["malz"] = "Paslanmaz 304"
    elif "alu" in tl: veriler["malz"] = "Alüminyum"
    else: veriler["malz"] = "S235JR (Siyah)"
    return veriler

def excel_analiz(file):
    """Metalix veya CypCut Excel Raporlarını Okur"""
    try:
        df = pd.read_excel(file)
        # Sütun isimlerini küçük harfe çevirip arama yapalım
        df.columns = [str(col).lower() for col in df.columns]
        
        veriler = {}
        # Metalix/Cypcut sütun tahminleri (Header keywords)
        for col in df.columns:
            if "time" in col or "süre" in col or "cut" in col:
                # İlk satırdaki süreyi al (Genelde toplam süre ilk satırdadır veya toplamdadır)
                val = str(df[col].iloc[0])
                veriler["sure"] = sureyi_dakikaya_cevir(val)
            if "mat" in col or "malz" in col:
                val = str(df[col].iloc[0]).lower()
                if "dkp" in val: veriler["malz"] = "DKP"
                elif "galv" in val: veriler["malz"] = "Galvaniz"
                elif "pas" in val or "inox" in val: veriler["malz"] = "Paslanmaz 304"
                elif "alu" in val: veriler["malz"] = "Alüminyum"
            if "thic" in col or "kal" in col:
                try: veriler["kal"] = float(str(df[col].iloc[0]).replace(',', '.'))
                except: pass
            # X ve Y boyutları (Genelde Sheet Size veya Used Size olarak geçer)
            if ("len" in col or "boy" in col or "x" in col) and "size" not in col:
                 try: veriler["x"] = float(str(df[col].iloc[0]).replace(',', '.'))
                 except: pass
            if ("wid" in col or "en" in col or "y" in col) and "size" not in col:
                 try: veriler["y"] = float(str(df[col].iloc[0]).replace(',', '.'))
                 except: pass
                 
        return veriler
    except Exception as e:
        st.error(f"Excel okuma hatası: {e}")
        return {}

def word_oku(file):
    try:
        doc = Document(file)
        text = "\n".join([p.text for p in doc.paragraphs] + [" ".join([c.text for c in r.cells]) for t in doc.tables for r in t.rows])
        return regex_taramasi(text)
    except: return {}

def resim_oku(image):
    try:
        img_np = np.array(image)
        if len(img_np.shape) == 3: img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        else: img_gray = img_np
        _, img_thresh = cv2.threshold(img_gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text = pytesseract.image_to_string(Image.fromarray(img_thresh))
        return regex_taramasi(text)
    except: return {}

# --- ARAYÜZ ---

# Müşteri Seçimi (EN ÜSTTE)
st.title("🏭 Lazer Yönetim & Metalix")
col_mus1, col_mus2 = st.columns([3, 1])

with col_mus1:
    kayitli = musteri_listesi_getir()
    secenekler = ["➕ Yeni Müşteri"] + kayitli
    secim = st.selectbox("Müşteri Seçin", secenekler)

with col_mus2:
    if secim == "➕ Yeni Müşteri":
        aktif_musteri = st.text_input("Firma Adı", placeholder="Yeni Firma...")
    else:
        aktif_musteri = secim
        st.info(f"Seçili: **{aktif_musteri}**")

if not aktif_musteri:
    st.warning("Devam etmek için müşteri seçin.")
    st.stop()

st.divider()

# Sekmeler
tab1, tab2, tab3 = st.tabs(["🛒 Yeni Teklif", "🗂️ Müşteri Geçmişi", "⚙️ Ayarlar"])

with tab1:
    col_sol, col_sag = st.columns([1, 1.3])
    
    # SOL: VERİ GİRİŞİ
    with col_sol:
        st.markdown("#### 1. İş Verisi")
        st.caption("Metalix Excel, Word veya Resim yükleyebilirsin.")
        uploaded_file = st.file_uploader("Dosya Yükle", type=['xlsx', 'xls', 'docx', 'jpg', 'png'])
        
        if uploaded_file and "dosya_token" not in st.session_state:
            vals = {}
            if uploaded_file.name.endswith(('.xlsx', '.xls')):
                vals = excel_analiz(uploaded_file)
                st.toast("Excel verisi okundu (Metalix Modu)", icon="📊")
            elif uploaded_file.name.endswith('.docx'):
                vals = word_oku(uploaded_file)
                st.toast("Word verisi okundu", icon="📝")
            else:
                vals = resim_oku(Image.open(uploaded_file))
                st.toast("Resim tarandı", icon="📸")
            
            # Formu Doldur
            if vals:
                for k, v in vals.items():
                    if k in ['x', 'y', 'sure', 'kal', 'malz']:
                        st.session_state[f'form_{k}'] = v
                st.session_state.dosya_token = True
        
        if not uploaded_file and "dosya_token" in st.session_state: del st.session_state.dosya_token
        
        with st.form("ekle_form"):
            c1, c2 = st.columns(2)
            # Malzeme index hatasını önlemek için try-except
            try:
                idx = list(st.session_state.malzeme_db.keys()).index(st.session_state.form_malz)
            except: idx = 0
            
            f_malz = c1.selectbox("Malzeme", list(st.session_state.malzeme_db.keys()), index=idx)
            f_kal = c2.number_input("Kalınlık (mm)", value=float(st.session_state.form_kal))
            
            c3, c4 = st.columns(2)
            f_x = c3.number_input("X (mm)", value=float(st.session_state.form_x))
            f_y = c4.number_input("Y (mm)", value=float(st.session_state.form_y))
            
            c5, c6 = st.columns(2)
            f_sure = c5.number_input("Süre (dk)", value=float(st.session_state.form_sure))
            f_adet = c6.number_input("Adet", 1, min_value=1)
            
            f_fire = st.number_input("Fire (%)", value=0.0)
            
            if st.form_submit_button("Sepete Ekle ⬇️", type="primary", use_container_width=True):
                st.session_state.sepet.append({
                    "Malzeme": f_malz, "K": f_kal, "X": f_x, "Y": f_y, 
                    "Süre": f_sure, "Adet": f_adet, "Fire": f_fire
                })
                st.rerun()

    # SAĞ: HESAP
    with col_sag:
        st.markdown(f"#### 2. Sepet ({len(st.session_state.sepet)} Kalem)")
        
        if st.session_state.sepet:
            df = pd.DataFrame(st.session_state.sepet)
            st.dataframe(df, use_container_width=True, height=200)
            
            if st.button("Temizle", key="clean"):
                st.session_state.sepet = []
                st.rerun()
                
            toplam_tl = 0
            toplam_kg = 0
            
            for p in st.session_state.sepet:
                db = st.session_state.malzeme_db[p["Malzeme"]]
                hacim = p["X"] * p["Y"] * p["K"]
                kg = (hacim * db["yogunluk"]) / 1_000_000 * p["Adet"]
                
                fiyat = db["fiyat"] * st.session_state.dolar_kuru if db["birim"] == "USD" else db["fiyat"]
                fire_kat = 1 / (1 - p["Fire"]/100) if p["Fire"] < 100 else 1
                
                malz_tut = kg * fiyat * fire_kat
                lazer_tut = (p["Süre"] * p["Adet"]) * st.session_state.lazer_dk_ucret
                
                toplam_tl += malz_tut + lazer_tut
                toplam_kg += kg
                
            st.divider()
            c1, c2 = st.columns(2)
            c1.metric("Toplam KG", f"{toplam_kg:.2f}")
            c2.metric("Maliyet", f"{toplam_tl:.2f} TL")
            
            st.write("#### 💰 Satış Fiyatı")
            kc1, kc2 = st.columns(2)
            kar = kc1.number_input("Kâr (%)", 25, step=5)
            ekstra = kc2.number_input("Ekstra Gider", 0)
            
            teklif = (toplam_tl * (1 + kar/100)) + ekstra
            st.success(f"### TOPLAM: {teklif:,.2f} TL")
            
            is_adi = st.text_input("İş Açıklaması", placeholder="Örn: Metalix Proje 1")
            if st.button("💾 Kaydet", type="primary", use_container_width=True):
                kayit_ekle(aktif_musteri, is_adi or "Genel", teklif, f"{len(st.session_state.sepet)} parça")
                st.session_state.sepet = []
                st.success("Kaydedildi!")
                
        else:
            st.info("Sepet boş.")

with tab2:
    st.header(f"{aktif_musteri} - Geçmiş")
    if os.path.exists("musteri_gecmisi.csv"):
        try:
            df_all = pd.read_csv("musteri_gecmisi.csv")
            df_mus = df_all[df_all["Müşteri"] == aktif_musteri]
            st.dataframe(df_mus, use_container_width=True)
            st.info(f"Toplam Hacim: {df_mus['Tutar (TL)'].sum():,.2f} TL")
        except: st.write("Kayıt yok.")

with tab3:
    st.write("### Ayarlar")
    c1, c2 = st.columns(2)
    st.session_state.dolar_kuru = c1.number_input("Dolar", value=st.session_state.dolar_kuru)
    st.session_state.lazer_dk_ucret = c2.number_input("Lazer (TL/dk)", value=st.session_state.lazer_dk_ucret)
    if st.button("Kaydet"): st.toast("Kaydedildi")
