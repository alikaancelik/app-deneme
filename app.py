import streamlit as st
import pandas as pd
import cv2
import pytesseract
from PIL import Image
from docx import Document
import re
import os
import numpy as np
import json
import requests
from datetime import datetime

# --- SAYFA AYARLARI ---
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
    .metric-value {font-size: 24px; font-weight: bold; color: #1E3A8A; margin: 0;}
    .metric-label {font-size: 14px; color: #555; margin-bottom: 5px;}
    /* Tablo başlıklarını düzenle */
    th {background-color: #f0f2f6 !important;}
    </style>
""", unsafe_allow_html=True)

# --- KALICI AYARLAR (JSON SİSTEMİ) ---
CONFIG_FILE = "config.json"
DATA_FILE = "ozcelik_data.csv"

DEFAULT_CONFIG = {
    "malzemeler": {
        "Siyah Sac": {"fiyat": 0.85, "birim": "USD", "yogunluk": 7.85},
        "Paslanmaz": {"fiyat": 3.50, "birim": "USD", "yogunluk": 7.93},
        "Galvaniz": {"fiyat": 1.00, "birim": "USD", "yogunluk": 7.85},
        "ST52": {"fiyat": 0.95, "birim": "USD", "yogunluk": 7.85},
        "Hardox 400": {"fiyat": 2.00, "birim": "USD", "yogunluk": 7.85},
        "Hardox 450": {"fiyat": 2.20, "birim": "USD", "yogunluk": 7.85},
        "Hardox 500": {"fiyat": 2.50, "birim": "USD", "yogunluk": 7.85},
    },
    "ayarlar": {
        "lazer_dk": 25.0,
        "abkant_bukum": 15.0,
        "kaynak_saat": 400.0,
        "dolar_kuru": 34.50,
        "kar_orani": 25.0,
        "kdv_orani": 20.0,
        "kdv_ekle": True
    }
}

def ayarlari_yukle():
    """Ayarları dosyadan yükler, yoksa varsayılanı oluşturur"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()

def ayarlari_kaydet(config):
    """Ayarları dosyaya kalıcı olarak yazar"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# BAŞLANGIÇTA AYARLARI YÜKLE
if 'config' not in st.session_state:
    st.session_state.config = ayarlari_yukle()

# Session State Tanımları
if 'sepet' not in st.session_state: st.session_state.sepet = []
if 'form_malz' not in st.session_state: st.session_state.form_malz = "Siyah Sac"
if 'aktif_musteri' not in st.session_state: st.session_state.aktif_musteri = None

# --- YARDIMCI FONKSİYONLAR ---

def canli_dolar_cek():
    """API'den güncel kuru çeker"""
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=2)
        data = response.json()
        kur = data["rates"]["TRY"]
        return float(kur)
    except:
        return None

def musteri_veritabani_yukle():
    if os.path.exists(DATA_FILE):
        try:
            return pd.read_csv(DATA_FILE)
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
    df.to_csv(DATA_FILE, index=False)
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
        
        zaman_match = re.search(r'(?:Kesim|Cut|Time).*?(\d{2}:\d{2}:\d{2})', text, re.IGNORECASE)
        if zaman_match: veriler["sure"] = sure_cevir(zaman_match.group(1))
        
        x_match = re.search(r'X\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
        y_match = re.search(r'Y\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
        if x_match: veriler["x"] = float(x_match.group(1).replace(',', '.'))
        if y_match: veriler["y"] = float(y_match.group(1).replace(',', '.'))
        
        fire_match = re.search(r'Fire.*?(\d+[.,]\d+)', text, re.IGNORECASE)
        if fire_match: veriler["fire"] = float(fire_match.group(1).replace(',', '.'))
        
        kal_match = re.search(r'x\s*(\d+[.,]?\d*)\s*$', text, re.MULTILINE)
        if not kal_match: kal_match = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
        if kal_match: veriler["kal"] = float(kal_match.group(1).replace(',', '.'))

        tl = text.lower()
        if "hardox" in tl:
            if "400" in tl: veriler["malz"] = "Hardox 400"
            elif "500" in tl: veriler["malz"] = "Hardox 500"
            else: veriler["malz"] = "Hardox 450"
        elif "st52" in tl: veriler["malz"] = "ST52"
        elif "galvaniz" in tl: veriler["malz"] = "Galvaniz"
        elif "paslanmaz" in tl: veriler["malz"] = "Paslanmaz"
        else: veriler["malz"] = "Siyah Sac"
    except Exception as e: print(f"OCR: {e}")
    return veriler

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## 🏭 ÖZÇELİK ENDÜSTRİ")
    st.info("Lazer Kesim Yönetim Sistemi v2.0")
    st.markdown("---")
    secilen_sayfa = st.radio("MENÜ", ["🧮 Maliyet Hesaplama", "👥 Müşteri Veritabanı", "⚙️ Ayarlar (Kalıcı)"])
    st.markdown("---")
    
    # Canlı Dolar Butonu
    col_d1, col_d2 = st.columns([2, 1])
    with col_d1:
        st.metric("Dolar Kuru", f"{st.session_state.config['ayarlar']['dolar_kuru']:.2f}")
    with col_d2:
        if st.button("🔄", help="Kuru Güncelle"):
            yeni_kur = canli_dolar_cek()
            if yeni_kur:
                st.session_state.config['ayarlar']['dolar_kuru'] = yeni_kur
                ayarlari_kaydet(st.session_state.config)
                st.rerun()
            else:
                st.error("Çekilemedi")

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
        
        # Müşteriyi Hafızaya Al
        if aktif_musteri:
            st.session_state.aktif_musteri = aktif_musteri
    
    st.markdown("---")

    # GİRİŞ ALANI
    tab_dosya, tab_manuel = st.tabs(["📂 Dosya Yükle", "✍️ Manuel Giriş"])
    
    with tab_dosya:
        uploaded_files = st.file_uploader("Dosyaları Sürükleyin", type=['png', 'jpg', 'jpeg', 'docx'], accept_multiple_files=True)
        if st.button("Analiz Et ve Ekle"):
            if uploaded_files:
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
                st.success("Dosyalar sepete eklendi!")

    with tab_manuel:
        st.markdown("##### 📏 Ölçü Birimi ve Veriler")
        birim_secimi = st.radio("Birim:", ["mm", "cm", "m"], horizontal=True)
        
        with st.form("manuel_form"):
            c_m1, c_m2, c_m3 = st.columns(3)
            # value=None yapıyoruz ki kutu BOŞ gelsin, "0.00" silmekle uğraşma
            m_malz = c_m1.selectbox("Malzeme", list(st.session_state.config['malzemeler'].keys()))
            m_kal = c_m2.number_input("Kalınlık (mm)", value=None, placeholder="Örn: 2")
            m_adet = c_m3.number_input("Adet", value=None, min_value=1, placeholder="Örn: 1")
            
            c_m4, c_m5, c_m6 = st.columns(3)
            m_en = c_m4.number_input(f"En ({birim_secimi})", value=None, placeholder="Genişlik")
            m_boy = c_m5.number_input(f"Boy ({birim_secimi})", value=None, placeholder="Uzunluk")
            m_sure = c_m6.number_input("Kesim Süresi (dk)", value=None, placeholder="Dakika")
            
            m_bukum = st.number_input("Büküm Sayısı (Adet başı)", value=None, placeholder="0")
            
            if st.form_submit_button("Listeye Ekle"):
                # Boş bırakılanları 0 kabul et
                carpan = 1000 if birim_secimi == "m" else (10 if birim_secimi == "cm" else 1)
                
                en_val = float(m_en) if m_en is not None else 0.0
                boy_val = float(m_boy) if m_boy is not None else 0.0
                kal_val = float(m_kal) if m_kal is not None else 0.0
                adet_val = int(m_adet) if m_adet is not None else 1
                sure_val = float(m_sure) if m_sure is not None else 0.0
                bukum_val = int(m_bukum) if m_bukum is not None else 0
                
                st.session_state.sepet.append({
                    "Dosya": "Manuel",
                    "Malzeme": m_malz, 
                    "K (mm)": kal_val, 
                    "En (mm)": en_val * carpan, 
                    "Boy (mm)": boy_val * carpan, 
                    "Adet": adet_val, 
                    "Süre (dk)": sure_val, 
                    "Fire (%)": 0.0,
                    "Büküm": bukum_val
                })
                st.rerun()

    # SEPET VE HESAPLAMA
    st.markdown("### 🛒 Sipariş Listesi")
    
    if len(st.session_state.sepet) > 0:
        df_sepet = pd.DataFrame(st.session_state.sepet)
        
        # Excel Tarzı Düzenlenebilir Tablo
        edited_df = st.data_editor(
            df_sepet,
            column_config={
                "Malzeme": st.column_config.SelectboxColumn("Malzeme", options=list(st.session_state.config['malzemeler'].keys()), required=True),
                "En (mm)": st.column_config.NumberColumn("En", format="%.1f"),
                "Boy (mm)": st.column_config.NumberColumn("Boy", format="%.1f"),
                "Adet": st.column_config.NumberColumn("Adet", min_value=1),
                "Fire (%)": st.column_config.NumberColumn("Fire %", max_value=100)
            },
            num_rows="dynamic", # SİLME BURADAN YAPILIR
            use_container_width=True,
            key="sepet_editor"
        )
        
        # HESAPLA BUTONU
        if st.button("💰 Hesapla", type="primary"):
            # ÖNEMLİ: Düzenlenmiş tabloyu (edited_df) sepete geri kaydedelim ki silinenler gitsin
            st.session_state.sepet = edited_df.to_dict('records')
            
            toplam_tl = 0
            toplam_kg = 0
            cfg = st.session_state.config
            
            for row in st.session_state.sepet:
                malz = cfg['malzemeler'][row["Malzeme"]]
                ayarlar = cfg['ayarlar']
                
                # None kontrolü (Düzenlerken boş bırakılırsa)
                en = float(row["En (mm)"] or 0)
                boy = float(row["Boy (mm)"] or 0)
                kal = float(row["K (mm)"] or 0)
                adet = int(row["Adet"] or 1)
                sure = float(row["Süre (dk)"] or 0)
                bukum = int(row["Büküm"] or 0)
                fire = float(row["Fire (%)"] or 0)
                
                hacim = en * boy * kal
                kg = (hacim * malz["yogunluk"]) / 1_000_000 * adet
                
                fiyat = malz["fiyat"] * ayarlar["dolar_kuru"] if malz["birim"] == "USD" else malz["fiyat"]
                fire_carpan = 1 / (1 - fire/100) if fire < 100 else 1
                tutar_malzeme = kg * fiyat * fire_carpan
                
                tutar_lazer = (sure * adet) * ayarlar["lazer_dk"]
                tutar_bukum = (bukum * adet) * ayarlar["abkant_bukum"]
                
                toplam_tl += tutar_malzeme + tutar_lazer + tutar_bukum
                toplam_kg += kg
            
            # Kâr ve KDV
            ayarlar = cfg['ayarlar']
            kar_tutari = toplam_tl * (ayarlar["kar_orani"] / 100)
            ara_toplam = toplam_tl + kar_tutari
            
            kdv_tutari = 0
            if ayarlar["kdv_ekle"]:
                kdv_tutari = ara_toplam * (ayarlar["kdv_orani"] / 100)
            
            genel_toplam = ara_toplam + kdv_tutari
            
            # SONUÇLAR
            st.markdown("---")
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Toplam Ağırlık</div><div class="metric-value">{toplam_kg:.2f} kg</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">Ham Maliyet</div><div class="metric-value">{toplam_tl:.2f} TL</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">Kâr (%{ayarlar["kar_orani"]})</div><div class="metric-value">{kar_tutari:.2f} TL</div></div>', unsafe_allow_html=True)
            kdv_txt = f"+ KDV %{ayarlar['kdv_orani']}" if ayarlar['kdv_ekle'] else "KDV Dahil Değil"
            with c4: st.markdown(f'<div class="metric-card" style="border-left: 5px solid #10B981;"><div class="metric-label">TEKLİF ({kdv_txt})</div><div class="metric-value">{genel_toplam:,.2f} TL</div></div>', unsafe_allow_html=True)

            # KAYDET
            st.markdown("---")
            is_adi = st.text_input("İş Tanımı / Proje Adı", placeholder="Örn: 2024 Makina Kapakları")
            if st.button("💾 Müşteriye Kaydet ve Temizle"):
                if not st.session_state.aktif_musteri:
                    st.error("Lütfen yukarıdan Müşteri Seçin!")
                else:
                    is_kaydet(st.session_state.aktif_musteri, is_adi or "Genel Sipariş", genel_toplam, f"{len(st.session_state.sepet)} kalem, {toplam_kg:.1f}kg")
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
        if not df.empty:
            st.info(f"Toplam Ciro: **{df['Tutar'].sum():,.2f} TL**")
    else:
        st.warning("Kayıt yok.")

# --- SAYFA 3: AYARLAR ---
elif secilen_sayfa == "⚙️ Ayarlar":
    st.markdown('<div class="main-header">Kalıcı Sistem Ayarları</div>', unsafe_allow_html=True)
    
    tab_genel, tab_malz = st.tabs(["⚙️ Genel Ayarlar", "🔩 Malzeme Fiyatları"])
    
    with tab_genel:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Finansal Ayarlar")
            # Değerleri session'dan alıp güncelleme
            yeni_kar = st.number_input("Varsayılan Kâr Oranı (%)", value=st.session_state.config['ayarlar']['kar_orani'])
            yeni_kdv = st.number_input("KDV Oranı (%)", value=st.session_state.config['ayarlar']['kdv_orani'])
            yeni_kdv_ekle = st.checkbox("Hesaplamaya KDV Ekle?", value=st.session_state.config['ayarlar']['kdv_ekle'])
            
        with c2:
            st.subheader("İşçilik & Kur")
            yeni_dolar = st.number_input("Manuel Dolar Kuru (TL)", value=st.session_state.config['ayarlar']['dolar_kuru'])
            yeni_lazer = st.number_input("Lazer (TL/dk)", value=st.session_state.config['ayarlar']['lazer_dk'])
            yeni_abkant = st.number_input("Abkant (TL/vuruş)", value=st.session_state.config['ayarlar']['abkant_bukum'])

        if st.button("Genel Ayarları Kaydet (Kalıcı)"):
            st.session_state.config['ayarlar'].update({
                "kar_orani": yeni_kar, "kdv_orani": yeni_kdv, "kdv_ekle": yeni_kdv_ekle,
                "dolar_kuru": yeni_dolar, "lazer_dk": yeni_lazer, "abkant_bukum": yeni_abkant
            })
            ayarlari_kaydet(st.session_state.config)
            st.success("Ayarlar kaydedildi!")

    with tab_malz:
        malz_list = []
        for k, v in st.session_state.config['malzemeler'].items():
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
        
        if st.button("Malzeme Listesini Kaydet (Kalıcı)"):
            yeni_sozluk = {}
            for index, row in edited_malz.iterrows():
                yeni_sozluk[row["Malzeme"]] = {
                    "fiyat": row["Fiyat"],
                    "birim": row["Birim"],
                    "yogunluk": row["Yoğunluk"]
                }
            st.session_state.config['malzemeler'] = yeni_sozluk
            ayarlari_kaydet(st.session_state.config)
            st.success("Malzeme listesi güncellendi!")
    
    st.markdown("---")
    if st.button("⚠️ FABRİKA AYARLARINA DÖN (RESET)", type="secondary"):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        del st.session_state.config
        st.rerun()
