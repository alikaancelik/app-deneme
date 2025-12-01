import streamlit as st
import pandas as pd
import cv2
import pytesseract
from PIL import Image
from docx import Document
import re
import requests
import os
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Pro Lazer Atölyesi", layout="wide", page_icon="🏭")

# --- GLOBAL DEĞİŞKENLER VE SESSION STATE ---
if 'malzeme_db' not in st.session_state:
    # Başlangıç veritabanı (İstediğin yeni malzemeler eklendi)
    st.session_state.malzeme_db = {
        "DKP": {"fiyat": 0.90, "birim": "USD", "yogunluk": 7.85},
        "Siyah Sac": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
        "ST37": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
        "S235JR": {"fiyat": 0.88, "birim": "USD", "yogunluk": 7.85},
        "Galvaniz": {"fiyat": 1.00, "birim": "USD", "yogunluk": 7.85},
        "Paslanmaz (304)": {"fiyat": 3.50, "birim": "USD", "yogunluk": 7.9},
        "Paslanmaz (316)": {"fiyat": 4.50, "birim": "USD", "yogunluk": 8.0},
        "Alüminyum": {"fiyat": 3.00, "birim": "USD", "yogunluk": 2.7}
    }

if 'iscilik_db' not in st.session_state:
    st.session_state.iscilik_db = {
        "lazer_dk": 20.0,
        "abkant": 10.0,
        "kaynak": 350.0
    }

if 'dolar_kuru' not in st.session_state:
    st.session_state.dolar_kuru = 34.0

# --- YARDIMCI FONKSİYONLAR ---

def dolar_kuru_getir():
    """Canlı dolar kurunu çekmeye çalışır, olmazsa manuel değeri kullanır"""
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=2)
        data = response.json()
        kur = data["rates"]["TRY"]
        return float(kur)
    except:
        return st.session_state.dolar_kuru

@st.dialog("⚙️ Atölye Ayarları")
def ayarlari_ac():
    st.write("Birim fiyatları ve döviz ayarlarını buradan yönetebilirsiniz.")
    
    # 1. Döviz Ayarı
    col_kur1, col_kur2 = st.columns([2, 1])
    with col_kur1:
        yeni_kur = st.number_input("Dolar Kuru (TL)", value=float(st.session_state.dolar_kuru), format="%.4f")
    with col_kur2:
        if st.button("🔄 Canlı Kur Çek"):
            canli = dolar_kuru_getir()
            st.session_state.dolar_kuru = canli
            st.rerun()
            
    st.session_state.dolar_kuru = yeni_kur
    st.markdown("---")
    
    # 2. Malzeme Fiyatları
    st.subheader("Malzeme Fiyatları")
    # Malzemeleri alfabetik sıraya göre gösterelim ki karışmasın
    sirali_malzemeler = sorted(st.session_state.malzeme_db.items())
    
    for malz, detay in sirali_malzemeler:
        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            st.write(f"**{malz}**")
        with c2:
            yeni_fiyat = st.number_input(f"Fiyat", value=float(detay['fiyat']), key=f"f_{malz}")
        with c3:
            yeni_birim = st.selectbox(f"Birim", ["USD", "TL"], index=0 if detay['birim']=="USD" else 1, key=f"b_{malz}")
        
        # Güncelleme
        st.session_state.malzeme_db[malz]['fiyat'] = yeni_fiyat
        st.session_state.malzeme_db[malz]['birim'] = yeni_birim
    
    st.markdown("---")
    # 3. İşçilikler
    st.subheader("İşçilik Giderleri (TL)")
    lazer = st.number_input("Lazer Kesim (TL/dk)", value=st.session_state.iscilik_db['lazer_dk'])
    abkant = st.number_input("Abkant (Vuruş Başı)", value=st.session_state.iscilik_db['abkant'])
    
    if st.button("Ayarları Kaydet ve Kapat", type="primary"):
        st.session_state.iscilik_db['lazer_dk'] = lazer
        st.session_state.iscilik_db['abkant'] = abkant
        st.rerun()

def kayitlari_yukle():
    if os.path.exists("teklifler.csv"):
        return pd.read_csv("teklifler.csv")
    return pd.DataFrame(columns=["Tarih", "Musteri", "Is_Adi", "Malzeme", "Tutar", "Durum"])

def kayit_ekle(musteri, is_adi, malzeme, tutar, durum):
    df = kayitlari_yukle()
    yeni_kayit = {
        "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Musteri": musteri if musteri else "Ayaklı Müşteri",
        "Is_Adi": is_adi,
        "Malzeme": malzeme,
        "Tutar": round(tutar, 2),
        "Durum": durum
    }
    df = pd.concat([df, pd.DataFrame([yeni_kayit])], ignore_index=True)
    df.to_csv("teklifler.csv", index=False)

