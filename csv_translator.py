"""
CSV Translator - Multi-language translation via Ollama TranslateGemma:12b
Usage: python csv_translator.py input.csv output.csv
Text matching any active protect pattern is preserved and not translated.
"""

import csv
import re
import sys
import time
import argparse
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "translategemma:12b"

# Built-in protect patterns - name: (regex, example)
PROTECT_PATTERNS = {
    "Pipe":         (r"\|[^|]*\|",     "|text|"),
    "Curly":        (r"\{[^}]*\}",     "{text}"),
    "Square":       (r"\[[^\]]*\]",    "[text]"),
    "Angle":        (r"<[^>]*>",       "<text>"),
    "Double curly": (r"\{\{[^}]*\}\}", "{{text}}"),
    "Percent":      (r"%[^%]*%",       "%text%"),
    "Dollar":       (r"\$[^$]*\$",     "$text$"),
    "Hash":         (r"#[^#]*#",       "#text#"),
}

# Active patterns (list of regex strings) - default: Pipe only
ACTIVE_PATTERNS = [PROTECT_PATTERNS["Pipe"][0]]


def set_active_patterns(names):
    """Set active patterns by name list, e.g. ['Pipe', 'Curly']"""
    global ACTIVE_PATTERNS
    ACTIVE_PATTERNS = []
    for name in names:
        if name in PROTECT_PATTERNS:
            ACTIVE_PATTERNS.append(PROTECT_PATTERNS[name][0])


def build_combined_pattern():
    """Combine all active patterns into one regex."""
    if not ACTIVE_PATTERNS:
        return None
    return "|".join("(?:" + p + ")" for p in ACTIVE_PATTERNS)


def build_prompt(text, src_name, src_code, tgt_name, tgt_code):
    """Official TranslateGemma prompt format."""
    has_placeholders = "__PROTECTED_" in text
    placeholder_instruction = (
        "The text contains placeholders in the format __PROTECTED_N__ (where N is a number). "
        "These are protected tokens that must be copied into the translation exactly as they appear, "
        "without any modification, translation, or replacement. "
    ) if has_placeholders else ""
    return (
        "You are a professional " + src_name + " (" + src_code + ") to "
        + tgt_name + " (" + tgt_code + ") translator. "
        "Your goal is to accurately convey the meaning and nuances of the original "
        + src_name + " text while adhering to " + tgt_name + " grammar, vocabulary, "
        "and cultural sensitivities. Produce only the " + tgt_name + " translation, "
        "without any additional explanations or commentary. "
        + placeholder_instruction
        + "Please translate the following " + src_name + " text into " + tgt_name + ":\n\n\n"
        + text
    )


def extract_protected_segments(text):
    """Replace all protected segments with placeholders.

    Always-protected (regardless of user settings):
      - Literal escape sequences: \\r\\n, \\n, \\r, \\t  (game engine tokens)
      - HTML/markup tags: <i>, </i>, <s>, </s>, <b>, <br/>, etc.

    Then user-configured patterns (Pipe, Curly, etc.) are applied on top.
    """
    placeholders = {}
    counter = [0]

    def make_placeholder(value):
        key = "__PROTECTED_" + str(counter[0]) + "__"
        placeholders[key] = value
        counter[0] += 1
        return key

    # Step 1: Always protect literal escape sequences (\\r\\n before \\n).
    ESCAPE_RE = re.compile(r'\\r\\n|\\n|\\r|\\t')
    text = ESCAPE_RE.sub(lambda m: make_placeholder(m.group(0)), text)

    # Step 2: Always protect HTML/markup tags like <i>, </b>, <br/>, etc.
    HTML_TAG_RE = re.compile(r'</?[a-zA-Z][^>]*?/?>')
    text = HTML_TAG_RE.sub(lambda m: make_placeholder(m.group(0)), text)

    # Step 3: Apply user-configured protect patterns (Pipe, Curly, etc.)
    pattern = build_combined_pattern()
    if pattern:
        try:
            text = re.sub(pattern, lambda m: make_placeholder(m.group(0)), text)
        except re.error:
            pass

    return text, placeholders


def restore_protected_segments(text, placeholders):
    for key, value in placeholders.items():
        text = text.replace(key, value)
    return text


