import streamlit as st
import pandas as pd
from github import Github
import numpy as np
import cv2
import pytesseract
from PIL import Image
from docx import Document
import re
import io
import requests
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="ÖZÇELİK ENDÜSTRİ", layout="wide", page_icon="🏭")

# --- CSS İYİLEŞTİRMELERİ ---
st.markdown("""
    <style>
    .main-header {font-size: 28px; font-weight: bold; color: #0f172a;}
    .metric-card {background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;}
    .metric-val {font-size: 24px; font-weight: bold; color: #0f172a;}
    .stButton>button {width: 100%;}
    </style>
""", unsafe_allow_html=True)

# --- GITHUB VERİTABANI BAĞLANTISI ---
# Bu fonksiyonlar dosyaları GitHub'dan okur ve yazar.

def get_github_repo():
    """GitHub reposuna bağlanır"""
    token = st.secrets["github"]["token"]
    repo_name = st.secrets["github"]["repo_name"]
    g = Github(token)
    return g.get_repo(repo_name)

def read_csv_from_github(filename):
    """GitHub'dan CSV dosyasını okur"""
    try:
        repo = get_github_repo()
        contents = repo.get_contents(filename)
        return pd.read_csv(io.StringIO(contents.decoded_content.decode()))
    except:
        # Dosya yoksa boş DataFrame döndür
        if filename == "musteriler.csv":
            return pd.DataFrame(columns=["Firma Adı", "Yetkili", "Telefon"])
        elif filename == "siparisler.csv":
            return pd.DataFrame(columns=["Tarih", "Müşteri", "İş Adı", "Tutar", "Detay"])
        elif filename == "ayarlar.csv":
            # Varsayılan Ayarlar
            return pd.DataFrame([
                {"Ayar": "dolar_kuru", "Deger": 34.50},
                {"Ayar": "kar_orani", "Deger": 25.0},
                {"Ayar": "kdv_durum", "Deger": "Evet"},
                {"Ayar": "lazer_dk", "Deger": 25.0},
                {"Ayar": "abkant_vurus", "Deger": 15.0}
            ])
        elif filename == "malzemeler.csv":
            # Varsayılan Malzemeler
            return pd.DataFrame([
                {"Malzeme": "Siyah Sac", "Fiyat": 0.85, "Birim": "USD", "Yogunluk": 7.85},
                {"Malzeme": "Paslanmaz", "Fiyat": 3.50, "Birim": "USD", "Yogunluk": 7.93},
                {"Malzeme": "Galvaniz", "Fiyat": 1.00, "Birim": "USD", "Yogunluk": 7.85},
                {"Malzeme": "Hardox 450", "Fiyat": 2.20, "Birim": "USD", "Yogunluk": 7.85},
                {"Malzeme": "ST52", "Fiyat": 0.95, "Birim": "USD", "Yogunluk": 7.85}
            ])
        return pd.DataFrame()

def save_csv_to_github(filename, df, message="Veri güncellendi"):
    """DataFrame'i GitHub'a CSV olarak kaydeder"""
    repo = get_github_repo()
    content = df.to_csv(index=False)
    try:
        # Dosya varsa güncelle
        contents = repo.get_contents(filename)
        repo.update_file(contents.path, message, content, contents.sha)
    except:
        # Dosya yoksa oluştur
        repo.create_file(filename, message, content)

# --- ANALİZ MOTORU ---
def sure_cevir(zaman_str):
    try:
        parts = list(map(int, str(zaman_str).strip().split(':')))
        if len(parts) == 3: return (parts[0] * 60) + parts[1] + (parts[2] / 60)
        elif len(parts) == 2: return parts[0] + (parts[1] / 60)
        return 0.0
    except: return 0.0

