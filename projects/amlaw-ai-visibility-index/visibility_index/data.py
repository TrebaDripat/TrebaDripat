"""Parse the versioned replay format before a run can produce any output."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit


class DataError(ValueError):
    """A dataset, budget or output path cannot be used as supplied."""


@dataclass(frozen=True)
class Firm:
    id: str
    name: str
    aliases: tuple[tuple[str, ...], ...]
    domains: tuple[str, ...]


@dataclass(frozen=True)
class Engine:
    id: str
    input_nanos: int
    output_nanos: int


@dataclass(frozen=True)
class Citation:
    url: str
    host: str


@dataclass(frozen=True)
class Answer:
    line: int
    engine: str
    prompt: str
    text: str
    citations: tuple[Citation, ...]
    input_tokens: int
    output_tokens: int
    max_output_tokens: int


@dataclass(frozen=True)
class Dataset:
    label: str
    firms: dict[str, Firm]
    engines: dict[str, Engine]
    prompts: dict[str, str]
    answers: tuple[Answer, ...]
    sha256: dict[str, str]


def words(text: str) -> tuple[str, ...]:
    folded = unicodedata.normalize("NFKC", text).casefold().replace("&", " and ")
    return tuple(re.findall(r"[^\W_]+", folded))


def decimal_units(value: str, places: int) -> int:
    if not isinstance(value, str) or not re.fullmatch(
        rf"[0-9]{{1,16}}(?:\.[0-9]{{1,{places}}})?", value
    ):
        raise DataError(
            f"expected a nonnegative decimal string with up to {places} fractional digits"
        )
    whole, _, fraction = value.partition(".")
    return int(whole) * 10**places + int(fraction.ljust(places, "0"))


def domain(value: str) -> str:
    if not isinstance(value, str):
        raise DataError("expected a DNS hostname")
    try:
        host = value.removesuffix(".").encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise DataError("invalid DNS hostname") from error
    labels = host.split(".")
    label_pattern = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if (
        len(host) > 253
        or len(labels) < 2
        or labels[-1].isdigit()
        or not all(re.fullmatch(label_pattern, label) for label in labels)
    ):
        raise DataError(f"invalid DNS hostname {value!r}")
    return host


def citation(value: str) -> Citation:
    if not isinstance(value, str) or any(
        c.isspace() or ord(c) < 32 or c == "\\" for c in value
    ):
        raise DataError("expected an absolute HTTP(S) citation URL")
    try:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or parts.username is not None
            or not parts.hostname
        ):
            raise DataError(
                "expected an absolute HTTP(S) citation URL without credentials"
            )
        host = domain(parts.hostname)
        port = parts.port
    except ValueError as error:
        raise DataError(f"invalid citation URL: {error}") from error
    authority = host
    if port is not None and (parts.scheme, port) not in {("http", 80), ("https", 443)}:
        authority = f"{host}:{port}"
    url = urlunsplit((parts.scheme, authority, parts.path or "/", parts.query, ""))
    return Citation(url, host)


def _object(value, fields: str) -> dict:
    if not isinstance(value, dict):
        raise DataError("expected a JSON object")
    expected = set(fields.split())
    if expected != value.keys():
        raise DataError(
            f"missing fields {sorted(expected - value.keys())}, unexpected fields {sorted(value.keys() - expected)}"
        )
    return value


def _array(value, *, required=False) -> list:
    if not isinstance(value, list) or (required and not value):
        raise DataError(
            "expected a nonempty array" if required else "expected an array"
        )
    return value


def _text(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataError("expected nonempty text")
    return value


def _key(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-z0-9]+(?:[-_][a-z0-9]+)*", value
    ):
        raise DataError("expected a lowercase identifier")
    return value


def _tokens(value) -> int:
    if type(value) is not int or value < 0:
        raise DataError("token counts must be nonnegative integers")
    return value


def _unique_fields(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise DataError(f"duplicate JSON field {key!r}")
        obj[key] = value
    return obj


def _records(raw, fields):
    seen = set()
    for item in _array(raw, required=True):
        obj = _object(item, fields)
        key = _key(obj["id"])
        if key in seen:
            raise DataError(f"duplicate identifier {key!r}")
        seen.add(key)
        yield key, obj


def _catalog(raw):
    obj = _object(raw, "schema_version label firms engines prompts")
    if type(obj["schema_version"]) is not int or obj["schema_version"] != 1:
        raise DataError("expected schema_version 1")
    firms = {}
    alias_owners = {}
    domain_owners = {}
    for key, entry in _records(obj["firms"], "id name aliases domains"):
        name = _text(entry["name"])
        aliases = tuple(
            dict.fromkeys(words(_text(a)) for a in [name, *_array(entry["aliases"])])
        )
        domains = tuple(
            dict.fromkeys(domain(h) for h in _array(entry["domains"], required=True))
        )
        for alias in aliases:
            if not alias or alias_owners.setdefault(alias, key) != key:
                raise DataError(f"empty or ambiguous firm alias for {key!r}")
        for host in domains:
            if domain_owners.setdefault(host, key) != key:
                raise DataError(f"ambiguous domain {host!r}")
        firms[key] = Firm(key, name, aliases, domains)
    engines = {
        key: Engine(
            key,
            decimal_units(e["input_usd_per_million"], 3),
            decimal_units(e["output_usd_per_million"], 3),
        )
        for key, e in _records(
            obj["engines"], "id input_usd_per_million output_usd_per_million"
        )
    }
    prompts = {key: _text(p["text"]) for key, p in _records(obj["prompts"], "id text")}
    return _text(obj["label"]), firms, engines, prompts


def _answer(raw, line, engines, prompts):
    obj = _object(
        raw, "engine prompt text citations input_tokens output_tokens max_output_tokens"
    )
    engine = _key(obj["engine"])
    prompt = _key(obj["prompt"])
    if engine not in engines or prompt not in prompts:
        raise DataError(f"unknown engine or prompt in {(engine, prompt)!r}")
    if not isinstance(obj["text"], str):
        raise DataError("answer text must be a string")
    used = _tokens(obj["output_tokens"])
    limit = _tokens(obj["max_output_tokens"])
    if used > limit:
        raise DataError("output_tokens exceeds max_output_tokens")
    links = tuple(dict.fromkeys(citation(link) for link in _array(obj["citations"])))
    return Answer(
        line,
        engine,
        prompt,
        obj["text"],
        links,
        _tokens(obj["input_tokens"]),
        used,
        limit,
    )


def load_dataset(directory: Path) -> Dataset:
    hashes = {}

    def read(name):
        content = (directory / name).read_bytes()
        hashes[name] = hashlib.sha256(content).hexdigest()
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise DataError(f"{name}: expected UTF-8") from error

    try:
        label, firms, engines, prompts = _catalog(
            json.loads(read("catalog.json"), object_pairs_hook=_unique_fields)
        )
    except (ValueError, RecursionError) as error:
        raise DataError(f"catalog.json: {error}") from error
    answers = []
    observed = set()
    for line, text in enumerate(read("answers.jsonl").split("\n"), start=1):
        if not text.strip():
            continue
        try:
            answer = _answer(
                json.loads(text, object_pairs_hook=_unique_fields),
                line,
                engines,
                prompts,
            )
            key = answer.engine, answer.prompt
            if key in observed:
                raise DataError(f"duplicate observation {key!r}")
            observed.add(key)
            answers.append(answer)
        except (ValueError, RecursionError) as error:
            raise DataError(f"answers.jsonl:{line}: {error}") from error
    return Dataset(label, firms, engines, prompts, tuple(answers), hashes)
