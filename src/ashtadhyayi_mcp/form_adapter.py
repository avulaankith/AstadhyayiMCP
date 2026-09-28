"""Validate and decode the actual upstream form encodings without repairing them."""

import re
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Literal, cast

from .domain import DataError, Evidence, ShabdaData
from .form_models import FormCell, FormData, Linga, Purusha, SourceCoverageData
from .form_sources import FORM_SOURCES, LAKARAS, SHABDA_PATH, FormSource

if TYPE_CHECKING:
    from .adapters import Corpus


def pointer_part(text: str) -> str:
    return text.replace("~", "~0").replace("/", "~1")


def variants(text: str, separator: str) -> list[str]:
    return [v.strip() for v in re.split(separator, text) if v.strip() and v.strip() != "-"]


def cells_for(source: FormSource, raw: str, linga: str | None = None) -> Iterator[FormCell]:
    if source.category == "tinanta":
        persons: tuple[Purusha, ...] = ("prathama", "madhyama", "uttama")
        for index, value in enumerate(raw.split(";")):
            yield FormCell(
                group_index=0,
                slot_index=index,
                raw_text=value,
                variants=variants(value, r"[,/]"),
                role="finite",
                purusha=persons[index // 3],
                vacana=index % 3 + 1,
            )
    elif source.category == "subanta":
        for index, value in enumerate(raw.split(";")):
            yield FormCell(
                group_index=0,
                slot_index=index,
                raw_text=value,
                variants=variants(value, "-"),
                role="declined",
                linga=cast(Linga | None, linga),
                vibhakti=index // 3 + 1,
                vacana=index % 3 + 1,
            )
    elif source.family == "upstream":
        yield FormCell(
            group_index=0,
            slot_index=0,
            raw_text=raw,
            variants=variants(raw, r"[,/]"),
            role="unspecified",
        )
    else:
        genders: tuple[Literal["P", "S", "N"] | None, ...] = (None, "P", "S", "N")
        for group_index, group in enumerate(raw.split(";")):
            parts = group.split(",")
            if len(parts) != 4:
                yield FormCell(
                    group_index=group_index,
                    slot_index=0,
                    raw_text=group,
                    variants=[group] if group.strip() else [],
                    role="unparsed",
                )
                continue
            for slot, value in enumerate(parts):
                yield FormCell(
                    group_index=group_index,
                    slot_index=slot,
                    raw_text=value,
                    variants=variants(value, "/"),
                    linga=genders[slot],
                    role="stem_or_indeclinable" if slot == 0 else "gender_form",
                )


def decode_form(
    source: FormSource,
    identifier: str | None,
    baseindex: str | None,
    key: str,
    raw: str,
    linga: str | None = None,
) -> FormData:
    cells = list(cells_for(source, raw, linga))
    bad = sum(cell.role == "unparsed" for cell in cells)
    status: Literal["decoded", "partial", "unparsed"] = (
        "unparsed" if bad and bad == len(cells) else "partial" if bad else "decoded"
    )
    return FormData(
        lemma_id=identifier,
        baseindex=baseindex,
        source_family=source.family,
        category=source.category,
        derivation=source.derivation,
        prayoga=source.prayoga,
        source_key=key,
        pada=("P" if key[0] == "p" else "A") if source.category == "tinanta" else None,
        lakara=key[1:] if source.category == "tinanta" else None,
        pratyaya=key if source.category == "krdanta" else None,
        raw_text=raw,
        cells=cells,
        parse_status=status,
        warnings=[f"{bad} group(s) do not have four kṛdanta columns; kept unparsed"] if bad else [],
    )


def parse_form_documents(corpus: "Corpus", documents: dict[str, Any]) -> None:
    """Validate every entry, including those not reached by a sample query."""
    baseindices = {d.data.baseindex for d in corpus.dhatus}
    try:
        if SHABDA_PATH in corpus.manifest.files:
            doc = documents[SHABDA_PATH]
            if not isinstance(doc, dict) or not isinstance(doc.get("data"), list):
                raise ValueError("śabda catalog requires a data array")
            seen: set[str] = set()
            for index, record in enumerate(doc["data"]):
                required = ("urlid", "word", "linga", "forms")
                if not isinstance(record, dict) or any(
                    not isinstance(record.get(k), str) for k in required
                ):
                    raise ValueError("Invalid śabda record")
                identifier = record["urlid"]
                if (
                    not identifier
                    or identifier in seen
                    or record["linga"] not in ("P", "S", "N", "A")
                ):
                    raise ValueError("Duplicate śabda ID or unsupported linga code")
                seen.add(identifier)
                if len(record["forms"].split(";")) != 24:
                    raise ValueError("Śabda paradigm must have 24 slots, including empty slots")
                corpus.shabdas.append(
                    Evidence(
                        data=ShabdaData(
                            upstream_id=identifier,
                            text=record["word"],
                            linga=record["linga"],
                            upstream_record=record,
                        ),
                        provenance=corpus.provenance(SHABDA_PATH, identifier, f"/data/{index}"),
                    )
                )
            if not seen:
                raise ValueError("Empty śabda catalog")
        for source in FORM_SOURCES:
            path = source.path
            if path not in corpus.manifest.files:
                continue
            keys: set[str] = set()
            count = bad = 0
            if path == SHABDA_PATH:
                rows = {
                    s.data.upstream_id: {"forms": str(s.data.upstream_record["forms"])}
                    for s in corpus.shabdas
                }
                unlinked: list[str] = []
            else:
                rows = documents[path]
                if not isinstance(rows, dict):
                    raise ValueError(f"{path}: expected baseindex map")
                unlinked = sorted(set(rows) - baseindices)
                for baseindex, row in rows.items():
                    if not re.fullmatch(r"[0-9]{2}\.[0-9]{4}", baseindex) or not isinstance(
                        row, dict
                    ):
                        raise ValueError(f"{path}: invalid root key or row")
                    for key, raw in row.items():
                        if not isinstance(raw, str) or not key.strip():
                            raise ValueError(f"{path}: expected string form values")
                        if source.category == "tinanta":
                            if key[0] not in "pa" or key[1:] not in LAKARAS:
                                raise ValueError(f"{path}: unknown finite paradigm key {key}")
                            if len(raw.split(";")) != 9:
                                raise ValueError(f"{path}: finite paradigm must have 9 slots")
                        elif source.family == "vidyut":
                            bad += sum(len(group.split(",")) != 4 for group in raw.split(";"))
                corpus.dhatu_forms[path] = rows
            for row in rows.values():
                keys.update(row)
                count += len(row)
            corpus.form_coverage.append(
                Evidence(
                    data=SourceCoverageData(
                        source_path=path,
                        family=source.family,
                        category=source.category,
                        derivation=source.derivation,
                        prayoga=source.prayoga,
                        records=len(rows),
                        paradigm_fields=count,
                        unparsed_groups=bad,
                        unlinked_identifiers=unlinked,
                        available_keys=sorted(keys),
                    ),
                    provenance=corpus.provenance(path, path, ""),
                )
            )
    except (ValueError, TypeError, KeyError) as exc:
        raise DataError("UPSTREAM_SCHEMA_ERROR", f"Invalid forms data: {exc}") from exc
