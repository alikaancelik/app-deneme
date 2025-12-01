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

# --- CSS (GÖRÜNÜM) ---
st.markdown("""
    <style>
    .main-header {font-size: 28px; font-weight: bold; color: #0f172a;}
    .metric-card {
        background-color: #ffffff !important; 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid #ccc; 
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-label {font-size: 16px; color: #000000 !important; font-weight: 500;}
    .metric-val {font-size: 26px; font-weight: bold; color: #000000 !important;}
    .stButton>button {width: 100%; border-radius: 5px;}
    </style>
""", unsafe_allow_html=True)

# --- GITHUB BAĞLANTISI ---
def get_github_repo():
    token = st.secrets["github"]["token"]
    repo_name = st.secrets["github"]["repo_name"]
    g = Github(token)
    return g.get_repo(repo_name)

def read_csv_from_github(filename):
    try:
        repo = get_github_repo()
        contents = repo.get_contents(filename)
        return pd.read_csv(io.StringIO(contents.decoded_content.decode()))
    except:
        # Dosya yoksa boş şablon döndür
        if filename == "musteriler.csv": return pd.DataFrame(columns=["Firma Adı", "Yetkili", "Telefon", "Adres"])
        elif filename == "siparisler.csv": return pd.DataFrame(columns=["Tarih", "Müşteri", "İş Adı", "Tutar", "Detay"])
        elif filename == "ayarlar.csv":
            return pd.DataFrame([
                {"Ayar": "dolar_kuru", "Deger": 34.50},
                {"Ayar": "kar_orani", "Deger": 25.0},
                {"Ayar": "kdv_durum", "Deger": "Evet"},
                {"Ayar": "lazer_dk", "Deger": 25.0},
                {"Ayar": "abkant_vurus", "Deger": 15.0}
            ])
        elif filename == "malzemeler.csv":
            return pd.DataFrame([{"Malzeme": "Siyah Sac", "Fiyat": 0.85, "Birim": "USD", "Yogunluk": 7.85}])
        return pd.DataFrame()

def save_csv_to_github(filename, df, message="Veri güncellendi"):
    repo = get_github_repo()
    content = df.to_csv(index=False)
    try:
        contents = repo.get_contents(filename)
        repo.update_file(contents.path, message, content, contents.sha)
    except:
        repo.create_file(filename, message, content)

# --- ANALİZ MOTORLARI ---
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
        
        tl = text.lower()
        if "hardox" in tl: veriler["malz"] = "Hardox 450"
        elif "paslanmaz" in tl: veriler["malz"] = "Paslanmaz"
        elif "galvaniz" in tl: veriler["malz"] = "Galvaniz"
        else: veriler["malz"] = "Siyah Sac"
    except: pass
    return veriler

# --- AYARLARI VE STATE'LERİ YÜKLE ---
if 'ayarlar_cache' not in st.session_state:
    st.session_state.ayarlar_cache = read_csv_from_github("ayarlar.csv")
    st.session_state.malzeme_cache = read_csv_from_github("malzemeler.csv")

df_ayar = st.session_state.ayarlar_cache
try:
    DOLAR = float(df_ayar.loc[df_ayar['Ayar']=='dolar_kuru', 'Deger'].values[0])
    KAR = float(df_ayar.loc[df_ayar['Ayar']=='kar_orani', 'Deger'].values[0])
    KDV_DURUM = str(df_ayar.loc[df_ayar['Ayar']=='kdv_durum', 'Deger'].values[0])
    LAZER_DK = float(df_ayar.loc[df_ayar['Ayar']=='lazer_dk', 'Deger'].values[0])
    ABKANT_TL = float(df_ayar.loc[df_ayar['Ayar']=='abkant_vurus', 'Deger'].values[0])
except:
    DOLAR, KAR, KDV_DURUM, LAZER_DK, ABKANT_TL = 34.50, 25.0, "Evet", 25.0, 15.0

if 'sepet' not in st.session_state: st.session_state.sepet = []
if 'secili_musteri_hafiza' not in st.session_state: st.session_state.secili_musteri_hafiza = "Seçiniz..."

# --- ARAYÜZ BAŞLANGICI ---

with st.sidebar:
    st.image("https://ozcelikendustri.com/wp-content/uploads/2021/01/logo-1.png", width=200)
    st.markdown("### 🏭 ÖZÇELİK ENDÜSTRİ")
    menu = st.radio("Menü", ["Hesaplama & Teklif", "Müşteri Yönetimi", "Ayarlar & Malzemeler"])
    st.divider()
    st.info(f"💲 Dolar: **{DOLAR} TL**")
    
    if st.button("🔄 Kuru Güncelle"):
        try:
            r = requests.get("https://api.exchangerate-api.com/v4/latest/USD").json()
            yeni_kur = float(r["rates"]["TRY"])
            df_ayar.loc[df_ayar['Ayar']=='dolar_kuru', 'Deger'] = yeni_kur
            save_csv_to_github("ayarlar.csv", df_ayar)
            st.session_state.ayarlar_cache = df_ayar
            st.success(f"Kur: {yeni_kur}")
            st.rerun()
        except: st.error("Hata")

