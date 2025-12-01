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
st.set_page_config(page_title="Pro Lazer Hesaplama", layout="wide", page_icon="🏭")

# --- SABİTLER (DEFAULT AYARLAR) ---
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

DEFAULT_ISCILIK_DB = {
    "lazer_dk": 20.0,
    "abkant": 10.0,
    "kaynak": 350.0
}

# --- SESSION STATE BAŞLATMA ---
if 'malzeme_db' not in st.session_state:
    st.session_state.malzeme_db = DEFAULT_MALZEME_DB.copy()

if 'iscilik_db' not in st.session_state:
    st.session_state.iscilik_db = DEFAULT_ISCILIK_DB.copy()

if 'dolar_kuru' not in st.session_state:
    st.session_state.dolar_kuru = 34.0

# İş Sepeti (Dataframe olarak tutacağız ama session_state'de liste olarak saklayalım)
if 'is_listesi' not in st.session_state:
    st.session_state.is_listesi = []

# --- YARDIMCI FONKSİYONLAR ---

def dolar_kuru_getir():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=2)
        return float(response.json()["rates"]["TRY"])
    except:
        return st.session_state.dolar_kuru

@st.dialog("⚙️ Gelişmiş Atölye Ayarları")
def ayarlari_ac():
    st.write("Birim fiyatlar, yoğunluklar ve döviz ayarları.")
    
    # 1. Döviz
    col1, col2 = st.columns([2,1])
    with col1:
        yeni_kur = st.number_input("Dolar Kuru (TL)", value=float(st.session_state.dolar_kuru), format="%.4f")
    with col2:
        if st.button("🔄 Canlı Kur Çek"):
            st.session_state.dolar_kuru = dolar_kuru_getir()
            st.rerun()
    st.session_state.dolar_kuru = yeni_kur
    
    st.markdown("---")
    
    # 2. Malzeme Veritabanı (Fiyat + Yoğunluk Düzenleme)
    st.subheader("Malzeme Veritabanı")
    sirali = sorted(st.session_state.malzeme_db.items())
    
    # Tablo başlıkları
    hc1, hc2, hc3, hc4 = st.columns([2, 1.5, 1.5, 1.5])
    hc1.markdown("**Malzeme Adı**")
    hc2.markdown("**Fiyat**")
    hc3.markdown("**Birim**")
    hc4.markdown("**Yoğunluk**")
    
    for malz, detay in sirali:
        c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 1.5])
        c1.text(malz)
        yeni_fiyat = c2.number_input(f"Fiyat ({malz})", value=float(detay['fiyat']), label_visibility="collapsed")
        yeni_birim = c3.selectbox(f"Birim ({malz})", ["USD", "TL"], index=0 if detay['birim']=="USD" else 1, label_visibility="collapsed")
        yeni_yogunluk = c4.number_input(f"Y ({malz})", value=float(detay['yogunluk']), step=0.01, format="%.2f", label_visibility="collapsed")
        
        st.session_state.malzeme_db[malz]['fiyat'] = yeni_fiyat
        st.session_state.malzeme_db[malz]['birim'] = yeni_birim
        st.session_state.malzeme_db[malz]['yogunluk'] = yeni_yogunluk
    
    st.markdown("---")
    # 3. İşçilik
    st.subheader("İşçilik (TL)")
    lazer = st.number_input("Lazer Kesim (TL/dk)", value=st.session_state.iscilik_db['lazer_dk'])
    
    # RESET BUTONU
    st.markdown("---")
    col_save, col_reset = st.columns([3, 2])
    with col_save:
        if st.button("💾 Ayarları Kaydet ve Çık", type="primary"):
            st.session_state.iscilik_db['lazer_dk'] = lazer
            st.rerun()
    with col_reset:
        if st.button("⚠️ Fabrika Ayarlarına Dön (Reset)"):
            st.session_state.malzeme_db = DEFAULT_MALZEME_DB.copy()
            st.session_state.iscilik_db = DEFAULT_ISCILIK_DB.copy()
            st.rerun()

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
    """Geliştirilmiş Regex ile Veri Okuma"""
    veriler = {"sure": 0.0, "x": 0.0, "y": 0.0, "kalinlik": 2.0, "adet": 1, "fire": 0.0, "malzeme": "S235JR"}
    
    # 1. SÜRE (Düzeltildi: Sadece 'Kesim' veya 'Time' kelimesinden sonra gelen saati alır)
    # Önceki kod her saati alıyordu (16:15 gibi). Şimdi "Kesim" kelimesini şart koşuyoruz.
    # (?i) büyük küçük harf duyarsız yapar.
    zaman_match = re.search(r'(?:Kesim|Time|Cut)\s*[:|]?\s*(\d{2}:\d{2}:\d{2})', text, re.IGNORECASE)
    if zaman_match: 
        veriler["sure"] = sureyi_dakikaya_cevir(zaman_match.group(1))
    
    # 2. X ve Y (Düzeltildi: Tablo çizgileri | karakteri veya uzak boşluklar için esneklik)
    # X......:.....2988.5 yapısını yakalar
    x_match = re.search(r'[X]\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
    y_match = re.search(r'[Y]\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
    
    if x_match: veriler["x"] = float(x_match.group(1).replace(',', '.'))
    if y_match: veriler["y"] = float(y_match.group(1).replace(',', '.'))
    
    # 3. Kalınlık
    kalinlik_match = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
    if kalinlik_match: veriler["kalinlik"] = float(kalinlik_match.group(1).replace(',', '.'))
    
    # 4. Adet (Nest içindeki parça sayısı, bunu not olarak alırız)
    # Genelde maliyet PLAKA tekrarı üzerinden hesaplanır ama bu bilgiyi de alalım.
    adet_match = re.search(r'Adet\s*[:]?\s*(\d+)', text)
    if adet_match: veriler["adet"] = int(adet_match.group(1))
    
    # 5. Fire
    fire_match = re.search(r'Fire\s*\(%\)\s*(\d+[.,]\d+)', text)
    if fire_match: veriler["fire"] = float(fire_match.group(1).replace(',', '.'))
    
    # 6. Malzeme Tahmini
    text_lower = text.lower()
    if any(x in text_lower for x in ["dkp", "steel", "hr", "s235", "st37"]): veriler["malzeme"] = "S235JR"
    elif any(x in text_lower for x in ["galvaniz", "dx51"]): veriler["malzeme"] = "Galvaniz"
    elif any(x in text_lower for x in ["paslanmaz", "inox", "304"]): veriler["malzeme"] = "Paslanmaz (304)"
    elif any(x in text_lower for x in ["alu", "alüminyum"]): veriler["malzeme"] = "Alüminyum"
    
    return veriler

# --- ANA ARAYÜZ ---

col_head1, col_head2 = st.columns([5, 1])
with col_head1:
    st.title("🏭 Lazer Kesim Yönetim Paneli")
with col_head2:
    if st.button("⚙️ Ayarlar", type="primary"):
        ayarlari_ac()

st.info(f"💵 Dolar Kuru: **{st.session_state.dolar_kuru:.4f} TL** | Sistemdeki İş Sayısı: **{len(st.session_state.is_listesi)}**")

tab_hesap, tab_gecmis = st.tabs(["🛒 Hesaplama Sepeti", "🗂️ Kayıtlı Teklifler"])

with tab_hesap:
    
    # --- 1. DOSYA YÜKLEME VE MANUEL EKLEME ---
    with st.expander("➕ Yeni İş / Rapor Ekle", expanded=True):
        col_up1, col_up2 = st.columns(2)
        
        with col_up1:
            uploaded_file = st.file_uploader("Rapor Yükle (Resim/Word)", type=['docx', 'png', 'jpg', 'jpeg'], key="uploader")
            if uploaded_file:
                try:
                    # Analiz
                    if uploaded_file.name.endswith('.docx'):
                        doc = Document(uploaded_file)
                        text = "\n".join([p.text for p in doc.paragraphs] + [" ".join([c.text for c in r.cells]) for t in doc.tables for r in t.rows])
                        v = analiz_et(text)
                    else:
                        image = Image.open(uploaded_file)
                        text = pytesseract.image_to_string(image)
                        v = analiz_et(text)
                    
                    # Listeye Ekleme
                    yeni_is = {
                        "Dosya/Ad": uploaded_file.name,
                        "Malzeme": v["malzeme"],
                        "Kalınlık (mm)": v["kalinlik"],
                        "X (mm)": v["x"],
                        "Y (mm)": v["y"],
                        "Süre (dk)": v["sure"],
                        "Fire (%)": v["fire"],
                        "Tekrar (Plaka)": 1, # Varsayılan 1 plaka kesilecek
                        "Birim": "mm"
                    }
                    st.session_state.is_listesi.append(yeni_is)
                    st.success(f"✅ {uploaded_file.name} listeye eklendi! Aşağıdan düzenleyebilirsiniz.")
                    # Dosyayı "tükettik", uploader temizlenmesi için rerun gerekebilir ama streamlit'te key değişimi ile halledilir.
                except Exception as e:
                    st.error(f"Okuma Hatası: {e}")

        with col_up2:
            st.write("veya **Manuel İş Ekle**")
            if st.button("El ile Satır Ekle"):
                manual_is = {
                    "Dosya/Ad": "Manuel İş",
                    "Malzeme": "S235JR",
                    "Kalınlık (mm)": 2.0,
                    "X (mm)": 1000.0,
                    "Y (mm)": 1000.0,
                    "Süre (dk)": 10.0,
                    "Fire (%)": 0.0,
                    "Tekrar (Plaka)": 1,
                    "Birim": "mm"
                }
                st.session_state.is_listesi.append(manual_is)

    # --- 2. DÜZENLENEBİLİR LİSTE (TABLO) ---
    st.markdown("### 📋 İş Listesi (Düzenlenebilir)")
    
    if len(st.session_state.is_listesi) > 0:
        # Dataframe oluştur
        df_isler = pd.DataFrame(st.session_state.is_listesi)
        
        # Kullanıcının tabloyu düzenlemesine izin ver
        edited_df = st.data_editor(
            df_isler,
            num_rows="dynamic", # Satır silip ekleyebilir
            column_config={
                "Malzeme": st.column_config.SelectboxColumn(
                    "Malzeme",
                    options=list(st.session_state.malzeme_db.keys()),
                    required=True
                ),
                "Birim": st.column_config.SelectboxColumn(
                    "Birim",
                    options=["mm", "cm", "m"],
                    required=True
                ),
                "Tekrar (Plaka)": st.column_config.NumberColumn(
                    "Plaka Adeti (Tekrar)",
                    help="Bu yerleşimden kaç plaka kesileceği",
                    min_value=1,
                    step=1
                ),
                "Süre (dk)": st.column_config.NumberColumn(
                    "Kesim Süresi (dk)",
                    help="Tek bir plakanın kesim süresi",
                    format="%.2f"
                )
            },
            use_container_width=True
        )
        
        # --- 3. HESAPLAMA BUTONU ---
        col_calc1, col_calc2 = st.columns([1, 4])
        hesapla = col_calc1.button("💰 MALİYET HESAPLA", type="primary")
        
        if hesapla:
            toplam_tutar = 0
            toplam_agirlik_genel = 0
            detaylar = []
            
            # Tablodaki her satır için hesap yap
            for index, row in edited_df.iterrows():
                malz_adi = row["Malzeme"]
                malz_data = st.session_state.malzeme_db[malz_adi]
                
                # Birim Çevirme (Hepsini mm'ye)
                carpan = 1
                if row["Birim"] == "cm": carpan = 10
                elif row["Birim"] == "m": carpan = 1000
                
                x_mm = row["X (mm)"] * carpan
                y_mm = row["Y (mm)"] * carpan
                kalinlik = row["Kalınlık (mm)"]
                tekrar = row["Tekrar (Plaka)"]
                sure = row["Süre (dk)"]
                fire = row["Fire (%)"]
                
                # Ağırlık Hesabı
                yogunluk = malz_data['yogunluk']
                hacim_mm3 = x_mm * y_mm * kalinlik
                agirlik_tek = (hacim_mm3 * yogunluk) / 1_000_000
                toplam_agirlik_satir = agirlik_tek * tekrar
                
                # Fiyatlandırma
                if malz_data['birim'] == "USD":
                    kg_fiyat_tl = malz_data['fiyat'] * st.session_state.dolar_kuru
                else:
                    kg_fiyat_tl = malz_data['fiyat']
                
                # Fire maliyete eklenir
                fire_katsayisi = 1 / (1 - (fire/100)) if fire < 100 else 1
                
                malzeme_maliyeti = toplam_agirlik_satir * kg_fiyat_tl * fire_katsayisi
                # Süre: Tek plaka süresi * Plaka tekrarı
                lazer_maliyeti = (sure * tekrar) * st.session_state.iscilik_db['lazer_dk']
                
                satir_toplam = malzeme_maliyeti + lazer_maliyeti
                
                toplam_tutar += satir_toplam
                toplam_agirlik_genel += toplam_agirlik_satir
                
                detaylar.append({
                    "İş": row["Dosya/Ad"],
                    "Malzeme": f"{malz_adi} {kalinlik}mm",
                    "Ağırlık": f"{toplam_agirlik_satir:.2f} kg",
                    "Maliyet": f"{satir_toplam:.2f} TL"
                })
            
            # --- SONUÇLAR ---
            st.markdown("---")
            st.subheader("📊 Hesaplama Sonuçları")
            
            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Toplam Malzeme Ağırlığı", f"{toplam_agirlik_genel:.2f} kg")
            rc2.metric("Toplam Ham Maliyet", f"{toplam_tutar:.2f} TL")
            
            kar_orani = st.slider("Kâr Marjı (%)", 0, 100, 25)
            satis_fiyati = toplam_tutar * (1 + kar_orani/100)
            
            rc3.metric("TEKLİF FİYATI", f"{satis_fiyati:.2f} TL", delta_color="inverse")
            
            # Detay Tablosu
            st.table(pd.DataFrame(detaylar))
            
            # Listeyi güncelle (kullanıcı satır sildiyse state de güncellensin)
            st.session_state.is_listesi = edited_df.to_dict('records')

    else:
        st.info("Sepetiniz boş. Yukarıdan dosya yükleyin veya manuel satır ekleyin.")

with tab_gecmis:
    st.write("Kayıt sistemi burada olacak...")
    # (Önceki kayıt kodları buraya entegre edilebilir)
