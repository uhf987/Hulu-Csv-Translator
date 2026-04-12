# CSV Translator 🌐

A desktop application for translating CSV files using **Google's TranslateGemma:12b** model running locally via [Ollama](https://ollama.com). Translate between 75+ languages without sending your data to any external server — fully offline and private.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue) ![Ollama](https://img.shields.io/badge/Ollama-TranslateGemma%3A12b-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Features

- 🌍 **75+ languages** powered by TranslateGemma:12b
- 🔒 **Fully local** — no API keys, no internet required after setup
- 🛡️ **Protect patterns** — preserve game codes, placeholders, tags from translation
- 📊 **Column selector** — choose exactly which columns to translate
- 📺 **Live log** — watch each cell being translated in real time
- ⏱️ **Progress bar** with estimated time remaining
- ⇄ **Swap languages** with one click
- ⏹️ **Stop button** — safely cancel mid-translation
- 🖥️ **GUI** and **CLI** support

---

## Screenshots

> GUI with language selection, protect patterns, and live translation log.

---

## Requirements

### 1. Python 3.8+
Download from https://www.python.org/downloads/

### 2. Ollama
Download and install from https://ollama.com

Then pull the TranslateGemma model:
```bash
ollama pull translategemma:12b
```

> ⚠️ The model is ~8GB. Download only needs to happen once.

### 3. Python dependencies
```bash
pip install requests
```

---

## Installation

```bash
git clone https://github.com/your-username/csv-translator.git
cd csv-translator
pip install requests
```

Make sure Ollama is running:
```bash
ollama serve
```

---

## Usage

### GUI (recommended)

```bash
python csv_translator_gui.py
```

**Steps:**
1. **Input CSV** — browse and select your source file
2. **Output CSV** — choose where to save the result
3. **Source / Target** — pick languages from the dropdowns
4. **Protect Patterns** — check which markers should be skipped (see below)
5. **Columns to translate** — enter column numbers (e.g. `2` or `1 3 5`). Leave empty to translate all columns
6. Click **▶ Start Translation**

---

### CLI

```bash
python csv_translator.py input.csv output.csv
```

**Options:**

| Option | Description | Example |
|--------|-------------|---------|
| `--source` | Source language | `--source English` |
| `--target` | Target language | `--target Turkish` |
| `--columns` | Columns to translate (1-based) | `--columns 2` or `--columns 1 3 5` |
| `--protect` | Protect pattern name(s) | `--protect Pipe Curly` |
| `--model` | Ollama model name | `--model translategemma:12b` |
| `--delimiter` | CSV delimiter | `--delimiter ";"` |
| `--no-header` | First row is data, not header | `--no-header` |
| `-v` | Verbose output per cell | `-v` |

**Examples:**
```bash
# Translate column 2 from English to Turkish
python csv_translator.py items.csv items_tr.csv --columns 2

# Translate columns 1 and 3, semicolon-delimited file
python csv_translator.py data.csv data_tr.csv --columns 1 3 --delimiter ";"

# French to Japanese, protect curly braces and square brackets
python csv_translator.py ui.csv ui_ja.csv --source French --target Japanese --protect Curly Square

# Translate all columns, no header row
python csv_translator.py raw.csv raw_tr.csv --no-header
```

---

## Protect Patterns

Protect patterns let you mark text that should **never be translated** — useful for game codes, UI variables, HTML tags, format strings, etc.

You can enable multiple patterns at the same time.

| Pattern name | Syntax | Example |
|---|---|---|
| **Pipe** | `\|text\|` | `\|ITEM_001\|` |
| **Curly** | `{text}` | `{player_name}` |
| **Square** | `[text]` | `[QUEST_ID]` |
| **Angle** | `<text>` | `<color=red>` |
| **Double curly** | `{{text}}` | `{{variable}}` |
| **Percent** | `%text%` | `%score%` |
| **Dollar** | `$text$` | `$reward$` |
| **Hash** | `#text#` | `#NPC_42#` |

**Example cell:**

| Original | Protected | Result |
|---|---|---|
| `Talk to \|NPC_001\| to get your {reward}` | Pipe + Curly | `\|NPC_001\| ile konuş ve {reward} al` |
| `<b>Hello</b> world` | Angle | `<b>Merhaba</b> dünya` |

---

## Supported Languages

<details>
<summary>Click to expand all 75 languages</summary>

Afrikaans, Albanian, Amharic, Arabic, Armenian, Azerbaijani, Bengali, Bulgarian, Burmese, Catalan, Chinese (Simplified), Chinese (Traditional), Croatian, Czech, Danish, Dutch, English, Filipino, Finnish, French, Galician, Georgian, German, Greek, Gujarati, Hausa, Hebrew, Hindi, Hungarian, Igbo, Indonesian, Italian, Japanese, Kannada, Kazakh, Khmer, Korean, Kyrgyz, Lao, Latvian, Lithuanian, Macedonian, Malay, Malayalam, Marathi, Mongolian, Nepali, Norwegian, Persian, Polish, Portuguese, Punjabi, Romanian, Russian, Serbian, Sindhi, Sinhala, Slovak, Slovenian, Somali, Spanish, Swahili, Swedish, Tagalog, Tajik, Tamil, Telugu, Thai, Turkish, Turkmen, Ukrainian, Urdu, Uyghur, Uzbek, Vietnamese, Yoruba, Zulu

</details>

---

## Build as EXE (Windows)

Create a standalone executable with PyInstaller:

```bash
pip install pyinstaller
python -m PyInstaller --onefile --noconsole --name "CSV_Translator" csv_translator_gui.py
```

The executable will be at `dist/CSV_Translator.exe`.

> **Note:** `csv_translator.py` must be in the same folder as the `.exe`.

---

## Project Structure

```
csv-translator/
├── csv_translator.py       # Core translation engine + CLI
├── csv_translator_gui.py   # Desktop GUI (tkinter)
└── README.md
```

---

## How It Works

1. The CSV is parsed row by row
2. For each selected cell, protect patterns are extracted and replaced with internal placeholders
3. The remaining text is sent to TranslateGemma:12b running locally via Ollama
4. The translated result is returned and placeholders are restored to their original values
5. The final CSV is written with the same structure as the input

---

## Troubleshooting

**"Ollama NOT Connected" shown in the app**
Make sure Ollama is running:
```bash
ollama serve
```

**Translation is slow**
TranslateGemma:12b processes one cell at a time. Speed depends on your hardware. A GPU is strongly recommended. For smaller/faster results try `translategemma:4b`.

**Wrong column being translated**
Columns are **1-based** — column `1` is the first column, `2` is the second, etc.

**Output file looks garbled**
Make sure your input CSV is saved as **UTF-8**. Re-save it from Excel using "Save As → CSV UTF-8".

---

## License

MIT — free to use, modify, and distribute.

---

## Acknowledgements

- [Google TranslateGemma](https://huggingface.co/google/translategemma-12b-it) — translation model
- [Ollama](https://ollama.com) — local model serving
