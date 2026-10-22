import streamlit as st
import fitz
import pandas as pd
import json
import re
from io import BytesIO
from google import genai


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="ScholarPilot",
    page_icon="🎓",
    layout="wide",
)

st.title("🎓 ScholarPilot")
st.subheader("Your AI-Powered Research Paper Assistant")

st.markdown(
    """
    Upload research papers to extract key information, organize
    findings, identify research gaps, and compare studies.

    **New:** Evidence quotations and PDF page references help
    you verify important claims against the original papers.
    """
)


# =========================================================
# GEMINI CLIENT
# =========================================================

def get_gemini_client():
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")

        if not api_key:
            st.error(
                "Gemini API key not found. Add GEMINI_API_KEY "
                "to your Streamlit app Secrets."
            )
            return None

        return genai.Client(api_key=api_key)

    except Exception as error:
        st.error(f"Could not connect to Gemini: {error}")
        return None


# =========================================================
# PDF EXTRACTION
# =========================================================

def extract_pdf(uploaded_file):
    """Extract text from each PDF page separately."""

    try:
        pdf_bytes = uploaded_file.getvalue()
        document = fitz.open(stream=pdf_bytes, filetype="pdf")

        pages = []

        for page_index, page in enumerate(document):
            pages.append(
                {
                    "page": page_index + 1,
                    "text": page.get_text("text").strip(),
                }
            )

        document.close()
        return pages

    except Exception as error:
        st.error(
            f"Could not read {uploaded_file.name}: {error}"
        )
        return []


def prepare_paper_text(pages, max_chars=45000):
    """
    Combine extracted text while preserving PDF page labels.
    The character limit helps control API usage.
    """

    sections = []
    remaining = max_chars

    for page in pages:
        page_text = page.get("text", "")

        if not page_text:
            continue

        section = (
            f"\n[PDF PAGE {page['page']}]\n"
            f"{page_text}\n"
        )

        if len(section) > remaining:
            if remaining > 100:
                sections.append(section[:remaining])
            break

        sections.append(section)
        remaining -= len(section)

        if remaining <= 0:
            break

    return "\n".join(sections)


# =========================================================
# GEMINI RESPONSE HELPERS
# =========================================================

