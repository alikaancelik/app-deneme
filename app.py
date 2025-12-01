import streamlit as st
import pandas as pd
from github import Github
import io
from datetime import datetime
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="ÖZÇELİK ENDÜSTRİ", layout="wide", page_icon="🏭")

# --- CSS İYİLEŞTİRMELERİ ---
st.markdown("""
    <style>
    .main-header {font-size: 28px; font-weight: bold; color: #0f172a;}
    .metric-card {background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;}
    .metric-val {font-size: 24px; font-weight: bold; color: #0f172a;}
    .stButton>button {width: 100%; border-radius: 5px; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

# --- GITHUB VE VERİ YÖNETİMİ ---
def get_repo():
    token = st.secrets["github"]["token"]
    repo_name = st.secrets["github"]["repo_name"]
    return Github(token).get_repo(repo_name)

def load_data(filename):
    """Veriyi okur ve sütun isimlerini otomatik onarır"""
    try:
        repo = get_repo()
        content = repo.get_contents(filename).decoded_content.decode()
        df = pd.read_csv(io.StringIO(content))
        
        # --- OTOMATİK ONARIM (HATA ÖNLEYİCİ) ---
        if "musteri" in filename:
            # Eski "Firma" sütunu varsa "Firma Adı" yap
            if "Firma" in df.columns: df.rename(columns={"Firma": "Firma Adı"}, inplace=True)
            if "Tel" in df.columns: df.rename(columns={"Tel": "Telefon"}, inplace=True)
            # Eksik sütun varsa ekle
            for col in ["Firma Adı", "Yetkili", "Telefon", "Adres"]:
                if col not in df.columns: df[col] = "-"
                
        elif "ayarlar" in filename:
            if "Key" in df.columns: df.rename(columns={"Key": "Ayar", "Val": "Deger"}, inplace=True)
            
        elif "malzemeler" in filename:
            if "Ad" in df.columns: df.rename(columns={"Ad": "Malzeme", "Kur": "Birim", "Yog": "Yogunluk"}, inplace=True)
            
        return df
    except:
        # Dosya yoksa veya bozuksa varsayılanı döndür
        if "musteri" in filename: return pd.DataFrame(columns=["Firma Adı", "Yetkili", "Telefon", "Adres"])
        if "siparis" in filename: return pd.DataFrame(columns=["Tarih", "Müşteri", "İş Adı", "Tutar", "Detay"])
        if "ayar" in filename: return pd.DataFrame([
            {"Ayar":"dolar_kuru", "Deger":34.50}, {"Ayar":"kar_orani", "Deger":25.0}, 
            {"Ayar":"kdv_durum", "Deger":"Evet"}, {"Ayar":"lazer_dk", "Deger":25.0}, {"Ayar":"abkant_vurus", "Deger":15.0}
        ])
        if "malz" in filename: return pd.DataFrame([{"Malzeme":"Siyah Sac", "Fiyat":0.85, "Birim":"USD", "Yogunluk":7.85}])
        return pd.DataFrame()

def save_data(filename, df):
    """Veriyi kaydeder"""
    repo = get_repo()
    try:
        contents = repo.get_contents(filename)
        repo.update_file(contents.path, "Guncelleme", df.to_csv(index=False), contents.sha)
    except:
        repo.create_file(filename, "Yeni Dosya", df.to_csv(index=False))

# --- AYARLARI ÇEK ---
if 'db_ayar' not in st.session_state:
    st.session_state.db_ayar = load_data("ayarlar.csv")
    st.session_state.db_malz = load_data("malzemeler.csv")

# Değişkenleri Yükle (Hata olursa varsayılanı kullan)
try:
    df_a = st.session_state.db_ayar.set_index("Ayar")
    DOLAR = float(df_a.loc["dolar_kuru", "Deger"])
    KAR = float(df_a.loc["kar_orani", "Deger"])
    KDV_DURUM = str(df_a.loc["kdv_durum", "Deger"])
    LAZER_DK = float(df_a.loc["lazer_dk", "Deger"])
    ABKANT_TL = float(df_a.loc["abkant_vurus", "Deger"])
except:
    DOLAR, KAR, KDV_DURUM, LAZER_DK, ABKANT_TL = 34.50, 25.0, "Evet", 25.0, 15.0

# Sepet Başlat
if 'sepet' not in st.session_state: st.session_state.sepet = []

# --- SOL MENÜ ---
with st.sidebar:
    st.title("🏭 ÖZÇELİK")
    menu = st.radio("Menü", ["Hesaplama", "Müşteriler", "Ayarlar"])
    st.divider()
    st.info(f"💲 Dolar: {DOLAR} | Kâr: %{KAR}")

# ==================================================
# 1. HESAPLAMA EKRANI
# ==================================================
if menu == "Hesaplama":
    st.markdown('<p class="main-header">Teklif Hazırla</p>', unsafe_allow_html=True)
    
    # --- MÜŞTERİ SEÇİMİ ---
    df_mus = load_data("musteriler.csv")
    
    # Listeyi güvenli oluştur
    kayitli_list = []
    if not df_mus.empty and "Firma Adı" in df_mus.columns:
        kayitli_list = df_mus["Firma Adı"].dropna().unique().tolist()
    
    secim_tipi = st.radio("İşlem Türü:", ["⚡ Hızlı (Yeni/Kayıtsız)", "📂 Kayıtlı Müşteri"], horizontal=True)
    
    aktif_musteri = ""
    
    if secim_tipi == "📂 Kayıtlı Müşteri":
        if not kayitli_list:
            st.warning("Kayıtlı müşteri bulunamadı.")
        else:
            aktif_musteri = st.selectbox("Firma Seç:", kayitli_list)
    else:
        c1, c2 = st.columns([2,1])
        girilen = c1.text_input("Müşteri Adı (Boşsa 'İsimsiz' olur):")
        if girilen:
            aktif_musteri = girilen
        else:
            aktif_musteri = f"İsimsiz İş {datetime.now().strftime('%d%m-%H%M')}"
        c2.info(f"Müşteri: **{aktif_musteri}**")

    st.divider()

    # --- MANUEL GİRİŞ ---
    with st.expander("➕ Parça Ekle (Manuel)", expanded=True):
        c1, c2, c3 = st.columns(3)
        # Malzeme listesi güvenli çekim
        malz_opt = ["Siyah Sac"]
        if "Malzeme" in st.session_state.db_malz.columns:
            malz_opt = st.session_state.db_malz["Malzeme"].tolist()
            
        i_malz = c1.selectbox("Malzeme", malz_opt)
        i_kal = c2.number_input("Kalınlık (mm)", value=None, placeholder="Örn: 2")
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
            else:
                st.error("Lütfen ölçüleri girin.")

    # --- SEPET TABLOSU ---
    if st.session_state.sepet:
        st.markdown("### 🛒 Liste")
        df_sepet = pd.DataFrame(st.session_state.sepet)
        
        # SİLME CHECKBOX
        edited_df = st.data_editor(
            df_sepet,
            column_config={
                "Sil": st.column_config.CheckboxColumn("Sil?", width="small"),
                "En": st.column_config.NumberColumn("En (mm)", format="%.1f"),
                "Boy": st.column_config.NumberColumn("Boy (mm)", format="%.1f"),
            },
            hide_index=True,
            use_container_width=True
        )
        
        if st.button("🗑️ Seçili Satırları Sil"):
            # Silinmeyenleri filtrele
            yeni_liste = [row for row in edited_df.to_dict('records') if not row.get("Sil")]
            # Sil işaretlerini temizle
            for r in yeni_liste: r["Sil"] = False
            st.session_state.sepet = yeni_liste
            st.rerun()

        st.divider()

        # --- HESAPLAMA ---
        if st.button("💰 HESAPLA", type="primary"):
            # SİLİNMİŞLERİ HARİÇ TUT
            final_sepet = [row for row in edited_df.to_dict('records') if not row.get("Sil")]
            
            if not final_sepet:
                st.error("Hesaplanacak ürün yok.")
            else:
                toplam_tl = 0
                toplam_kg = 0
                
                # Malzemeleri indeksle
                df_m = st.session_state.db_malz.set_index("Malzeme")
                
                for item in final_sepet:
                    try:
                        m_info = df_m.loc[item["Malzeme"]]
                        m_fiyat = float(m_info["Fiyat"])
                        m_yog = float(m_info["Yogunluk"])
                        if m_info["Birim"] == "USD": m_fiyat *= DOLAR
                        
                        hacim = item["En"] * item["Boy"] * item["Kalınlık"]
                        kg = (hacim * m_yog) / 1_000_000 * item["Adet"]
                        
                        tutar_malz = kg * m_fiyat
                        tutar_iscilik = (item["Süre"] * item["Adet"] * LAZER_DK) + (item["Büküm"] * item["Adet"] * ABKANT_TL)
                        
                        toplam_tl += tutar_malz + tutar_iscilik
                        toplam_kg += kg
                    except: pass
                
                # Kar ve KDV
                karli = toplam_tl * (1 + KAR/100)
                kdv = karli * 0.20 if KDV_DURUM == "Evet" else 0
                son_fiyat = karli + kdv
                
                # Sonuçları göster
                c1, c2, c3 = st.columns(3)
                c1.markdown(f'<div class="metric-card"><div class="metric-label">Ağırlık</div><div class="metric-val">{toplam_kg:.1f} kg</div></div>', unsafe_allow_html=True)
                c2.markdown(f'<div class="metric-card"><div class="metric-label">Maliyet</div><div class="metric-val">{toplam_tl:,.0f} TL</div></div>', unsafe_allow_html=True)
                c3.markdown(f'<div class="metric-card" style="border-color: green;"><div class="metric-label">TEKLİF</div><div class="metric-val">{son_fiyat:,.0f} TL</div></div>', unsafe_allow_html=True)
                
                st.divider()
                
                # KAYDETME
                c_save, c_clear = st.columns([2,1])
                not_txt = c_save.text_input("İş Notu:")
                
                if c_save.button("💾 MÜŞTERİYE KAYDET"):
                    with st.spinner("Kaydediliyor..."):
                        # 1. Müşteriyi Ekle (Yoksa)
                        df_mus_guncel = load_data("musteriler.csv")
                        if aktif_musteri not in df_mus_guncel["Firma Adı"].values:
                            new_m = pd.DataFrame([{"Firma Adı": aktif_musteri, "Yetkili": "-", "Telefon": "-", "Adres": "-"}])
                            save_data("musteriler.csv", pd.concat([df_mus_guncel, new_m], ignore_index=True))
                        
                        # 2. Siparişi Ekle
                        df_sip = load_data("siparisler.csv")
                        new_s = pd.DataFrame([{
                            "Tarih": datetime.now().strftime("%d-%m-%Y %H:%M"),
                            "Müşteri": aktif_musteri,
                            "İş Adı": not_txt or "Genel",
                            "Tutar": round(son_fiyat, 2),
                            "Detay": f"{len(final_sepet)} parça, {toplam_kg:.1f}kg"
                        }])
                        save_data("siparisler.csv", pd.concat([df_sip, new_s], ignore_index=True))
                        
                        st.success(f"{aktif_musteri} için kayıt başarılı!")
                        st.session_state.sepet = []
                        time.sleep(1)
                        st.rerun()
                
                if c_clear.button("🗑️ TEMİZLE"):
                    st.session_state.sepet = []
                    st.rerun()

# ==================================================
# 2. MÜŞTERİ YÖNETİMİ
# ==================================================
elif menu == "Müşteriler":
    st.header("👥 Müşteri Paneli")
    
    df_mus = load_data("musteriler.csv")
    df_sip = load_data("siparisler.csv")
    
    tab1, tab2 = st.tabs(["📋 Liste & Geçmiş", "➕ Yeni Ekle"])
    
    with tab1:
        if df_mus.empty:
            st.warning("Müşteri yok.")
        else:
            isimler = sorted(df_mus["Firma Adı"].unique())
            secilen = st.selectbox("Müşteri Seç:", ["Tümü"] + isimler)
            
            if secilen != "Tümü":
                st.divider()
                c1, c2 = st.columns([1, 2])
                with c1:
                    info = df_mus[df_mus["Firma Adı"] == secilen].iloc[0]
                    st.info(f"**Yetkili:** {info.get('Yetkili','-')}\n\n**Tel:** {info.get('Telefon','-')}")
                    if st.button("Sil"):
                        # Sadece müşteriyi sil
                        yeni_mus = df_mus[df_mus["Firma Adı"] != secilen]
                        save_data("musteriler.csv", yeni_mus)
                        st.success("Silindi!")
                        st.rerun()
                with c2:
                    st.subheader("Geçmiş İşler")
                    if not df_sip.empty:
                        sip = df_sip[df_sip["Müşteri"] == secilen]
                        if not sip.empty:
                            st.dataframe(sip, use_container_width=True)
                            st.success(f"Toplam: {sip['Tutar'].sum():,.2f} TL")
                        else: st.info("Sipariş yok.")
            else:
                st.dataframe(df_mus, use_container_width=True)

    with tab2:
        with st.form("yeni"):
            f = st.text_input("Firma Adı")
            y = st.text_input("Yetkili")
            t = st.text_input("Telefon")
            if st.form_submit_button("Kaydet"):
                if f:
                    # Tekrar kontrolü
                    if f in df_mus["Firma Adı"].values:
                        st.error("Bu firma zaten var.")
                    else:
                        new = pd.DataFrame([{"Firma Adı": f, "Yetkili": y, "Telefon": t, "Adres": "-"}])
                        save_data("musteriler.csv", pd.concat([df_mus, new], ignore_index=True))
                        st.success("Eklendi!")
                        st.rerun()

# ==================================================
# 3. AYARLAR
# ==================================================
elif menu == "Ayarlar":
    st.header("⚙️ Ayarlar")
    
    t1, t2 = st.tabs(["Genel", "Malzemeler"])
    
    with t1:
        c1, c2 = st.columns(2)
        n_dolar = c1.number_input("Dolar Kuru", value=DOLAR)
        n_kar = c2.number_input("Kâr Oranı (%)", value=KAR)
        n_kdv = st.selectbox("KDV Durumu", ["Evet", "Hayır"], index=0 if KDV_DURUM=="Evet" else 1)
        n_lazer = c1.number_input("Lazer (TL/dk)", value=LAZER_DK)
        n_abkant = c2.number_input("Abkant (TL/vuruş)", value=ABKANT_TL)
        
        if st.button("Ayarları Kaydet"):
            new_df = pd.DataFrame([
                {"Ayar":"dolar_kuru", "Deger":n_dolar}, {"Ayar":"kar_orani", "Deger":n_kar}, 
                {"Ayar":"kdv_durum", "Deger":n_kdv}, {"Ayar":"lazer_dk", "Deger":n_lazer}, {"Ayar":"abkant_vurus", "Deger":n_abkant}
            ])
            save_data("ayarlar.csv", new_df)
            del st.session_state.db_ayar
            st.success("Kaydedildi!")
            st.rerun()

    with tab2:
        df_m = st.session_state.db_malz
        edited = st.data_editor(df_m, num_rows="dynamic", use_container_width=True)
        if st.button("Malzeme Listesini Kaydet"):
            save_data("malzemeler.csv", edited)
            del st.session_state.db_malz
            st.success("Güncellendi!")
            st.rerun()
