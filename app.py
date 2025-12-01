import streamlit as st
import pandas as pd
from github import Github
import io
from datetime import datetime
import time
from PIL import Image
import cv2
import pytesseract
import numpy as np
# Word desteği
try:
    from docx import Document
except ImportError:
    pass

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="ÖZÇELİK ENDÜSTRİ", layout="wide", page_icon="🏭")

# --- CSS (GÖRÜNÜM: NET SİYAH YAZILAR) ---
st.markdown("""
    <style>
    .main-header {font-size: 28px; font-weight: bold; color: #0f172a;}
    
    div[data-testid="metric-container"] {
        background-color: #ffffff !important;
        border: 1px solid #cccccc !important;
        padding: 10px !important;
        border-radius: 5px !important;
        color: #000000 !important;
    }
    label {color: #000000 !important; font-weight: bold;}
    .stMetricValue {color: #000000 !important;}
    .stMetricLabel {color: #333333 !important;}
    .stButton>button {width: 100%; border-radius: 5px; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

# --- GITHUB BAĞLANTISI ---
def get_repo():
    token = st.secrets["github"]["token"]
    repo_name = st.secrets["github"]["repo_name"]
    return Github(token).get_repo(repo_name)

def load_data(filename):
    """Veriyi okur"""
    try:
        repo = get_repo()
        content = repo.get_contents(filename).decoded_content.decode()
        df = pd.read_csv(io.StringIO(content))
        
        # MALZEME DOSYASI İÇİN ÖZEL DÜZELTME (TL'ye Çeviri)
        if "malz" in filename:
            # Eğer eski dosya geldiyse sütunları düzelt
            rename_map = {"Malzeme": "Ad", "Birim Fiyat": "Fiyat", "Yoğunluk": "Yog"}
            df.rename(columns=rename_map, inplace=True)
            # Ad, Fiyat, Yog sütunlarının olduğundan emin ol
            if "Ad" not in df.columns: df["Ad"] = "Siyah Sac"
            if "Fiyat" not in df.columns: df["Fiyat"] = 30.0
            if "Yog" not in df.columns: df["Yog"] = 7.85
            # Sadece ihtiyacımız olanları al
            df = df[["Ad", "Fiyat", "Yog"]]
            
        return df
    except:
        # Varsayılanlar (TL BAZLI)
        if "ayar" in filename: return pd.DataFrame([
            {"Key":"kar", "Val":25.0}, 
            {"Key":"kdv", "Val":20.0}, 
            {"Key":"lazer_dk", "Val":25.0}, 
            {"Key":"abkant", "Val":15.0}
        ])
        if "malz" in filename: return pd.DataFrame([
            {"Ad":"Siyah Sac", "Fiyat":32.0, "Yog":7.85},
            {"Ad":"Paslanmaz", "Fiyat":180.0, "Yog":7.93},
            {"Ad":"Galvaniz", "Fiyat":45.0, "Yog":7.85},
            {"Ad":"ST52", "Fiyat":38.0, "Yog":7.85},
            {"Ad":"Hardox 450", "Fiyat":120.0, "Yog":7.85}
        ])
        if "siparis" in filename: return pd.DataFrame(columns=["Tarih", "Müşteri", "İş Adı", "Tutar", "Detay"])
        if "musteri" in filename: return pd.DataFrame(columns=["Firma", "Yetkili", "Tel", "Adres"])
        return pd.DataFrame()

def save_data(filename, df):
    """Veriyi kaydeder"""
    repo = get_repo()
    try:
        contents = repo.get_contents(filename)
        repo.update_file(contents.path, "Update", df.to_csv(index=False), contents.sha)
    except:
        repo.create_file(filename, "New", df.to_csv(index=False))

# --- AYARLARI ÇEK ---
if 'db_ayar' not in st.session_state:
    st.session_state.db_ayar = load_data("ayarlar.csv")
    st.session_state.db_malz = load_data("malzemeler.csv")

# Değişkenleri Yükle (TL)
try:
    df_a = st.session_state.db_ayar.set_index("Key")
    KAR = float(df_a.loc["kar", "Val"])
    KDV_ORAN = float(df_a.loc["kdv", "Val"])
    LAZER_DK = float(df_a.loc["lazer_dk", "Val"])
    ABKANT_TL = float(df_a.loc["abkant", "Val"])
except:
    KAR, KDV_ORAN, LAZER_DK, ABKANT_TL = 25.0, 20.0, 25.0, 15.0

# Sepet
if 'sepet' not in st.session_state: st.session_state.sepet = []

# --- ANALİZ ---
def sure_cevir(zaman_str):
    try:
        parts = list(map(int, str(zaman_str).strip().split(':')))
        if len(parts) == 3: return (parts[0] * 60) + parts[1] + (parts[2] / 60)
        elif len(parts) == 2: return parts[0] + (parts[1] / 60)
        return 0.0
    except: return 0.0

def analiz_et(dosya, tip):
    veriler = {"x":0.0, "y":0.0, "sure":0.0, "kal":2.0, "malz":"Siyah Sac"}
    text = ""
    try:
        if tip == "docx":
            doc = Document(dosya)
            text_list = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    text_list.append(" ".join([cell.text for cell in row.cells]))
            text = "\n".join(text_list)
        else:
            img_np = np.array(Image.open(dosya))
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
        elif "st52" in tl: veriler["malz"] = "ST52"
    except: pass
    return veriler

# --- ARAYÜZ ---
with st.sidebar:
    st.image("https://ozcelikendustri.com/wp-content/uploads/2021/01/logo-1.png", width=200)
    st.title("ÖZÇELİK")
    menu = st.radio("Menü", ["Hesaplama", "Sipariş Geçmişi", "Ayarlar"])
    st.divider()
    st.info(f"Kâr: %{KAR}")

# ==================================================
# 1. HESAPLAMA (MÜŞTERİ SEÇİMİ YOK, DİREKT İŞ)
# ==================================================
if menu == "Hesaplama":
    st.header("Teklif Hesaplayıcı")
    
    # BASİT MÜŞTERİ GİRİŞİ (ZORUNLU DEĞİL)
    col_mus, col_info = st.columns([2, 1])
    with col_mus:
        musteri_adi = st.text_input("Müşteri / İş Adı (Opsiyonel):", placeholder="Örn: Ahmet Bey")
    
    if not musteri_adi:
        musteri_adi = f"İsimsiz İş {datetime.now().strftime('%H%M')}"

    st.divider()

    # GİRİŞ ALANI
    with st.expander("➕ Parça Ekle (Manuel & Word & Resim)", expanded=True):
        tab_man, tab_dos = st.tabs(["✍️ Manuel", "📂 Dosya"])
        
        with tab_man:
            c1, c2, c3 = st.columns(3)
            # Malzemeler
            malz_opt = ["Siyah Sac"]
            if "Ad" in st.session_state.db_malz.columns:
                malz_opt = st.session_state.db_malz["Ad"].tolist()
                
            i_malz = c1.selectbox("Malzeme", malz_opt)
            i_kal = c2.number_input("Kalınlık (mm)", value=None, placeholder="2")
            i_adet = c3.number_input("Adet", value=None, min_value=1, placeholder="1")
            
            c4, c5, c6 = st.columns(3)
            birim = c4.radio("Birim", ["mm", "cm", "m"], horizontal=True)
            i_en = c5.number_input("En", value=None, placeholder="Genişlik")
            i_boy = c6.number_input("Boy", value=None, placeholder="Uzunluk")
            
            c7, c8 = st.columns(2)
            i_sure = c7.number_input("Kesim (dk)", value=None, placeholder="0")
            i_bukum = c8.number_input("Büküm", value=None, placeholder="0")
            
            if st.button("Listeye Ekle"):
                if i_en and i_boy and i_kal:
                    carp = 1000 if birim == "m" else (10 if birim == "cm" else 1)
                    st.session_state.sepet.append({
                        "Malzeme": i_malz, 
                        "Kalınlık": float(i_kal),
                        "En": float(i_en) * carp,
                        "Boy": float(i_boy) * carp,
                        "Adet": int(i_adet or 1),
                        "Süre": float(i_sure or 0),
                        "Büküm": int(i_bukum or 0),
                        "Sil": False
                    })
                    st.rerun()
                else: st.error("Ölçü girin.")

        with tab_dos:
            files = st.file_uploader("Dosya Yükle", type=['png', 'jpg', 'jpeg', 'docx'], accept_multiple_files=True)
            if st.button("Analiz Et ve Ekle"):
                for f in files:
                    vals = {}
                    if f.name.endswith('.docx'):
                        vals = analiz_et(f, "docx")
                    else:
                        vals = analiz_et(f, "img")
                    st.session_state.sepet.append({
                        "Malzeme": vals.get("malz", "Siyah Sac"),
                        "Kalınlık": vals.get("kal", 2.0),
                        "En": vals.get("y", 1000.0),
                        "Boy": vals.get("x", 2000.0),
                        "Adet": 1,
                        "Süre": vals.get("sure", 0.0),
                        "Büküm": 0,
                        "Sil": False
                    })
                st.success("Eklendi")
                st.rerun()

    # SEPET TABLOSU
    if st.session_state.sepet:
        st.markdown("### 🛒 Liste")
        df_sepet = pd.DataFrame(st.session_state.sepet)
        
        edited_df = st.data_editor(
            df_sepet,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Sil": st.column_config.CheckboxColumn("Sil?", width="small"),
                "En": st.column_config.NumberColumn("En (mm)", format="%.1f"),
                "Boy": st.column_config.NumberColumn("Boy (mm)", format="%.1f"),
                "Kalınlık": st.column_config.NumberColumn("Kal (mm)", format="%.1f"),
            }
        )
        
        # HESAPLA
        if st.button("💰 HESAPLA", type="primary"):
            final_sepet = [r for r in edited_df.to_dict('records') if not r.get("Sil")]
            
            toplam_tl = 0
            toplam_kg = 0
            
            try:
                df_m = st.session_state.db_malz.set_index("Ad")
            except:
                st.error("Malzeme veritabanı hatası.")
                st.stop()
            
            for item in final_sepet:
                try:
                    # Malzeme Fiyatını Al (TL)
                    if item["Malzeme"] in df_m.index:
                        m_info = df_m.loc[item["Malzeme"]]
                        m_fiyat = float(m_info["Fiyat"])
                        m_yog = float(m_info["Yog"])
                    else:
                        m_fiyat = 32.0 # Varsayılan TL
                        m_yog = 7.85
                    
                    hacim = item["En"] * item["Boy"] * item["Kalınlık"]
                    kg = (hacim * m_yog) / 1_000_000 * item["Adet"]
                    
                    tutar_malz = kg * m_fiyat
                    tutar_iscilik = (item["Süre"] * item["Adet"] * LAZER_DK) + (item["Büküm"] * item["Adet"] * ABKANT_TL)
                    
                    toplam_tl += tutar_malz + tutar_iscilik
                    toplam_kg += kg
                except: pass
            
            karli = toplam_tl * (1 + KAR/100)
            kdv = karli * (KDV_ORAN/100)
            son_fiyat = karli + kdv
            
            st.session_state.sonuc = {"kg": toplam_kg, "ham": toplam_tl, "son": son_fiyat, "items": final_sepet}

        # SONUÇ GÖSTERİMİ
        if 'sonuc' in st.session_state:
            res = st.session_state.sonuc
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Toplam Ağırlık", f"{res['kg']:.1f} kg")
            c2.metric("Maliyet", f"{res['ham']:,.0f} TL")
            c3.metric("TEKLİF (+KDV)", f"{res['son']:,.0f} TL")
            
            st.divider()
            
            # KAYDETME
            col_k, col_t = st.columns([2,1])
            not_txt = col_k.text_input("Sipariş Notu (Opsiyonel):")
            
            if col_k.button("💾 KAYDET"):
                with st.spinner("Kaydediliyor..."):
                    # Siparişi Kaydet
                    df_s = load_data("siparisler.csv")
                    new_s = pd.DataFrame([{
                        "Tarih": datetime.now().strftime("%d-%m-%Y %H:%M"),
                        "Müşteri": musteri_adi,
                        "İş Adı": not_txt or "Genel",
                        "Tutar": round(res["son"], 2),
                        "Detay": f"{len(res['items'])} parça"
                    }])
                    save_data("siparisler.csv", pd.concat([df_s, new_s], ignore_index=True))
                    
                    # Müşteriyi de kaydet
                    df_mus = load_data("musteriler.csv")
                    if musteri_adi not in df_mus["Firma"].values:
                        new_mus = pd.DataFrame([{"Firma": musteri_adi, "Yetkili": "-", "Tel": "-", "Adres": "-"}])
                        save_data("musteriler.csv", pd.concat([df_mus, new_mus], ignore_index=True))

                    st.success(f"✅ {musteri_adi} kaydedildi!")
                    st.session_state.sepet = []
                    del st.session_state.sonuc
                    time.sleep(1)
                    st.rerun()
            
            if col_t.button("🗑️ TEMİZLE"):
                st.session_state.sepet = []
                if 'sonuc' in st.session_state: del st.session_state.sonuc
                st.rerun()

# ==================================================
# 2. SİPARİŞ GEÇMİŞİ
# ==================================================
elif menu == "Sipariş Geçmişi":
    st.header("📜 Geçmiş İşler")
    df = load_data("siparisler.csv")
    
    if df.empty:
        st.warning("Henüz kayıt yok.")
    else:
        # Arama
        search = st.text_input("🔍 Ara (Müşteri veya Tarih):")
        if search:
            mask = df.apply(lambda x: x.astype(str).str.contains(search, case=False)).any(axis=1)
            df = df[mask]
        
        # Silme Özelliği
        df["Sil"] = False
        cols = ["Sil", "Tarih", "Müşteri", "İş", "Tutar"]
        if "Detay" in df.columns: cols.append("Detay")
        
        # Hata önleyici: Sadece var olan kolonları göster
        mevcut_cols = [c for c in cols if c in df.columns]
        
        edited_hist = st.data_editor(df[mevcut_cols], hide_index=True, use_container_width=True)
        
        if st.button("🗑️ Seçili Kayıtları Sil"):
            to_delete = edited_hist[edited_hist["Sil"]]
            if not to_delete.empty:
                full_df = load_data("siparisler.csv")
                # Basit eşleştirme
                def create_key(row): return f"{row['Tarih']}_{row['Müşteri']}_{row['Tutar']}"
                
                full_df['key'] = full_df.apply(create_key, axis=1)
                to_delete['key'] = to_delete.apply(create_key, axis=1)
                
                new_df = full_df[~full_df['key'].isin(to_delete['key'])].drop(columns=['key'])
                
                save_data("siparisler.csv", new_df)
                st.success("Silindi!")
                st.rerun()

# ==================================================
# 3. AYARLAR
# ==================================================
elif menu == "Ayarlar":
    st.header("⚙️ Ayarlar")
    
    tab1, tab2 = st.tabs(["Genel", "Malzemeler (TL)"])
    
    with tab1:
        c1, c2 = st.columns(2)
        n_kar = c1.number_input("Kâr (%)", value=KAR)
        n_kdv = c2.number_input("KDV (%)", value=KDV_ORAN)
        n_lazer = c1.number_input("Lazer (TL/dk)", value=LAZER_DK)
        n_abkant = c2.number_input("Abkant (TL/vuruş)", value=ABKANT_TL)
        
        if st.button("Ayarları Kaydet"):
            new_df = pd.DataFrame([
                {"Key":"kar", "Val":n_kar}, {"Key":"kdv", "Val":n_kdv}, 
                {"Key":"lazer_dk", "Val":n_lazer}, {"Key":"abkant", "Val":n_abkant}
            ])
            save_data("ayarlar.csv", new_df)
            del st.session_state.db_ayar
            st.success("Kaydedildi!")
            st.rerun()

    with tab2:
        df_m = st.session_state.db_malz
        edited = st.data_editor(
            df_m, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "Fiyat": st.column_config.NumberColumn("Fiyat (TL)", format="%.2f")
            }
        )
        if st.button("Malzemeleri Kaydet"):
            save_data("malzemeler.csv", edited)
            del st.session_state.db_malz
            st.success("Güncellendi!")
            st.rerun()