def clean_json_response(response_text):
    """Remove Markdown code fences if Gemini returns them."""

    text = response_text.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\s*```$", "", text)

    return text.strip()


def generate_content(client, prompt, json_mode=False):
    """Call Gemini and return the generated text."""

    config = {"temperature": 0.1}

    if json_mode:
        config["response_mime_type"] = "application/json"

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=config,
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    return response.text


# =========================================================
# ANALYZE ONE RESEARCH PAPER
# =========================================================

def analyze_paper(client, filename, pages):
    paper_text = prepare_paper_text(pages)

    if not paper_text.strip():
        raise ValueError(
            "No readable text was extracted from this PDF. "
            "It may be a scanned document requiring OCR."
        )

    prompt = f"""
You are ScholarPilot, an academic research assistant.

Analyze the supplied research paper carefully.

Return ONLY valid JSON. Do not wrap the JSON in Markdown.

Use exactly these keys:

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
  "Research Gaps": "",
  "Evidence for Key Findings": "",
  "Evidence for Limitations": "",
  "Evidence for Research Gaps": ""
}}

INSTRUCTIONS:

1. Use information explicitly supported by the paper.
2. Do not invent missing details, authors, dates, or statistics.
3. If information cannot be determined, write "Not reported".
4. Keep findings and limitations concise but informative.
5. Distinguish limitations explicitly stated by the authors from
   limitations you infer.
6. Distinguish research gaps explicitly stated by the authors
   from potential gaps inferred from the paper.
7. For evidence fields, provide short exact quotations from
   the supplied paper text whenever possible.
8. Include the PDF page number associated with each quotation.
9. Use this format for evidence:

   "Exact quotation from the paper" (PDF p. 4)

10. Only cite page numbers shown in the supplied text labels.
11. Never invent a quotation or page number.
12. If suitable direct evidence cannot be found, explain that
    the paper text provided does not contain a verifiable quote.
13. The PDF page numbers refer to the actual PDF page order,
    which may differ from printed page numbers.

SOURCE FILE: {filename}

PAPER TEXT:

{paper_text}
"""

    response_text = generate_content(
        client,
        prompt,
        json_mode=True,
    )

    cleaned_text = clean_json_response(response_text)

    try:
        result = json.loads(cleaned_text)

    except json.JSONDecodeError as error:
        raise ValueError(
            "Gemini returned information that could not be "
            f"read as JSON. Details: {error}"
        )

    expected_fields = [
        "Paper Title",
        "Authors",
        "Publication Year",
        "Research Objective",
        "Methodology",
        "Study Design",
        "Sample Size",
        "Key Findings",
        "Limitations",
        "Research Gaps",
        "Evidence for Key Findings",
        "Evidence for Limitations",
        "Evidence for Research Gaps",
    ]

    for field in expected_fields:
        result.setdefault(field, "Not reported")

    result["Source File"] = filename

    return result


# =========================================================
# LITERATURE REVIEW MATRIX
# =========================================================

def build_literature_matrix(papers):
    fields = [
        "Source File",
        "Paper Title",
        "Authors",
        "Publication Year",
        "Research Objective",
        "Methodology",
        "Study Design",
        "Sample Size",
        "Key Findings",
        "Limitations",
        "Research Gaps",
        "Evidence for Key Findings",
        "Evidence for Limitations",
        "Evidence for Research Gaps",
    ]

    rows = []

    for paper in papers:
        rows.append(
            {
                field: paper.get(field, "Not reported")
                for field in fields
            }
        )

    return pd.DataFrame(rows, columns=fields)


# =========================================================
# EXCEL EXPORT
# =========================================================

def create_excel_file(dataframe):
    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:
        dataframe.to_excel(
            writer,
            index=False,
            sheet_name="Literature Matrix",
        )

    output.seek(0)

    return output.getvalue()


# =========================================================
# COMPARE RESEARCH PAPERS
# =========================================================

def compare_papers(client, papers):
    summaries = []

    for paper in papers:
        summaries.append(
            {
                "Source File": paper.get("Source File", ""),
                "Paper Title": paper.get(
                    "Paper Title",
                    "Not reported",
                ),
                "Authors": paper.get("Authors", ""),
                "Publication Year": paper.get(
                    "Publication Year",
                    "",
                ),
                "Research Objective": paper.get(
                    "Research Objective",
                    "",
                ),
                "Methodology": paper.get("Methodology", ""),
                "Study Design": paper.get("Study Design", ""),
                "Sample Size": paper.get("Sample Size", ""),
                "Key Findings": paper.get("Key Findings", ""),
                "Limitations": paper.get("Limitations", ""),
                "Research Gaps": paper.get("Research Gaps", ""),
                "Evidence for Key Findings": paper.get(
                    "Evidence for Key Findings",
                    "",
                ),
                "Evidence for Limitations": paper.get(
                    "Evidence for Limitations",
                    "",
                ),
                "Evidence for Research Gaps": paper.get(
                    "Evidence for Research Gaps",
                    "",
                ),
            }
        )

    prompt = f"""
You are an academic literature review assistant.

Compare the following extracted research paper information:

{json.dumps(summaries, ensure_ascii=False, indent=2)}

Write a Markdown report with these headings:

## Common Themes
Identify themes supported by the supplied papers.

## Agreements
Identify findings that appear consistent. Refer to paper titles
and relevant evidence where available.

## Differences
Compare findings, methods, study designs, and populations.

## Unresolved Inquiries
Describe questions the supplied papers do not adequately answer.

## Research Gaps
Distinguish gaps explicitly reported by the authors from
potential gaps inferred by comparing the papers.

## Overall Synthesis
Write a concise, balanced preliminary literature synthesis.

## Evidence and Verification Notes
Identify important claims that should be checked against the
original PDFs. Include available source filenames, quotations,
and PDF page references.

IMPORTANT RULES:

- Do not invent citations, quotations, statistics, or page numbers.
- Use only evidence included in the supplied summaries.
- Distinguish evidence from interpretation.
- Similar topics do not automatically mean that studies agree.
- If information is insufficient, say so.
- Do not claim that a research gap is definitive without evidence.
- Make clear when a comparison is an interpretation.
- This synthesis is a starting point, not a substitute for
  reading the original research papers.
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={"temperature": 0.2},
    )

    if not response.text:
        raise ValueError(
            "Gemini did not return a comparison report."
        )

    return response.text


# =========================================================
# MAIN APPLICATION
# =========================================================

st.divider()

st.header("📄 Upload Research Papers")

uploaded_files = st.file_uploader(
    "Choose one or more research paper PDFs",
    type=["pdf"],
    accept_multiple_files=True,
    help=(
        "For best results, use PDFs containing selectable text. "
        "Scanned PDFs may require OCR."
    ),
)

if uploaded_files:
    st.info(
        f"{len(uploaded_files)} PDF file(s) selected."
    )

    analyze_button = st.button(
        "🚀 Analyze Research Papers",
        type="primary",
        use_container_width=True,
    )

    if analyze_button:
        client = get_gemini_client()

        if client:
            results = []
            progress = st.progress(0)
            status = st.empty()

            total_files = len(uploaded_files)

            for index, uploaded_file in enumerate(uploaded_files):
                status.write(
                    f"Analyzing {index + 1} of {total_files}: "
                    f"{uploaded_file.name}"
                )

                pages = extract_pdf(uploaded_file)

                if not pages:
                    st.warning(
                        f"Skipping {uploaded_file.name}: "
                        "no pages could be extracted."
                    )
                    progress.progress(
                        (index + 1) / total_files
                    )
                    continue

                try:
                    with st.spinner(
                        f"Analyzing {uploaded_file.name}..."
                    ):
                        paper_result = analyze_paper(
                            client,
                            uploaded_file.name,
                            pages,
                        )

                    results.append(paper_result)

                    st.success(
                        f"Successfully analyzed "
                        f"{uploaded_file.name}"
                    )

                except Exception as error:
                    st.error(
                        f"Could not analyze "
                        f"{uploaded_file.name}: {error}"
                    )

                progress.progress(
                    (index + 1) / total_files
                )

            status.empty()

            st.session_state["scholarpilot_results"] = results

            if results:
                st.success(
                    f"Analysis complete! "
                    f"{len(results)} paper(s) processed."
                )
            else:
                st.warning(
                    "No papers were analyzed successfully."
                )


# =========================================================
# DISPLAY RESULTS
# =========================================================

papers = st.session_state.get(
    "scholarpilot_results",
    [],
)

if papers: 
    # RESEARCH DASHBOARD
    st.divider()

    st.header("📊 Research Dashboard")

    st.write(
        "An overview of your analyzed research collection."
    )

    total_papers = len(papers)

    findings_count = sum(
        1 for paper in papers
        if str(paper.get("Key Findings", "")).strip().lower()
        not in ("", "not reported", "none", "n/a")
    )

    limitations_count = sum(
        1 for paper in papers
        if str(paper.get("Limitations", "")).strip().lower()
        not in ("", "not reported", "none", "n/a")
    )

    gaps_count = sum(
        1 for paper in papers
        if str(paper.get("Research Gaps", "")).strip().lower()
        not in ("", "not reported", "none", "n/a")
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            label="📄 Papers Analyzed",
            value=total_papers,
        )

    with col2:
        st.metric(
            label="🔍 Papers With Key Findings",
            value=findings_count,
        )

    col3, col4 = st.columns(2)

    with col3:
        st.metric(
            label="⚠️ Papers With Limitations",
            value=limitations_count,
        )

    with col4:
        st.metric(
            label="🎯 Papers With Research Gaps",
            value=gaps_count,
        )

    st.caption(
        "Counts are based on information extracted by AI. "
        "Verify important findings against the original papers."
    )

st.divider()    
st.header("📚 Literature Review Matrix")

matrix = build_literature_matrix(papers)

    st.dataframe(
        matrix,
        use_container_width=True,
        hide_index=True,
    )

    excel_data = create_excel_file(matrix)

    st.download_button(
        label="📥 Download Literature Matrix (Excel)",
        data=excel_data,
        file_name="scholarpilot_literature_matrix.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        use_container_width=True,
    )

    # -----------------------------------------------------
    # INDIVIDUAL PAPER REVIEWS
    # -----------------------------------------------------

    st.divider()

    st.header("🔍 Review Individual Papers")

    for index, paper in enumerate(papers):
        title = paper.get(
            "Paper Title",
            "Untitled paper",
        )

        filename = paper.get(
            "Source File",
            f"Paper {index + 1}",
        )

        with st.expander(
            f"📄 {title} — {filename}",
            expanded=False,
        ):
            st.markdown(f"**Source file:** {filename}")

            st.markdown("### Paper Information")

            display_fields = [
                "Authors",
                "Publication Year",
                "Research Objective",
                "Methodology",
                "Study Design",
                "Sample Size",
                "Key Findings",
                "Limitations",
                "Research Gaps",
            ]

            for field in display_fields:
                st.markdown(f"**{field}**")
                st.write(
                    paper.get(field, "Not reported")
                )

            st.markdown("### Evidence and Page References")

            evidence_fields = [
                "Evidence for Key Findings",
                "Evidence for Limitations",
                "Evidence for Research Gaps",
            ]

            for field in evidence_fields:
                st.markdown(f"**{field}**")
                st.write(
                    paper.get(field, "Not reported")
                )

    # -----------------------------------------------------
    # COMPARE PAPERS
    # -----------------------------------------------------

    st.divider()

    st.header("⚖️ Compare Research Papers")

    if len(papers) >= 2:
        st.write(
            "Compare the selected papers to identify shared "
            "themes, agreements, differences, and research gaps."
        )

        if st.button(
            "Generate Research Comparison",
            type="primary",
            use_container_width=True,
        ):
            client = get_gemini_client()

            if client:
                try:
                    with st.spinner(
                        "Comparing your research papers..."
                    ):
                        comparison = compare_papers(
                            client,
                            papers,
                        )

                    st.session_state[
                        "scholarpilot_comparison"
                    ] = comparison

                except Exception as error:
                    st.error(
                        f"Could not compare the papers: {error}"
                    )

        comparison = st.session_state.get(
            "scholarpilot_comparison",
            "",
        )

        if comparison:
            st.markdown(comparison)

            st.download_button(
                label="📥 Download Comparison Report",
                data=comparison,
                file_name="scholarpilot_comparison.md",
                mime="text/markdown",
                use_container_width=True,
            )

    else:
        st.info(
            "Upload and successfully analyze at least two "
            "papers to use the comparison feature."
        )

    # -----------------------------------------------------
    # CLEAR RESULTS
    # -----------------------------------------------------

    st.divider()

    if st.button("🗑️ Clear Results"):
        st.session_state.pop(
            "scholarpilot_results",
            None,
        )

        st.session_state.pop(
            "scholarpilot_comparison",
            None,
        )

        st.rerun()


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "ScholarPilot | AI-assisted academic research analysis. "
    "Always verify quotations, page numbers, and interpretations "
    "against the original research papers."
        )
