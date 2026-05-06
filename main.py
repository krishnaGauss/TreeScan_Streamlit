import streamlit as st

from qr_gen import process_csv
from pdf_gen import process_pdf_zip

st.set_page_config(page_title="Tree QR & PDF Generator", page_icon="🌿", layout="centered")
st.title("Tree QR & PDF Generator")

mode = st.radio("Mode", ["QR Generation", "PDF Generation"], horizontal=True)

with st.form("main_form"):
    if mode == "QR Generation":
        base_url = st.text_input("Base URL *", placeholder="https://example.com/docs")
        upload   = st.file_uploader("CSV file *", type=["csv"])
        st.caption("Tree number and name are read automatically from `S_No_` and `Vernacular` columns.")
        fmt    = st.radio("Output format", ["PNG", "JPG"], horizontal=True)
        csv_up = None
        zip_up = None
    else:
        csv_up   = st.file_uploader("CSV file *", type=["csv"])
        zip_up   = st.file_uploader("PDF ZIP *", type=["zip"])
        st.caption("Each PDF in the ZIP must be named `<S_No_>.pdf` to match CSV rows.")
        base_url = ""
        fmt      = "PNG"
        upload   = None

    go = st.form_submit_button("Generate", use_container_width=True, type="primary")

if go:
    errors: list[str] = []
    if mode == "QR Generation":
        if not base_url.strip():
            errors.append("Base URL is required.")
        if upload is None:
            errors.append("Please upload a CSV file.")
    else:
        if csv_up is None:
            errors.append("Please upload a CSV file.")
        if zip_up is None:
            errors.append("Please upload a ZIP of PDFs.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        with st.spinner("Generating..."):
            if mode == "QR Generation":
                save_fmt = "JPEG" if fmt == "JPG" else "PNG"
                result   = process_csv(upload.read(), base_url.strip(), save_fmt)
                st.success("Done!")
                st.download_button(
                    "Download QR Codes ZIP",
                    data=result,
                    file_name="qr_codes.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
            else:
                result = process_pdf_zip(zip_up.read(), csv_up.read())
                st.success("Done!")
                st.download_button(
                    "Download Modified PDFs ZIP",
                    data=result,
                    file_name="tree_pdfs.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
