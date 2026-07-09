#!/usr/bin/env python3
"""Generate static localized legal pages from the canonical French pages."""

from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "_data" / "legal_pages_cache.json"
LOCALES = {
    "fr": ("Français", "fr"), "en": ("English", "en"),
    "de": ("Deutsch", "de"), "es": ("Español", "es"),
    "it": ("Italiano", "it"), "pt-BR": ("Português (Brasil)", "pt"),
    "pt-PT": ("Português (Portugal)", "pt"), "ja": ("日本語", "ja"),
    "ko": ("한국어", "ko"), "nl": ("Nederlands", "nl"),
    "sv": ("Svenska", "sv"), "da": ("Dansk", "da"),
    "nb": ("Norsk bokmål", "nb"), "pl": ("Polski", "pl"),
    "cs": ("Čeština", "cs"), "sk": ("Slovenčina", "sk"),
    "sl": ("Slovenščina", "sl"), "hr": ("Hrvatski", "hr"),
    "hu": ("Magyar", "hu"), "ro": ("Română", "ro"),
    "bg": ("Български", "bg"), "el": ("Ελληνικά", "el"),
    "fi": ("Suomi", "fi"), "et": ("Eesti", "et"),
    "lv": ("Latviešu", "lv"), "lt": ("Lietuvių", "lt"),
    "ga": ("Gaeilge", "ga"), "mt": ("Malti", "mt"),
    "is": ("Íslenska", "is"), "uk": ("Українська", "uk"),
    "tr": ("Türkçe", "tr"), "ca": ("Català", "ca"),
    "zh-Hans": ("简体中文", "zh-Hans"), "zh-Hant": ("繁體中文", "zh-Hant"),
    "hi": ("हिन्दी", "hi"), "en-GB": ("English (UK)", "en"),
    "es-419": ("Español (Latinoamérica)", "es"),
}


def translate_document(source: str, target: str, cache: dict, key: str) -> str:
    if key not in cache or target in {"hr", "mt", "is"}:
        if target in {"hr", "mt", "is"}:
            cache[key] = translate_with_mymemory(source, target)
        else:
            cache[key] = translate_with_libre(source, target)
            CACHE.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    result = cache[key]
    result = re.sub(r'<html lang="[^"]+">', f'<html lang="{key.split(":")[1]}">', result, count=1)
    result = re.sub(r'data-locale="[^"]+"', f'data-locale="{key.split(":")[1]}"', result, count=1)
    return result.rstrip() + "\n"


def translate_with_libre(source: str, target: str) -> str:
    article_match = re.search(r"(<article\b.*?</article>)", source, re.DOTALL)
    if not article_match:
        raise RuntimeError("article not found")
    article = article_match.group(1)
    texts = []
    for match in re.finditer(r">([^<>]+)<", article):
        text = match.group(1).strip()
        if text and text not in texts and text not in {
            "devbrindy@gmail.com", "2026-07-09", "1.0",
        }:
            texts.append(text)

    translations = {}
    batches, current = [], []
    for text in texts:
        candidate = "".join(
            f'<span data-bagolisto="{index}">{html.escape(value)}</span>'
            for index, value in enumerate(current + [text])
        )
        if current and len(candidate) > 3000:
            batches.append(current)
            current = [text]
        else:
            current.append(text)
    if current:
        batches.append(current)

    for batch in batches:
        payload_html = "<div>" + "".join(
            f'<span data-bagolisto="{index}">{html.escape(value)}</span>'
            for index, value in enumerate(batch)
        ) + "</div>"
        data = json.dumps({
            "q": payload_html,
            "source": "fr",
            "target": target,
            "format": "html",
        }).encode()
        request = urllib.request.Request(
            "https://translate.fedilab.app/translate",
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Bagolisto legal localization generator",
            },
        )
        for attempt in range(5):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    translated = json.loads(response.read().decode())["translatedText"]
                parts = re.findall(
                    r'<span data-bagolisto="\d+">(.*?)</span>',
                    translated,
                    re.DOTALL,
                )
                if len(parts) != len(batch):
                    raise RuntimeError("translation delimiter mismatch")
                translations.update(
                    (original, html.unescape(value.strip()))
                    for original, value in zip(batch, parts)
                )
                break
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(3 * (attempt + 1))

    for original in sorted(translations, key=len, reverse=True):
        source = source.replace(original, translations[original])
    return source


def translate_with_mymemory(source: str, target: str) -> str:
    def replace(match: re.Match) -> str:
        prefix, text, suffix = match.groups()
        if not text.strip():
            return match.group(0)
        query = urllib.parse.urlencode({
            "q": text.strip(), "langpair": f"fr|{target}",
            "de": "devbrindy@gmail.com",
        })
        with urllib.request.urlopen(
            f"https://api.mymemory.translated.net/get?{query}", timeout=60
        ) as response:
            translated = json.loads(response.read().decode())
        if translated.get("responseStatus") != 200:
            raise RuntimeError(translated.get("responseDetails"))
        return prefix + translated["responseData"]["translatedText"] + suffix

    return re.sub(
        r"(<(?:a|h1|h2|p|title|strong)[^>]*>)([^<>]+)(</(?:a|h1|h2|p|title|strong)>)",
        replace,
        source,
    )


def main() -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    for document in ("privacy-policy", "terms"):
        canonical = (ROOT / document / "index.html").read_text(encoding="utf-8")
        for locale, (_, target) in LOCALES.items():
            if locale == "fr":
                continue
            print(f"{document}: {locale}")
            output = ROOT / document / locale / "index.html"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                translate_document(
                    canonical, target, cache, f"{document}:{locale}"
                ),
                encoding="utf-8",
                newline="\n",
            )
            time.sleep(1.5)


if __name__ == "__main__":
    main()
