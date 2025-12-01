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
    .sub-header {font-size: 20px; font-weight: bold; color: #444;}
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #1E3A8A;}
    </style>
""", unsafe_allow_html=True)

# --- VARSAYILAN VERİTABANI ---
DEFAULT_MALZEME = {
    "S235JR (Siyah)": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
    "DKP": {"fiyat": 0.90, "birim": "USD", "yogunluk": 7.85},
    "Galvaniz": {"fiyat": 1.00, "birim": "USD", "yogunluk": 7.85},
    "Paslanmaz 304": {"fiyat": 3.50, "birim": "USD", "yogunluk": 7.93},
    "Paslanmaz 316": {"fiyat": 4.50, "birim": "USD", "yogunluk": 8.00},
    "Alüminyum": {"fiyat": 3.00, "birim": "USD", "yogunluk": 2.70},
    "ST37": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
}

DEFAULT_ISCILIK = {
    "lazer_dk": 25.0,  # TL/dk
    "abkant_bukum": 15.0, # TL/vuruş
    "kaynak_saat": 400.0, # TL/saat
    "dolar_kuru": 34.50
}

# --- SESSION STATE (Hafıza Yönetimi) ---
if 'sepet' not in st.session_state: st.session_state.sepet = []
if 'malzemeler' not in st.session_state: st.session_state.malzemeler = DEFAULT_MALZEME.copy()
if 'ayarlar' not in st.session_state: st.session_state.ayarlar = DEFAULT_ISCILIK.copy()
if 'form_malz' not in st.session_state: st.session_state.form_malz = "S235JR (Siyah)"

# --- FONKSİYONLAR ---

def musteri_veritabani_yukle():
    """CSV dosyasından müşteri geçmişini çeker"""
    if os.path.exists("ozcelik_data.csv"):
        try:
            return pd.read_csv("ozcelik_data.csv")
        except:
            return pd.DataFrame(columns=["Tarih", "Müşteri", "İş Adı", "Tutar", "Detay"])
    return pd.DataFrame(columns=["Tarih", "Müşteri", "İş Adı", "Tutar", "Detay"])

def is_kaydet(musteri, is_adi, tutar, detay):
    """Yeni işi veritabanına ekler"""
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
    """00:21:34 formatını dakikaya çevirir"""
    try:
        parts = list(map(int, str(zaman_str).strip().split(':')))
        if len(parts) == 3: return (parts[0] * 60) + parts[1] + (parts[2] / 60)
        elif len(parts) == 2: return parts[0] + (parts[1] / 60)
        return 0.0
    except: return 0.0

def cypcut_ocr_analiz(image):
    """CypCut ekran görüntüsüne özel analiz (X, Y, Süre, Fire)"""
    veriler = {}
    try:
        # Görüntü işleme
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

    except Exception as e:
        print(f"OCR Hatası: {e}")
    return veriler

# --- ARAYÜZ (SIDEBAR VE MENÜLER) ---

with st.sidebar:
    st.markdown("## 🏭 ÖZÇELİK ENDÜSTRİ")
    st.info("Lazer Kesim & Büküm Yönetim Sistemi")
    
    st.markdown("---")
    secilen_sayfa = st.radio("MENÜ", ["🧮 Maliyet Hesaplama", "👥 Müşteri Veritabanı", "⚙️ Ayarlar & Malzemeler"])
    
    st.markdown("---")
    st.caption(f"Dolar Kuru: **{st.session_state.ayarlar['dolar_kuru']} TL**")

# --- SAYFA 1: MALİYET HESAPLAMA ---
if secilen_sayfa == "🧮 Maliyet Hesaplama":
    st.markdown('<div class="main-header">Teklif ve Maliyet Hesaplayıcı</div>', unsafe_allow_html=True)
    
    # Müşteri Seçimi
    df_musteri = musteri_veritabani_yukle()
    musteri_listesi = sorted(df_musteri["Müşteri"].unique().tolist())
    
    c1, c2 = st.columns([3, 1])
    with c1:
        secilen_musteri = st.selectbox("Müşteri Seçin (veya yazarak arayın):", ["-- Yeni Müşteri --"] + musteri_listesi)
    with c2:
        if secilen_musteri == "-- Yeni Müşteri --":
            aktif_musteri = st.text_input("Firma Adı:", placeholder="Örn: Yılmaz Makina")
        else:
            aktif_musteri = secilen_musteri
    
    st.markdown("---")

    # GİRİŞ ALANI
    tab_dosya, tab_manuel = st.tabs(["📂 Dosya Yükle (OCR/Word)", "✍️ Manuel Giriş"])
    
    with tab_dosya:
        col_upload, col_preview = st.columns([1, 2])
        with col_upload:
            uploaded_files = st.file_uploader("CypCut Fotosu veya Word Raporu", type=['png', 'jpg', 'jpeg', 'docx'], accept_multiple_files=True)
            if st.button("Analiz Et ve Ekle"):
                if uploaded_files:
                    count = 0
                    for f in uploaded_files:
                        vals = {}
                        if f.name.endswith('.docx'):
                            try:
                                doc = Document(f)
                                vals = cypcut_ocr_analiz(Image.new('RGB', (10, 10))) # Word için dummy
                            except: pass
                        else:
                            vals = cypcut_ocr_analiz(Image.open(f))
                        
                        st.session_state.sepet.append({
                            "Dosya": f.name,
                            "Malzeme": st.session_state.form_malz,
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
        with st.form("manuel_form"):
            c_m1, c_m2, c_m3 = st.columns(3)
            # HATANIN DÜZELTİLDİĞİ YER: value=... parametreleri eklendi
            m_malz = c_m1.selectbox("Malzeme", list(st.session_state.malzemeler.keys()))
            m_kal = c_m2.number_input("Kalınlık (mm)", value=2.0)
            m_adet = c_m3.number_input("Adet", value=1, min_value=1)
            
            c_m4, c_m5, c_m6 = st.columns(3)
            m_en = c_m4.number_input("En (mm)", value=0.0)
            m_boy = c_m5.number_input("Boy (mm)", value=0.0)
            m_sure = c_m6.number_input("Kesim Süresi (dk)", value=0.0)
            
            m_bukum = st.number_input("Büküm Sayısı (Adet başı)", value=0)
            
            if st.form_submit_button("Listeye Ekle"):
                st.session_state.sepet.append({
                    "Dosya": "Manuel",
                    "Malzeme": m_malz, "K (mm)": m_kal, 
                    "En (mm)": m_en, "Boy (mm)": m_boy, 
                    "Adet": m_adet, "Süre (dk)": m_sure, "Fire (%)": 0.0,
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
            
            for idx, row in edited_df.iterrows():
                malz = st.session_state.malzemeler[row["Malzeme"]]
                ayarlar = st.session_state.ayarlar
                
                hacim = row["En (mm)"] * row["Boy (mm)"] * row["K (mm)"]
                kg = (hacim * malz["yogunluk"]) / 1_000_000 * row["Adet"]
                
                fiyat = malz["fiyat"] * ayarlar["dolar_kuru"] if malz["birim"] == "USD" else malz["fiyat"]
                fire_carpan = 1 / (1 - row["Fire (%)"]/100) if row["Fire (%)"] < 100 else 1
                tutar_malzeme = kg * fiyat * fire_carpan
                
                tutar_lazer = (row["Süre (dk)"] * row["Adet"]) * ayarlar["lazer_dk"]
                tutar_bukum = (row["Büküm"] * row["Adet"]) * ayarlar["abkant_bukum"]
                
                satir_toplam = tutar_malzeme + tutar_lazer + tutar_bukum
                toplam_tl += satir_toplam
                toplam_kg += kg
                
            col_res1, col_res2, col_res3 = st.columns(3)
            with col_res1:
                st.markdown('<div class="metric-card">Toplam Ağırlık<br><h3>{:.2f} kg</h3></div>'.format(toplam_kg), unsafe_allow_html=True)
            with col_res2:
                st.markdown('<div class="metric-card">Ham Maliyet<br><h3>{:.2f} TL</h3></div>'.format(toplam_tl), unsafe_allow_html=True)
            
            with col_res3:
                kar = st.number_input("Kâr Oranı (%)", value=25)
                teklif = toplam_tl * (1 + kar/100)
                st.success(f"TEKLİF: {teklif:,.2f} TL")
            
            st.markdown("---")
            is_adi = st.text_input("İş Tanımı / Proje Adı", placeholder="Örn: 2024 Makina Kapakları")
            if st.button("💾 Müşteriye Kaydet ve Temizle"):
                if not aktif_musteri:
                    st.error("Müşteri adı girilmedi!")
                else:
                    is_kaydet(aktif_musteri, is_adi or "Genel Sipariş", teklif, f"{len(edited_df)} kalem, {toplam_kg:.1f}kg")
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
        col_f1, col_f2 = st.columns([1, 2])
        filtre_musteri = col_f1.selectbox("Müşteri Filtrele", ["Tümü"] + sorted(df["Müşteri"].unique().tolist()))
        
        if filtre_musteri != "Tümü":
            df_goster = df[df["Müşteri"] == filtre_musteri]
        else:
            df_goster = df
            
        st.dataframe(df_goster, use_container_width=True, height=500)
        
        if not df_goster.empty:
            toplam_ciro = df_goster["Tutar"].sum()
            st.info(f"Seçili dönem/müşteri toplam iş hacmi: **{toplam_ciro:,.2f} TL**")
    else:
        st.warning("Henüz veritabanında kayıtlı iş yok.")

# --- SAYFA 3: AYARLAR ---
elif secilen_sayfa == "⚙️ Ayarlar & Malzemeler":
    st.markdown('<div class="main-header">Sistem Ayarları</div>', unsafe_allow_html=True)
    
    tab_malzeme, tab_iscilik = st.tabs(["🔩 Malzeme Fiyatları & Yoğunluk", "⚡ İşçilik & Döviz"])
    
    with tab_malzeme:
        st.info("Buradaki değişiklikler yeni hesaplamaları etkiler.")
        
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
        
        if st.button("Malzeme Ayarlarını Kaydet"):
            yeni_sozluk = {}
            for index, row in edited_malz.iterrows():
                yeni_sozluk[row["Malzeme"]] = {
                    "fiyat": row["Fiyat"],
                    "birim": row["Birim"],
                    "yogunluk": row["Yoğunluk"]
                }
            st.session_state.malzemeler = yeni_sozluk
            st.success("Malzeme listesi güncellendi!")

    with tab_iscilik:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Döviz")
            yeni_dolar = st.number_input("Dolar Kuru (TL)", value=float(st.session_state.ayarlar["dolar_kuru"]))
        with c2:
            st.subheader("İşçilik Giderleri (TL)")
            yeni_lazer = st.number_input("Lazer Kesim (TL/dk)", value=float(st.session_state.ayarlar["lazer_dk"]))
            yeni_bukum = st.number_input("Abkant Büküm (TL/vuruş)", value=float(st.session_state.ayarlar["abkant_bukum"]))
            yeni_kaynak = st.number_input("Kaynak (TL/saat)", value=float(st.session_state.ayarlar["kaynak_saat"]))
            
        if st.button("Genel Ayarları Kaydet"):
            st.session_state.ayarlar["dolar_kuru"] = yeni_dolar
            st.session_state.ayarlar["lazer_dk"] = yeni_lazer
            st.session_state.ayarlar["abkant_bukum"] = yeni_bukum
            st.session_state.ayarlar["kaynak_saat"] = yeni_kaynak
            st.success("İşçilik ve döviz kurları güncellendi.")
