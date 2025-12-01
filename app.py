import streamlit as st
import pandas as pd
import cv2
import pytesseract
from PIL import Image
from docx import Document
import re
import requests
import os
import numpy as np
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Pro Lazer Yöneticisi", layout="wide", page_icon="🏭")

# --- SABİTLER ---
DEFAULT_MALZEME_DB = {
    "DKP": {"fiyat": 0.90, "birim": "USD", "yogunluk": 7.85},
    "Siyah Sac": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
    "ST37": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
    "S235JR": {"fiyat": 0.88, "birim": "USD", "yogunluk": 7.85},
    "Galvaniz": {"fiyat": 1.00, "birim": "USD", "yogunluk": 7.85},
    "Paslanmaz (304)": {"fiyat": 3.50, "birim": "USD", "yogunluk": 7.9},
    "Paslanmaz (316)": {"fiyat": 4.50, "birim": "USD", "yogunluk": 8.0},
    "Alüminyum": {"fiyat": 3.00, "birim": "USD", "yogunluk": 2.7}
}

DEFAULT_ISCILIK_DB = {"lazer_dk": 20.0, "abkant": 10.0, "kaynak": 350.0}

# --- SESSION STATE ---
if 'malzeme_db' not in st.session_state: st.session_state.malzeme_db = DEFAULT_MALZEME_DB.copy()
if 'iscilik_db' not in st.session_state: st.session_state.iscilik_db = DEFAULT_ISCILIK_DB.copy()
if 'dolar_kuru' not in st.session_state: st.session_state.dolar_kuru = 34.0
if 'is_listesi' not in st.session_state: st.session_state.is_listesi = []

# --- FONKSİYONLAR ---

def dolar_kuru_getir():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        return float(requests.get(url, timeout=2).json()["rates"]["TRY"])
    except:
        return st.session_state.dolar_kuru

@st.dialog("⚙️ Atölye Ayarları")
def ayarlari_ac():
    st.write("### 💵 Döviz & Fiyatlar")
    col1, col2 = st.columns([2,1])
    with col1:
        yeni_kur = st.number_input("Dolar Kuru (TL)", value=float(st.session_state.dolar_kuru), format="%.4f")
    with col2:
        if st.button("🔄 Kuru Güncelle"):
            st.session_state.dolar_kuru = dolar_kuru_getir()
            st.rerun()
    st.session_state.dolar_kuru = yeni_kur
    
    st.write("### 🔩 Malzeme Veritabanı")
    st.info("Yoğunluk (Y) değerini buradan kalıcı olarak değiştirebilirsin.")
    
    for malz, detay in sorted(st.session_state.malzeme_db.items()):
        c1, c2, c3, c4 = st.columns([2, 1.5, 1.2, 1.5])
        c1.text(malz)
        yeni_f = c2.number_input(f"Fiyat", value=float(detay['fiyat']), key=f"f_{malz}", label_visibility="collapsed")
        yeni_b = c3.selectbox(f"Birim", ["USD", "TL"], index=0 if detay['birim']=="USD" else 1, key=f"b_{malz}", label_visibility="collapsed")
        yeni_y = c4.number_input(f"Yog", value=float(detay['yogunluk']), key=f"y_{malz}", label_visibility="collapsed")
        
        st.session_state.malzeme_db[malz].update({'fiyat': yeni_f, 'birim': yeni_b, 'yogunluk': yeni_y})
    
    st.write("### ⚡ İşçilik (TL)")
    lazer = st.number_input("Lazer Kesim (TL/dk)", value=st.session_state.iscilik_db['lazer_dk'])
    
    st.markdown("---")
    c_save, c_reset = st.columns([3,2])
    if c_save.button("✅ Ayarları Kaydet", type="primary"):
        st.session_state.iscilik_db['lazer_dk'] = lazer
        st.rerun()
    if c_reset.button("⚠️ Sıfırla (Reset)"):
        st.session_state.malzeme_db = DEFAULT_MALZEME_DB.copy()
        st.session_state.iscilik_db = DEFAULT_ISCILIK_DB.copy()
        st.rerun()

