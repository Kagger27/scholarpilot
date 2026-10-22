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

# =========================================================
# PREMIUM LANDING PAGE
# =========================================================
if "show_workspace" not in st.session_state:
    st.session_state.show_workspace = False

if not st.session_state.show_workspace:
    st.markdown(
        """
        <style>
        .sp-hero {
            position: relative;
            overflow: hidden;
            text-align: center;
            padding: 76px 20px 42px;
            border-radius: 24px;
            background: radial-gradient(ellipse at 50% 12%, #302451 0%, #15182D 46%, #0B1020 100%);
            border: 1px solid #353052;
            margin: 6px 0 20px;
        }
        .sp-watermark {
            position: absolute;
            top: 12px;
            left: 0;
            width: 100%;
            font-size: clamp(42px, 11vw, 112px);
            line-height: 1.1;
            font-weight: 900;
            letter-spacing: 3px;
            color: #A78BFA;
            opacity: 0.12;
            text-shadow: 2px 2px 0 #302454, 5px 5px 0 #211A3C, 0 0 28px #8B5CF6;
            pointer-events: none;
            white-space: nowrap;
        }
        .sp-content { position: relative; z-index: 1; }
        .sp-badge {
            display: inline-block;
            padding: 7px 14px;
            border: 1px solid #6552A8;
            border-radius: 30px;
            color: #D8CCFF;
            background: rgba(33, 26, 60, 0.85);
            font-size: 13px;
            margin: 12px 0 22px;
        }
        .sp-title {
            font-size: clamp(30px, 5vw, 54px);
            font-weight: 800;
            line-height: 1.15;
            color: #F8FAFC;
            margin-bottom: 18px;
        }
        .sp-title span { color: #B7A0FF; }
        .sp-description {
            max-width: 680px;
            margin: 0 auto;
            color: #CBD5E1;
            font-size: 17px;
            line-height: 1.8;
        }
        .sp-features {
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 30px;
        }
        .sp-feature {
            background: rgba(23, 29, 49, 0.9);
            border: 1px solid #303A55;
            border-radius: 12px;
            padding: 13px 16px;
            color: #E2E8F0;
            font-size: 14px;
        }
        .sp-signature {
            margin-top: 32px;
            color: #B7A0FF;
            font-size: 12px;
            letter-spacing: 2px;
        }
        [data-testid="stButton"] button {
            border-radius: 12px;
            min-height: 50px;
            font-weight: 700;
        }
        </style>

        <div class="sp-hero">
            <div class="sp-watermark">KAgger☕</div>
            <div class="sp-content">
                <div class="sp-badge">✦ YOUR AI RESEARCH COMPANION</div>
                <div class="sp-title">
                    Turn Research Papers<br>
                    Into <span>Meaningful Insights.</span>
                </div>
                <div class="sp-description">
                    Analyze academic papers, discover key findings,
                    identify research gaps, and organize your literature
                    review in one intelligent workspace.
                </div>
                <div class="sp-features">
                    <div class="sp-feature">📄 AI Paper Analysis</div>
                    <div class="sp-feature">🔎 Evidence &amp; Page References</div>
                    <div class="sp-feature">📚 Literature Review Matrix</div>
                </div>
                <div class="sp-signature">DESIGNED WITH PURPOSE · SCHOLARPILOT</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    if st.button(
        "🚀 Start Researching",
        type="primary",
        use_container_width=True,
        key="start_researching",
    ):
        st.session_state.show_workspace = True
        st.rerun()

    st.caption(
        "AI-assisted research analysis. Always verify important findings "
        "against original papers."
    )
    st.stop()

# =========================================================
# WORKSPACE HEADER / RETURN HOME
# =========================================================
top_left, top_right = st.columns([5, 1])
with top_left:
    st.title("🎓 ScholarPilot")
    st.subheader("Your AI-Powered Research Paper Assistant")
    st.markdown(
        "Analyze research papers, organize findings, identify research gaps, "
        "and compare studies using AI."
    )
with top_right:
    if st.button("🏠 Home", use_container_width=True):
        st.session_state.show_workspace = False
        st.rerun()

# =========================================================
# GEMINI CLIENT
# =========================================================
def get_gemini_client():
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            st.error(
                "Gemini API key not found. Please check your Streamlit app Secrets."
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
    """Extract text from every PDF page."""
    try:
        pdf_bytes = uploaded_file.getvalue()
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page_index, page in enumerate(document):
            pages.append({
                "page": page_index + 1,
                "text": page.get_text("text").strip(),
            })
        document.close()
        return pages
    except Exception as error:
        st.error(f"Could not read {uploaded_file.name}: {error}")
        return []

def prepare_paper_text(pages, max_chars=45000):
    """Prepare PDF text while retaining PDF page numbers."""
    sections = []
    remaining = max_chars
    for page in pages:
        page_text = page.get("text", "")
        if not page_text:
            continue
        section = f"\n[PDF PAGE {page['page']}]\n{page_text}\n"
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
    """Remove Markdown code fences from JSON if present."""
    text = response_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def generate_content(client, prompt, json_mode=False):
    """Generate content using Gemini."""
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
# ANALYZE INDIVIDUAL RESEARCH PAPER
# =========================================================
def analyze_paper(client, filename, pages):
    paper_text = prepare_paper_text(pages)
    if not paper_text.strip():
        raise ValueError(
            "No readable text was extracted from this PDF. "
            "The document may be scanned and require OCR."
        )

    prompt = f"""
You are ScholarPilot, an academic research assistant.
Analyze the supplied research paper.

Return ONLY valid JSON. Do not use Markdown code fences.
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
1. Use information supported by the supplied paper.
2. Do not invent authors, dates, statistics, or results.
3. If information is unavailable, write "Not reported".
4. Summarize findings clearly and accurately.
5. Distinguish author-reported limitations from your own interpretation.
6. Distinguish author-reported research gaps from potential gaps inferred from the paper.
7. For evidence fields, provide short, exact quotations from the supplied paper text when possible.
8. Include the corresponding PDF page number for each quote.
9. Format quotations like this: "Exact quotation from the paper" (PDF p. 4)
10. Only use page numbers shown in the supplied text.
11. Never invent quotations or page references.
12. If suitable evidence is unavailable, explain that.
13. PDF page numbers refer to actual PDF page order and may differ from printed page numbers.

SOURCE FILE: {filename}

PAPER TEXT:
{paper_text}
"""
    response_text = generate_content(client, prompt, json_mode=True)
    cleaned_text = clean_json_response(response_text)
    try:
        result = json.loads(cleaned_text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Gemini returned a response that could not be read as JSON: {error}"
        )

    expected_fields = [
        "Paper Title", "Authors", "Publication Year", "Research Objective",
        "Methodology", "Study Design", "Sample Size", "Key Findings",
        "Limitations", "Research Gaps", "Evidence for Key Findings",
        "Evidence for Limitations", "Evidence for Research Gaps",
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
        "Source File", "Paper Title", "Authors", "Publication Year",
        "Research Objective", "Methodology", "Study Design", "Sample Size",
        "Key Findings", "Limitations", "Research Gaps",
        "Evidence for Key Findings", "Evidence for Limitations",
        "Evidence for Research Gaps",
    ]
    rows = []
    for paper in papers:
        rows.append({field: paper.get(field, "Not reported") for field in fields})
    return pd.DataFrame(rows, columns=fields)

# =========================================================
# EXCEL EXPORT
# =========================================================
def create_excel_file(dataframe):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Literature Matrix")
    output.seek(0)
    return output.getvalue()

# =========================================================
# COMPARE RESEARCH PAPERS
# =========================================================
def compare_papers(client, papers):
    summary_fields = [
        "Source File", "Paper Title", "Authors", "Publication Year",
        "Research Objective", "Methodology", "Study Design", "Sample Size",
        "Key Findings", "Limitations", "Research Gaps",
        "Evidence for Key Findings", "Evidence for Limitations",
        "Evidence for Research Gaps",
    ]
    summaries = [
        {field: paper.get(field, "") for field in summary_fields}
        for paper in papers
    ]
    prompt = f"""
You are an academic literature review assistant.
Compare the following research paper summaries:
{json.dumps(summaries, ensure_ascii=False, indent=2)}

Write a Markdown report with these sections:
## Common Themes
Identify themes supported by the supplied papers.
## Agreements
Describe findings that appear consistent, citing paper titles and available evidence.
## Differences
Compare findings, methods, study designs, and populations.
## Unresolved Inquiries
Identify questions the papers do not adequately answer.
## Research Gaps
Distinguish gaps reported by authors from potential gaps inferred by comparing papers.
## Overall Synthesis
Write a balanced preliminary literature synthesis.
## Evidence and Verification Notes
Identify claims that should be checked against original PDFs. Include available quotations and PDF page references.

RULES:
- Do not invent citations, quotations, statistics, or page numbers.
- Use only the supplied summaries.
- Distinguish evidence from interpretation.
- Similar topics do not automatically mean studies agree.
- State when information is insufficient.
- Do not claim that a research gap is definitive without evidence.
- This synthesis does not replace reading the original papers.
"""
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={"temperature": 0.2},
    )
    if not response.text:
        raise ValueError("Gemini did not return a comparison report.")
    return response.text

# =========================================================
# MAIN APPLICATION: UPLOAD PAPERS
# =========================================================
st.divider()
st.header("📄 Upload Research Papers")
uploaded_files = st.file_uploader(
    "Choose one or more research paper PDFs",
    type=["pdf"],
    accept_multiple_files=True,
    help="For best results, use PDFs containing selectable text. Scanned PDFs may require OCR.",
)

if uploaded_files:
    st.info(f"{len(uploaded_files)} PDF file(s) selected.")
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
                    f"Analyzing {index + 1} of {total_files}: {uploaded_file.name}"
                )
                pages = extract_pdf(uploaded_file)
                if not pages:
                    st.warning(
                        f"Skipping {uploaded_file.name}: no pages could be extracted."
                    )
                    progress.progress((index + 1) / total_files)
                    continue
                try:
                    with st.spinner(f"Analyzing {uploaded_file.name}..."):
                        paper_result = analyze_paper(
                            client, uploaded_file.name, pages
                        )
                    results.append(paper_result)
                    st.success(f"Successfully analyzed {uploaded_file.name}")
                except Exception as error:
                    st.error(f"Could not analyze {uploaded_file.name}: {error}")
                progress.progress((index + 1) / total_files)

            status.empty()
            st.session_state["scholarpilot_results"] = results
            st.session_state.pop("scholarpilot_comparison", None)
            if results:
                st.success(
                    f"Analysis complete! {len(results)} paper(s) processed."
                )
            else:
                st.warning("No papers were analyzed successfully.")

# =========================================================
# DISPLAY RESULTS AND DASHBOARD
# =========================================================
papers = st.session_state.get("scholarpilot_results", [])

if papers:
    st.divider()
    st.header("📊 Research Dashboard")
    st.write("An overview of your analyzed research collection.")

    def has_reported_information(value):
        if value is None:
            return False
        normalized = str(value).strip().lower()
        return normalized not in (
            "", "not reported", "none", "n/a", "not available"
        )

    total_papers = len(papers)
    findings_count = sum(
        1 for paper in papers
        if has_reported_information(paper.get("Key Findings", ""))
    )
    limitations_count = sum(
        1 for paper in papers
        if has_reported_information(paper.get("Limitations", ""))
    )
    gaps_count = sum(
        1 for paper in papers
        if has_reported_information(paper.get("Research Gaps", ""))
    )

    col1, col2 = st.columns(2)
    with col1:
        st.metric("📄 Papers Analyzed", total_papers)
    with col2:
        st.metric("🔍 Papers With Key Findings", findings_count)
    col3, col4 = st.columns(2)
    with col3:
        st.metric("⚠️ Papers With Limitations", limitations_count)
    with col4:
        st.metric("🎯 Papers With Research Gaps", gaps_count)

    st.caption(
        "Counts reflect information extracted by AI. Verify important claims "
        "against the original papers."
    )

    st.divider()
    st.header("📚 Literature Review Matrix")
    matrix = build_literature_matrix(papers)
    st.dataframe(matrix, use_container_width=True, hide_index=True)
    excel_data = create_excel_file(matrix)
    st.download_button(
        label="📥 Download Literature Matrix (Excel)",
        data=excel_data,
        file_name="scholarpilot_literature_matrix.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()
    st.header("🔍 Review Individual Papers")
    for index, paper in enumerate(papers):
        title = paper.get("Paper Title", "Untitled paper")
        filename = paper.get("Source File", f"Paper {index + 1}")
        with st.expander(f"📄 {title} — {filename}", expanded=False):
            st.markdown(f"**Source file:** {filename}")
            st.markdown("### Paper Information")
            display_fields = [
                "Authors", "Publication Year", "Research Objective",
                "Methodology", "Study Design", "Sample Size",
                "Key Findings", "Limitations", "Research Gaps",
            ]
            for field in display_fields:
                st.markdown(f"**{field}**")
                st.write(paper.get(field, "Not reported"))
            st.markdown("### Evidence and Page References")
            evidence_fields = [
                "Evidence for Key Findings", "Evidence for Limitations",
                "Evidence for Research Gaps",
            ]
            for field in evidence_fields:
                st.markdown(f"**{field}**")
                st.write(paper.get(field, "Not reported"))

    st.divider()
    st.header("⚖️ Compare Research Papers")
    if len(papers) >= 2:
        st.write(
            "Compare papers to explore shared themes, agreements, differences, "
            "and research gaps."
        )
        if st.button(
            "Generate Research Comparison",
            type="primary",
            use_container_width=True,
        ):
            client = get_gemini_client()
            if client:
                try:
                    with st.spinner("Comparing your research papers..."):
                        comparison = compare_papers(client, papers)
                    st.session_state["scholarpilot_comparison"] = comparison
                except Exception as error:
                    st.error(f"Could not compare the papers: {error}")

        comparison = st.session_state.get("scholarpilot_comparison", "")
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
            "Analyze at least two papers to use the research comparison feature."
        )

    st.divider()
    if st.button("🗑️ Clear Results"):
        st.session_state.pop("scholarpilot_results", None)
        st.session_state.pop("scholarpilot_comparison", None)
        st.rerun()

# =========================================================
# FOOTER
# =========================================================
st.divider()
st.caption(
    "ScholarPilot | AI-assisted academic research analysis. Always verify "
    "quotations, page numbers, and interpretations against the original papers."
)
