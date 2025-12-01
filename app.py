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
st.set_page_config(page_title="Pro Lazer CRM", layout="wide", page_icon="🏭")

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

# --- SESSION STATE ---
if 'sepet' not in st.session_state: st.session_state.sepet = []
if 'malzeme_db' not in st.session_state: st.session_state.malzeme_db = DEFAULT_MALZEME
if 'dolar_kuru' not in st.session_state: st.session_state.dolar_kuru = 34.50
if 'lazer_dk_ucret' not in st.session_state: st.session_state.lazer_dk_ucret = 20.0
if 'aktif_musteri' not in st.session_state: st.session_state.aktif_musteri = None

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
        zaman_str = str(zaman_str).strip()
        parts = list(map(int, zaman_str.split(':')))
        if len(parts) == 3: return (parts[0] * 60) + parts[1] + (parts[2] / 60)
        elif len(parts) == 2: return parts[0] + (parts[1] / 60)
        return 0.0
    except: return 0.0

# --- ANALİZ MOTORU ---

def regex_taramasi(text):
    veriler = {"x":0.0, "y":0.0, "sure":0.0, "kal":2.0, "malz":"S235JR (Siyah)"}
    try:
        # Süre
        zaman_match = re.search(r'(?:Kesim|Cut|Time|Süre).*?(\d{2}:\d{2}:\d{2})', text, re.IGNORECASE | re.DOTALL)
        if zaman_match: veriler["sure"] = sureyi_dakikaya_cevir(zaman_match.group(1))
        
        # X ve Y
        x_match = re.search(r'[X]\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
        y_match = re.search(r'[Y]\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
        if x_match: veriler["x"] = float(x_match.group(1).replace(',', '.'))
        if y_match: veriler["y"] = float(y_match.group(1).replace(',', '.'))
        
        # Kalınlık
        kal_match = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
        if kal_match: veriler["kal"] = float(kal_match.group(1).replace(',', '.'))
        else:
            kal_alt = re.search(r'(?:Kalınlık|Thick|Sac)\s*[:]?\s*(\d+[.,]?\d*)', text, re.IGNORECASE)
            if kal_alt: veriler["kal"] = float(kal_alt.group(1).replace(',', '.'))

        # Malzeme
        tl = text.lower()
        if "dkp" in tl: veriler["malz"] = "DKP"
        elif "galvaniz" in tl: veriler["malz"] = "Galvaniz"
        elif "paslanmaz" in tl or "304" in tl: veriler["malz"] = "Paslanmaz 304"
        elif "alu" in tl: veriler["malz"] = "Alüminyum"
        elif "st37" in tl or "s235" in tl: veriler["malz"] = "S235JR (Siyah)"

    except: pass
    return veriler

def word_oku(file):
    try:
        doc = Document(file)
        text_list = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                text_list.append(" ".join([cell.text for cell in row.cells]))
        return regex_taramasi("\n".join(text_list))
    except: return regex_taramasi("")

def resim_oku(image):
    try:
        img_np = np.array(image)
        if len(img_np.shape) == 3: img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        else: img_gray = img_np
        _, img_thresh = cv2.threshold(img_gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text = pytesseract.image_to_string(Image.fromarray(img_thresh))
        return regex_taramasi(text)
    except: return regex_taramasi("")

# --- ARAYÜZ ---

st.title("🏭 Lazer CRM - Profesyonel")

# 1. MÜŞTERİ SEÇİMİ
col_m1, col_m2 = st.columns([3, 1])
with col_m1:
    musteriler = musteri_listesi_getir()
    secenekler = ["➕ Yeni Müşteri Ekle"] + musteriler
    secim = st.selectbox("Müşteri Seçimi", secenekler)
with col_m2:
    if secim == "➕ Yeni Müşteri Ekle":
        yeni_ad = st.text_input("Firma Adı", placeholder="Yeni Ad...")
        if yeni_ad: st.session_state.aktif_musteri = yeni_ad
    else:
        st.session_state.aktif_musteri = secim
        st.success(f"**{st.session_state.aktif_musteri}**")

if not st.session_state.aktif_musteri:
    st.info("İşlem yapmak için müşteri seçin.")
    st.stop()

st.divider()

# SEKMELER
tab_is, tab_gecmis, tab_ayar = st.tabs(["🛒 Yeni Teklif", "🗂️ Geçmiş", "⚙️ Ayarlar"])

# --- TAB 1: İŞLEM ALANI ---
with tab_is:
    st.markdown("### 1. Dosya Yükle (Çoklu Seçim)")
    st.caption("Birden fazla fotoğrafı veya Word dosyasını aynı anda seçip yükleyebilirsiniz.")
    
    # accept_multiple_files=True ile çoklu seçim açıldı
    uploaded_files = st.file_uploader("Dosyaları Sürükleyin", type=['docx', 'jpg', 'png', 'jpeg'], accept_multiple_files=True)
    
    if st.button("📥 Seçilen Dosyaları Analiz Et ve Sepete At"):
        if uploaded_files:
            sayac = 0
            for file in uploaded_files:
                vals = {}
                if file.name.endswith('.docx'):
                    vals = word_oku(file)
                else:
                    vals = resim_oku(Image.open(file))
                
                # Sepete Ekle (Varsayılan değerlerle)
                # Eksik verileri varsayılanlarla dolduruyoruz ki tablo boş kalmasın
                yeni_satir = {
                    "Dosya": file.name,
                    "Malzeme": vals.get("malz", "S235JR (Siyah)"),
                    "K (mm)": vals.get("kal", 2.0),
                    "X (mm)": vals.get("x", 0.0),
                    "Y (mm)": vals.get("y", 0.0),
                    "Süre (dk)": vals.get("sure", 0.0),
                    "Adet": 1,
                    "Fire (%)": 0.0,
                    "Birim": "mm"
                }
                st.session_state.sepet.append(yeni_satir)
                sayac += 1
            st.success(f"{sayac} adet dosya sepete eklendi! Aşağıdan düzenleyebilirsiniz.")
        else:
            st.warning("Lütfen önce dosya seçin.")

    st.markdown("---")
    st.markdown("### 2. Sepet & Düzenleme (Excel Modu)")
    
    if len(st.session_state.sepet) > 0:
        # PANDAS DataFrame oluştur
        df_sepet = pd.DataFrame(st.session_state.sepet)
        
        # DATA EDITOR: Excel gibi düzenlenebilir tablo
        # num_rows="dynamic" sayesinde satır silip ekleyebilirsin
        edited_df = st.data_editor(
            df_sepet,
            column_config={
                "Malzeme": st.column_config.SelectboxColumn("Malzeme", options=list(st.session_state.malzeme_db.keys()), required=True),
                "Birim": st.column_config.SelectboxColumn("Birim", options=["mm", "cm", "m"], required=True),
                "Adet": st.column_config.NumberColumn("Adet", min_value=1, step=1),
                "Fire (%)": st.column_config.NumberColumn("Fire %", min_value=0.0, max_value=100.0),
                "X (mm)": st.column_config.NumberColumn("X", format="%.2f"),
                "Y (mm)": st.column_config.NumberColumn("Y", format="%.2f"),
                "Süre (dk)": st.column_config.NumberColumn("Süre", format="%.2f")
            },
            num_rows="dynamic", # SİLME VE EKLEME İZNİ
            use_container_width=True,
            key="editor"
        )
        
        # Hesaplama Butonu
        if st.button("💰 Fiyatı Hesapla", type="primary"):
            toplam_tl = 0
            toplam_kg = 0
            
            # Düzenlenmiş tablo üzerinden hesapla (edited_df)
            for index, row in edited_df.iterrows():
                try:
                    malz_info = st.session_state.malzeme_db[row["Malzeme"]]
                    
                    # Birim çeviri
                    carpan = 1000 if row["Birim"] == "m" else (10 if row["Birim"] == "cm" else 1)
                    x_mm = float(row["X (mm)"]) * carpan
                    y_mm = float(row["Y (mm)"]) * carpan
                    
                    # Ağırlık
                    hacim = x_mm * y_mm * float(row["K (mm)"])
                    kg = (hacim * malz_info["yogunluk"]) / 1_000_000 * int(row["Adet"])
                    
                    # Fiyat
                    fiyat = malz_info["fiyat"] * st.session_state.dolar_kuru if malz_info["birim"] == "USD" else malz_info["fiyat"]
                    
                    # Fire
                    fire_orani = float(row["Fire (%)"])
                    fire_kat = 1 / (1 - fire_orani/100) if fire_orani < 100 else 1
                    
                    malz_tutar = kg * fiyat * fire_kat
                    lazer_tutar = (float(row["Süre (dk)"]) * int(row["Adet"])) * st.session_state.lazer_dk_ucret
                    
                    toplam_tl += malz_tutar + lazer_tutar
                    toplam_kg += kg
                except Exception as e:
                    st.error(f"Satır hesaplama hatası: {e}")
            
            # SONUÇ GÖSTERİMİ
            st.divider()
            col_res1, col_res2 = st.columns(2)
            col_res1.metric("Toplam Ağırlık", f"{toplam_kg:.2f} kg")
            col_res2.metric("Ham Maliyet", f"{toplam_tl:.2f} TL")
            
            st.markdown("#### Satış Ayarları")
            c1, c2 = st.columns(2)
            kar = c1.number_input("Kâr Marjı (%)", value=25, step=5)
            ekstra = c2.number_input("Ekstra Gider (TL)", value=0)
            
            teklif = (toplam_tl * (1 + kar/100)) + ekstra
            st.success(f"### TEKLİF FİYATI: {teklif:,.2f} TL")
            
            # Kaydetme Bölümü
            is_adi = st.text_input("İş Tanımı", placeholder="Örn: 2024 Proje 1")
            if st.button("💾 Müşteriye Kaydet"):
                kayit_ekle(st.session_state.aktif_musteri, is_adi or "Toplu İş", teklif, f"{len(edited_df)} kalem ürün")
                st.session_state.sepet = [] # Temizle
                st.balloons()
                st.success("Kaydedildi!")

    else:
        st.info("Sepetiniz boş. Yukarıdan dosya yükleyin.")

# --- TAB 2: GEÇMİŞ ---
with tab_gecmis:
    st.header(f"🗂️ {st.session_state.aktif_musteri} Geçmişi")
    if os.path.exists("musteri_gecmisi.csv"):
        try:
            df_all = pd.read_csv("musteri_gecmisi.csv")
            df_mus = df_all[df_all["Müşteri"] == st.session_state.aktif_musteri]
            if not df_mus.empty:
                st.dataframe(df_mus, use_container_width=True)
            else: st.warning("Kayıt yok.")
        except: st.error("Dosya hatası.")

# --- TAB 3: AYARLAR ---
with tab_ayar:
    st.write("### Ayarlar")
    c1, c2 = st.columns(2)
    st.session_state.dolar_kuru = c1.number_input("Dolar", value=st.session_state.dolar_kuru)
    st.session_state.lazer_dk_ucret = c2.number_input("Lazer (TL/dk)", value=st.session_state.lazer_dk_ucret)
