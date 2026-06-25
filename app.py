import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

import streamlit as st
import streamlit.components.v1 as components

# =========================================================
# App chuyen tone cam am Do Re Mi
# Chay: streamlit run app.py
# =========================================================

NOTE_TO_SEMITONE: Dict[str, int] = {
    "do": 0,
    "re": 2,
    "mi": 4,
    "fa": 5,
    "sol": 7,
    "la": 9,
    "si": 11,
}

SHARP_NAMES = ["do", "do#", "re", "re#", "mi", "fa", "fa#", "sol", "sol#", "la", "la#", "si"]
FLAT_NAMES  = ["do", "reb", "re", "mib", "mi", "fa", "solb", "sol", "lab", "la", "sib", "si"]

TONE_OPTIONS = [
    ("Do", 0), ("Do# / Reb", 1), ("Re", 2), ("Re# / Mib", 3),
    ("Mi", 4), ("Fa", 5), ("Fa# / Solb", 6), ("Sol", 7),
    ("Sol# / Lab", 8), ("La", 9), ("La# / Sib", 10), ("Si", 11),
]
TONE_NAME_BY_SEMITONE = {value: name for name, value in TONE_OPTIONS}
EASY_TONES_SHARP_ONLY = [0, 7, 5, 2, 10, 9, 3, 4, 8, 11, 1, 6]

NOTE_PATTERN = re.compile(r"(?i)\b(sol|do|re|mi|fa|la|si)([#b♭]?)([0-9`']*)([#b♭]?)")


@dataclass
class ParsedNote:
    original: str
    note_name: str
    accidental: str
    octave_text: str
    semitone: int
    octave: int


def normalize_accidental(acc1: str, acc2: str) -> str:
    acc = acc1 or acc2 or ""
    return acc.replace("♭", "b").lower()


def parse_octave(octave_text: str) -> int:
    octave = 0
    if not octave_text:
        return octave
    low_marks = octave_text.count("`") + octave_text.count("'")
    octave -= low_marks
    digits = "".join(ch for ch in octave_text if ch.isdigit())
    if digits:
        number = int(digits)
        if number >= 2:
            octave += number - 1
    return octave


def note_to_abs_semitone(note_name: str, accidental: str, octave: int) -> int:
    semi = NOTE_TO_SEMITONE[note_name.lower()]
    if accidental == "#":   semi += 1
    elif accidental == "b": semi -= 1
    return octave * 12 + semi


def octave_suffix(octave: int) -> str:
    if octave == 0:  return ""
    if octave > 0:   return str(octave + 1)
    return "`" * abs(octave)


def name_for_semitone(semitone: int, spelling: str) -> str:
    semitone = semitone % 12
    return FLAT_NAMES[semitone] if spelling == "Cho phép b nếu dễ nhìn hơn" else SHARP_NAMES[semitone]


def parse_note_match(match: re.Match) -> ParsedNote:
    note_name  = match.group(1).lower()
    accidental = normalize_accidental(match.group(2), match.group(4))
    octave_text = match.group(3) or ""
    octave = parse_octave(octave_text)
    semi_abs = note_to_abs_semitone(note_name, accidental, octave)
    return ParsedNote(
        original=match.group(0), note_name=note_name,
        accidental=accidental, octave_text=octave_text,
        semitone=semi_abs % 12, octave=octave,
    )


def transpose_text(text: str, shift: int, spelling: str) -> str:
    def replace(match: re.Match) -> str:
        parsed = parse_note_match(match)
        old_abs = note_to_abs_semitone(parsed.note_name, parsed.accidental, parsed.octave)
        new_abs = old_abs + shift
        new_octave, new_semitone = divmod(new_abs, 12)
        return name_for_semitone(new_semitone, spelling) + octave_suffix(new_octave)
    return NOTE_PATTERN.sub(replace, text)


def collect_notes(text: str) -> List[int]:
    return [parse_note_match(m).semitone for m in NOTE_PATTERN.finditer(text)]


def last_note_semitone(text: str):
    matches = list(NOTE_PATTERN.finditer(text))
    return parse_note_match(matches[-1]).semitone if matches else None


