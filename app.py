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

# --- CSS (GÖRÜNÜM AYARLARI) ---
st.markdown("""
    <style>
    .main-header {font-size: 28px; font-weight: bold; color: #ffffff;}
    
    /* Input Başlıklarını BEYAZ Yap (İsteğin Üzerine) */
    label, .stMarkdown p {
        color: #ffffff !important;
        font-weight: 500;
    }
    
    /* Sonuç Kartları: Beyaz Zemin, Siyah Yazı (Okunabilirlik İçin) */
    div[data-testid="metric-container"] {
        background-color: #ffffff !important;
        border: 1px solid #cccccc !important;
        padding: 10px !important;
        border-radius: 5px !important;
        color: #000000 !important;
    }
    div[data-testid="metric-container"] label {
        color: #333333 !important; /* Kart içindeki başlık gri olsun */
    }
    div[data-testid="metric-container"] div {
        color: #000000 !important; /* Rakamlar siyah olsun */
    }
    
    .stButton>button {width: 100%; border-radius: 5px; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

# --- VARSAYILAN VERİTABANI (Eğer GitHub boşsa burası devreye girer) ---
DEFAULT_MALZEMELER = [
    {"Malzeme": "Siyah Sac", "Fiyat": 0.85, "Birim": "USD", "Yogunluk": 7.85},
    {"Malzeme": "Paslanmaz", "Fiyat": 3.50, "Birim": "USD", "Yogunluk": 7.93},
    {"Malzeme": "Galvaniz", "Fiyat": 1.00, "Birim": "USD", "Yogunluk": 7.85},
    {"Malzeme": "ST52", "Fiyat": 0.95, "Birim": "USD", "Yogunluk": 7.85},
    {"Malzeme": "Hardox 400", "Fiyat": 2.00, "Birim": "USD", "Yogunluk": 7.85},
    {"Malzeme": "Hardox 450", "Fiyat": 2.20, "Birim": "USD", "Yogunluk": 7.85},
    {"Malzeme": "Hardox 500", "Fiyat": 2.50, "Birim": "USD", "Yogunluk": 7.85}
]

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
        if "malz" in filename: return pd.DataFrame(DEFAULT_MALZEMELER)
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
        if "hardox" in tl:
            if "400" in tl: veriler["malz"] = "Hardox 400"
            elif "500" in tl: veriler["malz"] = "Hardox 500"
            else: veriler["malz"] = "Hardox 450"
        elif "st52" in tl: veriler["malz"] = "ST52"
        elif "paslanmaz" in tl: veriler["malz"] = "Paslanmaz"
        elif "galvaniz" in tl: veriler["malz"] = "Galvaniz"
        
    except Exception as e:
        print(f"Hata: {e}")
        
    return veriler

# --- ARAYÜZ ---
with st.sidebar:
    st.image("https://ozcelikendustri.com/wp-content/uploads/2021/01/logo-1.png", width=200)
    st.title("ÖZÇELİK")
    menu = st.radio("Menü", ["Hesaplama", "Sipariş Geçmişi", "Ayarlar"])
    st.divider()
    st.info(f"💲 Dolar: {DOLAR}")

# ==================================================
# 1. HESAPLAMA (OTURMUŞ SİSTEM)
# ==================================================
if menu == "Hesaplama":
    st.markdown('<p class="main-header">Teklif Hesaplayıcı</p>', unsafe_allow_html=True)
    
    # --- MÜŞTERİ SEÇİMİ ---
    df_mus = load_data("musteriler.csv")
    kayitli_list = df_mus["Firma"].tolist() if not df_mus.empty else []
    
    # Başlıkları Beyaz Yapmıştık (CSS)
    secim_tipi = st.radio("İşlem Türü:", ["⚡ Hızlı (Yeni/Kayıtsız)", "📂 Kayıtlı Müşteri"], horizontal=True)
    
    aktif_musteri = ""
    
    if secim_tipi == "📂 Kayıtlı Müşteri":
        if not kayitli_list:
            st.warning("Kayıtlı müşteri yok.")
        else:
            aktif_musteri = st.selectbox("Firma Seç:", kayitli_list)
    else:
        c1, c2 = st.columns([2,1])
        girilen = c1.text_input("Müşteri Adı (Boşsa 'İsimsiz' olur):")
        # Otomatik isimlendirme
        if girilen:
            aktif_musteri = girilen
        else:
            # İsimsiz X mantığı
            df_sip = load_data("siparisler.csv")
            sayi = 1
            if not df_sip.empty:
                sayi = len(df_sip[df_sip["Müşteri"].str.contains("İsimsiz")]) + 1
            aktif_musteri = f"İsimsiz İş {sayi}"
            
        c2.info(f"Kayıt: **{aktif_musteri}**")

    st.divider()

    # --- MANUEL GİRİŞ ---
    with st.expander("➕ Parça Ekle (Manuel & Word & Resim)", expanded=True):
        tab_man, tab_dos = st.tabs(["✍️ Manuel", "📂 Dosya (Word/Resim)"])
        
        with tab_man:
            c1, c2, c3 = st.columns(3)
            # Malzemeler veritabanından, yoksa varsayılandan
            if "Malzeme" in st.session_state.db_malz.columns:
                malz_opt = st.session_state.db_malz["Malzeme"].tolist()
            else:
                malz_opt = [m["Malzeme"] for m in DEFAULT_MALZEMELER]
                
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
            files = st.file_uploader("Dosya Sürükle", type=['png', 'jpg', 'jpeg', 'docx'], accept_multiple_files=True)
            
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
                st.success("Dosyalar eklendi!")
                st.rerun()

    # --- SEPET TABLOSU ---
    if st.session_state.sepet:
        st.markdown("### 🛒 Liste")
        df_sepet = pd.DataFrame(st.session_state.sepet)
        
        # SİLMEK İÇİN CHECKBOX
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
                df_m = st.session_state.db_malz.set_index("Malzeme")
            except:
                st.error("Malzeme listesi hatası.")
                st.stop()
            
            for item in final_sepet:
                try:
                    if item["Malzeme"] in df_m.index:
                        m_info = df_m.loc[item["Malzeme"]]
                        m_fiyat = float(m_info["Fiyat"])
                        m_yog = float(m_info["Yogunluk"])
                        if m_info["Birim"] == "USD": m_fiyat *= DOLAR
                    else:
                        m_fiyat = 0.85 * DOLAR
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
            c1.markdown(f'<div class="metric-card"><div class="metric-label">Toplam Ağırlık</div><div class="metric-val">{res["kg"]:.1f} kg</div></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="metric-card"><div class="metric-label">Maliyet</div><div class="metric-val">{res["ham"]:,.0f} TL</div></div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="metric-card" style="border-color: green;"><div class="metric-label">TEKLİF (+KDV)</div><div class="metric-val" style="color:#000000 !important;">{res["son"]:,.0f} TL</div></div>', unsafe_allow_html=True)
            
            st.divider()
            
            # KAYDETME
            c_save, c_clear = st.columns([2,1])
            not_txt = c_save.text_input("İş Notu:", placeholder="İşin detayı...")
            
            if c_save.button("💾 MÜŞTERİYE KAYDET"):
                with st.spinner("Kaydediliyor..."):
                    # 1. Müşteriyi Kaydet (Eğer yoksa)
                    df_m = load_data("musteriler.csv")
                    if aktif_musteri not in df_m["Firma"].values:
                        new_m = pd.DataFrame([{"Firma": aktif_musteri, "Yetkili": "-", "Tel": "-", "Adres": "-"}])
                        save_data("musteriler.csv", pd.concat([df_m, new_m], ignore_index=True))
                    
                    # 2. Siparişi Kaydet
                    df_s = load_data("siparisler.csv")
                    new_s = pd.DataFrame([{
                        "Tarih": datetime.now().strftime("%d-%m-%Y %H:%M"),
                        "Müşteri": aktif_musteri,
                        "İş Adı": not_txt or "Genel",
                        "Tutar": round(res["son"], 2),
                        "Detay": f"{len(res['items'])} parça"
                    }])
                    save_data("siparisler.csv", pd.concat([df_s, new_s], ignore_index=True))
                    
                    st.success(f"✅ {aktif_musteri} kaydedildi!")
                    st.session_state.sepet = []
                    del st.session_state.sonuc
                    time.sleep(1)
                    st.rerun()
            
            if c_clear.button("🗑️ TEMİZLE (İPTAL)"):
                st.session_state.sepet = []
                if 'sonuc' in st.session_state: del st.session_state.sonuc
                st.rerun()

# ==================================================
# 2. SİPARİŞ GEÇMİŞİ (ARAMA VE SİLME EKLENDİ)
# ==================================================
elif menu == "Sipariş Geçmişi":
    st.header("📜 Geçmiş İşler")
    
    df_sip = load_data("siparisler.csv")
    
    if df_sip.empty:
        st.warning("Henüz kayıt yok.")
    else:
        # ARAMA ÇUBUĞU
        arama = st.text_input("🔍 Ara (İş Adı, Müşteri veya Tarih)", placeholder="Örn: Ahmet veya 2024...")
        
        # Filtreleme
        if arama:
            df_sip = df_sip[
                df_sip["Müşteri"].astype(str).str.contains(arama, case=False) |
                df_sip["İş Adı"].astype(str).str.contains(arama, case=False) |
                df_sip["Tarih"].astype(str).str.contains(arama, case=False)
            ]
        
        if df_sip.empty:
            st.info("Sonuç bulunamadı.")
        else:
            # SİLMEK İÇİN CHECKBOX EKLE
            # Önce "Sil" sütunu ekleyelim varsayılan False
            df_sip["Sil"] = False
            
            edited_history = st.data_editor(
                df_sip,
                column_config={
                    "Sil": st.column_config.CheckboxColumn("Sil?", width="small")
                },
                use_container_width=True,
                hide_index=True
            )
            
            if st.button("🗑️ Seçili Geçmişi Sil"):
                # Silinmeyecek olanları (Sil=False olanları) al
                to_keep = edited_history[~edited_history["Sil"]]
                
                # Orijinal dosyayı güncelle (Arada filtrelenmiş veriyi kaybetmemek için tüm dosyayı yeniden yükleyip ID ile eşleştirmek daha doğru ama burada basitçe üzerine yazıyoruz)
                # Daha güvenli yöntem: Tüm veriyi çek, sadece silinenleri çıkar.
                full_df = load_data("siparisler.csv")
                
                # Eşleştirme (Tarih + Müşteri + İş Adı + Tutar kombinasyonu benzersiz sayılır basitçe)
                # Silineceklerin listesini oluştur
                to_delete = edited_history[edited_history["Sil"]]
                
                if not to_delete.empty:
                    # Merge ile silinenleri ana listeden düşür
                    keys = ["Tarih", "Müşteri", "İş Adı", "Tutar"]
                    # Left join indicator ile
                    merged = full_df.merge(to_delete[keys], on=keys, how='left', indicator=True)
                    final_df = merged[merged['_merge'] == 'left_only'].drop(columns=['_merge'])
                    
                    save_data("siparisler.csv", final_df)
                    st.success("Silindi!")
                    st.rerun()

# ==================================================
# 3. AYARLAR
# ==================================================
elif menu == "Ayarlar":
    st.header("⚙️ Sistem Ayarları")
    
    tab1, tab2 = st.tabs(["Genel", "Malzemeler"])
    
    with tab1:
        c1, c2 = st.columns(2)
        n_dolar = c1.number_input("Dolar Kuru", value=DOLAR)
        n_kar = c2.number_input("Kâr Oranı (%)", value=KAR)
        n_kdv = c1.number_input("KDV (%)", value=KDV_ORAN)
        n_lazer = c2.number_input("Lazer (TL/dk)", value=LAZER_DK)
        n_abkant = st.number_input("Abkant (TL/vuruş)", value=ABKANT_TL)
        
        if st.button("Ayarları Kaydet"):
            new_df = pd.DataFrame([
                {"Key":"dolar", "Val":n_dolar}, {"Key":"kar", "Val":n_kar}, 
                {"Key":"kdv", "Val":n_kdv}, {"Key":"lazer_dk", "Val":n_lazer}, {"Key":"abkant", "Val":n_abkant}
            ])
            save_data("ayarlar.csv", new_df)
            del st.session_state.db_ayar # Cache temizle
            st.success("Kaydedildi!")
            st.rerun()

    with tab2:
        df_m = st.session_state.db_malz
        edited = st.data_editor(df_m, num_rows="dynamic", use_container_width=True)
        if st.button("Malzemeleri Kaydet"):
            save_data("malzemeler.csv", edited)
            del st.session_state.db_malz
            st.success("Malzemeler güncellendi!")
            st.rerun()
