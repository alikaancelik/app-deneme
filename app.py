import streamlit as st
import pandas as pd

# Sayfa Ayarları
st.set_page_config(page_title="Pro Lazer Teklif", layout="wide", page_icon="🏭")

# --- VERİ TABANI (BURAYI KENDİ MAKİNENE GÖRE GÜNCELLEYEBİLİRSİN) ---
# Buradaki hızlar (mm/dk) temsilidir. Kendi makinenin değerlerini buraya yazmalısın.
kesim_verileri = [
    {"malzeme": "DKP", "kalinlik": 1.0, "hiz": 25000, "gaz": "O2"},
    {"malzeme": "DKP", "kalinlik": 2.0, "hiz": 18000, "gaz": "O2"},
    {"malzeme": "DKP", "kalinlik": 3.0, "hiz": 12000, "gaz": "O2"},
    {"malzeme": "DKP", "kalinlik": 5.0, "hiz": 6000, "gaz": "O2"},
    {"malzeme": "DKP", "kalinlik": 10.0, "hiz": 1800, "gaz": "O2"},
    
    {"malzeme": "Paslanmaz (304)", "kalinlik": 1.0, "hiz": 20000, "gaz": "N2"},
    {"malzeme": "Paslanmaz (304)", "kalinlik": 2.0, "hiz": 12000, "gaz": "N2"},
    {"malzeme": "Paslanmaz (304)", "kalinlik": 5.0, "hiz": 3500, "gaz": "N2"},
    
    {"malzeme": "Alüminyum", "kalinlik": 2.0, "hiz": 15000, "gaz": "N2"},
    {"malzeme": "Alüminyum", "kalinlik": 5.0, "hiz": 5000, "gaz": "N2"},
]
df_hiz = pd.DataFrame(kesim_verileri)

# --- SOL MENÜ: FİYATLANDIRMA PARAMETRELERİ ---
st.sidebar.title("⚙️ Parametreler")

with st.sidebar.expander("Döviz & Kurlar", expanded=True):
    dolar_kuru = st.number_input("Dolar Kuru (TL)", value=32.0)
    euro_kuru = st.number_input("Euro Kuru (TL)", value=34.5)

with st.sidebar.expander("Malzeme Kg Fiyatları ($)", expanded=False):
    st.info("Fiyatları DOLAR ($) cinsinden giriniz.")
    fiyat_dkp = st.number_input("DKP ($/kg)", value=0.90)
    fiyat_paslanmaz = st.number_input("Paslanmaz 304 ($/kg)", value=3.50)
    fiyat_alu = st.number_input("Alüminyum ($/kg)", value=3.00)

with st.sidebar.expander("İşçilik Ücretleri (TL)", expanded=False):
    lazer_dk_ucret = st.number_input("Lazer Dakika (TL)", value=20.0)
    abkant_vurus = st.number_input("Abkant Vuruş Başı (TL)", value=10.0)
    kaynak_saat = st.number_input("Kaynakçılık (TL/Saat)", value=350.0)
    boya_m2 = st.number_input("Boya (TL/m²)", value=150.0)

# --- ANA EKRAN ---
st.title("🏭 Profesyonel Maliyet Hesaplayıcı")
st.markdown("---")