def major_scale(root: int) -> set:
    return {(root + x) % 12 for x in [0, 2, 4, 5, 7, 9, 11]}


def guess_current_tone(text: str) -> List[Tuple[str, int, int]]:
    notes = collect_notes(text)
    if not notes: return []
    ending = last_note_semitone(text)
    results = []
    for name, root in TONE_OPTIONS:
        scale = major_scale(root)
        score = sum(1 for n in notes if n in scale)
        if ending == root: score += 2
        results.append((name, root, score))
    results.sort(key=lambda x: x[2], reverse=True)
    return results[:3]


def shortest_shift(source: int, target: int) -> int:
    shift = (target - source) % 12
    return shift - 12 if shift > 6 else shift


def count_symbols(text: str) -> Tuple[int, int, int]:
    sharp_count = text.count("#")
    flat_count  = len(re.findall(
        r"(?i)(?<=\bdo)b|(?<=\bre)b|(?<=\bmi)b|(?<=\bfa)b|(?<=\bsol)b|(?<=\bla)b|(?<=\bsi)b", text))
    return sharp_count, flat_count, sharp_count + flat_count


def suggest_easy_targets(source_root: int, input_text: str, spelling: str, max_abs_shift: int) -> List[dict]:
    rows = []
    for target_root in EASY_TONES_SHARP_ONLY:
        shift = shortest_shift(source_root, target_root)
        if abs(shift) > max_abs_shift: continue
        output = transpose_text(input_text, shift, spelling)
        s, f, total = count_symbols(output)
        rows.append({
            "Tone gợi ý": TONE_NAME_BY_SEMITONE[target_root],
            "Dịch": shift, "Số dấu #": s, "Số dấu b": f,
            "Tổng dấu lạ": total, "output": output,
        })
    rows.sort(key=lambda r: (r["Tổng dấu lạ"], abs(r["Dịch"]), r["Số dấu #"]))
    return rows


def shift_label(shift: int) -> str:
    if shift == 0:   return "giữ nguyên"
    if shift > 0:    return f"lên {shift} nấc"
    return f"xuống {abs(shift)} nấc"


# ══════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════
st.set_page_config(page_title="Chuyển tone cảm âm", page_icon="🎹", layout="wide")

# ── Toàn bộ CSS + JS override ────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Tokens ── */
:root {
  --bg:       #0d0d14;
  --card:     #15151f;
  --card2:    #1c1c28;
  --border:   rgba(255,255,255,0.08);
  --gold:     #f0b429;
  --gold2:    #ffd166;
  --blue:     #60a5fa;
  --green:    #34d399;
  --red:      #f87171;
  --txt:      #e2e2f0;
  --muted:    #7070a0;
  --r:        10px;
  --mono:     'JetBrains Mono', monospace;
}

/* ── App shell ── */
.stApp { background: var(--bg) !important; color: var(--txt); font-family: 'Inter', sans-serif; }
.main .block-container { padding: 1rem 1.1rem 4rem !important; max-width: 1140px; }
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--card2); border-radius: 3px; }

/* ── Custom section labels ── */
.lbl {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 10px; font-weight: 700; letter-spacing: .12em;
  text-transform: uppercase; color: var(--gold);
  margin-bottom: 6px; margin-top: 4px;
}
.lbl-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--gold); flex-shrink: 0;
}

/* ── Result card ── */
.result-card {
  background: var(--card);
  border: 1px solid rgba(240,180,41,0.25);
  border-left: 3px solid var(--gold);
  border-radius: var(--r);
  padding: 1rem 1.1rem;
  margin: 0.5rem 0 0.8rem;
  font-family: var(--mono);
  font-size: 0.97rem;
  line-height: 1.8;
  color: var(--txt);
  white-space: pre-wrap;
  word-break: break-all;
}
.result-card .sharp  { color: var(--gold);  font-weight: 600; }
.result-card .flat   { color: var(--blue);  font-weight: 600; }
.result-card .high   { color: var(--green); font-size: 0.82em; vertical-align: super; }
.result-card .low    { color: var(--muted); font-size: 0.82em; vertical-align: sub; }

