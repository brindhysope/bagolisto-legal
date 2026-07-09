#!/usr/bin/env python3
"""Validate the 37 static legal localizations."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("fr","en","de","es","it","pt-BR","pt-PT","ja","ko","nl","sv","da","nb","pl","cs","sk","sl","hr","hu","ro","bg","el","fi","et","lv","lt","ga","mt","is","uk","tr","ca","zh-Hans","zh-Hant","hi","en-GB","es-419")
EXPECTED = {"privacy-policy": 12, "terms": 6}


def localized_path(document: str, locale: str) -> str:
    if locale == "fr":
        return f"/bagolisto-legal/{document}/"
    return f"/bagolisto-legal/{document}/{locale}/"


def main() -> None:
    errors = []
    for document, count in EXPECTED.items():
        canonical = (ROOT / document / "index.html").read_text(encoding="utf-8")
        canonical_sections = re.findall(
            r'<section data-section="\d+">.*?<p>(.*?)</p></section>',
            canonical,
            re.DOTALL,
        )
        other_document = "terms" if document == "privacy-policy" else "privacy-policy"
        for locale in LOCALES:
            path = ROOT / document / ("index.html" if locale == "fr" else f"{locale}/index.html")
            if not path.exists():
                errors.append(f"absent: {path.relative_to(ROOT)}")
                continue
            text = path.read_text(encoding="utf-8")
            checks = {
                "locale": f'data-locale="{locale}"' in text,
                "version": 'data-version="1.0"' in text,
                "date": 'data-effective-date="2026-07-09"' in text,
                "sections": len(re.findall(r"<section data-section=", text)) == count,
                "contact": text.count("devbrindy@gmail.com") >= 2,
                "prévalence française": 'data-rule="french-prevails"' in text,
                "HTML": text.startswith("<!doctype html>") and text.rstrip().endswith("</html>"),
                "navigation mobile langues": '<details><summary>Langues / Languages</summary><div class="language-links">' in text,
                "lien interne localisé": f'href="{localized_path(other_document, locale)}"' in text,
            }
            for label, ok in checks.items():
                if not ok:
                    errors.append(f"{path.relative_to(ROOT)}: {label}")
            if locale != "fr":
                localized_sections = re.findall(
                    r'<section data-section="\d+">.*?<p>(.*?)</p></section>',
                    text,
                    re.DOTALL,
                )
                if any(
                    localized == french
                    for localized, french in zip(
                        localized_sections, canonical_sections
                    )
                ):
                    errors.append(
                        f"{path.relative_to(ROOT)}: section française non traduite"
                    )
                if (
                    "En cas d’écart de traduction, la version française prévaut"
                    in text
                ):
                    errors.append(
                        f"{path.relative_to(ROOT)}: règle de prévalence non traduite"
                    )
    repository = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in ROOT.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".html", ".md"}
        and ".git" not in p.parts
    ).lower()
    if "support@brindhysope.fr" in repository:
        errors.append("ancienne adresse de contact présente")
    if errors:
        raise SystemExit("\n".join(errors))
    print("OK: 37 locales × 2 documents, structure, date, version, liens internes localisés, navigation mobile et contact cohérents.")


if __name__ == "__main__":
    main()
