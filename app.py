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

# --- SAYFA VE STİL AYARLARI ---
st.set_page_config(page_title="ÖZÇELİK ENDÜSTRİ", layout="wide", page_icon="🏭")

# --- ÖZEL CSS (Görünüm İyileştirme) ---
st.markdown("""
    <style>
    .main-header {font-size: 30px; font-weight: bold; color: #1E3A8A;}
    .metric-card {
        background-color: #ffffff; 
        padding: 15px; 
        border-radius: 10px; 
        border: 1px solid #ddd;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        color: #000000;
        text-align: center;
    }
    .metric-value {
        font-size: 24px; 
        font-weight: bold; 
        color: #1E3A8A;
        margin: 0;
    }
    .metric-label {
        font-size: 14px; 
        color: #555;
        margin-bottom: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# --- GÜNCELLENMİŞ MALZEME LİSTESİ ---
DEFAULT_MALZEME = {
    "Siyah Sac": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
    "Paslanmaz": {"fiyat": 3.50, "birim": "USD", "yogunluk": 7.93},
    "Galvaniz": {"fiyat": 1.00, "birim": "USD", "yogunluk": 7.85},
    "ST52": {"fiyat": 0.95, "birim": "USD", "yogunluk": 7.85},
    "Hardox 400": {"fiyat": 2.00, "birim": "USD", "yogunluk": 7.85},
    "Hardox 450": {"fiyat": 2.20, "birim": "USD", "yogunluk": 7.85},
    "Hardox 500": {"fiyat": 2.50, "birim": "USD", "yogunluk": 7.85},
}

DEFAULT_AYARLAR = {
    "lazer_dk": 25.0,  # TL/dk
    "abkant_bukum": 15.0, # TL/vuruş
    "kaynak_saat": 400.0, # TL/saat
    "dolar_kuru": 34.50,
    "kar_orani": 25.0, # % Varsayılan Kâr
    "kdv_orani": 20.0, # % KDV
    "kdv_ekle": True   # KDV Dahil mi?
}

# --- SESSION STATE ---
if 'sepet' not in st.session_state: st.session_state.sepet = []
if 'malzemeler' not in st.session_state: st.session_state.malzemeler = DEFAULT_MALZEME.copy()
if 'ayarlar' not in st.session_state: st.session_state.ayarlar = DEFAULT_AYARLAR.copy()
if 'form_malz' not in st.session_state: st.session_state.form_malz = "Siyah Sac"

# --- FONKSİYONLAR ---

def musteri_veritabani_yukle():
    if os.path.exists("ozcelik_data.csv"):
        try:
            return pd.read_csv("ozcelik_data.csv")
        except:
            return pd.DataFrame(columns=["Tarih", "Müşteri", "İş Adı", "Tutar", "Detay"])
    return pd.DataFrame(columns=["Tarih", "Müşteri", "İş Adı", "Tutar", "Detay"])

def is_kaydet(musteri, is_adi, tutar, detay):
    df = musteri_veritabani_yukle()
    yeni_kayit = {
        "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Müşteri": musteri,
        "İş Adı": is_adi,
        "Tutar": round(tutar, 2),
        "Detay": detay
    }
    df = pd.concat([df, pd.DataFrame([yeni_kayit])], ignore_index=True)
    df.to_csv("ozcelik_data.csv", index=False)
    return True

def sure_cevir(zaman_str):
    try:
        parts = list(map(int, str(zaman_str).strip().split(':')))
        if len(parts) == 3: return (parts[0] * 60) + parts[1] + (parts[2] / 60)
        elif len(parts) == 2: return parts[0] + (parts[1] / 60)
        return 0.0
    except: return 0.0

def cypcut_ocr_analiz(image):
    veriler = {}
    try:
        img_np = np.array(image)
        if len(img_np.shape) == 3: img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        else: img_gray = img_np
        _, img_thresh = cv2.threshold(img_gray, 150, 255, cv2.THRESH_BINARY)
        text = pytesseract.image_to_string(Image.fromarray(img_thresh))
        
        # Süre
        zaman_match = re.search(r'(?:Kesim|Cut|Time).*?(\d{2}:\d{2}:\d{2})', text, re.IGNORECASE)
        if zaman_match: veriler["sure"] = sure_cevir(zaman_match.group(1))
        
        # X ve Y
        x_match = re.search(r'X\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
        y_match = re.search(r'Y\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
        if x_match: veriler["x"] = float(x_match.group(1).replace(',', '.'))
        if y_match: veriler["y"] = float(y_match.group(1).replace(',', '.'))
        
        # Fire
        fire_match = re.search(r'Fire.*?(\d+[.,]\d+)', text, re.IGNORECASE)
        if fire_match: veriler["fire"] = float(fire_match.group(1).replace(',', '.'))
        
        # Kalınlık
        kal_match = re.search(r'x\s*(\d+[.,]?\d*)\s*$', text, re.MULTILINE)
        if not kal_match:
             kal_match = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
        if kal_match: veriler["kal"] = float(kal_match.group(1).replace(',', '.'))

        # MALZEME TESPİTİ (Yeni Listeye Göre)
        tl = text.lower()
        if "hardox" in tl:
            if "400" in tl: veriler["malz"] = "Hardox 400"
            elif "500" in tl: veriler["malz"] = "Hardox 500"
            else: veriler["malz"] = "Hardox 450"
        elif "st52" in tl: veriler["malz"] = "ST52"
        elif "galvaniz" in tl: veriler["malz"] = "Galvaniz"
        elif "paslanmaz" in tl or "inox" in tl or "304" in tl: veriler["malz"] = "Paslanmaz"
        elif "siyah" in tl or "dkp" in tl or "hr" in tl or "s235" in tl: veriler["malz"] = "Siyah Sac"
        else: veriler["malz"] = "Siyah Sac" # Varsayılan

    except Exception as e:
        print(f"OCR Hatası: {e}")
    return veriler

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## 🏭 ÖZÇELİK ENDÜSTRİ")
    st.info("Lazer Kesim & Büküm Yönetim Sistemi")
    st.markdown("---")
    secilen_sayfa = st.radio("MENÜ", ["🧮 Maliyet Hesaplama", "👥 Müşteri Veritabanı", "⚙️ Ayarlar"])
    st.markdown("---")
    st.caption(f"Dolar: **{st.session_state.ayarlar['dolar_kuru']} TL** | KDV: **{'Var' if st.session_state.ayarlar['kdv_ekle'] else 'Yok'}**")

# --- SAYFA 1: HESAPLAMA ---
if secilen_sayfa == "🧮 Maliyet Hesaplama":
    st.markdown('<div class="main-header">Teklif ve Maliyet Hesaplayıcı</div>', unsafe_allow_html=True)
    
    # Müşteri Seçimi
    df_musteri = musteri_veritabani_yukle()
    musteri_listesi = sorted(df_musteri["Müşteri"].unique().tolist())
    
    c1, c2 = st.columns([3, 1])
    with c1:
        secilen_musteri = st.selectbox("Müşteri Seçin:", ["-- Yeni Müşteri --"] + musteri_listesi)
    with c2:
        if secilen_musteri == "-- Yeni Müşteri --":
            aktif_musteri = st.text_input("Firma Adı:", placeholder="Örn: Yılmaz Makina")
        else:
            aktif_musteri = secilen_musteri
    
    st.markdown("---")

    # TABLAR
    tab_dosya, tab_manuel = st.tabs(["📂 Dosya Yükle", "✍️ Manuel Giriş"])
    
    with tab_dosya:
        col_upload, col_preview = st.columns([1, 2])
        with col_upload:
            uploaded_files = st.file_uploader("Dosyaları Sürükleyin", type=['png', 'jpg', 'jpeg', 'docx'], accept_multiple_files=True)
            if st.button("Analiz Et ve Ekle"):
                if uploaded_files:
                    count = 0
                    for f in uploaded_files:
                        vals = {}
                        if f.name.endswith('.docx'):
                            try:
                                doc = Document(f)
                                vals = cypcut_ocr_analiz(Image.new('RGB', (10, 10))) 
                            except: pass
                        else:
                            vals = cypcut_ocr_analiz(Image.open(f))
                        
                        st.session_state.sepet.append({
                            "Dosya": f.name,
                            "Malzeme": vals.get("malz", "Siyah Sac"),
                            "K (mm)": vals.get("kal", 2.0),
                            "En (mm)": vals.get("y", 1000.0),
                            "Boy (mm)": vals.get("x", 2000.0),
                            "Adet": 1,
                            "Süre (dk)": vals.get("sure", 0.0),
                            "Fire (%)": vals.get("fire", 0.0),
                            "Büküm": 0
                        })
                        count += 1
                    st.success(f"{count} dosya sepete eklendi!")

    with tab_manuel:
        st.markdown("##### 📏 Ölçü Birimi ve Veriler")
        
        birim_secimi = st.radio("Kullanılacak Birim:", ["mm", "cm", "m"], horizontal=True)
        
        with st.form("manuel_form"):
            c_m1, c_m2, c_m3 = st.columns(3)
            m_malz = c_m1.selectbox("Malzeme", list(st.session_state.malzemeler.keys()))
            m_kal = c_m2.number_input("Kalınlık (mm)", value=2.0)
            m_adet = c_m3.number_input("Adet", value=1, min_value=1)
            
            c_m4, c_m5, c_m6 = st.columns(3)
            m_en = c_m4.number_input(f"En ({birim_secimi})", value=0.0)
            m_boy = c_m5.number_input(f"Boy ({birim_secimi})", value=0.0)
            m_sure = c_m6.number_input("Kesim Süresi (dk)", value=0.0)
            
            m_bukum = st.number_input("Büküm Sayısı (Adet başı)", value=0)
            
            if st.form_submit_button("Listeye Ekle"):
                carpan = 1000 if birim_secimi == "m" else (10 if birim_secimi == "cm" else 1)
                
                en_mm = m_en * carpan
                boy_mm = m_boy * carpan
                
                st.session_state.sepet.append({
                    "Dosya": "Manuel",
                    "Malzeme": m_malz, 
                    "K (mm)": m_kal, 
                    "En (mm)": en_mm, 
                    "Boy (mm)": boy_mm, 
                    "Adet": m_adet, 
                    "Süre (dk)": m_sure, 
                    "Fire (%)": 0.0,
                    "Büküm": m_bukum
                })
                st.rerun()

    # SEPET VE HESAPLAMA
    st.markdown("### 🛒 Sipariş Listesi")
    
    if len(st.session_state.sepet) > 0:
        df_sepet = pd.DataFrame(st.session_state.sepet)
        
        edited_df = st.data_editor(
            df_sepet,
            column_config={
                "Malzeme": st.column_config.SelectboxColumn("Malzeme", options=list(st.session_state.malzemeler.keys()), required=True),
                "En (mm)": st.column_config.NumberColumn("En", format="%.1f"),
                "Boy (mm)": st.column_config.NumberColumn("Boy", format="%.1f"),
                "Adet": st.column_config.NumberColumn("Adet", min_value=1),
                "Fire (%)": st.column_config.NumberColumn("Fire %", max_value=100)
            },
            num_rows="dynamic",
            use_container_width=True,
            key="sepet_editor"
        )
        
        if st.button("💰 Hesapla", type="primary"):
            toplam_tl = 0
            toplam_kg = 0
            ayarlar = st.session_state.ayarlar
            
            for idx, row in edited_df.iterrows():
                malz = st.session_state.malzemeler[row["Malzeme"]]
                
                hacim = row["En (mm)"] * row["Boy (mm)"] * row["K (mm)"]
                kg = (hacim * malz["yogunluk"]) / 1_000_000 * row["Adet"]
                
                fiyat = malz["fiyat"] * ayarlar["dolar_kuru"] if malz["birim"] == "USD" else malz["fiyat"]
                fire_carpan = 1 / (1 - row["Fire (%)"]/100) if row["Fire (%)"] < 100 else 1
                tutar_malzeme = kg * fiyat * fire_carpan
                
                tutar_lazer = (row["Süre (dk)"] * row["Adet"]) * ayarlar["lazer_dk"]
                tutar_bukum = (row["Büküm"] * row["Adet"]) * ayarlar["abkant_bukum"]
                
                toplam_tl += tutar_malzeme + tutar_lazer + tutar_bukum
                toplam_kg += kg
            
            # Kâr ve KDV
            kar_tutari = toplam_tl * (ayarlar["kar_orani"] / 100)
            ara_toplam = toplam_tl + kar_tutari
            
            kdv_tutari = 0
            if ayarlar["kdv_ekle"]:
                kdv_tutari = ara_toplam * (ayarlar["kdv_orani"] / 100)
            
            genel_toplam = ara_toplam + kdv_tutari
            
            # GÖRSEL KARTLAR
            st.markdown("---")
            c1, c2, c3, c4 = st.columns(4)
            
            with c1:
                st.markdown(f"""<div class="metric-card"><div class="metric-label">Toplam Ağırlık</div><div class="metric-value">{toplam_kg:.2f} kg</div></div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""<div class="metric-card"><div class="metric-label">Ham Maliyet</div><div class="metric-value">{toplam_tl:.2f} TL</div></div>""", unsafe_allow_html=True)
            with c3:
                st.markdown(f"""<div class="metric-card"><div class="metric-label">Kâr (%{ayarlar['kar_orani']})</div><div class="metric-value">{kar_tutari:.2f} TL</div></div>""", unsafe_allow_html=True)
            with c4:
                kdv_text = f"+ KDV (%{ayarlar['kdv_orani']})" if ayarlar['kdv_ekle'] else "KDV Dahil Değil"
                st.markdown(f"""<div class="metric-card" style="border-left: 5px solid #10B981;"><div class="metric-label">TEKLİF ({kdv_text})</div><div class="metric-value">{genel_toplam:,.2f} TL</div></div>""", unsafe_allow_html=True)

            # KAYDETME
            st.markdown("---")
            is_adi = st.text_input("İş Tanımı / Proje Adı", placeholder="Örn: 2024 Makina Kapakları")
            if st.button("💾 Müşteriye Kaydet ve Temizle"):
                if not aktif_musteri:
                    st.error("Müşteri adı girilmedi!")
                else:
                    is_kaydet(aktif_musteri, is_adi or "Genel Sipariş", genel_toplam, f"{len(edited_df)} kalem, {toplam_kg:.1f}kg")
                    st.session_state.sepet = []
                    st.balloons()
                    st.success("İşlem başarıyla kaydedildi!")
                    st.rerun()
    else:
        st.info("Sepet boş. Yukarıdan manuel veya dosya ekleyerek başlayın.")

# --- SAYFA 2: MÜŞTERİ VERİTABANI ---
elif secilen_sayfa == "👥 Müşteri Veritabanı":
    st.markdown('<div class="main-header">Müşteri Geçmişi</div>', unsafe_allow_html=True)
    df = musteri_veritabani_yukle()
    if not df.empty:
        c1, c2 = st.columns([1, 2])
        filtre_musteri = c1.selectbox("Müşteri Filtrele", ["Tümü"] + sorted(df["Müşteri"].unique().tolist()))
        if filtre_musteri != "Tümü": df = df[df["Müşteri"] == filtre_musteri]
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Henüz veritabanında kayıtlı iş yok.")

# --- SAYFA 3: AYARLAR ---
elif secilen_sayfa == "⚙️ Ayarlar":
    st.markdown('<div class="main-header">Sistem Ayarları</div>', unsafe_allow_html=True)
    
    tab_genel, tab_malz = st.tabs(["⚙️ Genel Ayarlar (Kâr/KDV)", "🔩 Malzeme Fiyatları"])
    
    with tab_genel:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Finansal Ayarlar")
            st.session_state.ayarlar["kar_orani"] = st.number_input("Varsayılan Kâr Oranı (%)", value=st.session_state.ayarlar["kar_orani"])
            st.session_state.ayarlar["kdv_orani"] = st.number_input("KDV Oranı (%)", value=st.session_state.ayarlar["kdv_orani"])
            st.session_state.ayarlar["kdv_ekle"] = st.checkbox("Hesaplamaya KDV Ekle?", value=st.session_state.ayarlar["kdv_ekle"])
            
        with c2:
            st.subheader("İşçilik & Kur")
            st.session_state.ayarlar["dolar_kuru"] = st.number_input("Dolar Kuru (TL)", value=st.session_state.ayarlar["dolar_kuru"])
            st.session_state.ayarlar["lazer_dk"] = st.number_input("Lazer (TL/dk)", value=st.session_state.ayarlar["lazer_dk"])
            st.session_state.ayarlar["abkant_bukum"] = st.number_input("Abkant (TL/vuruş)", value=st.session_state.ayarlar["abkant_bukum"])
            
    with tab_malz:
        malz_list = []
        for k, v in st.session_state.malzemeler.items():
            row = {"Malzeme": k, "Fiyat": v["fiyat"], "Birim": v["birim"], "Yoğunluk": v["yogunluk"]}
            malz_list.append(row)
        
        df_malz = pd.DataFrame(malz_list)
        edited_malz = st.data_editor(
            df_malz,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Birim": st.column_config.SelectboxColumn("Birim", options=["USD", "TL"]),
                "Yoğunluk": st.column_config.NumberColumn("Yoğunluk (g/cm3)", format="%.2f"),
                "Fiyat": st.column_config.NumberColumn("Birim Fiyat", format="%.2f")
            }
        )
        
        if st.button("Malzeme Listesini Güncelle"):
            yeni_sozluk = {}
            for index, row in edited_malz.iterrows():
                yeni_sozluk[row["Malzeme"]] = {
                    "fiyat": row["Fiyat"],
                    "birim": row["Birim"],
                    "yogunluk": row["Yoğunluk"]
                }
            st.session_state.malzemeler = yeni_sozluk
            st.success("Malzeme listesi kaydedildi!")
