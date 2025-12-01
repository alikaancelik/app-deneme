import streamlit as st
import pandas as pd
import cv2
import numpy as np
import pytesseract
from PIL import Image
from docx import Document
import re

# Sayfa Ayarları
st.set_page_config(page_title="Pro Lazer Teklif (Hibrit)", layout="wide", page_icon="🏭")

# --- YARDIMCI FONKSİYONLAR ---

def sureyi_dakikaya_cevir(zaman_str):
    """00:21:34 formatını dakikaya çevirir"""
    try:
        if not zaman_str: return 0.0
        zaman_str = str(zaman_str).strip()
        parts = list(map(int, zaman_str.split(':')))
        if len(parts) == 3: return (parts[0] * 60) + parts[1] + (parts[2] / 60)
        elif len(parts) == 2: return parts[0] + (parts[1] / 60)
        return 0.0
    except:
        return 0.0

def verileri_temizle(text):
    """Metin içinden regex ile verileri çeker (Hem Word hem Resim için ortak mantık)"""
    veriler = {
        "sure": 0.0, "x": 0.0, "y": 0.0, "kalinlik": 0.0, 
        "adet": 1, "fire": 0.0, "malzeme": "Belirsiz"
    }
    
    # 1. Süre (Kesim 00:21:34)
    zaman_match = re.search(r'(\d{2}:\d{2}:\d{2})', text)
    if zaman_match: veriler["sure"] = sureyi_dakikaya_cevir(zaman_match.group(1))
    
    # 2. X ve Y
    x_match = re.search(r'X\s*[:]?\s*(\d+[.,]\d+)', text)
    y_match = re.search(r'Y\s*[:]?\s*(\d+[.,]\d+)', text)
    if x_match: veriler["x"] = float(x_match.group(1).replace(',', '.'))
    if y_match: veriler["y"] = float(y_match.group(1).replace(',', '.'))
    
    # 3. Kalınlık (3000 x 1500 x 1)
    kalinlik_match = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
    if kalinlik_match: veriler["kalinlik"] = float(kalinlik_match.group(1).replace(',', '.'))
    
    # 4. Adet ve Fire
    adet_match = re.search(r'Adet\s*[:]?\s*(\d+)', text)
    if adet_match: veriler["adet"] = int(adet_match.group(1))
    
    fire_match = re.search(r'Fire\s*\(%\)\s*(\d+[.,]\d+)', text)
    if fire_match: veriler["fire"] = float(fire_match.group(1).replace(',', '.'))
    
    # 5. Malzeme Tahmini
    text_lower = text.lower()
    if any(x in text_lower for x in ["dkp", "steel", "siyah", "hr"]): veriler["malzeme"] = "DKP"
    elif any(x in text_lower for x in ["paslanmaz", "inox", "304", "316"]): veriler["malzeme"] = "Paslanmaz"
    elif any(x in text_lower for x in ["alu", "alüminyum"]): veriler["malzeme"] = "Alüminyum"
        
    return veriler

def resimden_oku(image):
    """Görüntüyü işler ve metne çevirir"""
    text = pytesseract.image_to_string(image)
    return veriler_temizle(text)

def wordden_oku(file):
    """Word dosyasını işler ve metne çevirir"""
    doc = Document(file)
    full_text = []
    for para in doc.paragraphs: full_text.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            full_text.append(" ".join([cell.text for cell in row.cells]))
    return veriler_temizle("\n".join(full_text))

# --- ARAYÜZ ---
st.sidebar.header("⚙️ Ayarlar")
with st.sidebar.expander("Fiyatlar ($/TL)", expanded=True):
    dolar_kuru = st.number_input("Dolar Kuru", value=32.0)
    f_dkp = st.number_input("DKP ($/kg)", value=0.90)
    f_pas = st.number_input("Paslanmaz ($/kg)", value=3.50)
    f_alu = st.number_input("Alüminyum ($/kg)", value=3.00)
    lazer_dk_tl = st.number_input("Lazer (TL/dk)", value=20.0)

st.title("🏭 Çoklu Rapor Analizcisi")
st.caption("İster Fotoğraf (.jpg), İster Dosya (.docx) yükleyin.")

