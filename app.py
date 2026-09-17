import re
import html
import hashlib
import json
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

NOTE_PATTERN = re.compile(r"(?i)(?<!\w)(sol|do|re|mi|fa|la|si)([#b♭♯]?)([0-9`']*)([#b♭♯]?)(?![\w#♭♯`'])")


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
    return acc.replace("♭", "b").replace("♯", "#").lower()


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


# =========================================================
# Hợp âm và căn vị trí. Chạy cục bộ, không cần API/AI.
# =========================================================
CHORD_NAMES_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
CHORD_NAMES_FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
CHORD_ROOTS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
CHORD_RE = re.compile(
    r'(?P<root>[A-G])(?P<acc>[#b♯♭]?)(?P<quality>(?:(?:maj|min|dim|aug|sus|add|omit|no|m|M|ø|°|\+|-)|[0-9#b♯♭]|\([0-9#b♯♭,+]+\))*)'
    r'(?:/(?P<bass>[A-G])(?P<bacc>[#b♯♭]?))?'
)
BRACKET_RE = re.compile(r'\[([^\]\n]+)\]')
WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


@dataclass
class ChordRow:
    chords: list
    fractions: list
    weight: int
    source: str
    has_lyrics: bool = False


def chord_match(token):
    return CHORD_RE.fullmatch(token.strip())


def transpose_chord(token, shift, flats=False):
    m = chord_match(token)
    if not m:
        raise ValueError(f'Hợp âm chưa được hỗ trợ: {token}')
    names = CHORD_NAMES_FLAT if flats else CHORD_NAMES_SHARP

    def root(name, accidental):
        delta = 1 if accidental in ('#', '♯') else -1 if accidental in ('b', '♭') else 0
        return names[(CHORD_ROOTS[name] + delta + shift) % 12]

    result = root(m['root'], m['acc']) + m['quality'].replace('♯', '#').replace('♭', 'b')
    if m['bass']:
        result += '/' + root(m['bass'], m['bacc'])
    return result


def bare_chords(line):
    """Only chord-only lines; do not treat A/G inside normal prose as chords."""
    expanded = re.sub(r'\[([^\]]+)\]', r'\1', line.strip())
    repeat = re.search(r'\s*[x×]\s*(\d+)\s*$', expanded, re.I)
    times = 1
    if repeat:
        times = int(repeat[1])
        if not 1 <= times <= 32:
            raise ValueError('Số lần lặp hợp âm phải từ 1 đến 32.')
        expanded = expanded[:repeat.start()].strip()
    # Parentheses may wrap a progression; retain C7(b9) extensions.
    if expanded.startswith('(') and expanded.endswith(')'):
        expanded = expanded[1:-1]
    tokens = [t for t in re.split(r'\s+|[|,;→–—]+|(?<=[A-G0-9m])-(?=[A-G])', expanded) if t and t != '-']
    if tokens and all(chord_match(t) for t in tokens):
        # Locate original columns for chord-over-lyrics input.
        locations = []
        cursor = 0
        for t in tokens:
            p = line.find(t, cursor)
            locations.append(max(0, p))
            cursor = max(cursor, p + len(t))
        return tokens * times, locations * times, times
    return None