# --- SAYFA 1: HESAPLAMA ---
if menu == "Hesaplama & Teklif":
    st.markdown('<p class="main-header">Teklif Masası</p>', unsafe_allow_html=True)
    
    # 1. MÜŞTERİ SEÇİMİ
    df_mus = read_csv_from_github("musteriler.csv")
    mus_listesi = ["Seçiniz..."]
    if not df_mus.empty:
        mus_listesi += df_mus["Firma Adı"].tolist()
    
    secenekler = ["⚡ HIZLI İŞLEM (Kayitsiz)"] + mus_listesi
    yeni_secim = st.selectbox("Müşteri Seçin:", secenekler)
    
    # Müşteri değişince sepeti temizle
    if yeni_secim != st.session_state.secili_musteri_hafiza:
        st.session_state.sepet = [] 
        st.session_state.secili_musteri_hafiza = yeni_secim 
        st.toast("Müşteri değişti, sepet temizlendi.", icon="🧹")

    # Müşteri Adı Belirleme ve Input
    aktif_musteri_adi = ""
    temp_ad_input = ""
    
    if yeni_secim == "⚡ HIZLI İŞLEM (Kayitsiz)":
        c1, c2 = st.columns([1, 2])
        c1.info("Kayıtsız İşlem Modu")
        temp_ad_input = c2.text_input("Müşteri / İş İsmi (Boş bırakırsan 'İsimsiz İş X' olur):", placeholder="Örn: Ahmet Bey")
    elif yeni_secim == "Seçiniz...":
        st.warning("Lütfen işlem yapmak için bir müşteri seçin.")
        st.stop()
    else:
        aktif_musteri_adi = yeni_secim
        st.success(f"Çalışılan Müşteri: **{aktif_musteri_adi}**")

    st.divider()

    # 2. ÜRÜN EKLEME ALANI
    with st.expander("➕ Ürün Ekle", expanded=True):
        tab_man, tab_dos = st.tabs(["✍️ Manuel Ekle", "📂 Dosya Ekle"])
        
        with tab_man:
            c1, c2, c3 = st.columns(3)
            malz_listesi = st.session_state.malzeme_cache["Malzeme"].tolist()
            m_malz = c1.selectbox("Malzeme", malz_listesi)
            m_kal = c2.number_input("Kalınlık (mm)", value=None, placeholder="2")
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
                        "Sil": False, "Malzeme": m_malz, "Kalınlık": float(m_kal),
                        "En (mm)": float(m_en) * carpan, "Boy (mm)": float(m_boy) * carpan,
                        "Adet": int(m_adet or 1), "Süre": float(m_sure or 0), "Büküm": int(m_bukum or 0)
                    })
                    st.rerun()
                else: st.error("Ölçü giriniz.")
        
        with tab_dos:
            files = st.file_uploader("Dosya Sürükle", accept_multiple_files=True)
            if st.button("Analiz Et ve Ekle"):
                for f in files:
                    vals = {}
                    if f.name.endswith('.docx'):
                        try:
                            doc = Document(f)
                            vals = cypcut_analiz(Image.new('RGB',(10,10)))
                        except: pass
                    else:
                        vals = cypcut_analiz(Image.open(f))
                    st.session_state.sepet.append({
                        "Sil": False, "Malzeme": vals.get("malz", "Siyah Sac"),
                        "Kalınlık": vals.get("kal", 2.0), "En (mm)": vals.get("y", 1000.0),
                        "Boy (mm)": vals.get("x", 2000.0), "Adet": 1, "Süre": vals.get("sure", 0.0), "Büküm": 0
                    })
                st.rerun()

    # 3. SEPET VE HESAPLAMA
    st.markdown("### 🛒 Sipariş Listesi")
    if st.session_state.sepet:
        df_sepet = pd.DataFrame(st.session_state.sepet)
        edited_df = st.data_editor(
            df_sepet,
            column_config={
                "Sil": st.column_config.CheckboxColumn("Sil?", width="small"),
                "Adet": st.column_config.NumberColumn("Adet", min_value=1),
                "En (mm)": st.column_config.NumberColumn("En", format="%.1f"),
                "Boy (mm)": st.column_config.NumberColumn("Boy", format="%.1f"),
            },
            use_container_width=True, hide_index=True, key="basket_editor"
        )
        
        if st.button("🗑️ Seçili Satırları Sil"):
            yeni_sepet = [row for row in edited_df.to_dict('records') if not row.get("Sil", False)]
            for row in yeni_sepet: row["Sil"] = False
            st.session_state.sepet = yeni_sepet
            st.rerun()

        st.divider()

        # FİYAT HESAPLAMA BUTONU
        if st.button("💰 FİYATI HESAPLA", type="primary"):
            guncel_sepet = [row for row in edited_df.to_dict('records') if not row.get("Sil", False)]
            if not guncel_sepet:
                st.warning("Hesaplanacak ürün yok.")
            else:
                toplam_tl = 0
                toplam_kg = 0
                df_m = st.session_state.malzeme_cache
                
                for item in guncel_sepet:
                    try:
                        m_row = df_m[df_m["Malzeme"] == item["Malzeme"]].iloc[0]
                        m_fiyat = float(m_row["Fiyat"])
                        m_birim = str(m_row["Birim"])
                        m_yog = float(m_row["Yogunluk"])
                        
                        if m_birim == "USD": m_fiyat = m_fiyat * DOLAR
                        
                        hacim = item["En (mm)"] * item["Boy (mm)"] * item["Kalınlık"]
                        kg = (hacim * m_yog) / 1_000_000 * item["Adet"]
                        malz_tut = kg * m_fiyat
                        lazer_tut = (item["Süre"] * item["Adet"]) * LAZER_DK
                        bukum_tut = (item["Büküm"] * item["Adet"]) * ABKANT_TL
                        toplam_tl += malz_tut + lazer_tut + bukum_tut
                        toplam_kg += kg
                    except: pass
                
                karli = toplam_tl * (1 + KAR/100)
                kdv = karli * 0.20 if KDV_DURUM == "Evet" else 0
                genel = karli + kdv
                
                c1, c2, c3 = st.columns(3)
                c1.markdown(f'<div class="metric-card"><div class="metric-label">Toplam Ağırlık</div><div class="metric-val">{toplam_kg:.2f} kg</div></div>', unsafe_allow_html=True)
                c2.markdown(f'<div class="metric-card"><div class="metric-label">Ham Maliyet</div><div class="metric-val">{toplam_tl:,.2f} TL</div></div>', unsafe_allow_html=True)
                kdv_txt = "+ KDV" if KDV_DURUM == "Evet" else "KDV Yok"
                c3.markdown(f'<div class="metric-card" style="border-left: 5px solid green;"><div class="metric-label">TEKLİF ({kdv_txt})</div><div class="metric-val">{genel:,.2f} TL</div></div>', unsafe_allow_html=True)
                
                st.divider()
                
                # --- KAYDETME VE TEMİZLEME ALANI ---
                col_kaydet, col_temizle = st.columns([2, 1])
                
                notlar = st.text_input("Sipariş Notu (Opsiyonel):", placeholder="Örn: Haftaya teslim")
                
                with col_kaydet:
                    if st.button("💾 TEKLİFİ KAYDET", type="primary", use_container_width=True):
                        # İSİMLENDİRME MANTIĞI
                        final_musteri_adi = ""
                        
                        if yeni_secim == "⚡ HIZLI İŞLEM (Kayitsiz)":
                            if temp_ad_input:
                                final_musteri_adi = temp_ad_input
                            else:
                                # İSİMSİZ İŞ 1, 2, 3 MANTIĞI
                                df_sip = read_csv_from_github("siparisler.csv")
                                if not df_sip.empty:
                                    isimsiz_sayisi = len(df_sip[df_sip["Müşteri"].astype(str).str.startswith("İsimsiz İş")])
                                else:
                                    isimsiz_sayisi = 0
                                final_musteri_adi = f"İsimsiz İş {isimsiz_sayisi + 1}"
                        else:
                            final_musteri_adi = yeni_secim
                        
                        # KAYIT İŞLEMİ
                        df_sip = read_csv_from_github("siparisler.csv")
                        yeni_sip = pd.DataFrame([{
                            "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Müşteri": final_musteri_adi,
                            "İş Adı": notlar or "Genel Sipariş",
                            "Tutar": round(genel, 2),
                            "Detay": f"{len(guncel_sepet)} parça, {toplam_kg:.1f}kg"
                        }])
                        
                        save_csv_to_github("siparisler.csv", pd.concat([df_sip, yeni_sip], ignore_index=True))
                        
                        st.session_state.sepet = []
                        st.balloons()
                        st.success(f"✅ Başarıyla Kaydedildi: **{final_musteri_adi}**")
                        st.rerun()

                with col_temizle:
                    # Hepsini sil ve başa dön
                    if st.button("🗑️ TEMİZLE (İPTAL)", type="secondary", use_container_width=True):
                        st.session_state.sepet = []
                        st.rerun()

    else: st.info("Sepet boş.")

