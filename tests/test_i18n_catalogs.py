"""Language catalog checks. No FastAPI needed: pure file checks."""
import json
import re
from pathlib import Path

I18N = Path(__file__).resolve().parents[1] / "static" / "i18n"
LANGS = json.loads((I18N / "languages.json").read_text(encoding="utf-8"))
EN = json.loads((I18N / "en.json").read_text(encoding="utf-8"))
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def test_six_languages_in_native_script():
    assert [l["code"] for l in LANGS] == ["ml", "hi", "kn", "ta", "te", "en"]
    assert all(l["native"] and l["english"] for l in LANGS)


def test_every_language_has_every_key_and_placeholders():
    for lang in LANGS:
        data = json.loads((I18N / f"{lang['code']}.json").read_text(encoding="utf-8"))
        assert set(data) == set(EN), (lang["code"], set(EN) ^ set(data))
        for key, text in data.items():
            assert text.strip(), (lang["code"], key)
            assert set(PLACEHOLDER.findall(text)) == set(PLACEHOLDER.findall(EN[key])), (lang["code"], key)


def test_non_english_catalogs_are_actually_translated():
    script = {"ml": "\u0d00-\u0d7f", "hi": "\u0900-\u097f", "kn": "\u0c80-\u0cff", "ta": "\u0b80-\u0bff", "te": "\u0c00-\u0c7f"}
    for code, block in script.items():
        data = json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))
        in_script = sum(1 for v in data.values() if re.search(f"[{block}]", v))
        assert in_script / len(data) > 0.95, code


def test_dashboard_html_i18n_keys_exist_in_english_catalog():
    html = (Path(__file__).resolve().parents[1] / "frontend" / "dashboard-v2.html").read_text(encoding="utf-8")
    used = set(re.findall(r'data-i18n(?:-placeholder)?="(\w+)"', html))
    assert used - set(EN) == set()