def parse_chord_source(text):
    rows, warnings = [], []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or re.fullmatch(r'[\s_\-=]+', line):
            continue
        if re.match(r'^\s*(?:capo|tone|key|intro\s*:|verse\s*:|chorus\s*:|bridge\s*:|outro\s*:)', line, re.I):
            # Keep chords after labels; ignore metadata such as Key: C.
            if re.match(r'^\s*(capo|tone|key)\b', line, re.I):
                continue
            line = line.split(':', 1)[1]
        if re.fullmatch(r'\s*\{.*\}\s*', line):
            continue
        if re.fullmatch(r'\s*(?:\[)?(?:intro|verse|chorus|bridge|outro|điệp khúc|phiên khúc|dạo đầu|dạo kết)(?:\s*\d+)?(?:\])?\s*', line, re.I):
            continue
        bare = bare_chords(line)
        if bare:
            chords, columns, times = bare
            lyric = lines[i] if i < len(lines) else ''
            # A plain lyric line following chord-only text gives column alignment.
            lyric_candidate = bool(WORD_RE.search(lyric)) and not BRACKET_RE.search(lyric)
            lyric_candidate = lyric_candidate and not re.match(r'^\s*(?:capo|tone|key|verse|chorus|intro|bridge|outro)\b', lyric, re.I)
            if lyric_candidate and times == 1 and not bare_chords(lyric):
                words = list(WORD_RE.finditer(lyric))
                nearest = [min(range(len(words)), key=lambda j: abs(words[j].start() - p)) for p in columns]
                rows.append(ChordRow(chords, [p / len(words) for p in nearest], len(words), line + '\n' + lyric, True))
                i += 1
            else:
                rows.append(ChordRow(chords, [j / len(chords) for j in range(len(chords))], len(chords), line))
            continue
        matches = [m for m in BRACKET_RE.finditer(line) if chord_match(m[1])]
        if matches:
            plain = BRACKET_RE.sub('', line)
            words = max(1, len(WORD_RE.findall(plain)))
            offsets = [len(WORD_RE.findall(BRACKET_RE.sub('', line[:m.start()]))) / words for m in matches]
            rows.append(ChordRow([m[1].strip() for m in matches], offsets, words, line, True))
        elif re.search(r'\b[A-G](?:[#b]|m|maj|sus|dim|aug|7)', line):
            warnings.append(f'Chưa đọc được dòng: {line[:100]}. Dùng [C]lời hát hoặc dòng chỉ có hợp âm.')
        elif rows and rows[-1].has_lyrics and WORD_RE.search(line) and not BRACKET_RE.search(line):
            # A wrapped lyric continues the previous phrase without changing chords.
            previous = rows[-1]
            new_weight = previous.weight + len(WORD_RE.findall(line))
            previous.fractions = [f * previous.weight / new_weight for f in previous.fractions]
            previous.weight = new_weight
            previous.source += '\n' + line
    return rows, warnings


def strip_chords(text):
    return BRACKET_RE.sub(lambda m: '' if chord_match(m[1]) else m[0], text)


def melody_lines(text):
    # Keep headings, punctuation, repeats and empty lines in the original text.
    return [(i, line, list(NOTE_PATTERN.finditer(line)))
            for i, line in enumerate(text.split('\n')) if NOTE_PATTERN.search(line)]


def distinct_positions(fractions, count):
    if len(fractions) > count:
        raise ValueError(f'Có {len(fractions)} hợp âm nhưng chỉ {count} nốt. Hãy tách câu hoặc giảm số hợp âm.')
    positions = []
    for j, fraction in enumerate(fractions):
        intended = int(fraction * count + 0.5)
        low = positions[-1] + 1 if positions else 0
        high = count - (len(fractions) - j)
        positions.append(min(high, max(low, intended)))
    return positions


