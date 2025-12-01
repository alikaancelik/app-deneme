import streamlit as st

# Sayfa başlığı
st.title("Merhaba! 👋")

# Alt başlık
st.header("Bu benim ilk canlı uygulamam")

# Basit bir yazı
st.write("Şu an bu site tamamen ücretsiz bir sunucuda çalışıyor.")

# Etkileşimli bir buton
if st.button('Bana bir sürpriz yap'):
    st.balloons()
    st.success("Tebrikler! Sistemin sorunsuz çalışıyor.")