# OCR ve Analiz Fonksiyonları
def sureyi_dakikaya_cevir(zaman_str):
    try:
        if not zaman_str: return 0.0
        zaman_str = str(zaman_str).strip()
        parts = list(map(int, zaman_str.split(':')))
        if len(parts) == 3: return (parts[0] * 60) + parts[1] + (parts[2] / 60)
        elif len(parts) == 2: return parts[0] + (parts[1] / 60)
        return 0.0
    except: return 0.0

def analiz_et(text):
    veriler = {"sure": 0.0, "x": 0.0, "y": 0.0, "kalinlik": 2.0, "adet": 1, "fire": 0.0, "malzeme": "DKP"}
    
    zaman_match = re.search(r'(\d{2}:\d{2}:\d{2})', text)
    if zaman_match: veriler["sure"] = sureyi_dakikaya_cevir(zaman_match.group(1))
    
    x_match = re.search(r'X\s*[:]?\s*(\d+[.,]\d+)', text)
    y_match = re.search(r'Y\s*[:]?\s*(\d+[.,]\d+)', text)
    if x_match: veriler["x"] = float(x_match.group(1).replace(',', '.'))
    if y_match: veriler["y"] = float(y_match.group(1).replace(',', '.'))
    
    kalinlik_match = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
    if kalinlik_match: veriler["kalinlik"] = float(kalinlik_match.group(1).replace(',', '.'))
    
    adet_match = re.search(r'Adet\s*[:]?\s*(\d+)', text)
    if adet_match: veriler["adet"] = int(adet_match.group(1))
    
    fire_match = re.search(r'Fire\s*\(%\)\s*(\d+[.,]\d+)', text)
    if fire_match: veriler["fire"] = float(fire_match.group(1).replace(',', '.'))
    
    text_lower = text.lower()
    # Malzeme tahmin listesini genişlettik
    if any(x in text_lower for x in ["dkp", "siyah", "hr", "s235", "st37"]): veriler["malzeme"] = "S235JR"
    elif any(x in text_lower for x in ["galvaniz", "dx51"]): veriler["malzeme"] = "Galvaniz"
    elif any(x in text_lower for x in ["paslanmaz", "inox", "304"]): veriler["malzeme"] = "Paslanmaz (304)"
    elif any(x in text_lower for x in ["alu", "alüminyum"]): veriler["malzeme"] = "Alüminyum"
    
    return veriler

# --- ANA UYGULAMA ---

col_head1, col_head2 = st.columns([5, 1])
with col_head1:
    st.title("🏭 Lazer Kesim & Teklif Sistemi")
with col_head2:
    if st.button("⚙️ Ayarlar", type="primary"):
        ayarlari_ac()

st.info(f"💵 Güncel Dolar Kuru: **{st.session_state.dolar_kuru:.4f} TL**")

tab_hesap, tab_gecmis = st.tabs(["📝 Yeni Hesaplama", "🗂️ Kayıtlar & Müşteriler"])