/* ── Stat chips ── */
.chips { display: flex; gap: 8px; flex-wrap: wrap; margin: 0.5rem 0; }
.chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: 20px;
  font-size: 12px; font-weight: 600;
  background: var(--card2); border: 1px solid var(--border);
}
.chip.gold  { border-color: rgba(240,180,41,.4); color: var(--gold); }
.chip.blue  { border-color: rgba(96,165,250,.4); color: var(--blue); }
.chip.green { border-color: rgba(52,211,153,.4); color: var(--green); }

/* ── Tone guess banner ── */
.guess-banner {
  background: linear-gradient(135deg, rgba(96,165,250,.08), rgba(240,180,41,.06));
  border: 1px solid rgba(96,165,250,.2);
  border-radius: var(--r);
  padding: 0.7rem 1rem;
  font-size: 13px; color: var(--blue);
  margin-bottom: 0.8rem;
  display: flex; align-items: flex-start; gap: 8px;
}
.guess-banner .tone-pills { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
.tone-pill {
  background: rgba(96,165,250,.15);
  border: 1px solid rgba(96,165,250,.3);
  border-radius: 6px; padding: 2px 10px;
  font-weight: 700; font-size: 14px; color: var(--gold2);
}

/* ── Suggestion table override ── */
.st-suggestion-table { width: 100%; border-collapse: collapse; margin: 0.6rem 0; }
.st-suggestion-table th {
  font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); padding: 6px 10px; border-bottom: 1px solid var(--border);
  text-align: left;
}
.st-suggestion-table td {
  padding: 8px 10px; font-size: 13px; border-bottom: 1px solid rgba(255,255,255,.04);
}
.st-suggestion-table tr:hover td { background: var(--card2); }
.badge-zero { color: var(--green); font-weight: 700; }
.badge-low  { color: var(--gold);  font-weight: 600; }
.badge-high { color: var(--red);   font-weight: 500; }

/* ── WIDGET OVERRIDES (deep) ── */

/* Textarea */
textarea, .stTextArea textarea {
  background: var(--card) !important;
  border: 1px solid rgba(255,255,255,0.1) !important;
  border-radius: var(--r) !important;
  color: var(--txt) !important;
  font-family: var(--mono) !important;
  font-size: 14px !important;
  line-height: 1.75 !important;
  caret-color: var(--gold) !important;
}
textarea:focus, .stTextArea textarea:focus {
  border-color: rgba(240,180,41,0.5) !important;
  outline: none !important;
  box-shadow: 0 0 0 3px rgba(240,180,41,0.1) !important;
}

/* Selectbox */
[data-baseweb="select"] > div {
  background: var(--card) !important;
  border-color: rgba(255,255,255,0.1) !important;
  border-radius: var(--r) !important;
}
[data-baseweb="select"] > div:hover { border-color: var(--gold) !important; }
[data-baseweb="select"] span, [data-baseweb="select"] div { color: var(--txt) !important; }
[data-baseweb="popover"] { background: var(--card2) !important; border: 1px solid var(--border) !important; }
[role="option"] { background: transparent !important; color: var(--txt) !important; }
[role="option"]:hover, [aria-selected="true"] { background: rgba(240,180,41,0.12) !important; color: var(--gold) !important; }

/* Radio */
[data-baseweb="radio"] {
  background: var(--card) !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  border-radius: 8px !important;
  padding: 10px 14px !important;
  margin-bottom: 6px !important;
  transition: all .15s !important;
  cursor: pointer;
}
[data-baseweb="radio"]:hover { border-color: rgba(240,180,41,.4) !important; background: var(--card2) !important; }
[data-baseweb="radio"] label { color: var(--txt) !important; font-size: 13px !important; cursor: pointer; }
[data-baseweb="radio"] [data-checked="true"] ~ label { color: var(--gold) !important; font-weight: 600 !important; }
/* Radio circle */
[data-baseweb="radio"] div[role="radio"] {
  border-color: var(--muted) !important;
  background: transparent !important;
}
[data-baseweb="radio"] div[role="radio"][aria-checked="true"] {
  border-color: var(--gold) !important;
  background: var(--gold) !important;
}

