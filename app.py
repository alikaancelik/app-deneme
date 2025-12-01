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
# Word desteği için
try:
    from docx import Document
except ImportError:
    st.error("python-docx kütüphanesi eksik.")

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="ÖZÇELİK ENDÜSTRİ", layout="wide", page_icon="🏭")

# --- CSS (KESİN SİYAH YAZI) ---
st.markdown("""
    <style>
    .main-header {font-size: 28px; font-weight: bold; color: #0f172a;}
    
    /* Kartların içi her zaman beyaz, yazılar her zaman SİYAH olsun */
    div[data-testid="metric-container"] {
        background-color: #ffffff !important;
        border: 1px solid #cccccc !important;
        padding: 10px !important;
        border-radius: 5px !important;
        color: #000000 !important;
    }
    
    label {color: #000000 !important; font-weight: bold;}
    
    .stMetricValue {
        color: #000000 !important; /* Rakam rengi */
    }
    
    .stMetricLabel {
        color: #333333 !important; /* Başlık rengi */
    }
    
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
        return pd.read_csv(io.StringIO(content))
    except:
        # Varsayılanlar
        if "ayar" in filename: return pd.DataFrame([
            {"Key":"dolar", "Val":34.50}, {"Key":"kar", "Val":25.0}, 
            {"Key":"kdv", "Val":20.0}, {"Key":"lazer_dk", "Val":25.0}, {"Key":"abkant", "Val":15.0}
        ])
        if "malz" in filename: return pd.DataFrame([{"Ad":"Siyah Sac", "Fiyat":0.85, "Kur":"USD", "Yog":7.85}])
        if "siparis" in filename: return pd.DataFrame(columns=["Tarih", "İş Adı", "Tutar", "Detay"])
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

# Değişkenleri Yükle
try:
    df_a = st.session_state.db_ayar.set_index("Key")
    DOLAR = float(df_a.loc["dolar", "Val"])
    KAR = float(df_a.loc["kar", "Val"])
    KDV_ORAN = float(df_a.loc["kdv", "Val"])
    LAZER_DK = float(df_a.loc["lazer_dk", "Val"])
    ABKANT_TL = float(df_a.loc["abkant", "Val"])
except:
    DOLAR, KAR, KDV_ORAN, LAZER_DK, ABKANT_TL = 34.50, 25.0, 20.0, 25.0, 15.0

# Sepet
if 'sepet' not in st.session_state: st.session_state.sepet = []

# --- ANALİZ (WORD + RESİM) ---
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
        # WORD OKUMA
        if tip == "docx":
            doc = Document(dosya)
            text_list = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    text_list.append(" ".join([cell.text for cell in row.cells]))
            text = "\n".join(text_list)
            
        # RESİM OKUMA
        else:
            img_np = np.array(Image.open(dosya))
            if len(img_np.shape) == 3: img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else: img_gray = img_np
            _, img_thresh = cv2.threshold(img_gray, 150, 255, cv2.THRESH_BINARY)
            text = pytesseract.image_to_string(Image.fromarray(img_thresh))

        # REGEX İLE VERİ ÇEKME
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
        
    except Exception as e:
        print(f"Hata: {e}")
        
    return veriler

# --- ARAYÜZ ---
with st.sidebar:
    st.title("🏭 ÖZÇELİK")
    menu = st.radio("Menü", ["Hesaplama", "Sipariş Geçmişi", "Ayarlar"])
    st.divider()
    st.info(f"💲 Dolar: {DOLAR}")

# ==================================================
# 1. HESAPLAMA (MÜŞTERİ SEÇİMİ YOK, DİREKT İŞ)
# ==================================================
if menu == "Hesaplama":
    st.markdown('<p class="main-header">Teklif Hesaplayıcı</p>', unsafe_allow_html=True)
    
    # GİRİŞ ALANI
    with st.expander("➕ Parça Ekle (Manuel & Word & Resim)", expanded=True):
        tab_man, tab_dos = st.tabs(["✍️ Manuel", "📂 Dosya (Word/Resim)"])
        
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
                        "Büküm": int(i_bukum or 0)
                    })
                    st.rerun()
                else: st.error("Ölçü girin.")

        with tab_dos:
            # BURADA DOCX DESTEĞİ VAR
            files = st.file_uploader("Dosya Sürükle (Resim veya Word)", type=['png', 'jpg', 'jpeg', 'docx'], accept_multiple_files=True)
            
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
                        "Büküm": 0
                    })
                st.success("Dosyalar eklendi!")
                st.rerun()

    # SEPET LİSTESİ
    if st.session_state.sepet:
        st.markdown("### 🛒 Liste")
        df_sepet = pd.DataFrame(st.session_state.sepet)
        
        # SİLMEK İÇİN CHECKBOX
        edited_df = st.data_editor(
            df_sepet,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "En": st.column_config.NumberColumn("En (mm)", format="%.1f"),
                "Boy": st.column_config.NumberColumn("Boy (mm)", format="%.1f"),
                "Kalınlık": st.column_config.NumberColumn("Kal (mm)", format="%.1f"),
            }
        )
        
        # HESAPLA
        if st.button("💰 HESAPLA", type="primary"):
            final_sepet = edited_df.to_dict('records')
            
            toplam_tl = 0
            toplam_kg = 0
            
            # Malzeme verisini hazırla
            try:
                df_m = st.session_state.db_malz.set_index("Ad")
            except:
                st.error("Malzeme veritabanı hatası.")
                st.stop()
            
            for item in final_sepet:
                try:
                    # Malzeme bilgilerini çek
                    if item["Malzeme"] in df_m.index:
                        m_info = df_m.loc[item["Malzeme"]]
                        m_fiyat = float(m_info["Fiyat"])
                        m_yog = float(m_info["Yog"])
                        if m_info["Kur"] == "USD": m_fiyat *= DOLAR
                    else:
                        # Bulamazsa varsayılan
                        m_fiyat = 0.85 * DOLAR
                        m_yog = 7.85
                    
                    # Hesap
                    hacim = item["En"] * item["Boy"] * item["Kalınlık"]
                    kg = (hacim * m_yog) / 1_000_000 * item["Adet"]
                    
                    tutar_malz = kg * m_fiyat
                    tutar_iscilik = (item["Süre"] * item["Adet"] * LAZER_DK) + (item["Büküm"] * item["Adet"] * ABKANT_TL)
                    
                    toplam_tl += tutar_malz + tutar_iscilik
                    toplam_kg += kg
                except: pass
            
            # Kâr ve KDV
            karli = toplam_tl * (1 + KAR/100)
            kdv = karli * (KDV_ORAN/100)
            son_fiyat = karli + kdv
            
            st.session_state.sonuc = {"kg": toplam_kg, "ham": toplam_tl, "son": son_fiyat}

        # SONUÇ GÖSTERİMİ (BEYAZ KART İÇİNDE SİYAH YAZI)
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
            is_adi = col_k.text_input("İşin Adı (Kaydetmek için yazın):")
            
            if col_k.button("💾 LİSTEYE KAYDET"):
                df_s = load_data("siparisler.csv")
                new_s = pd.DataFrame([{
                    "Tarih": datetime.now().strftime("%d-%m-%Y %H:%M"),
                    "İş Adı": is_adi or "Genel İş",
                    "Tutar": round(res["son"], 2),
                    "Detay": f"{res['kg']:.1f}kg"
                }])
                save_data("siparisler.csv", pd.concat([df_s, new_s], ignore_index=True))
                st.success("Kaydedildi!")
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
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        st.info(f"Toplam Kayıtlı İş: {len(df)}")
    else:
        st.warning("Henüz kayıt yok.")

# ==================================================
# 3. AYARLAR
# ==================================================
elif menu == "Ayarlar":
    st.header("⚙️ Ayarlar")
    
    # Hata veren tab1, tab2 yapısını düzelttim
    tab_genel, tab_malz = st.tabs(["Genel", "Malzemeler"])
    
    with tab_genel:
        c1, c2 = st.columns(2)
        n_dolar = c1.number_input("Dolar", value=DOLAR)
        n_kar = c2.number_input("Kâr (%)", value=KAR)
        n_kdv = c1.number_input("KDV (%)", value=KDV_ORAN)
        n_lazer = c2.number_input("Lazer (TL/dk)", value=LAZER_DK)
        n_abkant = st.number_input("Abkant (TL/vuruş)", value=ABKANT_TL)
        
        if st.button("Ayarları Kaydet"):
            new_df = pd.DataFrame([
                {"Key":"dolar", "Val":n_dolar}, {"Key":"kar", "Val":n_kar}, 
                {"Key":"kdv", "Val":n_kdv}, {"Key":"lazer_dk", "Val":n_lazer}, {"Key":"abkant", "Val":n_abkant}
            ])
            save_data("ayarlar.csv", new_df)
            del st.session_state.db_ayar
            st.success("Kaydedildi!")
            st.rerun()

    with tab_malz:
        df_m = st.session_state.db_malz
        edited = st.data_editor(df_m, num_rows="dynamic", use_container_width=True)
        if st.button("Malzemeleri Kaydet"):
            save_data("malzemeler.csv", edited)
            del st.session_state.db_malz
            st.success("Güncellendi!")
            st.rerun()