uploaded_file = st.file_uploader("Dosya Seçin", type=['png', 'jpg', 'jpeg', 'docx'])

# Varsayılanlar
v = {"sure": 0.0, "x": 0.0, "y": 0.0, "kalinlik": 2.0, "adet": 1, "fire": 0.0, "malzeme": "DKP"}
kaynak_tipi = ""

if uploaded_file:
    with st.spinner('Dosya analiz ediliyor...'):
        try:
            if uploaded_file.name.endswith('.docx'):
                v = wordden_oku(uploaded_file)
                kaynak_tipi = "Word Dosyası"
                st.success("Word dosyası başarıyla okundu.")
            else:
                image = Image.open(uploaded_file)
                st.image(image, width=300)
                v = resimden_oku(image)
                kaynak_tipi = "Görüntü İşleme (OCR)"
                st.success("Fotoğraf başarıyla tarandı.")
                
        except Exception as e:
            st.error(f"Hata oluştu: {e}")

st.markdown("---")

# SONUÇ VE DÜZENLEME EKRANI
col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("1. Malzeme")
    # Malzeme listesindeki indexi bulma hatasını önlemek için kontrol
    liste_malzeme = ["DKP", "Paslanmaz", "Alüminyum"]
    secili_index = 0
    if v["malzeme"] in liste_malzeme: secili_index = liste_malzeme.index(v["malzeme"])
    
    r_malzeme = st.selectbox("Tür", liste_malzeme, index=secili_index)
    r_kalinlik = st.number_input("Kalınlık (mm)", value=float(v["kalinlik"] if v["kalinlik"]>0 else 2.0))
    r_adet = st.number_input("Plaka Adeti", value=int(v["adet"]))

with col2:
    st.subheader("2. Kullanım & Fire")
    r_x = st.number_input("X (mm)", value=float(v["x"]))
    r_y = st.number_input("Y (mm)", value=float(v["y"]))
    r_fire = st.number_input("Fire (%)", value=float(v["fire"]))
    
    # Fire 0 geldiyse ve boyutlar varsa tahmini hesapla
    if r_fire == 0 and r_x > 0:
        tahmini = ((4.5 - (r_x*r_y/1000000))/4.5)*100 # 3000x1500=4.5m2 varsayımı
        if tahmini > 0: st.caption(f"Otomatik Hesaplanan Tahmini Fire: %{tahmini:.1f}")

with col3:
    st.subheader("3. İşçilik")
    r_sure = st.number_input("Kesim Süresi (dk)", value=float(v["sure"]))
    r_ekstra = st.number_input("Ekstra Gider (TL)", value=0.0)

# HESAPLA
if st.button("HESAPLA", type="primary"):
    # Yoğunluklar
    rho = {"DKP": 7.85, "Paslanmaz": 7.9, "Alüminyum": 2.7}[r_malzeme]
    kg_fiyat = {"DKP": f_dkp, "Paslanmaz": f_pas, "Alüminyum": f_alu}[r_malzeme]
    
    # Ağırlık (Net parça ağırlığı değil, kullanılan plaka ağırlığı)
    kullanilan_hacim = r_x * r_y * r_kalinlik
    kullanilan_kg = (kullanilan_hacim * rho) / 1_000_000
    toplam_kg = kullanilan_kg * r_adet
    
    # Fire Maliyeti Hesabı
    # Eğer fire %20 ise, 100 birimlik malzemenin maliyeti 100/0.8 olur.
    fire_carpan = 1 / (1 - (r_fire/100)) if r_fire < 100 else 1
    
    malzeme_tl = toplam_kg * kg_fiyat * dolar_kuru * fire_carpan
    lazer_tl = r_sure * lazer_dk_tl
    toplam_maliyet = malzeme_tl + lazer_tl + r_ekstra
    
    st.info(f"Hesaplama Kaynağı: {kaynak_tipi}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam KG", f"{toplam_kg:.2f}")
    c2.metric("Maliyet", f"{toplam_maliyet:.2f} TL")
    
    kar = st.slider("Kâr %", 0, 100, 25)
    satis = toplam_maliyet * (1 + kar/100)
    c3.metric("TEKLİF", f"{satis:.2f} TL", delta_color="inverse")