/* Slider */
[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stSliderThumb"] {
  background: var(--gold) !important;
  border-color: var(--gold) !important;
  width: 18px !important; height: 18px !important;
}
[data-testid="stSlider"] [role="slider"] {
  background: var(--gold) !important;
  border-color: var(--gold) !important;
}

/* Labels (uppercase caps) */
[data-testid="stWidgetLabel"] p,
.stTextArea label p,
.stSelectbox label p,
.stSlider label p {
  font-size: 10px !important;
  font-weight: 700 !important;
  letter-spacing: .1em !important;
  text-transform: uppercase !important;
  color: var(--muted) !important;
}

/* Alerts */
[data-testid="stAlert"] {
  border-radius: var(--r) !important;
  border: 1px solid !important;
}
[data-testid="stAlert"][data-baseweb="notification"][kind="info"] {
  background: rgba(96,165,250,.08) !important;
  border-color: rgba(96,165,250,.3) !important;
  color: var(--blue) !important;
}
[data-testid="stAlert"][kind="success"], .element-container [data-testid="stAlert"]:has(svg[data-testid*="check"]) {
  background: rgba(52,211,153,.08) !important;
  border-color: rgba(52,211,153,.3) !important;
  color: var(--green) !important;
}
[data-testid="stAlert"][kind="warning"] {
  background: rgba(240,180,41,.08) !important;
  border-color: rgba(240,180,41,.3) !important;
  color: var(--gold) !important;
}

/* Code block */
[data-testid="stCode"] {
  background: var(--card2) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
}
[data-testid="stCode"] code, pre code {
  font-family: var(--mono) !important;
  font-size: 13px !important;
  line-height: 1.8 !important;
  color: #c9d1d9 !important;
  background: transparent !important;
}

/* Dataframe */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  overflow: hidden !important;
}

/* Divider */
hr { border-color: rgba(255,255,255,0.06) !important; margin: 1.5rem 0 !important; }

/* Help text */
.stMarkdown p { color: var(--muted); font-size: 13px; line-height: 1.65; }
.stMarkdown strong { color: var(--txt) !important; }
.stMarkdown code {
  background: var(--card2) !important;
  color: var(--gold) !important;
  border-radius: 4px !important;
  padding: 1px 6px !important;
  font-family: var(--mono) !important;
}

/* Column gap */
[data-testid="stHorizontalBlock"] { gap: 1.2rem !important; }

/* Mobile */
@media (max-width: 768px) {
  .main .block-container { padding: 0.6rem 0.5rem 3rem !important; }
  textarea { font-size: 15px !important; }
  [data-baseweb="radio"] { padding: 12px 14px !important; }
  .result-card { font-size: 15px !important; line-height: 1.9 !important; }
}
</style>
""", unsafe_allow_html=True)

# ── JS: inject deeper after render ──────────────────────
st.markdown("""
<script>
(function applyTheme() {
  const style = document.createElement('style');
  style.textContent = `
    /* Shadow DOM piercing fallback via attribute selectors */
    input[type="range"]::-webkit-slider-thumb { background: #f0b429 !important; }
    input[type="range"]::-moz-range-thumb { background: #f0b429 !important; }
    input[type="range"] { accent-color: #f0b429 !important; }
  `;
  document.head.appendChild(style);
})();
</script>
""", unsafe_allow_html=True)

# ── Hero header ──────────────────────────────────────────
components.html("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@700&display=swap');
  * { margin:0; padding:0; box-sizing:border-box; }
  .hero {
    background: linear-gradient(135deg, #0f0f1a 0%, #131320 50%, #101025 100%);
    border: 1px solid rgba(240,180,41,0.15);
    border-radius: 12px;
    padding: 20px 22px 16px;
    position: relative; overflow: hidden;
    font-family: 'Inter', sans-serif;
  }
  .hero::after {
    content: '';
    position: absolute; inset: 0;
    background: radial-gradient(ellipse at 80% 50%, rgba(240,180,41,0.06) 0%, transparent 70%);
    pointer-events: none;
  }
  .notes-bg {
    position: absolute; right: 16px; top: 50%; transform: translateY(-50%);
    font-size: 28px; opacity: 0.07; letter-spacing: 8px;
    color: #f0b429; user-select: none; white-space: nowrap;
  }
  .hero-title {
    font-size: clamp(18px, 4vw, 26px);
    font-weight: 700; line-height: 1.2;
    background: linear-gradient(90deg, #f0b429, #ffd166, #f0b429);
    background-size: 200%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: shimmer 3s ease-in-out infinite;
    margin-bottom: 6px;
  }
  @keyframes shimmer {
    0%,100% { background-position: 0% } 50% { background-position: 100% }
  }
  .hero-sub { font-size: 13px; color: #6060a0; }
  .hero-sub span { color: #8080c0; }
</style>
<div class="hero">
  <div class="notes-bg">♩ ♪ ♫ ♬ ♩ ♪ ♫</div>
  <div class="hero-title">🎹 Chuyển tone cảm âm Đô Rê Mi</div>
  <div class="hero-sub">
    Dán cảm âm vào — app tìm tone dễ chơi nhất. <span>Không cần biết nhạc lý.</span>
  </div>
</div>
""", height=90)

