import streamlit as st
import pandas as pd
from github import Github
import io
from datetime import datetime
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="ÖZÇELİK ENDÜSTRİ", layout="wide", page_icon="🏭")

# --- CSS (GÖRÜNÜM) ---
st.markdown("""
    <style>
    .main-header {font-size: 28px; font-weight: bold; color: #0f172a;}
    .metric-card {background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;}
    .metric-val {font-size: 28px; font-weight: bold; color: #0f172a;}
    .metric-label {font-size: 14px; color: #64748b; font-weight: 600;}
    .stButton>button {width: 100%; border-radius: 5px; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

# --- GITHUB BAĞLANTILARI ---
def get_repo():
    token = st.secrets["github"]["token"]
    repo_name = st.secrets["github"]["repo_name"]
    return Github(token).get_repo(repo_name)

def load_data(filename):
    """Veriyi okur, yoksa varsayılan boş tablo döner"""
    try:
        repo = get_repo()
        content = repo.get_contents(filename).decoded_content.decode()
        return pd.read_csv(io.StringIO(content))
    except:
        if "musteri" in filename: return pd.DataFrame(columns=["Firma", "Yetkili", "Tel", "Adres"])
        if "siparis" in filename: return pd.DataFrame(columns=["Tarih", "Müşteri", "İş", "Tutar"])
        if "ayar" in filename: return pd.DataFrame([
            {"Key":"dolar", "Val":34.50}, {"Key":"kar", "Val":25.0}, 
            {"Key":"kdv", "Val":20.0}, {"Key":"lazer_dk", "Val":25.0}, {"Key":"abkant", "Val":15.0}
        ])
        if "malz" in filename: return pd.DataFrame([{"Ad":"Siyah Sac", "Fiyat":0.85, "Kur":"USD", "Yog":7.85}])
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

# Kolay Erişim İçin Değişkenler
try:
    df_a = st.session_state.db_ayar.set_index("Key")
    DOLAR = float(df_a.loc["dolar", "Val"])
    KAR = float(df_a.loc["kar", "Val"])
    KDV_ORAN = float(df_a.loc["kdv", "Val"])
    LAZER_DK = float(df_a.loc["lazer_dk", "Val"])
    ABKANT_TL = float(df_a.loc["abkant", "Val"])
except:
    DOLAR, KAR, KDV_ORAN, LAZER_DK, ABKANT_TL = 34.50, 25.0, 20.0, 25.0, 15.0

# Sepet Başlat
if 'sepet' not in st.session_state: st.session_state.sepet = []

# --- SOL MENÜ ---
with st.sidebar:
    st.title("🏭 ÖZÇELİK")
    menu = st.radio("Menü", ["Hesaplama", "Müşteriler", "Ayarlar"])
    st.divider()
    st.info(f"💲 Dolar: {DOLAR} | Kâr: %{KAR} | KDV: %{KDV_ORAN}")

# ==================================================
# 1. HESAPLAMA EKRANI
# ==================================================
if menu == "Hesaplama":
    st.markdown('<p class="main-header">Teklif Hazırla</p>', unsafe_allow_html=True)
    
    # --- MÜŞTERİ SEÇİMİ ---
    df_mus = load_data("musteriler.csv")
    kayitli_list = df_mus["Firma"].tolist() if not df_mus.empty else []
    
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
        aktif_musteri = girilen if girilen else f"İsimsiz İş {datetime.now().strftime('%H%M')}"
        c2.info(f"Kayıt: **{aktif_musteri}**")

    st.divider()

    # --- MANUEL GİRİŞ (DÜZELTİLMİŞ) ---
    with st.expander("➕ Parça Ekle (Manuel)", expanded=True):
        # value=None sayesinde kutular boş gelir, 0.00 silmekle uğraşmazsın.
        c1, c2, c3 = st.columns(3)
        malz_opt = st.session_state.db_malz["Ad"].tolist()
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
                    "Büküm": int(i_bukum or 0)
                })
                st.rerun()
            else:
                st.error("Lütfen ölçüleri girin.")

    # --- SEPET TABLOSU ---
    if st.session_state.sepet:
        st.markdown("### 🛒 Liste")
        df_sepet = pd.DataFrame(st.session_state.sepet)
        
        # Excel Tarzı Düzenleme (SİLME ÖZELLİKLİ)
        # num_rows="dynamic" sayesinde satır seçip silebilirsin.
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
        
        st.caption("ℹ️ Satır silmek için solundaki kutuyu seçip 'Delete' tuşuna basın veya tablonun sağındaki eksiye basın.")

        # --- HESAPLAMA ---
        if st.button("💰 HESAPLA", type="primary"):
            # Düzenlenmiş tabloyu al
            final_sepet = edited_df.to_dict('records')
            
            toplam_maliyet = 0
            toplam_kg = 0
            
            df_m = st.session_state.db_malz.set_index("Ad")
            
            for item in final_sepet:
                try:
                    # Veritabanından bilgileri al
                    m_info = df_m.loc[item["Malzeme"]]
                    m_fiyat = float(m_info["Fiyat"])
                    m_yog = float(m_info["Yog"])
                    if m_info["Kur"] == "USD": m_fiyat *= DOLAR
                    
                    # Hesap
                    hacim = item["En"] * item["Boy"] * item["Kalınlık"]
                    kg = (hacim * m_yog) / 1_000_000 * item["Adet"]
                    
                    tutar_malz = kg * m_fiyat
                    tutar_iscilik = (item["Süre"] * item["Adet"] * LAZER_DK) + (item["Büküm"] * item["Adet"] * ABKANT_TL)
                    
                    toplam_maliyet += tutar_malz + tutar_iscilik
                    toplam_kg += kg
                except Exception as e:
                    st.error(f"Hesaplama hatası: {item['Malzeme']} veritabanında bulunamadı veya silinmiş.")
            
            # Kâr ve KDV
            karli_tutar = toplam_maliyet * (1 + KAR/100)
            kdv_tutar = karli_tutar * (KDV_ORAN/100)
            son_fiyat = karli_tutar + kdv_tutar
            
            # Sonuçları Session'a kaydet (Kaybolmasın)
            st.session_state.sonuc = {"kg": toplam_kg, "maliyet": toplam_maliyet, "teklif": son_fiyat}
            st.session_state.final_sepet_cache = final_sepet # Kayıt için sakla

        # SONUÇ GÖSTERİMİ
        if 'sonuc' in st.session_state:
            res = st.session_state.sonuc
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.markdown(f'<div class="metric-card"><div class="metric-label">Toplam Ağırlık</div><div class="metric-val">{res["kg"]:.1f} kg</div></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="metric-card"><div class="metric-label">Maliyet</div><div class="metric-val">{res["maliyet"]:,.0f} TL</div></div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="metric-card" style="border-color: #22c55e;"><div class="metric-label">TEKLİF (+KDV)</div><div class="metric-val" style="color:#15803d !important;">{res["teklif"]:,.0f} TL</div></div>', unsafe_allow_html=True)
            
            st.divider()
            
            # KAYDETME VE TEMİZLEME
            not_txt = st.text_input("İş Notu (Örn: Lazer + Büküm):")
            
            col_k, col_t = st.columns([2,1])
            
            with col_k:
                if st.button("💾 MÜŞTERİYE VE SİSTEME KAYDET"):
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
                            "İş": not_txt or "Genel",
                            "Tutar": round(res["teklif"], 2)
                        }])
                        save_data("siparisler.csv", pd.concat([df_s, new_s], ignore_index=True))
                        
                        st.success(f"✅ {aktif_musteri} kaydedildi!")
                        # Temizle
                        st.session_state.sepet = []
                        if 'sonuc' in st.session_state: del st.session_state.sonuc
                        time.sleep(2)
                        st.rerun()
            
            with col_t:
                if st.button("🗑️ TEMİZLE (İPTAL)"):
                    st.session_state.sepet = []
                    if 'sonuc' in st.session_state: del st.session_state.sonuc
                    st.rerun()

# ==================================================
# 2. MÜŞTERİ YÖNETİMİ
# ==================================================
elif menu == "Müşteriler":
    st.header("👥 Müşteri Paneli")
    
    df_mus = load_data("musteriler.csv")
    df_sip = load_data("siparisler.csv")
    
    if df_mus.empty:
        st.warning("Henüz müşteri yok.")
    else:
        # Filtreleme
        isimler = sorted(df_mus["Firma"].unique())
        secilen = st.selectbox("Müşteri Seç:", ["Tümü"] + isimler)
        
        if secilen != "Tümü":
            # Tek Müşteri Modu
            st.divider()
            c1, c2 = st.columns([1, 2])
            
            with c1:
                st.subheader(secilen)
                info = df_mus[df_mus["Firma"] == secilen].iloc[0]
                st.write(f"**Yetkili:** {info['Yetkili']}")
                st.write(f"**Tel:** {info['Tel']}")
                
                # Müşteri Silme
                if st.button("Bu Müşteriyi Sil"):
                    yeni_mus = df_mus[df_mus["Firma"] != secilen]
                    save_data("musteriler.csv", yeni_mus)
                    st.success("Silindi!")
                    st.rerun()

            with c2:
                st.subheader("Geçmiş İşler")
                if not df_sip.empty:
                    sip = df_sip[df_sip["Müşteri"] == secilen]
                    if not sip.empty:
                        st.dataframe(sip, use_container_width=True)
                        st.info(f"Toplam Ciro: **{sip['Tutar'].sum():,.2f} TL**")
                    else:
                        st.write("Sipariş yok.")
        else:
            # Tüm Liste
            st.dataframe(df_mus, use_container_width=True)

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
