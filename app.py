import streamlit as st

st.set_page_config(
    page_title="ScholarPilot",
    page_icon="📚",
    layout="wide"
)

st.title("📚 ScholarPilot")
st.subheader("Your AI Research Assistant")

st.write(
    "Turn research papers into an organized "
    "literature review matrix."
)

st.divider()

st.header("📄 Upload Research Papers")

uploaded_files = st.file_uploader(
    "Choose your research paper PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    st.success(
        f"{len(uploaded_files)} research paper(s) uploaded!"
    )

    if st.button("Analyze Papers"):
        st.info("Paper analysis will be added next.")

st.divider()

st.header("📊 Literature Review Matrix")
st.write("Your research results will appear here.")

st.caption("ScholarPilot | Research smarter, not harder.")