# ── Data ─────────────────────────────────────────────────
sample = """mi do# mi fa# la, do# fa# fa# la do# mi
re si re mi fa# si mi mi mi do#
do2# do2# do2# do2# do2# fa#, fa# si do2# si, do2# mi
Sol# si si do# mi, fa# mi fa# do# si la"""

col_left, col_right = st.columns([1, 1])

# ── LEFT COLUMN ──────────────────────────────────────────
with col_left:
    st.markdown('<div class="lbl"><span class="lbl-dot"></span>① Cảm âm gốc</div>', unsafe_allow_html=True)
    input_text = st.text_area(
        "cam_am", value=sample, height=210,
        help="Ví dụ: fa#, sol#, si`, do2. Dấu ` = nốt thấp; số 2 = nốt cao.",
        label_visibility="collapsed",
    )

    st.markdown('<div class="lbl" style="margin-top:10px"><span class="lbl-dot"></span>② Kiểu ghi nốt</div>', unsafe_allow_html=True)
    spelling = st.radio(
        "spelling", ["Chỉ dùng # như cảm âm thường gặp", "Cho phép b nếu dễ nhìn hơn"],
        index=0, label_visibility="collapsed",
    )

    st.markdown('<div class="lbl" style="margin-top:10px"><span class="lbl-dot"></span>③ Cách chuyển</div>', unsafe_allow_html=True)
    mode = st.radio(
        "mode",
        ["Tự chọn số nấc lên/xuống", "Chọn tone gốc và tone muốn chơi", "App tự gợi ý tone dễ chơi"],
        index=2, label_visibility="collapsed",
    )