def validate_and_fix(original, translated, placeholders):
    """
    Ceviri sonrasini dogrular ve duzeltir:
    1. Ceviride kalan __PROTECTED_X__ leakleri restore eder veya siler.
    2. Orijinalde olan ama ceviride eksik pipe/HTML taglari sona eklenir.
    3. Escape token sayisi tutmuyorsa None doner (caller orijinali kullanir).
    """
    PIPE_RE     = re.compile(r'\|[^|]*\|')
    HTML_TAG_RE = re.compile(r'</?[a-zA-Z][^>]*?/?>')
    ESCAPE_RE   = re.compile(r'\\r\\n|\\n|\\r|\\t')

    # 1. Leak: ceviride hala __PROTECTED_X__ varsa restore et veya sil
    for key in re.findall(r'__PROTECTED_\d+__', translated):
        if key in placeholders:
            translated = translated.replace(key, placeholders[key])
        else:
            translated = translated.replace(key, '')

    # 2. Pipe token kontrolu
    orig_pipes    = PIPE_RE.findall(original)
    tr_pipes      = PIPE_RE.findall(translated)
    missing_pipes = [p for p in orig_pipes if p not in tr_pipes]
    if missing_pipes:
        if len(missing_pipes) > max(1, len(orig_pipes) / 2):
            return None
        translated = translated.rstrip() + ' ' + ' '.join(missing_pipes)

    # 3. HTML tag kontrolu
    orig_tags    = HTML_TAG_RE.findall(original)
    tr_tags      = HTML_TAG_RE.findall(translated)
    missing_tags = [t for t in orig_tags if t not in tr_tags]
    if missing_tags:
        if len(missing_tags) > max(1, len(orig_tags) / 2):
            return None
        translated = translated.rstrip() + ''.join(missing_tags)

    # 4. Escape token sayisi eslesme kontrolu
    orig_esc = ESCAPE_RE.findall(original)
    tr_esc   = ESCAPE_RE.findall(translated)
    if len(orig_esc) != len(tr_esc):
        return None

    return translated.strip()


def translate_cell(text, src_name="English", src_code="en", tgt_name="Turkish", tgt_code="tr", verbose=False):
    global _stop_flag
    if _stop_flag:
        return text

    text = text.strip()
    if not text:
        return text

    cleaned, placeholders = extract_protected_segments(text)

    # Tum icerik korumali segmentlere ait ise cevrilecek metin yok, orijinali dondur
    translatable = re.sub(r"__PROTECTED_\d+__", "", cleaned).strip()
    if not cleaned.strip() or re.fullmatch(r"[\s_]*", cleaned) or not translatable:
        return text

    prompt = build_prompt(cleaned, src_name, src_code, tgt_name, tgt_code)

    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 180
    translated = None
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "top_k": 64, "top_p": 0.95},
                },
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            translated = response.json().get("response", "").strip()
            last_error = None
            break
        except requests.exceptions.ConnectionError:
            return "[ERROR: Could not connect to Ollama]"
        except requests.exceptions.Timeout:
            last_error = "Timeout after " + str(TIMEOUT_SECONDS) + "s (attempt " + str(attempt) + "/" + str(MAX_RETRIES) + ")"
            if verbose:
                print("  [RETRY] " + last_error)
            time.sleep(5)
        except Exception as e:
            last_error = str(e)
            break

    if last_error:
        return "[ERROR: " + last_error + "]"

    if verbose:
        print("  " + src_name + ": " + cleaned[:60])
        print("  " + tgt_name + ": " + translated[:60])

    # Restore et
    restored = restore_protected_segments(translated, placeholders)

    # Dogrula ve duzelt
    fixed = validate_and_fix(text, restored, placeholders)
    if fixed is None:
        if verbose:
            print("  [VALIDATION FAILED] Yeniden ceviri gerekiyor: " + text[:60])
        return "[RETRANSLATE: " + text + "]"

    return fixed