def build_chord_plan(source, melody, shift=0, flats=False, mode='lines', skip=0,
                     loop_unit='line', notes_per_chord=4):
    rows, warnings = parse_chord_source(source)
    if not rows:
        raise ValueError('Chưa tìm thấy hợp âm hợp lệ trong ô 1. Ví dụ: C - Am - Em - G hoặc [C]lời hát.')
    if not melody.strip():
        raise ValueError('Hãy dán cảm âm vào ô 2 hoặc lấy kết quả chuyển tone ở trên.')
    clean = strip_chords(melody)
    lines = melody_lines(clean)
    if not lines:
        raise ValueError('Chưa tìm thấy nốt do/re/mi/fa/sol/la/si trong ô 2.')
    if skip >= len(lines):
        raise ValueError('Số dòng bỏ qua phải ít hơn tổng số dòng cảm âm.')
    active = lines[skip:]
    plan = [{ 'Dòng': line_no + 1, 'Cảm âm': line, 'Hợp âm': '', 'Vị trí nốt': '' }
            for line_no, line, notes in lines]
    mapping = {entry['Dòng'] - 1: entry for entry in plan}
    transposed = [[transpose_chord(c, shift, flats) for c in row.chords] for row in rows]

    def assign(line_no, chords, positions):
        row = mapping[line_no]
        row['Hợp âm'] = ' '.join(chords)
        row['Vị trí nốt'] = ', '.join(str(p + 1) for p in positions)

    if mode == 'lines':
        if len(rows) != len(active):
            warnings.append(f'Có {len(rows)} dòng hợp âm và {len(active)} dòng cảm âm cần ghép. '
                            'Chế độ từng dòng chỉ ghép các cặp tương ứng; phần dư được giữ chưa ghép. '
                            'Có thể chọn Theo vị trí trong lời hoặc sửa cách xuống dòng.')
        for row, chords, (line_no, line, notes) in zip(rows, transposed, active):
            assign(line_no, chords, distinct_positions(row.fractions, len(notes)))
    elif mode == 'lyrics':
        if not any(r.has_lyrics for r in rows):
            warnings.append('Nguồn không có lời: các hợp âm được phân bố đều trên tổng số nốt.')
        total_weight = sum(row.weight for row in rows)
        fractions, chords = [], []
        before = 0
        for row, transformed in zip(rows, transposed):
            fractions.extend((before + f * row.weight) / total_weight for f in row.fractions)
            chords.extend(transformed)
            before += row.weight
        positions = distinct_positions(fractions, sum(len(notes) for _, _, notes in active))
        offset = 0
        for line_no, line, notes in active:
            selected = [(c, p - offset) for c, p in zip(chords, positions) if offset <= p < offset + len(notes)]
            assign(line_no, [c for c, p in selected], [p for c, p in selected])
            offset += len(notes)
        warnings.append('Vị trí được ước lượng theo số từ và số nốt. Các đoạn ngân, luyến, dạo và lặp có thể cần chỉnh lại.')
    elif mode == 'loop':
        sequence = [c for row in transposed for c in row]
        cursor = 0
        if loop_unit == 'line':
            for line_no, line, notes in active:
                assign(line_no, [sequence[cursor % len(sequence)]], [0])
                cursor += 1
        else:
            if notes_per_chord < 1:
                raise ValueError('Số nốt mỗi hợp âm phải lớn hơn 0.')
            total = 0
            for line_no, line, notes in active:
                positions = [p for p in range(len(notes)) if (total + p) % notes_per_chord == 0]
                chords = [sequence[(total + p) // notes_per_chord % len(sequence)] for p in positions]
                assign(line_no, chords, positions)
                total += len(notes)
    else:
        raise ValueError('Chế độ ghép không hợp lệ.')
    if re.search(r'[x×]\s*\d+', clean, re.I):
        warnings.append('Ký hiệu xN được giữ nguyên: phần trong ngoặc lặp cả nốt và hợp âm. '
                        'Nếu mỗi lượt cần hợp âm khác, hãy viết riêng các lượt trước khi ghép.')
    return clean, plan, warnings, transposed


def render_chord_plan(melody, plan):
    lines = melody.split('\n')
    for row in plan:
        idx = int(row['Dòng']) - 1
        chords_text = str(row.get('Hợp âm') or '').strip()
        positions_text = str(row.get('Vị trí nốt') or '').strip()
        if not chords_text and not positions_text:
            continue
        parsed = bare_chords(chords_text)
        if not parsed:
            raise ValueError(f'Dòng {idx + 1}: hợp âm không hợp lệ. Ví dụ: C G Am.')
        chords = parsed[0]
        if not re.fullmatch(r'\d+(?:\s*[,; ]\s*\d+)*', positions_text):
            raise ValueError(f'Dòng {idx + 1}: vị trí phải là số nốt, ví dụ 1, 5, 9.')
        positions = [int(p) for p in re.split(r'[,;\s]+', positions_text)]
        notes = list(NOTE_PATTERN.finditer(lines[idx]))
        if len(positions) != len(chords):
            raise ValueError(f'Dòng {idx + 1}: cần một vị trí cho mỗi hợp âm ({len(chords)} hợp âm).')
        if positions != sorted(set(positions)) or any(p < 1 or p > len(notes) for p in positions):
            raise ValueError(f'Dòng {idx + 1}: vị trí phải tăng dần, không trùng, từ 1 đến {len(notes)}.')
        for chord, position in reversed(list(zip(chords, positions))):
            at = notes[position - 1].start()
            lines[idx] = lines[idx][:at] + '[' + chord + ']' + lines[idx][at:]
    return '\n'.join(lines)


def highlighted_chords(text):
    parts, at = [], 0
    for match in BRACKET_RE.finditer(text):
        if chord_match(match[1]):
            parts.append(html.escape(text[at:match.start()]))
            parts.append('<b style="color:#ffd166">' + html.escape(match[0]) + '</b>')
            at = match.end()
    parts.append(html.escape(text[at:]))
    return ''.join(parts)


# ══════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════
def main():
    st.set_page_config(page_title="Cảm âm & Hợp âm", page_icon="🎹", layout="wide")

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
      <div class="hero-title">🎹 Cảm âm & Hợp âm</div>
      <div class="hero-sub">
        Chuyển tone, ghép hợp âm và chỉnh vị trí đổi hợp âm. <span>Dễ đọc, dễ tập đàn.</span>
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
            st.session_state['converted_text'] = output
            st.session_state['converted_shift'] = shift
            st.session_state['converted_tone'] = tone_values.get(tone_name)
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

    # ── Ghép hợp âm vào cảm âm ─────────────────────────────────
    st.divider()
    st.subheader('🎸 Ghép hợp âm vào cảm âm')
    st.caption('Dán hợp âm vào ô 1, cảm âm đã chuyển tone vào ô 2. App gợi ý vị trí và cho phép chỉnh trước khi sao chép.')

    with st.expander('Hướng dẫn nhập và chọn cách ghép'):
        st.markdown('''
    - **Vòng hợp âm:** `C - Am - Em - G`, `C | Am | F | G` hoặc `(C Am F G) x 2`.
    - **Kèm lời:** `[C]câu hát đầu [G]câu hát sau`. Cũng nhận dòng hợp âm nằm phía trên lời.
    - **Theo từng dòng:** mỗi dòng hợp âm ứng với một dòng cảm âm; hợp âm giữa câu được ước lượng theo vị trí trong lời.
    - **Theo vị trí trong lời:** phân bố hợp âm trên toàn đoạn; phù hợp khi hai ô xuống dòng khác nhau. Chỉ dán cùng một đoạn bài hát ở hai ô.
    - **Lặp vòng hợp âm:** lặp chuỗi theo từng dòng hoặc số nốt bạn chọn. Đây là cách đệm đều, không tự nhận diện nhịp.
    - Bảng chỉnh vị trí đếm nốt từ **1 trên từng dòng**, không đếm dấu phẩy. Ví dụ `C G Am` tại `1, 3, 5`.
    - App không phân tích âm thanh. Văn bản thiếu nhịp/trường độ nên cần nghe và chỉnh lại các điểm đổi hợp âm.
    ''')

    # Plain Vietnamese lyrics keep the demo about alignment rather than source notation.
    SAMPLE_CHORDS = '[G#]Câu hát đầu tiên\n[Fm]Câu hát tiếp theo\n[Cm]Một câu ngắn [D#]và câu sau\n[C#]Những ngày qua [D#]cùng lời ca\n[G#]Cùng nhau [D#]đi qua [Fm]đây'
    SAMPLE_MELODY = 'do2 re2 mi2, mi2\nsol2 re2 do2, sol2\nre2 mi2 mi2 re2 do2 re2\nfa2 fa2 mi2 si do2 re2\nmi2 mi2 sol2 sol2 do2'

    if 'merge_melody' not in st.session_state:
        st.session_state['merge_melody'] = ''
    if 'merge_chords' not in st.session_state:
        st.session_state['merge_chords'] = ''

    button_left, button_right = st.columns(2)
    with button_left:
        if st.button('↓ Lấy cảm âm đã chuyển ở trên', use_container_width=True):
            current = st.session_state.get('converted_text', '')
            if collect_notes(current):
                st.session_state['merge_melody'] = current
                selected_root = st.session_state.get('converted_tone')
                if selected_root is not None:
                    st.session_state['chord_target'] = selected_root
            else:
                st.warning('Phần chuyển tone ở trên chưa có cảm âm hợp lệ.')
    with button_right:
        if st.button('Thử mẫu G# → C', use_container_width=True):
            st.session_state.update(merge_chords=SAMPLE_CHORDS, merge_melody=SAMPLE_MELODY,
                                    chord_source=8, chord_target=0,
                                    chord_transpose_mode='Chọn tone hợp âm gốc → tone cảm âm',
                                    merge_mode='Theo từng dòng', merge_skip=0)

    left, right = st.columns(2)
    with left:
        chord_input = st.text_area('Ô 1 · Vòng hợp âm hoặc lời bài hát có hợp âm',
                                  key='merge_chords', height=260,
                                  placeholder='G# - Fm - Cm - D#\n\nHoặc:\n[G#]Lời bài hát ... [D#]lời tiếp theo')
    with right:
        melody_input = st.text_area('Ô 2 · Cảm âm đã chuyển tone', key='merge_melody', height=260,
                                   placeholder='do2 re2 mi2, mi2\nsol2 re2 do2, sol2\nre2 mi2 mi2, re2 do2 re2')

    trans_mode = st.selectbox('Chuyển tone hợp âm',
        ['Đã cùng tone — giữ nguyên', 'Chọn tone hợp âm gốc → tone cảm âm', 'Dùng số nấc chuyển ở trên'],
        key='chord_transpose_mode')
    chord_shift = 0
    if trans_mode == 'Chọn tone hợp âm gốc → tone cảm âm':
        ts, tt = st.columns(2)
        with ts:
            chord_source = st.selectbox('Tone hợp âm gốc', list(range(12)), key='chord_source',
                                        format_func=lambda n: f'{CHORD_NAMES_SHARP[n]} / {TONE_NAME_BY_SEMITONE[n]}')
        with tt:
            chord_target = st.selectbox('Tone của cảm âm ở ô 2', list(range(12)), key='chord_target',
                                        format_func=lambda n: f'{CHORD_NAMES_SHARP[n]} / {TONE_NAME_BY_SEMITONE[n]}')
        chord_shift = shortest_shift(chord_source, chord_target)
    elif trans_mode == 'Dùng số nấc chuyển ở trên':
        chord_shift = st.session_state.get('converted_shift', 0)
        st.caption('Dùng khi hợp âm gốc và cảm âm gốc cùng tone. Cảm âm trong ô 2 không bị chuyển lần nữa.')

    cfg1, cfg2 = st.columns([2, 1])
    with cfg1:
        merge_mode = st.selectbox('Cách ghép', ['Theo từng dòng', 'Theo vị trí trong lời', 'Lặp vòng hợp âm'], key='merge_mode')
    with cfg2:
        use_flats = st.checkbox('Viết hợp âm bằng dấu giáng (b)', value=False)
        skip_lines = st.number_input('Bỏ qua số dòng cảm âm đầu (đoạn dạo)', min_value=0, step=1, key='merge_skip')
    loop_unit, notes_per_chord = 'line', 4
    if merge_mode == 'Lặp vòng hợp âm':
        unit = st.radio('Đổi hợp âm theo', ['Mỗi dòng một hợp âm', 'Mỗi nhóm nốt một hợp âm'], horizontal=True)
        if unit == 'Mỗi nhóm nốt một hợp âm':
            loop_unit = 'notes'
            notes_per_chord = st.number_input('Số nốt mỗi hợp âm', min_value=1, max_value=64, value=4, step=1)

    st.caption(f'Hợp âm: {shift_label(chord_shift)}. Cảm âm ở ô 2 được giữ nguyên cao độ.')
    mode_key = {'Theo từng dòng': 'lines', 'Theo vị trí trong lời': 'lyrics', 'Lặp vòng hợp âm': 'loop'}[merge_mode]
    fingerprint = hashlib.sha256(json.dumps([chord_input, melody_input, chord_shift, use_flats,
                        mode_key, skip_lines, loop_unit, notes_per_chord], ensure_ascii=False).encode()).hexdigest()
    if st.button('✨ Tạo bản ghép hợp âm + cảm âm', type='primary', use_container_width=True):
        try:
            clean, plan, notices, chord_rows = build_chord_plan(
                chord_input, melody_input, chord_shift, use_flats, mode_key, int(skip_lines),
                loop_unit, int(notes_per_chord))
            st.session_state['merge_result'] = dict(fingerprint=fingerprint, clean=clean, plan=plan,
                                                   notices=notices, chord_rows=chord_rows)
            st.session_state['merge_generation'] = st.session_state.get('merge_generation', 0) + 1
        except ValueError as exc:
            st.session_state.pop('merge_result', None)
            st.error(str(exc))

    saved = st.session_state.get('merge_result')
    if saved and saved['fingerprint'] != fingerprint:
        st.info('Đầu vào hoặc cách ghép đã thay đổi. Bấm Tạo bản ghép để cập nhật kết quả.')
    elif saved:
        for notice in saved['notices']:
            st.warning(notice)
        with st.expander('Hợp âm đã nhận diện và chuyển tone'):
            st.code('\n'.join(' '.join('[' + c + ']' for c in row) for row in saved['chord_rows']), language='text')
        st.markdown('**Chỉnh vị trí đổi hợp âm**')
        st.caption('Chỉnh hai cột Hợp âm và Vị trí nốt. Ví dụ C G Am / 1, 3, 5. Dòng trống hợp âm tiếp tục giữ hợp âm trước đó.')
        edited_plan = st.data_editor(saved['plan'],
            key=f"chord_editor_{st.session_state.get('merge_generation', 0)}",
            disabled=['Dòng', 'Cảm âm'], hide_index=True, use_container_width=True,
            column_config={
                'Dòng': st.column_config.NumberColumn(width='small'),
                'Cảm âm': st.column_config.TextColumn(width='large'),
                'Hợp âm': st.column_config.TextColumn(width='medium'),
                'Vị trí nốt': st.column_config.TextColumn(width='medium'),
            })
        try:
            merged = render_chord_plan(saved['clean'], edited_plan)
            st.markdown('**Kết quả: cảm âm + hợp âm xen kẽ**')
            st.markdown('<div class="result-card">' + highlighted_chords(merged) + '</div>', unsafe_allow_html=True)
            st.code(merged, language='text')
            st.download_button('↓ Tải cảm âm kèm hợp âm (.txt)', data=merged.encode('utf-8'),
                               file_name='cam_am_hop_am.txt', mime='text/plain; charset=utf-8')
            st.caption('Sao chép bằng nút ở góc khung văn bản. Hợp âm có hiệu lực từ nốt ngay sau ký hiệu [C] đến hợp âm kế tiếp.')
        except ValueError as exc:
            st.error(str(exc))

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


if __name__ == "__main__":
    main()