with tab_hesap:
    uploaded_file = st.file_uploader("Rapor Yükle (Word veya Resim)", type=['docx', 'png', 'jpg', 'jpeg'])
    v = {"sure": 0.0, "x": 0.0, "y": 0.0, "kalinlik": 2.0, "adet": 1, "fire": 0.0, "malzeme": "DKP"}
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.docx'):
                doc = Document(uploaded_file)
                full_text = "\n".join([p.text for p in doc.paragraphs] + [" ".join([c.text for c in r.cells]) for t in doc.tables for r in t.rows])
                v = analiz_et(full_text)
                st.success("Word dosyası verileri çekildi.")
            else:
                image = Image.open(uploaded_file)
                text = pytesseract.image_to_string(image)
                v = analiz_et(text)
                st.success("Görüntü verileri çekildi.")
        except Exception as e:
            st.error(f"Hata: {e}")

    st.markdown("#### 1. İş Detayları")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Yeni malzemeler listeye geldi
        secilen_malzeme = st.selectbox("Malzeme", list(st.session_state.malzeme_db.keys()), index=0)
        kalinlik = st.number_input("Kalınlık (mm)", value=float(v["kalinlik"] if v["kalinlik"]>0 else 2.0))
        adet = st.number_input("Plaka/Parça Adeti", value=int(v["adet"]))
        
    with col2:
        # BİRİM SEÇİMİ EKLENDİ
        birim = st.radio("Ölçü Birimi", ["mm", "cm", "m"], horizontal=True)
        
        # Kullanıcı ne seçerse seçsin biz onu etikette gösterelim
        x_input = st.number_input(f"Kullanılan X ({birim})", value=float(v["x"]))
        y_input = st.number_input(f"Kullanılan Y ({birim})", value=float(v["y"]))
        
        # Arka planda hepsini mm'ye çevirelim ki formüller bozulmasın
        if birim == "cm":
            x_mm = x_input * 10
            y_mm = y_input * 10
        elif birim == "m":
            x_mm = x_input * 1000
            y_mm = y_input * 1000
        else: # zaten mm
            x_mm = x_input
            y_mm = y_input

    with col3:
        fire_orani = st.number_input("Fire Oranı (%)", value=float(v["fire"]))
        kesim_suresi = st.number_input("Kesim Süresi (dk)", value=float(v["sure"]))
        ekstra_tl = st.number_input("Ekstra Gider (TL)", value=0.0)
        kar_marji = st.slider("Kâr Marjı (%)", 0, 100, 25)

    # HESAPLAMA MOTORU
    malzeme_bilgi = st.session_state.malzeme_db[secilen_malzeme]
    birim_fiyat = malzeme_bilgi['fiyat']
    
    if malzeme_bilgi['birim'] == "USD":
        birim_fiyat_tl = birim_fiyat * st.session_state.dolar_kuru
    else:
        birim_fiyat_tl = birim_fiyat
        
    # Ağırlık (mm cinsinden hesaplıyoruz)
    yogunluk = malzeme_bilgi['yogunluk']
    hacim_mm3 = x_mm * y_mm * kalinlik
    agirlik_kg = (hacim_mm3 * yogunluk) / 1_000_000
    toplam_kg = agirlik_kg * adet
    
    fire_carpan = 1 / (1 - (fire_orani/100)) if fire_orani < 100 else 1
    
    malzeme_maliyeti = toplam_kg * birim_fiyat_tl * fire_carpan
    lazer_maliyeti = kesim_suresi * st.session_state.iscilik_db['lazer_dk']
    
    ham_maliyet = malzeme_maliyeti + lazer_maliyeti + ekstra_tl
    satis_fiyati = ham_maliyet * (1 + kar_marji/100)

    st.markdown("---")
    # SONUÇ GÖSTERİMİ
    c_res1, c_res2, c_res3 = st.columns(3)
    c_res1.metric("Toplam Ağırlık", f"{toplam_kg:.2f} kg")
    c_res2.metric("Ham Maliyet", f"{ham_maliyet:.2f} TL")
    c_res3.metric("SATIŞ FİYATI", f"{satis_fiyati:.2f} TL", delta_color="inverse")

    # KAYIT BÖLÜMÜ
    st.markdown("#### 💾 Kaydet ve Arşivle")
    with st.expander("Bu Teklifi Kaydet", expanded=True):
        kc1, kc2, kc3 = st.columns([2, 2, 1])
        with kc1:
            musteri_adi = st.text_input("Firma / Müşteri Adı", placeholder="Boş ise 'Ayaklı Müşteri'")
        with kc2:
            is_adi = st.text_input("İşin Adı / Tanımı", placeholder="Örn: 2mm ST37 Flanş")
        with kc3:
            kaydet_btn = st.button("Sisteme Kaydet", type="primary")
            
        if kaydet_btn:
            kayit_ekle(musteri_adi, is_adi, f"{secilen_malzeme} {kalinlik}mm", satis_fiyati, "Teklif Verildi")
            st.success("✅ Kayıt başarıyla eklendi! 'Kayıtlar' sekmesinden görebilirsiniz.")

with tab_gecmis:
    st.header("🗂️ Müşteri ve İş Kayıtları")
    df = kayitlari_yukle()
    
    firmalar = ["Tümü"] + list(df["Musteri"].unique()) if not df.empty else ["Tümü"]
    secilen_firma = st.selectbox("Firmaya Göre Filtrele", firmalar)
    
    if secilen_firma != "Tümü":
        gosterilecek_df = df[df["Musteri"] == secilen_firma]
    else:
        gosterilecek_df = df
        
    st.dataframe(gosterilecek_df, use_container_width=True)
    
    if not gosterilecek_df.empty:
        toplam_is_hacmi = gosterilecek_df["Tutar"].sum()
        st.caption(f"Görüntülenen Toplam İş Hacmi: {toplam_is_hacmi:,.2f} TL")
        with open("teklifler.csv", "rb") as file:
            st.download_button("Excel/CSV Olarak İndir", file, "teklifler.csv")