# Supported languages: Display name -> (English name for prompt, ISO code)
LANGUAGES = {
    "Afrikaans":             ("Afrikaans",            "af"),
    "Albanian":              ("Albanian",              "sq"),
    "Amharic":               ("Amharic",               "am"),
    "Arabic":                ("Arabic",                "ar"),
    "Armenian":              ("Armenian",              "hy"),
    "Azerbaijani":           ("Azerbaijani",           "az"),
    "Bengali":               ("Bengali",               "bn"),
    "Bulgarian":             ("Bulgarian",             "bg"),
    "Burmese":               ("Burmese",               "my"),
    "Catalan":               ("Catalan",               "ca"),
    "Chinese (Simplified)":  ("Chinese Simplified",    "zh"),
    "Chinese (Traditional)": ("Chinese Traditional",   "zh-TW"),
    "Croatian":              ("Croatian",              "hr"),
    "Czech":                 ("Czech",                 "cs"),
    "Danish":                ("Danish",                "da"),
    "Dutch":                 ("Dutch",                 "nl"),
    "English":               ("English",               "en"),
    "Filipino":              ("Filipino",              "fil"),
    "Finnish":               ("Finnish",               "fi"),
    "French":                ("French",                "fr"),
    "Galician":              ("Galician",              "gl"),
    "Georgian":              ("Georgian",              "ka"),
    "German":                ("German",                "de"),
    "Greek":                 ("Greek",                 "el"),
    "Gujarati":              ("Gujarati",              "gu"),
    "Hausa":                 ("Hausa",                 "ha"),
    "Hebrew":                ("Hebrew",                "he"),
    "Hindi":                 ("Hindi",                 "hi"),
    "Hungarian":             ("Hungarian",             "hu"),
    "Igbo":                  ("Igbo",                  "ig"),
    "Indonesian":            ("Indonesian",            "id"),
    "Italian":               ("Italian",               "it"),
    "Japanese":              ("Japanese",              "ja"),
    "Kannada":               ("Kannada",               "kn"),
    "Kazakh":                ("Kazakh",                "kk"),
    "Khmer":                 ("Khmer",                 "km"),
    "Korean":                ("Korean",                "ko"),
    "Kyrgyz":                ("Kyrgyz",                "ky"),
    "Lao":                   ("Lao",                   "lo"),
    "Latvian":               ("Latvian",               "lv"),
    "Lithuanian":            ("Lithuanian",            "lt"),
    "Macedonian":            ("Macedonian",            "mk"),
    "Malay":                 ("Malay",                 "ms"),
    "Malayalam":             ("Malayalam",             "ml"),
    "Marathi":               ("Marathi",               "mr"),
    "Mongolian":             ("Mongolian",             "mn"),
    "Nepali":                ("Nepali",                "ne"),
    "Norwegian":             ("Norwegian",             "no"),
    "Persian":               ("Persian",               "fa"),
    "Polish":                ("Polish",                "pl"),
    "Portuguese":            ("Portuguese",            "pt"),
    "Punjabi":               ("Punjabi",               "pa"),
    "Romanian":              ("Romanian",              "ro"),
    "Russian":               ("Russian",               "ru"),
    "Serbian":               ("Serbian",               "sr"),
    "Sindhi":                ("Sindhi",                "sd"),
    "Sinhala":               ("Sinhala",               "si"),
    "Slovak":                ("Slovak",                "sk"),
    "Slovenian":             ("Slovenian",             "sl"),
    "Somali":                ("Somali",                "so"),
    "Spanish":               ("Spanish",               "es"),
    "Swahili":               ("Swahili",               "sw"),
    "Swedish":               ("Swedish",               "sv"),
    "Tagalog":               ("Tagalog",               "tl"),
    "Tajik":                 ("Tajik",                 "tg"),
    "Tamil":                 ("Tamil",                 "ta"),
    "Telugu":                ("Telugu",                "te"),
    "Thai":                  ("Thai",                  "th"),
    "Turkish":               ("Turkish",               "tr"),
    "Turkmen":               ("Turkmen",               "tk"),
    "Ukrainian":             ("Ukrainian",             "uk"),
    "Urdu":                  ("Urdu",                  "ur"),
    "Uyghur":                ("Uyghur",                "ug"),
    "Uzbek":                 ("Uzbek",                 "uz"),
    "Vietnamese":            ("Vietnamese",            "vi"),
    "Yoruba":                ("Yoruba",                "yo"),
    "Zulu":                  ("Zulu",                  "zu"),
}