# --- SAYFA 2: MÜŞTERİ YÖNETİMİ ---
elif menu == "Müşteri Yönetimi":
    st.markdown('<p class="main-header">Müşteri Veritabanı</p>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Müşteri Geçmişi", "➕ Yeni Firma Ekle"])
    
    with tab1:
        # Verileri oku
        df_mus = read_csv_from_github("musteriler.csv")
        df_sip = read_csv_from_github("siparisler.csv")
        
        # Benzersiz müşteri listesi (Hem kayıtlı hem sipariş geçmişi olanlar)
        tum_musteriler = set()
        if not df_mus.empty: tum_musteriler.update(df_mus["Firma Adı"].dropna().tolist())
        if not df_sip.empty: tum_musteriler.update(df_sip["Müşteri"].dropna().tolist())
        
        sorted_musteriler = sorted(list(tum_musteriler))
        
        secilen_m = st.selectbox("Geçmişini Görmek İstediğin Müşteriyi Seç:", ["Seçiniz..."] + sorted_musteriler)
        
        if secilen_m != "Seçiniz...":
            # 1. Müşteri Bilgileri
            st.markdown("---")
            st.markdown(f"### 👤 {secilen_m}")
            
            bilgi = df_mus[df_mus["Firma Adı"] == secilen_m]
            if not bilgi.empty:
                b = bilgi.iloc[0]
                st.info(f"**Yetkili:** {b.get('Yetkili','-')} | **Tel:** {b.get('Telefon','-')} | **Adres:** {b.get('Adres','-')}")
            else:
                st.warning("Bu isimde kayıtlı firma kartı yok (Sadece hızlı işlem yapılmış).")
            
            # 2. Sipariş Geçmişi
            st.markdown("#### 📜 Sipariş Geçmişi")
            if not df_sip.empty:
                siparisler = df_sip[df_sip["Müşteri"] == secilen_m]
                if not siparisler.empty:
                    st.dataframe(siparisler, use_container_width=True)
                    toplam = siparisler["Tutar"].sum()
                    st.success(f"💰 Toplam Ciro: **{toplam:,.2f} TL**")
                else:
                    st.info("Bu müşteriye ait sipariş bulunamadı.")
            else:
                st.info("Henüz hiç sipariş yok.")

    with tab2:
        with st.form("yeni_mus"):
            f = st.text_input("Firma Adı")
            y = st.text_input("Yetkili")
            t = st.text_input("Telefon")
            a = st.text_input("Adres")
            if st.form_submit_button("Kaydet"):
                df_mus = read_csv_from_github("musteriler.csv")
                if f:
                    yeni = pd.DataFrame([{"Firma Adı": f, "Yetkili": y, "Telefon": t, "Adres": a}])
                    save_csv_to_github("musteriler.csv", pd.concat([df_mus, yeni], ignore_index=True))
                    st.success("Eklendi!")
                    st.rerun()
                else: st.error("İsim girin.")

# --- SAYFA 3: AYARLAR ---
elif menu == "Ayarlar & Malzemeler":
    st.markdown('<p class="main-header">Ayarlar</p>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["⚙️ Genel", "🔩 Malzemeler"])
    
    with tab1:
        c1, c2 = st.columns(2)
        yd = c1.number_input("Dolar", value=DOLAR)
        yk = c2.number_input("Kâr (%)", value=KAR)
        yl = c1.number_input("Lazer (TL/dk)", value=LAZER_DK)
        ya = c2.number_input("Abkant (TL/vuruş)", value=ABKANT_TL)
        ykdv = st.selectbox("KDV", ["Evet", "Hayır"], index=0 if KDV_DURUM=="Evet" else 1)
        
        if st.button("Ayarları Kaydet"):
            df_ayar.loc[df_ayar['Ayar']=='dolar_kuru', 'Deger'] = yd
            df_ayar.loc[df_ayar['Ayar']=='kar_orani', 'Deger'] = yk
            df_ayar.loc[df_ayar['Ayar']=='lazer_dk', 'Deger'] = yl
            df_ayar.loc[df_ayar['Ayar']=='abkant_vurus', 'Deger'] = ya
            df_ayar.loc[df_ayar['Ayar']=='kdv_durum', 'Deger'] = ykdv
            save_csv_to_github("ayarlar.csv", df_ayar)
            st.session_state.ayarlar_cache = df_ayar
            st.success("Güncellendi!")
            st.rerun()
            
    with tab2:
        df_m = st.session_state.malzeme_cache
        edited_m = st.data_editor(df_m, num_rows="dynamic", use_container_width=True)
        if st.button("Malzeme Listesini Kaydet"):
            save_csv_to_github("malzemeler.csv", edited_m)
            st.session_state.malzeme_cache = edited_m
            st.success("Kaydedildi!")
