import streamlit as st
import pandas as pd
import cv2
import numpy as np
import pytesseract
from PIL import Image
import re

# Sayfa Ayarları
st.set_page_config(page_title="Lazer Maliyet & Rapor Okuyucu", layout="wide", page_icon="🏭")

# --- FONKSİYONLAR ---

def sureyi_dakikaya_cevir(zaman_str):
    """00:21:34 formatını dakikaya çevirir"""
    try:
        saat, dakika, saniye = map(int, zaman_str.split(':'))
        toplam_dakika = (saat * 60) + dakika + (saniye / 60)
        return toplam_dakika
    except:
        return 0.0

def rapor_analiz_et(image):
    """Görüntüden metin okur ve verileri ayıklar"""
    text = pytesseract.image_to_string(image)
    
    # Verileri saklayacağımız sözlük
    veriler = {
        "kesim_suresi_dk": 0.0,
        "x_boyut": 0.0,
        "y_boyut": 0.0,
        "kalinlik": 0.0,
        "fire_orani": 0.0,
        "adet": 1
    }
    
    # 1. Kesim Süresini Bul (Örn: Kesim 00:21:34)
    zaman_match = re.search(r'(\d{2}:\d{2}:\d{2})', text)
    if zaman_match:
        veriler["kesim_suresi_dk"] = sureyi_dakikaya_cevir(zaman_match.group(1))
    
    # 2. X ve Y Boyutlarını Bul (Tablonun altındaki X ve Y değerleri)
    # Genelde "X 2988.5" gibi yazar
    x_match = re.search(r'X\s*(\d+[.,]\d+)', text)
    y_match = re.search(r'Y\s*(\d+[.,]\d+)', text)
    
    if x_match: veriler["x_boyut"] = float(x_match.group(1).replace(',', '.'))
    if y_match: veriler["y_boyut"] = float(y_match.group(1).replace(',', '.'))
    
    # 3. Kalınlığı Bul (Program no: 3000 x 1500 x 1 kısmından)
    # Genelde "x 1" veya "x 2" gibi biter
    kalinlik_match = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
    if kalinlik_match:
        veriler["kalinlik"] = float(kalinlik_match.group(1).replace(',', '.'))
        
    # 4. Adet (Sağ üstte "Adet: 104" yazar)
    adet_match = re.search(r'Adet[:\s]*(\d+)', text)
    if adet_match:
        veriler["adet"] = int(adet_match.group(1))

    # 5. Fire (Raporda Fire (%) yazıyorsa)
    fire_match = re.search(r'Fire\s*\(%\)\s*(\d+[.,]\d+)', text)
    if fire_match:
        veriler["fire_orani"] = float(fire_match.group(1).replace(',', '.'))
        
    return veriler, text

# --- SOL MENÜ: AYARLAR ---
st.sidebar.title("⚙️ Birim Fiyatlar")

with st.sidebar.expander("Döviz & Malzeme ($)", expanded=True):
    dolar_kuru = st.number_input("Dolar Kuru (TL)", value=32.0)
    fiyat_dkp = st.number_input("DKP ($/kg)", value=0.90)
    fiyat_paslanmaz = st.number_input("Paslanmaz ($/kg)", value=3.50)
    fiyat_alu = st.number_input("Alüminyum ($/kg)", value=3.00)

with st.sidebar.expander("İşçilik (TL)", expanded=False):
    lazer_dk_ucret = st.number_input("Lazer Dakika (TL)", value=20.0)
    abkant_vurus = st.number_input("Abkant Vuruş (TL)", value=10.0)
    kaynak_saat = st.number_input("Kaynak (TL/Saat)", value=350.0)

# --- ANA EKRAN ---
st.title("🏭 Akıllı Teklif Hazırlayıcı")

tab1, tab2 = st.tabs(["📸 Rapor Yükle (Otomatik)", "📝 Manuel Hesapla"])