_stop_flag = False


def set_stop():
    global _stop_flag
    _stop_flag = True


def reset_stop():
    global _stop_flag
    _stop_flag = False


def translate_csv(
    input_path,
    output_path,
    skip_header=True,
    columns=None,
    verbose=False,
    delimiter=",",
    source_lang="English",
    target_lang="Turkish",
    active_pattern_names=None,
    progress_callback=None,
    log_callback=None,
):
    global _stop_flag
    reset_stop()

    if active_pattern_names is not None:
        set_active_patterns(active_pattern_names)

    src_name, src_code = LANGUAGES.get(source_lang, ("English", "en"))
    tgt_name, tgt_code = LANGUAGES.get(target_lang, ("Turkish", "tr"))

    with open(input_path, newline="", encoding="utf-8") as f_in:
        reader = csv.reader(f_in, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        if log_callback:
            log_callback("File is empty.")
        return

    header = rows[0] if skip_header else None
    data_rows = rows[1:] if skip_header else rows
    total = len(data_rows)
    num_cols = len(rows[0]) if rows else 0

    if columns is not None:
        col_indices = set(columns)
    else:
        col_indices = set(range(num_cols))

    translated_rows = []
    start = time.time()

    for i, row in enumerate(data_rows, 1):
        if _stop_flag:
            if log_callback:
                log_callback("[STOPPED] Translation cancelled.")
            break

        new_row = []
        for j, cell in enumerate(row):
            if _stop_flag:
                new_row.append(cell)
                continue
            if j in col_indices:
                if log_callback:
                    preview = cell[:50].replace("\n", " ")
                    log_callback("[" + str(i) + "/" + str(total) + "] Col " + str(j + 1) + ": " + preview)
                translated = translate_cell(
                    cell,
                    src_name=src_name, src_code=src_code,
                    tgt_name=tgt_name, tgt_code=tgt_code,
                    verbose=verbose,
                )
                if log_callback and not _stop_flag:
                    log_callback("  -> " + translated[:60].replace("\n", " "))
                new_row.append(translated)
            else:
                new_row.append(cell)

        translated_rows.append(new_row)

        if progress_callback:
            elapsed = time.time() - start
            avg = elapsed / i
            remaining = avg * (total - i)
            progress_callback(i, total, int(remaining))

    if not _stop_flag:
        with open(output_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.writer(f_out, delimiter=delimiter)
            if header:
                writer.writerow(header)
            writer.writerows(translated_rows)

        elapsed = round(time.time() - start, 1)
        if log_callback:
            log_callback("")
            log_callback("DONE -> " + output_path)
            log_callback("Time: " + str(elapsed) + "s | " + str(total) + " rows")


def main():
    global MODEL

    parser = argparse.ArgumentParser(description="Translate a CSV file using Ollama TranslateGemma.")
    parser.add_argument("input", help="Input CSV file")
    parser.add_argument("output", help="Output CSV file")
    parser.add_argument("--no-header", action="store_true", help="Treat first row as data, not header")
    parser.add_argument("--columns", type=int, nargs="+", help="Column numbers to translate (1-based). Default: all")
    parser.add_argument("--model", default=MODEL, help="Ollama model name")
    parser.add_argument("--delimiter", default=",", help="CSV delimiter (default: comma)")
    parser.add_argument("--source", default="English", help="Source language (e.g. English)")
    parser.add_argument("--target", default="Turkish", help="Target language (e.g. Turkish)")
    parser.add_argument(
        "--protect", nargs="+",
        default=["Pipe"],
        help="Protect pattern name(s): Pipe, Curly, Square, Angle, 'Double curly', Percent, Dollar, Hash"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output per cell")

    args = parser.parse_args()
    MODEL = args.model

    translate_csv(
        input_path=args.input,
        output_path=args.output,
        skip_header=not args.no_header,
        columns=args.columns,
        verbose=args.verbose,
        delimiter=args.delimiter,
        source_lang=args.source,
        target_lang=args.target,
        active_pattern_names=args.protect,
        log_callback=print,
    )


if __name__ == "__main__":
    main()