# Sekmeli yapı
tab1, tab2, tab3 = st.tabs(["📝 Parça Bilgileri", "🔧 Ek İşlemler", "💰 Sonuç & Teklif"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Malzeme Seçimi")
        secilen_malzeme = st.selectbox("Malzeme Türü", ["DKP", "Paslanmaz (304)", "Alüminyum"])
        
        # Seçilen malzemeye uygun kalınlıkları getir
        uygun_kalinliklar = df_hiz[df_hiz["malzeme"] == secilen_malzeme]["kalinlik"].unique()
        uygun_kalinliklar.sort()
        
        secilen_kalinlik = st.selectbox("Kalınlık (mm)", uygun_kalinliklar)
        
        # Seçilen özelliklere göre hızı bul
        bulunan_veri = df_hiz[(df_hiz["malzeme"] == secilen_malzeme) & (df_hiz["kalinlik"] == secilen_kalinlik)].iloc[0]
        hiz_mm_dk = bulunan_veri["hiz"]
        st.caption(f"⚡ Makine Veritabanı Hızı: **{hiz_mm_dk} mm/dk** (Gaz: {bulunan_veri['gaz']})")

    with col2:
        st.subheader("Boyutlar")
        en = st.number_input("En (mm)", value=200)
        boy = st.number_input("Boy (mm)", value=300)
        adet = st.number_input("Adet", value=1, min_value=1)
        
        # Otomatik kesim yolu tahmini (Çevre + %20 iç delikler payı)
        tahmini_cevre = (en + boy) * 2
        kesim_yolu = st.number_input("Kesim Yolu (mm)", value=int(tahmini_cevre * 1.2), help="Otomatik olarak çevre x 1.2 hesaplandı, değiştirebilirsiniz.")
        patlatma_sayisi = st.number_input("Patlatma (Giriş) Sayısı", value=1)

with tab2:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Büküm & Kaynak")
        bukum_sayisi = st.number_input("Parça Başı Büküm Sayısı", value=0)
        kaynak_dk = st.number_input("Parça Başı Kaynak Süresi (dk)", value=0.0)
    
    with c2:
        st.subheader("Diğer")
        boya_var_mi = st.checkbox("Elektrostatik Boya İstiyor mu?")
        boyanacak_alan_m2 = (en * boy * 2) / 1_000_000 if boya_var_mi else 0 # Çift yüzey hesap
        if boya_var_mi:
            st.info(f"Tahmini Boya Alanı: {boyanacak_alan_m2:.3f} m² (Çift Yüz)")

# --- HESAPLAMALAR ---

# 1. Ağırlık ve Malzeme
yogunluklar = {"DKP": 7.85, "Paslanmaz (304)": 7.9, "Alüminyum": 2.7}
yogunluk = yogunluklar[secilen_malzeme]
hacim_cm3 = (en * boy * secilen_kalinlik) / 1000 
tek_agirlik_kg = hacim_cm3 * yogunluk / 1000
toplam_agirlik = tek_agirlik_kg * adet

# Malzeme Fiyat Seçimi
if secilen_malzeme == "DKP": birim_usd = fiyat_dkp
elif secilen_malzeme == "Paslanmaz (304)": birim_usd = fiyat_paslanmaz
else: birim_usd = fiyat_alu

malzeme_maliyeti_tl = toplam_agirlik * birim_usd * dolar_kuru

# 2. Lazer Kesim Maliyeti
# Zaman = (Yol / Hız) + (Patlatma * süre)
kesim_suresi_dk = (kesim_yolu / hiz_mm_dk) + (patlatma_sayisi * (3/60)) # her patlatma 3 saniye
lazer_maliyeti_tl = kesim_suresi_dk * lazer_dk_ucret * adet

# 3. İşçilikler
bukum_maliyeti_tl = bukum_sayisi * abkant_vurus * adet
kaynak_maliyeti_tl = (kaynak_dk / 60) * kaynak_saat * adet
boya_maliyeti_tl = boyanacak_alan_m2 * boya_m2 * adet if boya_var_mi else 0

toplam_ham_maliyet = malzeme_maliyeti_tl + lazer_maliyeti_tl + bukum_maliyeti_tl + kaynak_maliyeti_tl + boya_maliyeti_tl

with tab3:
    st.header("Sonuç Tablosu")
    
    kar_orani = st.slider("Kâr Marjı (%)", 0, 100, 25)
    satis_fiyati = toplam_ham_maliyet * (1 + kar_orani/100)
    
    col_res1, col_res2, col_res3 = st.columns(3)
    col_res1.metric("Toplam Ağırlık", f"{toplam_agirlik:.2f} kg")
    col_res2.metric("Maliyet (Kârsız)", f"{toplam_ham_maliyet:.2f} TL")
    col_res3.metric(f"TEKLİF FİYATI (+%{kar_orani})", f"{satis_fiyati:.2f} TL", delta_color="inverse")
    
    st.markdown("### 📊 Maliyet Dağılımı")
    data = {
        "Kalem": ["Malzeme", "Lazer Kesim", "Büküm", "Kaynak", "Boya"],
        "Tutar (TL)": [malzeme_maliyeti_tl, lazer_maliyeti_tl, bukum_maliyeti_tl, kaynak_maliyeti_tl, boya_maliyeti_tl]
    }
    df_sonuc = pd.DataFrame(data)
    
    # Basit bir bar grafik
    st.bar_chart(df_sonuc.set_index("Kalem"))
    
    # Detaylı tablo
    st.table(df_sonuc)
    
    if st.button("Teklif Özetini Kopyala"):
        st.code(f"""
        TEKLİF ÖZETİ
        ----------------
        Malzeme: {secilen_malzeme} {secilen_kalinlik}mm
        Adet: {adet}
        İşlemler: Lazer, Büküm ({bukum_sayisi}), Kaynak
        ----------------
        TOPLAM FİYAT: {satis_fiyati:.2f} TL + KDV
        """, language="text")