# --- TAB 1: RAPOR YÜKLEME ---
with tab1:
    st.info("CypCut veya makine raporunun fotoğrafını buraya yükleyin. Sistem verileri otomatik okuyacaktır.")
    uploaded_file = st.file_uploader("Rapor Fotoğrafı Seçin", type=['png', 'jpg', 'jpeg', 'pdf'])
    
    # Varsayılan Değerler
    oto_x = 0.0
    oto_y = 0.0
    oto_kalinlik = 2.0
    oto_sure = 0.0
    oto_adet = 1
    oto_fire = 0.0
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='Yüklenen Rapor', width=400)
        
        if st.button("🔍 Raporu Tara ve Verileri Çek"):
            with st.spinner('Görüntü işleniyor, lütfen bekleyin...'):
                try:
                    # OCR İşlemi
                    veriler, ham_metin = rapor_analiz_et(image)
                    
                    oto_x = veriler["x_boyut"]
                    oto_y = veriler["y_boyut"]
                    oto_sure = veriler["kesim_suresi_dk"]
                    oto_kalinlik = veriler["kalinlik"] if veriler["kalinlik"] > 0 else 2.0
                    oto_adet = veriler["adet"]
                    oto_fire = veriler["fire_orani"]
                    
                    st.success("Veriler başarıyla okundu! Aşağıdaki formu kontrol edin.")
                    
                    # Eğer fire okunamazsa manuel hesapla
                    if oto_fire == 0 and oto_x > 0:
                        plaka_alani = 3000 * 1500
                        kullanilan_alan = oto_x * oto_y
                        hesaplanan_fire = ((plaka_alani - kullanilan_alan) / plaka_alani) * 100
                        st.caption(f"Raporda fire oranı bulunamadı, X-Y boyutuna göre tahmini fire: %{hesaplanan_fire:.2f}")

                except Exception as e:
                    st.error(f"Okuma hatası: {e}. Lütfen GitHub'da packages.txt dosyasını oluşturduğunuzdan emin olun.")

    st.markdown("---")
    st.subheader("📊 Analiz Sonuçları (Düzenlenebilir)")
    
    # Form Alanları (Otomatik dolar veya elle girilir)
    col_a1, col_a2, col_a3 = st.columns(3)
    with col_a1:
        res_malzeme = st.selectbox("Malzeme", ["DKP", "Paslanmaz", "Alüminyum"])
        res_kalinlik = st.number_input("Kalınlık (mm)", value=float(oto_kalinlik))
        res_adet = st.number_input("Adet", value=int(oto_adet))
    
    with col_a2:
        res_x = st.number_input("Kullanılan X (mm)", value=float(oto_x), help="Sacın kullanılan genişliği")
        res_y = st.number_input("Kullanılan Y (mm)", value=float(oto_y), help="Sacın kullanılan yüksekliği")
        # Fireyi alana göre mi rapordan mı alalım?
        res_fire = st.number_input("Fire Oranı (%)", value=float(oto_fire))

    with col_a3:
        res_sure = st.number_input("Toplam Kesim Süresi (dk)", value=float(oto_sure))
        ekstra_iscilik = st.number_input("Ekstra İşçilik (TL)", value=0.0, help="Kaynak, boya vb. toplam tutar")

    # --- HESAPLAMA MOTORU ---
    if st.button("💰 Fiyat Hesapla"):
        # 1. Ağırlık Hesabı (Sadece kullanılan dikdörtgen alan)
        yogunluklar = {"DKP": 7.85, "Paslanmaz": 7.9, "Alüminyum": 2.7}
        rho = yogunluklar[res_malzeme]
        
        # Kullanılan alanın hacmi (mm3 -> kg)
        # Formül: En * Boy * Kalınlık * Yoğunluk / 1 Milyon
        hacim = res_x * res_y * res_kalinlik
        net_agirlik = (hacim * rho) / 1_000_000
        
        # Toplam ağırlık (Adet ile çarpılmaz çünkü rapordaki X-Y zaten o nestin tamamıdır)
        # Ama rapordaki süre toplam süredir.
        # Rapordaki X-Y genellikle o yerleşimin kapladığı alandır.
        
        # Malzeme Fiyatı
        if res_malzeme == "DKP": kg_fiyat = fiyat_dkp
        elif res_malzeme == "Paslanmaz": kg_fiyat = fiyat_paslanmaz
        else: kg_fiyat = fiyat_alu
        
        # Fire dahil maliyet hesabı
        # Eğer fire %10 ise, maliyeti (1 / 0.90) ile çarparız.
        fire_katsayisi = 1 / (1 - (res_fire / 100)) if res_fire < 100 else 1
        
        ham_malzeme_maliyeti = net_agirlik * kg_fiyat * dolar_kuru
        fireli_malzeme_maliyeti = ham_malzeme_maliyeti * fire_katsayisi
        
        # İşçilik
        lazer_maliyeti = res_sure * lazer_dk_ucret
        
        toplam_maliyet = fireli_malzeme_maliyeti + lazer_maliyeti + ekstra_iscilik
        
        # Sonuç Gösterimi
        st.success("Hesaplama Tamamlandı!")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Kullanılan Net Ağırlık", f"{net_agirlik:.2f} kg")
        c2.metric("Maliyet (KDV Hariç)", f"{toplam_maliyet:.2f} TL")
        
        kar_orani = st.slider("Kâr Marjı (%)", 10, 100, 25)
        satis = toplam_maliyet * (1 + kar_orani/100)
        c3.metric("TEKLİF FİYATI", f"{satis:.2f} TL", delta_color="inverse")
        
        st.info(f"Not: Bu yerleşimde {res_fire:.1f}% fire oluşmuştur. Maliyete yansıtılmıştır.")

# --- TAB 2: MANUEL ---
with tab2:
    st.write("Elinizde rapor yoksa, ölçüleri buraya elle girin.")
    # (Buraya eski manuel hesaplama kodları gelebilir veya sade bırakılabilir)
    m_en = st.number_input("Parça Eni (mm)", 100)
    m_boy = st.number_input("Parça Boyu (mm)", 100)
    m_adet = st.number_input("Kaç Adet?", 1)
    # ... Manuel kısım basit bırakıldı, istenirse detaylandırılır.