# ── RIGHT COLUMN ─────────────────────────────────────────
with col_right:
    st.markdown('<div class="lbl"><span class="lbl-dot"></span>④ Kết quả</div>', unsafe_allow_html=True)

    guesses = guess_current_tone(input_text)
    tone_names  = [name for name, _ in TONE_OPTIONS]
    tone_values = {name: value for name, value in TONE_OPTIONS}
    default_source_index = tone_names.index(guesses[0][0]) if guesses else 0

    # Guess banner custom HTML
    if guesses:
        pills_html = "".join(f'<span class="tone-pill">{n}</span>' for n, _, _ in guesses)
        components.html(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
  * {{ margin:0; padding:0; box-sizing:border-box; font-family:'Inter',sans-serif; }}
  .banner {{
    background: linear-gradient(135deg,rgba(96,165,250,.07),rgba(240,180,41,.05));
    border: 1px solid rgba(96,165,250,.2);
    border-radius: 10px; padding: 10px 14px;
    font-size: 12px; color: #7090c0;
  }}
  .banner-top {{ display:flex; align-items:center; gap:6px; margin-bottom:6px; }}
  .banner-icon {{ font-size:16px; }}
  .pills {{ display:flex; gap:6px; flex-wrap:wrap; }}
  .pill {{
    background: rgba(240,180,41,.12);
    border: 1px solid rgba(240,180,41,.3);
    border-radius: 6px; padding: 2px 10px;
    font-weight: 700; font-size: 14px; color: #f0c050;
  }}
  .banner-note {{ font-size:11px; color:#505080; margin-top:5px; }}
</style>
<div class="banner">
  <div class="banner-top"><span class="banner-icon">🎵</span><span>Tone hiện tại có thể là:</span></div>
  <div class="pills">{pills_html}</div>
  <div class="banner-note">Bài kết ở nốt nào thì tone đó thường đúng hơn.</div>
</div>
""", height=105)
    else:
        st.warning("⚠️ Chưa thấy nốt hợp lệ trong ô cảm âm.")

    # ── Helper: render result card với highlight ──────────
    def render_result(output: str, shift: int, sharp_count: int, flat_count: int, tone_name: str = ""):
        # Highlight # và số octave
        def highlight(text):
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            text = re.sub(r"#", '<span style="color:#f0b429;font-weight:700">#</span>', text)
            text = re.sub(r"\b([a-z]+)([2-5])\b", r'\1<sup style="color:#34d399;font-size:10px">\2</sup>', text)
            text = re.sub(r"`", '<sub style="color:#7070a0;font-size:10px">`</sub>', text)
            return text

        hl = highlight(output)
        lbl_shift = shift_label(shift)
        lbl_tone  = f"Tone <b style='color:#f0c050'>{tone_name}</b> · " if tone_name else ""
        chip_sharp = f'<span style="color:#f0b429">♯ {sharp_count}</span>'
        chip_flat  = f'<span style="color:#60a5fa">♭ {flat_count}</span>'
        total = sharp_count + flat_count
        chip_total_color = "#34d399" if total == 0 else ("#f0b429" if total <= 5 else "#f87171")
        chip_total = f'<span style="color:{chip_total_color}">⬡ {total} dấu lạ</span>'

        components.html(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Inter:wght@400;600;700&display=swap');
  * {{ margin:0;padding:0;box-sizing:border-box; }}
  body {{ background:transparent; }}
  .wrap {{ font-family:'Inter',sans-serif; }}
  .status {{
    font-size:12px; color:#50d090; margin-bottom:8px;
    display:flex; align-items:center; gap:6px;
  }}
  .status-dot {{ width:7px;height:7px;border-radius:50%;background:#34d399;flex-shrink:0; }}
  .chips {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px; }}
  .chip {{
    background:rgba(255,255,255,.05);
    border:1px solid rgba(255,255,255,.1);
    border-radius:20px; padding:3px 10px;
    font-size:12px; font-weight:600;
  }}
  .card {{
    background:#15151f;
    border:1px solid rgba(240,180,41,.2);
    border-left:3px solid #f0b429;
    border-radius:10px;
    padding:14px 16px;
    font-family:'JetBrains Mono',monospace;
    font-size:14px; line-height:1.85;
    color:#c8c8e8;
    white-space:pre-wrap;
    word-break:break-word;
  }}
  .copy-hint {{
    font-size:10px;color:#404060;margin-top:6px;
    text-align:right;letter-spacing:.05em;
  }}
  @media(max-width:600px){{.card{{font-size:15px;line-height:1.9}}}}
</style>
<div class="wrap">
  <div class="status"><span class="status-dot"></span>{lbl_tone}dịch <b>{lbl_shift}</b></div>
  <div class="chips">
    <span class="chip">{chip_sharp}</span>
    <span class="chip">{chip_flat}</span>
    <span class="chip">{chip_total}</span>
  </div>
  <div class="card">{hl}</div>
  <div class="copy-hint">↑ chọn tất cả rồi copy</div>
</div>
""", height=max(180, output.count("\n") * 28 + 160))
        # Vẫn giữ st.code để người dùng copy dễ
        st.code(output, language="text")

    # ── Mode 1 ────────────────────────────────────────────
    if mode == "Tự chọn số nấc lên/xuống":
        shift = st.slider("Dịch bao nhiêu nấc? (âm = xuống, dương = lên)", -12, 12, -2)
        output = transpose_text(input_text, shift, spelling)
        s, f, _ = count_symbols(output)
        render_result(output, shift, s, f)

    # ── Mode 2 ────────────────────────────────────────────
    elif mode == "Chọn tone gốc và tone muốn chơi":
        c1, c2 = st.columns(2)
        with c1: source_name = st.selectbox("Tone gốc", tone_names, index=default_source_index)
        with c2: target_name = st.selectbox("Tone muốn chơi", tone_names, index=tone_names.index("Sol"))
        shift = shortest_shift(tone_values[source_name], tone_values[target_name])
        output = transpose_text(input_text, shift, spelling)
        s, f, _ = count_symbols(output)
        render_result(output, shift, s, f, tone_name=target_name)

    # ── Mode 3 ────────────────────────────────────────────
    else:
        source_name = st.selectbox("Tone gốc của bài", tone_names, index=default_source_index)
        max_abs_shift = st.slider(
            "Dịch tối đa bao nhiêu nấc?", 1, 12, 5,
            help="Nhỏ = ít bị quá cao/thấp. Lớn = dễ tìm tone sạch hơn.",
        )
        suggestions = suggest_easy_targets(tone_values[source_name], input_text, spelling, max_abs_shift)

        if not suggestions:
            st.warning("⚠️ Không có gợi ý trong giới hạn đang chọn. Hãy tăng số nấc tối đa.")
        else:
            # Custom HTML table
            rows_html = ""
            for r in suggestions[:6]:
                t = r["Tổng dấu lạ"]
                cls = "badge-zero" if t == 0 else ("badge-low" if t <= 5 else "badge-high")
                badge_color = "#34d399" if t == 0 else ("#f0b429" if t <= 5 else "#f87171")
                rows_html += f"""
<tr>
  <td><b style="color:#f0c050">{r["Tone gợi ý"]}</b></td>
  <td style="color:#9090c0">{shift_label(r["Dịch"])}</td>
  <td style="color:#f0b429;font-family:monospace">{r["Số dấu #"]}</td>
  <td style="color:#60a5fa;font-family:monospace">{r["Số dấu b"]}</td>
  <td style="color:{badge_color};font-weight:700;font-family:monospace">{t}</td>
</tr>"""

            components.html(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  * {{ margin:0;padding:0;box-sizing:border-box; }}
  body {{ background:transparent; font-family:'Inter',sans-serif; }}
  .tbl-wrap {{
    border:1px solid rgba(255,255,255,.07);
    border-radius:10px; overflow:hidden;
    background:#15151f;
  }}
  table {{ width:100%; border-collapse:collapse; }}
  thead {{ background:rgba(255,255,255,.03); }}
  th {{
    font-size:10px;font-weight:700;letter-spacing:.1em;
    text-transform:uppercase;color:#505080;
    padding:8px 12px;text-align:left;
    border-bottom:1px solid rgba(255,255,255,.06);
  }}
  td {{ padding:9px 12px;font-size:13px;border-bottom:1px solid rgba(255,255,255,.03); }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:rgba(255,255,255,.02); }}
</style>
<div class="tbl-wrap">
<table>
  <thead><tr>
    <th>Tone</th><th>Cách dịch</th>
    <th>Dấu ♯</th><th>Dấu ♭</th><th>Tổng</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>
</div>
""", height=min(50 + len(suggestions[:6]) * 40, 310))

            labels = [f"{r['Tone gợi ý']} — {shift_label(r['Dịch'])} — {r['Tổng dấu lạ']} dấu lạ" for r in suggestions[:6]]
            chosen_label = st.selectbox("Chọn bản muốn lấy", labels)
            chosen = suggestions[labels.index(chosen_label)]
            s, f, _ = count_symbols(chosen["output"])
            render_result(chosen["output"], chosen["Dịch"], s, f, tone_name=chosen["Tone gợi ý"])

# ── Footer ───────────────────────────────────────────────
st.divider()
st.markdown("""
**Cách ghi nốt app hiểu được**

- `do re mi fa sol la si` — nốt bình thường
- Dấu thăng: `fa#` `sol#` `do2#`
- Nốt thấp hơn: thêm dấu backtick sau nốt → si` (thấp hơn)
- Nốt cao hơn: thêm số → `do2` `re3`

💡 **Mẹo:** chọn *App tự gợi ý* → chọn dòng **Tổng = 0** là bản sạch nhất, không có dấu lạ.
""")