def resim_iyilestir(image):
    """Görüntüyü OCR için optimize eder (Siyah/Beyaz yapma ve netleştirme)"""
    # PIL görselini OpenCV formatına çevir
    img_np = np.array(image)
    
    # Renkli ise griye çevir
    if len(img_np.shape) == 3:
        img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        img_gray = img_np
        
    # Gürültü azaltma ve threshold (eşikleme) uygulama
    # Bu işlem yazıları siyah, arka planı beyaz yapar, gri tonları yok eder.
    _, img_thresh = cv2.threshold(img_gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return Image.fromarray(img_thresh)

def sureyi_dakikaya_cevir(zaman_str):
    try:
        if not zaman_str: return 0.0
        parts = list(map(int, str(zaman_str).strip().split(':')))
        if len(parts) == 3: return (parts[0] * 60) + parts[1] + (parts[2] / 60)
        elif len(parts) == 2: return parts[0] + (parts[1] / 60)
        return 0.0
    except: return 0.0

def analiz_et(text):
    """Geliştirilmiş Regex - CypCut formatına özel"""
    veriler = {"sure": 0.0, "x": 0.0, "y": 0.0, "kalinlik": 2.0, "fire": 0.0, "malzeme": "S235JR"}
    
    # 1. SÜRE: "Kesim" kelimesinden sonra gelen saati yakala
    zaman_match = re.search(r'(?:Kesim|Time|Cut)\s*[:|]?\s*(\d{2}:\d{2}:\d{2})', text, re.IGNORECASE)
    if zaman_match: veriler["sure"] = sureyi_dakikaya_cevir(zaman_match.group(1))
    
    # 2. X ve Y: CypCut raporunda "X" ve sayı arasında çok boşluk olabilir.
    # Bu regex şuna bakar: X harfi -> arada boşluklar veya : -> Sayı
    x_match = re.search(r'X\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
    y_match = re.search(r'Y\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
    
    if x_match: veriler["x"] = float(x_match.group(1).replace(',', '.'))
    if y_match: veriler["y"] = float(y_match.group(1).replace(',', '.'))
    
    # 3. KALINLIK: Genelde "3000 x 1500 x 2" gibi yazar
    kalinlik_match = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
    if kalinlik_match: veriler["kalinlik"] = float(kalinlik_match.group(1).replace(',', '.'))
    
    # 4. FİRE
    fire_match = re.search(r'Fire\s*\(%\)\s*(\d+[.,]\d+)', text)
    if fire_match: veriler["fire"] = float(fire_match.group(1).replace(',', '.'))
    
    # 5. MALZEME
    text_lower = text.lower()
    if any(x in text_lower for x in ["dkp", "siyah", "hr", "s235", "st37"]): veriler["malzeme"] = "S235JR"
    elif any(x in text_lower for x in ["galvaniz", "dx51"]): veriler["malzeme"] = "Galvaniz"
    elif any(x in text_lower for x in ["paslanmaz", "inox", "304"]): veriler["malzeme"] = "Paslanmaz (304)"
    elif any(x in text_lower for x in ["alu", "alüminyum"]): veriler["malzeme"] = "Alüminyum"
    
    return veriler

# --- ARAYÜZ ---

col_h1, col_h2 = st.columns([6,1])
with col_h1: st.title("🏭 Pro Lazer Teklif Masası")
with col_h2: 
    if st.button("⚙️ Ayarlar", type="primary"): ayarlari_ac()

st.caption(f"Dolar Kuru: **{st.session_state.dolar_kuru:.4f} TL**")

# --- BÖLÜM 1: İŞ EKLEME ---
with st.expander("➕ Yeni İş Ekle (Fotoğraf, Word veya Manuel)", expanded=True):
    col_up1, col_up2 = st.columns([1, 1])
    
    with col_up1:
        st.markdown("##### 📄 Rapor Yükle")
        uploaded_file = st.file_uploader("Dosya Seç", type=['docx', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.docx'):
                    doc = Document(uploaded_file)
                    full_text = "\n".join([p.text for p in doc.paragraphs] + [" ".join([c.text for c in r.cells]) for t in doc.tables for r in t.rows])
                    v = analiz_et(full_text)
                    kaynak = "Word"
                else:
                    image = Image.open(uploaded_file)
                    # GÖRÜNTÜ İYİLEŞTİRME BURADA DEVREYE GİRİYOR
                    image_processed = resim_iyilestir(image)
                    text = pytesseract.image_to_string(image_processed)
                    v = analiz_et(text)
                    kaynak = "OCR (Görüntü)"
                
                st.info(f"Algılanan: {v['malzeme']} | {v['kalinlik']}mm | Süre: {v['sure']}dk")
                
                # Geçici Ekleme Butonu
                if st.button("📥 Listeye Ekle", key="add_upload"):
                    yeni_is = {
                        "Sil": False, # Silme kutucuğu
                        "İş Adı": uploaded_file.name,
                        "Malzeme": v["malzeme"],
                        "K (mm)": v["kalinlik"],
                        "X": v["x"],
                        "Y": v["y"],
                        "Birim": "mm",
                        "Süre (dk)": v["sure"],
                        "Adet": 1,
                        "Fire (%)": v["fire"]
                    }
                    st.session_state.is_listesi.append(yeni_is)
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Hata: {e}")

    with col_up2:
        st.markdown("##### ✍️ Manuel Ekle")
        with st.form("manuel_form"):
            c1, c2 = st.columns(2)
            m_ad = c1.text_input("İş Adı", "Özel Kesim")
            m_malz = c2.selectbox("Malzeme", list(st.session_state.malzeme_db.keys()))
            c3, c4, c5 = st.columns(3)
            m_kal = c3.number_input("Kalınlık", 2.0)
            m_x = c4.number_input("X", 1000.0)
            m_y = c5.number_input("Y", 500.0)
            c6, c7 = st.columns(2)
            m_sure = c6.number_input("Süre (dk)", 5.0)
            m_adet = c7.number_input("Adet", 1)
            
            if st.form_submit_button("📥 Listeye Ekle"):
                yeni_is = {
                    "Sil": False,
                    "İş Adı": m_ad,
                    "Malzeme": m_malz,
                    "K (mm)": m_kal,
                    "X": m_x,
                    "Y": m_y,
                    "Birim": "mm",
                    "Süre (dk)": m_sure,
                    "Adet": m_adet,
                    "Fire (%)": 0.0
                }
                st.session_state.is_listesi.append(yeni_is)
                st.rerun()

# --- BÖLÜM 2: İŞ LİSTESİ ---
st.markdown("### 📋 Yapılacak İşler Listesi")

if len(st.session_state.is_listesi) > 0:
    df = pd.DataFrame(st.session_state.is_listesi)
    
    # Data Editor (Tablo)
    edited_df = st.data_editor(
        df,
        column_config={
            "Sil": st.column_config.CheckboxColumn("Seç", help="Silmek için seçin", width="small"),
            "Malzeme": st.column_config.SelectboxColumn("Malzeme", options=list(st.session_state.malzeme_db.keys()), required=True),
            "Birim": st.column_config.SelectboxColumn("Birim", options=["mm", "cm", "m"], required=True),
            "Adet": st.column_config.NumberColumn("Plaka Adeti", min_value=1, step=1),
            "Süre (dk)": st.column_config.NumberColumn("Süre (dk)", format="%.1f"),
            "X": st.column_config.NumberColumn("X", format="%.1f"),
            "Y": st.column_config.NumberColumn("Y", format="%.1f"),
        },
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic" # Alternatif silme yöntemi
    )
    
    # --- SİLME VE TEMİZLEME BUTONLARI ---
    col_del1, col_del2, col_space = st.columns([1.5, 1.5, 5])
    
    # 1. Seçilileri Sil Butonu
    if col_del1.button("🗑️ Seçilileri Sil"):
        # Sil kutucuğu işaretli olmayanları filtrele ve listeyi güncelle
        yeni_liste = edited_df[edited_df["Sil"] == False].drop(columns=["Sil"]).to_dict('records')
        # Tekrar Sil sütunu ekleyerek state'e kaydet (çünkü drop ettik)
        for item in yeni_liste: item["Sil"] = False
        st.session_state.is_listesi = yeni_liste
        st.rerun()
        
    # 2. Tümünü Temizle Butonu
    if col_del2.button("🧹 Listeyi Temizle"):
        st.session_state.is_listesi = []
        st.rerun()

    # --- HESAPLAMA ---
    if st.button("💰 HESAPLA VE TEKLİF OLUŞTUR", type="primary", use_container_width=True):
        st.markdown("---")
        total_tl = 0
        total_kg = 0
        detaylar = []
        
        for index, row in edited_df.iterrows():
            if row["Sil"]: continue # Silinmek üzere seçilenleri hesaba katma
            
            # Veri Çekme
            malz = st.session_state.malzeme_db[row["Malzeme"]]
            
            # Birim Çeviri
            carpan = 1000 if row["Birim"] == "m" else (10 if row["Birim"] == "cm" else 1)
            x_mm = row["X"] * carpan
            y_mm = row["Y"] * carpan
            
            # Hesaplar
            hacim = x_mm * y_mm * row["K (mm)"]
            agirlik = (hacim * malz['yogunluk']) / 1_000_000 * row["Adet"]
            
            # Fiyat
            birim_fiyat = malz['fiyat'] * st.session_state.dolar_kuru if malz['birim'] == "USD" else malz['fiyat']
            fire_katsayi = 1 / (1 - (row["Fire (%)"]/100)) if row["Fire (%)"] < 100 else 1
            
            tutar_malzeme = agirlik * birim_fiyat * fire_katsayi
            tutar_lazer = (row["Süre (dk)"] * row["Adet"]) * st.session_state.iscilik_db['lazer_dk']
            
            satir_toplam = tutar_malzeme + tutar_lazer
            
            total_tl += satir_toplam
            total_kg += agirlik
            
            detaylar.append({
                "İş": row["İş Adı"],
                "Ağırlık": f"{agirlik:.1f} kg",
                "Maliyet": f"{satir_toplam:.2f} TL"
            })
            
        # Sonuçlar
        c1, c2, c3 = st.columns(3)
        c1.metric("Toplam Ağırlık", f"{total_kg:.1f} kg")
        c2.metric("Toplam Maliyet", f"{total_tl:.2f} TL")
        
        kar = st.slider("Kâr Marjı (%)", 0, 100, 25)
        satis = total_tl * (1 + kar/100)
        c3.metric("TEKLİF FİYATI", f"{satis:.2f} TL", delta_color="inverse")
        
        with st.expander("Detaylı Döküm"):
            st.table(pd.DataFrame(detaylar))

else:
    st.info("Listede iş yok. Yukarıdan ekleme yapın.")
