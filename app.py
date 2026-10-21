import streamlit as st
import fitz
import pandas as pd
import re
from io import BytesIO
from collections import Counter

st.set_page_config(
    page_title="ScholarPilot",
    page_icon="📚",
    layout="wide"
)

st.title("📚 ScholarPilot")
st.subheader("Your Free Research Assistant")

st.write(
    "Extract, organize, and compare research papers "
    "to help prepare your literature review."
)

st.info(
    "This version uses text-processing rules, not an AI model. "
    "Always verify extracted information against the original paper."
)


def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_pdf(uploaded_file):
    with fitz.open(
        stream=uploaded_file.getvalue(),
        filetype="pdf"
    ) as document:
        pages = [page.get_text() for page in document]

    return "\n".join(pages)


def get_section(text, headings, max_chars=1500):
    for heading in headings:
        pattern = re.compile(
            r"(?im)^\s*" + re.escape(heading) +
            r"\s*:?\s*$"
        )

        match = pattern.search(text)

        if match:
            following_text = text[match.end():]
            next_heading = re.search(
                r"(?im)^\s*(?:discussion|conclusion|"
                r"limitations|references|acknowledgments|"
                r"acknowledgements|results|methods|"
                r"methodology|introduction)\s*:?\s*$",
                following_text
            )

            if next_heading:
                following_text = following_text[:next_heading.start()]

            excerpt = clean_text(following_text)

            if excerpt:
                return excerpt[:max_chars]

    return "Needs manual review"


def analyze_paper(filename, text):
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    title = filename.removesuffix(".pdf")

    for line in lines[:15]:
        if len(line) > 20 and len(line) < 300:
            title = line
            break

    objective = get_section(
        text,
        [
            "Objectives",
            "Objective",
            "Study Aim",
            "Aim",
            "Purpose",
            "Research Questions",
        ]
    )

    methodology = get_section(
        text,
        [
            "Methods",
            "Methodology",
            "Materials and Methods",
            "Study Design",
        ]
    )

    findings = get_section(
        text,
        [
            "Results",
            "Findings",
            "Principal Findings",
        ]
    )

    limitations = get_section(
        text,
        [
            "Limitations",
            "Study Limitations",
            "Limitations and Future Research",
        ],
        max_chars=1200
    )

    if limitations == "Needs manual review":
        limitations = (
            "No clearly labeled limitations section found. "
            "Please review the full paper."
        )

    sample_size = "Needs manual review"

    sample_patterns = [
        r"\b(?:sample size of|sample of|included|enrolled|"
        r"randomized)\s+(\d[\d,]*)\s+"
        r"(?:participants|patients|subjects|clinicians|people)\b",
        r"\b(\d[\d,]*)\s+"
        r"(?:participants|patients|subjects|clinicians)\b",
    ]

    for pattern in sample_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            sample_size = match.group(1)
            break

    design = "Needs manual review"

    if re.search(r"\brandomized clinical trial\b", text, re.I):
        design = "Randomized clinical trial"
    elif re.search(r"\brandomized controlled trial\b", text, re.I):
        design = "Randomized controlled trial"
    elif re.search(r"\bsystematic review\b", text, re.I):
        design = "Systematic review"
    elif re.search(r"\bmeta-analysis\b", text, re.I):
        design = "Meta-analysis"
    elif re.search(r"\bcross-sectional study\b", text, re.I):
        design = "Cross-sectional study"
    elif re.search(r"\bcohort study\b", text, re.I):
        design = "Cohort study"
    elif re.search(r"\bqualitative study\b", text, re.I):
        design = "Qualitative study"

    authors = "Needs manual review"

    return {
        "Paper Title": title,
        "Authors": authors,
        "Research Objective": objective,
        "Methodology": methodology,
        "Study Design": design,
        "Sample Size": sample_size,
        "Key Findings": findings,
        "Limitations": limitations,
        "Research Gaps": (
            "Review the limitations and future research "
            "recommendations; no gap has been verified."
        ),
        "Source File": filename,
    }


def get_keywords(text):
    stop_words = {
        "about", "after", "again", "against", "among",
        "also", "been", "being", "between", "both",
        "could", "does", "during", "each", "from",
        "have", "into", "more", "most", "other",
        "over", "same", "such", "than", "that",
        "their", "them", "then", "there", "these",
        "they", "this", "those", "through", "under",
        "very", "were", "what", "when", "where",
        "which", "while", "with", "within", "would",
        "study", "studies", "results", "research",
        "using", "used", "based", "methods", "method",
        "data", "paper", "group", "groups", "conclusion",
    }

    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())

    return Counter(
        word for word in words
        if word not in stop_words
    )


st.divider()
st.header("📄 Upload Research Papers")

uploaded_files = st.file_uploader(
    "Select one or more PDF research papers",
    type=["pdf"],
    accept_multiple_files=True
)

if st.button(
    "Analyze Papers",
    disabled=not uploaded_files
):
    results = []
    texts = {}

    progress = st.progress(0)

    for index, file in enumerate(uploaded_files):
        try:
            text = extract_pdf(file)

            if not text.strip():
                st.warning(
                    f"{file.name} contains no extractable text. "
                    "It may be a scanned PDF requiring OCR."
                )
                continue

            texts[file.name] = text
            results.append(analyze_paper(file.name, text))

        except Exception as error:
            st.warning(
                f"Could not process {file.name}: {error}"
            )

        progress.progress((index + 1) / len(uploaded_files))

    st.session_state["results"] = results
    st.session_state["texts"] = texts

if st.session_state.get("results"):
    matrix = pd.DataFrame(st.session_state["results"])

    st.divider()
    st.header("📊 Individual Paper Analysis")

    st.dataframe(
        matrix,
        use_container_width=True
    )

    excel_buffer = BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:
        matrix.to_excel(
            writer,
            index=False,
            sheet_name="Literature Matrix"
        )

    st.download_button(
        "📥 Download Literature Matrix (Excel)",
        data=excel_buffer.getvalue(),
        file_name="ScholarPilot_Literature_Matrix.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    st.divider()
    st.header("🔎 Compare Research Papers")

    texts = st.session_state["texts"]

    if len(texts) >= 2:
        keyword_results = []

        for filename, text in texts.items():
            common_words = get_keywords(text).most_common(10)

            keyword_results.append({
                "Paper": filename,
                "Frequent Terms": ", ".join(
                    word for word, count in common_words
                )
            })

        st.subheader("Common Research Topics")

        st.write(
            "Frequent terms can help you spot potential themes. "
            "They do not prove that papers share the same conclusions."
        )

        st.dataframe(
            pd.DataFrame(keyword_results),
            use_container_width=True
        )

        all_keywords = [
            set(get_keywords(text).keys())
            for text in texts.values()
        ]

        shared_terms = set.intersection(*all_keywords)

        if shared_terms:
            st.subheader("Terms Appearing in Every Paper")

            st.write(
                ", ".join(sorted(shared_terms)[:50])
            )
        else:
            st.write(
                "No shared keywords were found using the "
                "current text-processing rules."
            )

        st.subheader("Compare Extracted Findings")

        st.dataframe(
            matrix[
                [
                    "Paper Title",
                    "Study Design",
                    "Sample Size",
                    "Key Findings",
                    "Limitations",
                ]
            ],
            use_container_width=True
        )

        st.caption(
            "This comparison is based on extracted text and "
            "keyword overlap. It does not establish causation, "
            "agreement between results, or definitive research gaps."
        )

    else:
        st.info(
            "Upload at least two papers to compare them."
        )

st.divider()

st.caption(
    "ScholarPilot | Research smarter, not harder."
    )
