import streamlit as st
import fitz
import pandas as pd
import re
from io import BytesIO

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


def extract_pdf_text(uploaded_file):
    text_parts = []

    with fitz.open(
        stream=uploaded_file.getvalue(),
        filetype="pdf"
    ) as document:
        for page in document:
            text_parts.append(page.get_text())

    return "\n".join(text_parts)


def find_section(text, keywords, max_chars=1200):
    """Find a likely section using headings or keywords."""
    for keyword in keywords:
        pattern = re.compile(
            rf"(?i)\b{re.escape(keyword)}\b\s*[:.\-]?\s*"
        )
        match = pattern.search(text)

        if match:
            excerpt = text[match.end():match.end() + max_chars]
            excerpt = re.sub(r"\s+", " ", excerpt).strip()

            if excerpt:
                return excerpt

    return "Needs manual review"


def analyze_paper(uploaded_file):
    text = extract_pdf_text(uploaded_file)

    if not text.strip():
        return {
            "Paper Title": uploaded_file.name,
            "Authors": "Needs manual review",
            "Research Objective": "No extractable text; manual review needed",
            "Methodology": "Needs manual review",
            "Sample Size": "Needs manual review",
            "Key Findings": "Needs manual review",
            "Research Gaps": "Needs manual review",
        }

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    title = lines[0] if lines else uploaded_file.name

    objective = find_section(
        text,
        [
            "objective",
            "objectives",
            "aim of this study",
            "purpose of this study",
            "study aim",
            "research question",
        ],
    )

    methodology = find_section(
        text,
        [
            "methods",
            "methodology",
            "study design",
            "materials and methods",
        ],
    )

    sample_size = "Needs manual review"
    sample_patterns = [
        r"\b(?:sample size of|sample of|included|enrolled|randomized)\s+"
        r"(\d[\d,]*)\s+(?:participants|patients|subjects|people|clinicians)",
        r"\b(\d[\d,]*)\s+(?:participants|patients|subjects|clinicians)\b",
    ]

    for pattern in sample_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            sample_size = match.group(1)
            break

    findings = find_section(
        text,
        [
            "results",
            "findings",
            "principal findings",
            "main findings",
        ],
    )

    gaps = find_section(
        text,
        [
            "limitations",
            "future research",
            "future studies",
            "research gaps",
        ],
        max_chars=1000,
    )

    authors = "Needs manual review"

    return {
        "Paper Title": title[:500],
        "Authors": authors,
        "Research Objective": objective,
        "Methodology": methodology,
        "Sample Size": sample_size,
        "Key Findings": findings,
        "Research Gaps": gaps,
    }


if uploaded_files:
    st.success(f"{len(uploaded_files)} paper(s) uploaded.")

    if st.button("Analyze Papers"):
        results = []

        progress = st.progress(0)
        status = st.empty()

        for index, uploaded_file in enumerate(uploaded_files):
            status.write(
                f"Analyzing {uploaded_file.name}..."
            )

            try:
                results.append(analyze_paper(uploaded_file))
            except Exception as error:
                st.warning(
                    f"Could not analyze {uploaded_file.name}: {error}"
                )

            progress.progress(
                (index + 1) / len(uploaded_files)
            )

        status.empty()

        if results:
            matrix = pd.DataFrame(results)

            st.session_state["matrix"] = matrix

            st.success("Analysis finished!")

if "matrix" in st.session_state:
    st.divider()
    st.header("📊 Literature Review Matrix")

    st.dataframe(
        st.session_state["matrix"],
        use_container_width=True
    )

    excel_file = BytesIO()

    with pd.ExcelWriter(
        excel_file,
        engine="openpyxl"
    ) as writer:
        st.session_state["matrix"].to_excel(
            writer,
            index=False,
            sheet_name="Literature Matrix"
        )

    st.download_button(
        label="📥 Download Literature Review Matrix",
        data=excel_file.getvalue(),
        file_name="ScholarPilot_Literature_Review_Matrix.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.divider()

st.caption(
    "ScholarPilot | Research smarter, not harder. "
    "Always verify extracted information against the original paper."
        )