def cypcut_analiz(image):
    veriler = {}
    try:
        img_np = np.array(image)
        if len(img_np.shape) == 3: img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        else: img_gray = img_np
        _, img_thresh = cv2.threshold(img_gray, 150, 255, cv2.THRESH_BINARY)
        text = pytesseract.image_to_string(Image.fromarray(img_thresh))
        
        zaman = re.search(r'(?:Kesim|Cut|Time).*?(\d{2}:\d{2}:\d{2})', text, re.IGNORECASE)
        if zaman: veriler["sure"] = sure_cevir(zaman.group(1))
        
        x = re.search(r'X\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
        y = re.search(r'Y\s*[:|]?\s*(\d{3,5}[.,]\d+)', text)
        if x: veriler["x"] = float(x.group(1).replace(',', '.'))
        if y: veriler["y"] = float(y.group(1).replace(',', '.'))
        
        kal = re.search(r'x\s*(\d+[.,]?\d*)\s*$', text, re.MULTILINE)
        if not kal: kal = re.search(r'3000\s*x\s*1500\s*x\s*(\d+[.,]?\d*)', text)
        if kal: veriler["kal"] = float(kal.group(1).replace(',', '.'))
        
        # Malzeme Otomatik Seçim
        tl = text.lower()
        if "hardox" in tl: veriler["malz"] = "Hardox 450"
        elif "paslanmaz" in tl: veriler["malz"] = "Paslanmaz"
        elif "galvaniz" in tl: veriler["malz"] = "Galvaniz"
        else: veriler["malz"] = "Siyah Sac"
        
    except: pass
    return veriler

# --- BAŞLANGIÇ AYARLARINI ÇEK ---
if 'ayarlar_cache' not in st.session_state:
    st.session_state.ayarlar_cache = read_csv_from_github("ayarlar.csv")
    st.session_state.malzeme_cache = read_csv_from_github("malzemeler.csv")

# Ayarları değişkene al (Kolay kullanım için)
df_ayar = st.session_state.ayarlar_cache
try:
    DOLAR = float(df_ayar.loc[df_ayar['Ayar']=='dolar_kuru', 'Deger'].values[0])
    KAR = float(df_ayar.loc[df_ayar['Ayar']=='kar_orani', 'Deger'].values[0])
    KDV_DURUM = str(df_ayar.loc[df_ayar['Ayar']=='kdv_durum', 'Deger'].values[0])
    LAZER_DK = float(df_ayar.loc[df_ayar['Ayar']=='lazer_dk', 'Deger'].values[0])
    ABKANT_TL = float(df_ayar.loc[df_ayar['Ayar']=='abkant_vurus', 'Deger'].values[0])
except:
    DOLAR, KAR, KDV_DURUM, LAZER_DK, ABKANT_TL = 34.50, 25.0, "Evet", 25.0, 15.0

# Session State
if 'sepet' not in st.session_state: st.session_state.sepet = []

# --- ARAYÜZ ---

# SOL MENÜ
with st.sidebar:
    st.image("https://ozcelikendustri.com/wp-content/uploads/2021/01/logo-1.png", width=200)
    st.markdown("### 🏭 ÖZÇELİK ENDÜSTRİ")
    menu = st.radio("Menü", ["Hesaplama & Teklif", "Müşteri Yönetimi", "Ayarlar & Malzemeler"])
    
    st.divider()
    st.info(f"💲 Dolar: **{DOLAR} TL**\n\n📊 Kâr: **%{KAR}**")
    
    # Canlı Dolar Butonu
    if st.button("🔄 Doları Güncelle (Netten Çek)"):
        try:
            r = requests.get("https://api.exchangerate-api.com/v4/latest/USD").json()
            yeni_kur = float(r["rates"]["TRY"])
            df_ayar.loc[df_ayar['Ayar']=='dolar_kuru', 'Deger'] = yeni_kur
            save_csv_to_github("ayarlar.csv", df_ayar)
            st.session_state.ayarlar_cache = df_ayar
            st.success(f"Kur güncellendi: {yeni_kur}")
            st.rerun()
        except:
            st.error("Kur çekilemedi.")

# --- SAYFA 1: HESAPLAMA ---
if menu == "Hesaplama & Teklif":
    st.markdown('<p class="main-header">Teklif Masası</p>', unsafe_allow_html=True)
    
    # Müşteri Seçimi (GitHub'dan)
    df_mus = read_csv_from_github("musteriler.csv")
    list_mus = ["Seçiniz..."] + df_mus["Firma Adı"].tolist() if not df_mus.empty else ["Seçiniz..."]
    
    c1, c2 = st.columns([3, 1])
    secilen_firma = c1.selectbox("Müşteri Seç:", list_mus)
    
    if secilen_firma == "Seçiniz...":
        st.warning("Lütfen işlem yapmak için müşteri seçin.")
        st.stop()
    
    st.success(f"Müşteri: **{secilen_firma}**")
    st.divider()

    # GİRİŞ ALANI
    with st.expander("➕ Ürün Ekle (Manuel & Dosya)", expanded=True):
        tab_man, tab_dos = st.tabs(["✍️ Manuel Ekle", "📂 Dosyadan Ekle"])
        
        # Manuel Giriş
        with tab_man:
            c1, c2, c3 = st.columns(3)
            malz_listesi = st.session_state.malzeme_cache["Malzeme"].tolist()
            m_malz = c1.selectbox("Malzeme", malz_listesi)
            m_kal = c2.number_input("Kalınlık (mm)", value=None, placeholder="Örn: 2")
            m_adet = c3.number_input("Adet", value=None, min_value=1, placeholder="1")
            
            c4, c5, c6 = st.columns(3)
            birim = c4.radio("Birim", ["mm", "cm", "m"], horizontal=True)
            m_en = c5.number_input("En", value=None, placeholder="Genişlik")
            m_boy = c6.number_input("Boy", value=None, placeholder="Uzunluk")
            
            c7, c8 = st.columns(2)
            m_sure = c7.number_input("Lazer Süresi (dk)", value=None, placeholder="0")
            m_bukum = c8.number_input("Büküm Sayısı", value=None, placeholder="0")
            
            if st.button("Sepete Ekle ⬇️", key="btn_man"):
                if m_en and m_boy and m_kal:
                    carpan = 1000 if birim == "m" else (10 if birim == "cm" else 1)
                    st.session_state.sepet.append({
                        "Malzeme": m_malz,
                        "Kalınlık": float(m_kal),
                        "En (mm)": float(m_en) * carpan,
                        "Boy (mm)": float(m_boy) * carpan,
                        "Adet": int(m_adet or 1),
                        "Süre": float(m_sure or 0),
                        "Büküm": int(m_bukum or 0)
                    })
                    st.rerun()
                else:
                    st.error("Lütfen ölçüleri girin.")
        
        # Dosyadan Ekle
        with tab_dos:
            files = st.file_uploader("Dosyaları Sürükle", accept_multiple_files=True)
            if st.button("Analiz Et ve Ekle"):
                for f in files:
                    vals = {}
                    if f.name.endswith('.docx'):
                        try:
                            doc = Document(f)
                            vals = cypcut_analiz(Image.new('RGB',(10,10))) # Dummy
                        except: pass
                    else:
                        vals = cypcut_analiz(Image.open(f))
                    
                    st.session_state.sepet.append({
                        "Malzeme": vals.get("malz", "Siyah Sac"),
                        "Kalınlık": vals.get("kal", 2.0),
                        "En (mm)": vals.get("y", 1000.0),
                        "Boy (mm)": vals.get("x", 2000.0),
                        "Adet": 1,
                        "Süre": vals.get("sure", 0.0),
                        "Büküm": 0
                    })
                st.success("Dosyalar eklendi!")
                st.rerun()

    # SEPET VE HESAP
    st.markdown("### 🛒 Sipariş Listesi")
    
    if st.session_state.sepet:
        df_sepet = pd.DataFrame(st.session_state.sepet)
        
        # SİLMEK İÇİN: num_rows="dynamic" en kolay yoldur.
        edited_df = st.data_editor(
            df_sepet,
            column_config={
                "Adet": st.column_config.NumberColumn("Adet", min_value=1),
                "En (mm)": st.column_config.NumberColumn("En", format="%.1f"),
                "Boy (mm)": st.column_config.NumberColumn("Boy", format="%.1f"),
            },
            num_rows="dynamic",
            use_container_width=True,
            key="basket_editor"
        )
        
        if st.button("💰 FİYATI HESAPLA", type="primary"):
            toplam_tl = 0
            toplam_kg = 0
            guncel_sepet = edited_df.to_dict('records')
            st.session_state.sepet = guncel_sepet # Hafızayı güncelle
            
            # Veritabanından Malzeme Fiyatlarını Al
            df_m = st.session_state.malzeme_cache
            
            for item in guncel_sepet:
                # Malzeme Bilgisi
                m_row = df_m[df_m["Malzeme"] == item["Malzeme"]].iloc[0]
                m_fiyat = float(m_row["Fiyat"])
                m_birim = str(m_row["Birim"])
                m_yog = float(m_row["Yogunluk"])
                
                if m_birim == "USD": m_fiyat = m_fiyat * DOLAR
                
                # Hesap
                hacim = item["En (mm)"] * item["Boy (mm)"] * item["Kalınlık"]
                kg = (hacim * m_yog) / 1_000_000 * item["Adet"]
                
                malz_tut = kg * m_fiyat
                lazer_tut = (item["Süre"] * item["Adet"]) * LAZER_DK
                bukum_tut = (item["Büküm"] * item["Adet"]) * ABKANT_TL
                
                toplam_tl += malz_tut + lazer_tut + bukum_tut
                toplam_kg += kg
            
            # Kâr ve KDV
            karli = toplam_tl * (1 + KAR/100)
            kdv = karli * 0.20 if KDV_DURUM == "Evet" else 0
            genel = karli + kdv
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.markdown(f'<div class="metric-card">Ağırlık<div class="metric-val">{toplam_kg:.2f} kg</div></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="metric-card">Maliyet<div class="metric-val">{toplam_tl:.2f} TL</div></div>', unsafe_allow_html=True)
            kdv_txt = "+ KDV" if KDV_DURUM == "Evet" else "KDV Yok"
            c3.markdown(f'<div class="metric-card" style="border-left: 5px solid green;">TEKLİF ({kdv_txt})<div class="metric-val">{genel:,.2f} TL</div></div>', unsafe_allow_html=True)
            
            st.divider()
            notlar = st.text_input("Sipariş Notu", placeholder="Örn: Acil teslim")
            if st.button("💾 Kaydet"):
                df_sip = read_csv_from_github("siparisler.csv")
                yeni_sip = pd.DataFrame([{
                    "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Müşteri": secilen_firma,
                    "İş Adı": notlar or "Genel",
                    "Tutar": round(genel, 2),
                    "Detay": f"{len(guncel_sepet)} parça, {toplam_kg:.1f}kg"
                }])
                df_yen = pd.concat([df_sip, yeni_sip], ignore_index=True)
                save_csv_to_github("siparisler.csv", df_yen)
                st.session_state.sepet = []
                st.balloons()
                st.success("Sipariş kaydedildi!")
                st.rerun()
    else:
        st.info("Sepet boş.")

# --- SAYFA 2: MÜŞTERİLER ---
elif menu == "Müşteri Yönetimi":
    st.markdown('<p class="main-header">Müşteri Veritabanı</p>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📋 Liste", "➕ Yeni Ekle", "📜 Sipariş Geçmişi"])
    
    with tab1:
        df = read_csv_from_github("musteriler.csv")
        st.dataframe(df, use_container_width=True)
        
    with tab2:
        with st.form("yeni_mus"):
            firma = st.text_input("Firma Adı")
            yetkili = st.text_input("Yetkili")
            tel = st.text_input("Telefon")
            if st.form_submit_button("Kaydet"):
                df_mus = read_csv_from_github("musteriler.csv")
                if firma in df_mus["Firma Adı"].values:
                    st.error("Bu firma zaten kayıtlı.")
                else:
                    yeni = pd.DataFrame([{"Firma Adı": firma, "Yetkili": yetkili, "Telefon": tel}])
                    save_csv_to_github("musteriler.csv", pd.concat([df_mus, yeni], ignore_index=True))
                    st.success("Müşteri eklendi!")
                    st.rerun()
                    
    with tab3:
        df_sip = read_csv_from_github("siparisler.csv")
        if not df_sip.empty:
            mus_filter = st.selectbox("Firma Seç", ["Tümü"] + df_sip["Müşteri"].unique().tolist())
            if mus_filter != "Tümü":
                df_sip = df_sip[df_sip["Müşteri"] == mus_filter]
            st.dataframe(df_sip, use_container_width=True)
        else:
            st.warning("Sipariş geçmişi yok.")

# --- SAYFA 3: AYARLAR ---
elif menu == "Ayarlar & Malzemeler":
    st.markdown('<p class="main-header">Ayarlar</p>', unsafe_allow_html=True)
    
    tab_gen, tab_malz = st.tabs(["⚙️ Genel", "🔩 Malzemeler"])
    
    with tab_gen:
        c1, c2 = st.columns(2)
        yd = c1.number_input("Dolar Kuru", value=DOLAR)
        yk = c2.number_input("Kâr Oranı (%)", value=KAR)
        yl = c1.number_input("Lazer (TL/dk)", value=LAZER_DK)
        ya = c2.number_input("Abkant (TL/vuruş)", value=ABKANT_TL)
        ykdv = st.selectbox("KDV Durumu", ["Evet", "Hayır"], index=0 if KDV_DURUM=="Evet" else 1)
        
        if st.button("Ayarları Kaydet"):
            # Güncelle
            df_ayar.loc[df_ayar['Ayar']=='dolar_kuru', 'Deger'] = yd
            df_ayar.loc[df_ayar['Ayar']=='kar_orani', 'Deger'] = yk
            df_ayar.loc[df_ayar['Ayar']=='lazer_dk', 'Deger'] = yl
            df_ayar.loc[df_ayar['Ayar']=='abkant_vurus', 'Deger'] = ya
            df_ayar.loc[df_ayar['Ayar']=='kdv_durum', 'Deger'] = ykdv
            save_csv_to_github("ayarlar.csv", df_ayar)
            st.session_state.ayarlar_cache = df_ayar
            st.success("Ayarlar güncellendi!")
            st.rerun()
            
    with tab_malz:
        df_m = st.session_state.malzeme_cache
        edited_m = st.data_editor(df_m, num_rows="dynamic", use_container_width=True)
        if st.button("Malzeme Listesini Kaydet"):
            save_csv_to_github("malzemeler.csv", edited_m)
            st.session_state.malzeme_cache = edited_m
            st.success("Malzemeler güncellendi!")
