import streamlit as st
import fitz
import pandas as pd
import re
import json
from io import BytesIO
from google import genai

st.set_page_config(
    page_title="ScholarPilot",
    page_icon="📚",
    layout="wide"
)

st.title("📚 ScholarPilot")
st.subheader("Your AI Research Assistant")

st.write(
    "Analyze research papers, build literature review matrices, "
    "and compare findings using Gemini AI."
)

st.info(
    "AI-generated information may contain errors. "
    "Always verify important details against the original papers."
)


# Connect to Gemini securely
def get_gemini_client():
    api_key = st.secrets.get("GEMINI_API_KEY")

    if not api_key:
        st.error(
            "Gemini API key not found. Check your Streamlit Secrets."
        )
        st.stop()

    return genai.Client(api_key=api_key)


# Extract text from PDF
def extract_pdf(uploaded_file):
    with fitz.open(
        stream=uploaded_file.getvalue(),
        filetype="pdf"
    ) as document:
        pages = [page.get_text() for page in document]

    return "\n".join(pages)


# Ask Gemini to analyze one paper
def analyze_paper(client, filename, text):
    prompt = f"""
You are a careful academic research assistant.

Analyze the research paper text below.

Extract the following fields:
1. Paper Title
2. Authors
3. Publication Year
4. Research Objective
5. Methodology
6. Study Design
7. Sample Size
8. Key Findings
9. Limitations
10. Research Gaps

RULES:
- Use only information supported by the provided paper text.
- Do not invent authors, dates, sample sizes, or findings.
- If information is unavailable, write "Not clearly reported".
- Distinguish the authors' stated limitations from your own inferences.
- Research gaps must be supported by the paper.
- If you infer a possible gap, label it "Potential gap".
- Keep each answer clear and concise.
- Return valid JSON only, without Markdown fences.
- Every field must contain a string.

Use exactly these JSON keys:
{{
  "Paper Title": "",
  "Authors": "",
  "Publication Year": "",
  "Research Objective": "",
  "Methodology": "",
  "Study Design": "",
  "Sample Size": "",
  "Key Findings": "",
  "Limitations": "",
  "Research Gaps": ""
}}

SOURCE FILE: {filename}

PAPER TEXT:
{text[:45000]}
"""

    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    )

    result = json.loads(response.text)

    result["Source File"] = filename

    return result


# Compare multiple papers
def compare_papers(client, papers):
    paper_summaries = []

    for paper in papers:
        paper_summaries.append({
            "title": paper.get("Paper Title", ""),
            "objective": paper.get("Research Objective", ""),
            "methodology": paper.get("Methodology", ""),
            "design": paper.get("Study Design", ""),
            "findings": paper.get("Key Findings", ""),
            "limitations": paper.get("Limitations", ""),
            "gaps": paper.get("Research Gaps", ""),
        })

    prompt = f"""
You are an academic literature review assistant.

Compare these AI-extracted research paper summaries:

{json.dumps(paper_summaries, ensure_ascii=False)}

Return a clear comparison in Markdown with these headings:

## Common Themes
Identify themes supported by multiple papers.

## Agreements
Explain findings that appear consistent across papers.

## Differences
Identify differences in findings, methods, populations, or study designs.

## Research Gaps
Identify potential gaps supported by the supplied summaries.
Clearly distinguish evidence from speculation.

## Overall Synthesis
Provide a short synthesis suitable as a starting point for a
literature review.

IMPORTANT:
- Use only the information supplied.
- Do not invent results, citations, or statistics.
- Do not assume two studies agree simply because they discuss
  the same topic.
- Mention when the summaries do not provide enough information.
- This is a preliminary synthesis, not a substitute for reading
  the original papers.
"""

    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
        config={"temperature": 0.2},
    )

    return response.text


# Upload interface
st.divider()
st.header("📄 Upload Research Papers")

uploaded_files = st.file_uploader(
    "Choose your research paper PDFs",
    type=["pdf"],
    accept_multiple_files=True,
)

if st.button(
    "🤖 Analyze Papers with AI",
    disabled=not uploaded_files,
):
    client = get_gemini_client()

    results = []
    texts = {}

    progress = st.progress(0)

    for index, file in enumerate(uploaded_files):
        try:
            text = extract_pdf(file)

            if not text.strip():
                st.warning(
                    f"{file.name} has no extractable text. "
                    "It may be a scanned PDF."
                )
            else:
                with st.spinner(f"Analyzing {file.name}..."):
                    result = analyze_paper(
                        client,
                        file.name,
                        text,
                    )

                results.append(result)
                texts[file.name] = text

        except Exception as error:
            st.warning(
                f"Could not analyze {file.name}. "
                f"Check the file and API quota. Details: {error}"
            )

        progress.progress((index + 1) / len(uploaded_files))

    st.session_state["results"] = results
    st.session_state["texts"] = texts


# Display results
if st.session_state.get("results"):
    matrix = pd.DataFrame(st.session_state["results"])

    st.divider()
    st.header("📊 Literature Review Matrix")

    st.dataframe(
        matrix,
        use_container_width=True,
    )

    # Excel export
    excel_buffer = BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl",
    ) as writer:
        matrix.to_excel(
            writer,
            index=False,
            sheet_name="Literature Matrix",
        )

    st.download_button(
        label="📥 Download Literature Matrix (Excel)",
        data=excel_buffer.getvalue(),
        file_name="ScholarPilot_Literature_Matrix.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )

    # Individual paper details
    st.divider()
    st.header("📖 Review Individual Papers")

    for paper in st.session_state["results"]:
        with st.expander(
            paper.get("Paper Title", "Research Paper")
        ):
            for key, value in paper.items():
                if key != "Source File":
                    st.markdown(f"**{key}:** {value}")

    # Compare papers
    st.divider()
    st.header("🔎 Compare Research Papers")

    if len(st.session_state["results"]) >= 2:
        if st.button("✨ Generate AI Comparison"):
            client = get_gemini_client()

            try:
                with st.spinner(
                    "Comparing papers with Gemini AI..."
                ):
                    comparison = compare_papers(
                        client,
                        st.session_state["results"],
                    )

                st.markdown(comparison)

                st.session_state["comparison"] = comparison

            except Exception as error:
                st.error(
                    f"Comparison failed: {error}"
                )

        if st.session_state.get("comparison"):
            st.download_button(
                "📥 Download AI Comparison",
                data=st.session_state["comparison"],
                file_name="ScholarPilot_Comparison.md",
                mime="text/markdown",
            )

    else:
        st.info(
            "Upload at least two papers to compare them."
        )

st.divider()

st.caption(
    "ScholarPilot | Research smarter, not harder."
    )
