"""Verified upstream form collections; no grammatical generation."""

from dataclasses import dataclass
from typing import Literal

Derivation = Literal["shuddha", "nich", "san", "yang", "yangluk"]
Category = Literal["tinanta", "krdanta", "subanta"]
Family = Literal["vidyut", "upstream", "shabda"]
Prayoga = Literal["kartari", "karmani"]
Lakara = Literal[
    "lat",
    "lit",
    "lut",
    "lrut",
    "let",
    "lot",
    "lang",
    "vidhiling",
    "ashirling",
    "lung",
    "lrung",
]
LAKARAS = (
    "lat",
    "lit",
    "lut",
    "lrut",
    "let",
    "lot",
    "lang",
    "vidhiling",
    "ashirling",
    "lung",
    "lrung",
)
SHABDA_PATH = "shabda/data2.txt"


@dataclass(frozen=True)
class FormSource:
    path: str
    family: Family
    category: Category
    derivation: Derivation | None
    prayoga: Prayoga | None


_DERIVATIONS: tuple[Derivation, ...] = ("shuddha", "nich", "san", "yang", "yangluk")
_PRAYOGAS: tuple[Prayoga, ...] = ("kartari", "karmani")
FORM_SOURCES = (
    FormSource("dhatu/dhatuforms_krut.txt", "upstream", "krdanta", None, None),
    *(
        FormSource(f"dhatu/dhatuforms_vidyut_{d}_{p}.txt", "vidyut", "tinanta", d, p)
        for d in _DERIVATIONS
        for p in _PRAYOGAS
    ),
    *(
        FormSource(f"dhatu/dhatuforms_vidyut_{d}_krut.txt", "vidyut", "krdanta", d, None)
        for d in _DERIVATIONS
    ),
    FormSource(SHABDA_PATH, "shabda", "subanta", None, None),
)
FORM_PATHS = tuple(s.path for s in FORM_SOURCES)
SOURCE_BY_PATH = {s.path: s for s in FORM_SOURCES}
