import streamlit as st
import pdfplumber
import google.generativeai as genai
import json
import re
import time
from io import BytesIO

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FactCheck Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main { background: #0f1117; }
.hero-title {
    font-size: 2.8rem; font-weight: 700;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-align: center; margin-bottom: 0.2rem;
}
.hero-sub { text-align: center; color: #8b8fa8; font-size: 1.05rem; margin-bottom: 2rem; }
.stat-box { background: #1a1d2e; border: 1px solid #2a2d3e; border-radius: 12px; padding: 1.2rem 1.5rem; text-align: center; }
.stat-num { font-size: 2rem; font-weight: 700; }
.stat-label { color: #8b8fa8; font-size: 0.85rem; margin-top: 0.2rem; }
.claim-card { background: #1a1d2e; border-radius: 12px; padding: 1.2rem 1.5rem; margin-bottom: 1rem; border-left: 4px solid #444; }
.claim-card.verified  { border-left-color: #22c55e; }
.claim-card.inaccurate{ border-left-color: #f59e0b; }
.claim-card.false     { border-left-color: #ef4444; }
.badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.badge-verified   { background: #166534; color: #86efac; }
.badge-inaccurate { background: #78350f; color: #fcd34d; }
.badge-false      { background: #7f1d1d; color: #fca5a5; }
.claim-text { font-size: 1rem; color: #e2e8f0; margin: 0.6rem 0; }
.evidence-text { font-size: 0.88rem; color: #94a3b8; line-height: 1.6; }
.upload-section { border: 2px dashed #2a2d3e; border-radius: 16px; padding: 2rem; text-align: center; background: #13151f; margin: 1rem 0; }
.step-badge { background: linear-gradient(135deg, #667eea, #764ba2); color: white; border-radius: 50%; width: 28px; height: 28px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700; margin-right: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(uploaded_file) -> str:
    with pdfplumber.open(uploaded_file) as pdf:
        pages_text = [page.extract_text() for page in pdf.pages if page.extract_text()]
    return "\n\n".join(pages_text)


def extract_claims(api_key: str, text: str) -> list:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""You are a meticulous fact-extraction assistant.

From the document text below, extract ALL specific verifiable claims — statistics, percentages, dates, financial figures, named facts, technical metrics, and quantitative statements.

Return a JSON array (no markdown, no extra text) where each item has:
  "claim": the exact claim as written in the document (max 200 chars)
  "category": one of [statistic, date, financial, technical, general_fact]

Extract at least 5 claims, up to 20. Prioritise numbers and named facts.

DOCUMENT:
{text[:6000]}

JSON ARRAY:"""
    resp = model.generate_content(prompt)
    raw = re.sub(r"^```(?:json)?|```$", "", resp.text.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw)


def verify_claim(api_key: str, claim: dict) -> dict:
    genai.configure(api_key=api_key)
    prompt = f"""You are a rigorous fact-checker. Use your knowledge and any available search to verify this claim.

CLAIM: "{claim['claim']}"
CATEGORY: {claim['category']}

Return a JSON object (no markdown, no extra text) with:
  "verdict": "Verified" | "Inaccurate" | "False"
  "explanation": 1-2 sentences explaining the verdict with actual correct data
  "correct_value": the correct figure/date/fact if the claim is wrong, else null
  "confidence": "High" | "Medium" | "Low"

Verdict rules:
- "Verified"   -> claim matches current known facts
- "Inaccurate" -> partially right but number/date is outdated or wrong
- "False"      -> fabricated, no basis, or completely wrong

JSON ONLY:"""

    try:
        # Try Gemini 1.5 Pro with Google Search grounding
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            tools="google_search_retrieval",
        )
        resp = model.generate_content(prompt)
        content = resp.text.strip()
    except Exception:
        # Fallback to Flash without grounding
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content(prompt)
        content = resp.text.strip()

    content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
    try:
        result = json.loads(content)
    except Exception:
        result = {"verdict": "False", "explanation": "Could not verify this claim.", "correct_value": None, "confidence": "Low"}
    return {**claim, **result}


def verdict_badge(verdict: str) -> str:
    cls = verdict.lower()
    icons = {"verified": "✅", "inaccurate": "⚠️", "false": "❌"}
    icon = icons.get(cls, "❓")
    return f'<span class="badge badge-{cls}">{icon} {verdict}</span>'


def render_claim_card(item: dict, idx: int):
    verdict = item.get("verdict", "False")
    cls = verdict.lower()
    badge = verdict_badge(verdict)
    correct = f"<br><strong>Correct:</strong> {item['correct_value']}" if item.get("correct_value") else ""
    conf = item.get("confidence", "")
    st.markdown(f"""
<div class="claim-card {cls}">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="color:#8b8fa8;font-size:0.8rem;">#{idx} · {item.get('category','').upper()}</span>
    <span>{badge} &nbsp; <span style="font-size:0.78rem;color:#8b8fa8;">{conf} confidence</span></span>
  </div>
  <p class="claim-text">"{item['claim']}"</p>
  <p class="evidence-text">{item.get('explanation','')}{correct}</p>
</div>
""", unsafe_allow_html=True)


# ── Main UI ────────────────────────────────────────────────────────────────────

st.markdown('<h1 class="hero-title">🔍 FactCheck Agent</h1>', unsafe_allow_html=True)
st.markdown('<p class="hero-sub">Upload a PDF → AI extracts claims → Live web verification → Verdict report</p>', unsafe_allow_html=True)

with st.expander("⚙️ Configuration", expanded=False):
    api_key = st.text_input(
        "Google Gemini API Key",
        type="password",
        placeholder="AIza...",
        help="Get your free key at https://aistudio.google.com/app/apikey — never stored, session only.",
    )

if not api_key:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

st.markdown("---")
col_up, col_info = st.columns([2, 1])

with col_up:
    st.markdown("### 📄 Upload Document")
    uploaded = st.file_uploader("Drop your PDF here", type=["pdf"], label_visibility="collapsed")

with col_info:
    st.markdown("### How it works")
    for step, label in [("1", "PDF text extracted"), ("2", "Claims identified by AI"), ("3", "Each claim web-verified"), ("4", "Full verdict report")]:
        st.markdown(f'<span class="step-badge">{step}</span> {label}', unsafe_allow_html=True)
        st.write("")

if uploaded:
    if not api_key:
        st.error("⛔ Please enter your Gemini API key in the Configuration section above.")
        st.stop()

    st.markdown("---")

    if st.button("🚀 Run Fact-Check Analysis", type="primary", use_container_width=True):

        with st.status("Running fact-check pipeline…", expanded=True) as status:

            st.write("📄 Extracting text from PDF…")
            try:
                pdf_text = extract_text_from_pdf(BytesIO(uploaded.read()))
            except Exception as e:
                st.error(f"Failed to read PDF: {e}")
                st.stop()

            if len(pdf_text.strip()) < 50:
                st.warning("Very little text found — the PDF may be image-based (scanned). Try a text PDF.")
                st.stop()

            st.write(f"✅ Extracted {len(pdf_text):,} characters from {uploaded.name}")

            st.write("🧠 Identifying verifiable claims…")
            try:
                claims = extract_claims(api_key, pdf_text)
            except Exception as e:
                st.error(f"Claim extraction failed: {e}")
                st.stop()

            st.write(f"✅ Found {len(claims)} claims to verify")

            st.write("🌐 Verifying claims against live data…")
            results = []
            progress = st.progress(0)

            for i, claim in enumerate(claims):
                try:
                    verified = verify_claim(api_key, claim)
                    results.append(verified)
                except Exception as e:
                    results.append({**claim, "verdict": "False", "explanation": f"Verification error: {e}", "correct_value": None, "confidence": "Low"})
                progress.progress((i + 1) / len(claims))
                time.sleep(0.3)

            status.update(label="✅ Analysis complete!", state="complete")

        st.markdown("---")
        st.markdown("## 📊 Fact-Check Report")

        counts = {"Verified": 0, "Inaccurate": 0, "False": 0}
        for r in results:
            v = r.get("verdict", "False")
            counts[v] = counts.get(v, 0) + 1

        total = len(results)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="stat-box"><div class="stat-num" style="color:#a78bfa">{total}</div><div class="stat-label">Total Claims</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="stat-box"><div class="stat-num" style="color:#22c55e">{counts["Verified"]}</div><div class="stat-label">✅ Verified</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="stat-box"><div class="stat-num" style="color:#f59e0b">{counts["Inaccurate"]}</div><div class="stat-label">⚠️ Inaccurate</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="stat-box"><div class="stat-num" style="color:#ef4444">{counts["False"]}</div><div class="stat-label">❌ False</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        tab_all, tab_v, tab_i, tab_f = st.tabs(["All Claims", "✅ Verified", "⚠️ Inaccurate", "❌ False"])

        def render_tab(tab, filter_verdict=None):
            with tab:
                filtered = [r for r in results if filter_verdict is None or r.get("verdict") == filter_verdict]
                if not filtered:
                    st.info("No claims in this category.")
                for idx, item in enumerate(filtered, 1):
                    render_claim_card(item, idx)

        render_tab(tab_all)
        render_tab(tab_v, "Verified")
        render_tab(tab_i, "Inaccurate")
        render_tab(tab_f, "False")

        st.markdown("---")
        st.download_button(
            "⬇️ Download Full Report (JSON)",
            data=json.dumps(results, indent=2),
            file_name="factcheck_report.json",
            mime="application/json",
        )

else:
    st.markdown("""
<div class="upload-section">
  <p style="font-size:3rem;margin:0">📂</p>
  <p style="color:#8b8fa8;margin:0.5rem 0">Drag and drop your PDF above to begin</p>
  <p style="color:#4b5563;font-size:0.85rem">Supports marketing reports, research papers, press releases, and more</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")
st.markdown('<p style="text-align:center;color:#4b5563;font-size:0.8rem;">FactCheck Agent · Powered by Google Gemini · Built for CogCulture Assessment</p>', unsafe_allow_html=True)
