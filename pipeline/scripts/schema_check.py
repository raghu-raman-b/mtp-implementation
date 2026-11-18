"""A small JSON Schema checker (standard library only) for the subset the pipeline's schemas use, plus references.

    from scripts.schema_check import Checker
    c = Checker(json.load(open("schemas/knowledge.schema.json")))
    c.check(data, "#/$defs/concepts_file", where="concepts.json")
    c.errors   # ["concepts.json$.C0001.name: expected string, got int", ...]
    c.refs     # [("concept", "C0002", "concepts.json$.C0001.relations.out[0].concept"), ...]
    c.ids      # {"concept": {"C0001": "concepts.json$.C0001", ...}, ...}

Keywords: type (one or a list; integer excludes booleans, number takes integers), enum, const, pattern, minLength,
minimum, maximum, items, minItems, maxItems, properties, required, additionalProperties (false or a schema),
propertyNames, anyOf, $ref ("#/..." within the same document). Anything else is ignored, so a schema that uses
another keyword is not checked on it; keep to this list.
References (not JSON Schema; names starting with x- are ignored by other checkers): "x-ref": kind on a string
records it as a reference to an ID of that kind; "x-id": kind records it as the definition of one; "x-key-id" and
"x-key-ref" on an object do the same for each of its keys. broken() then lists every reference with no definition.
"""
from __future__ import annotations

import re

TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is(value, t: str) -> bool:
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[t])


class Checker:
    def __init__(self, root: dict):
        self.root = root
        self.errors: list[str] = []
        self.refs: list[tuple[str, str, str]] = []
        self.ids: dict[str, dict[str, str]] = {}
        self.duplicates: list[str] = []
        self._re: dict[str, re.Pattern] = {}

    # ------------------------------------------------------------------ public
    def check(self, data, schema: dict | str, where: str = "") -> bool:
        """Check data against a schema (or a "#/..." pointer into the root); errors, refs and ids are added to."""
        n = len(self.errors)
        self._check(data, self._resolve(schema) if isinstance(schema, str) else schema, where + "$", self.errors,
                    self.refs, self.ids)
        return len(self.errors) == n

    def define(self, kind: str, value: str, path: str):
        self._define(self.ids, kind, value, path)

    def broken(self, extra_ids: dict[str, set] | None = None) -> list[dict]:
        """Every reference whose ID is defined nowhere (extra_ids: IDs defined outside the schema, by kind)."""
        out = []
        for kind, value, path in self.refs:
            if value not in self.ids.get(kind, {}) and value not in (extra_ids or {}).get(kind, ()):
                out.append({"kind": kind, "id": value, "at": path})
        return out

    # ------------------------------------------------------------------ internals
    def _resolve(self, pointer: str) -> dict:
        if not pointer.startswith("#"):
            raise ValueError(f"only local references are supported: {pointer}")
        node = self.root
        for part in [p for p in pointer[1:].split("/") if p]:
            node = node[part.replace("~1", "/").replace("~0", "~")]
        return node

    def _pattern(self, p: str) -> re.Pattern:
        if p not in self._re:
            self._re[p] = re.compile(p)
        return self._re[p]

    def _define(self, ids: dict, kind: str, value: str, path: str):
        seen = ids.setdefault(kind, {})
        if value in seen:
            self.duplicates.append(f"{kind} {value} defined at {seen[value]} and at {path}")
        else:
            seen[value] = path

    def _check(self, x, s: dict, path: str, errors: list, refs: list, ids: dict):
        if "$ref" in s:
            self._check(x, self._resolve(s["$ref"]), path, errors, refs, ids)
        if "anyOf" in s:
            for option in s["anyOf"]:
                e, r, i = [], [], {}
                self._check(x, option, path, e, r, i)
                if not e:
                    refs += r
                    for kind, vals in i.items():
                        for v, p in vals.items():
                            self._define(ids, kind, v, p)
                    break
            else:
                errors.append(f"{path}: matches none of the {len(s['anyOf'])} options")
        if "type" in s:
            types = s["type"] if isinstance(s["type"], list) else [s["type"]]
            if not any(_is(x, t) for t in types):
                errors.append(f"{path}: expected {' or '.join(types)}, got {type(x).__name__}")
                return
        if "enum" in s and x not in s["enum"]:
            errors.append(f"{path}: {x!r} is not one of {s['enum']}")
        if "const" in s and x != s["const"]:
            errors.append(f"{path}: {x!r} is not {s['const']!r}")
        if isinstance(x, str):
            if "pattern" in s and not self._pattern(s["pattern"]).search(x):
                errors.append(f"{path}: {x!r} does not match {s['pattern']}")
            if len(x) < s.get("minLength", 0):
                errors.append(f"{path}: shorter than {s['minLength']}")
            if "x-ref" in s:
                refs.append((s["x-ref"], x, path))
            if "x-id" in s:
                self._define(ids, s["x-id"], x, path)
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            if "minimum" in s and x < s["minimum"]:
                errors.append(f"{path}: {x} is below {s['minimum']}")
            if "maximum" in s and x > s["maximum"]:
                errors.append(f"{path}: {x} is above {s['maximum']}")
        if isinstance(x, list):
            if len(x) < s.get("minItems", 0):
                errors.append(f"{path}: fewer than {s['minItems']} items")
            if "maxItems" in s and len(x) > s["maxItems"]:
                errors.append(f"{path}: more than {s['maxItems']} items")
            items = s.get("items")
            if items == {"type": "number"}:                       # fast path (embedding vectors)
                if not all(_is(v, "number") for v in x):
                    errors.append(f"{path}: an item is not a number")
            elif items is not None:
                for i, v in enumerate(x):
                    self._check(v, items, f"{path}[{i}]", errors, refs, ids)
        if isinstance(x, dict):
            props = s.get("properties", {})
            for k in s.get("required", []):
                if k not in x:
                    errors.append(f"{path}: missing {k!r}")
            extra = s.get("additionalProperties", True)
            for k, v in x.items():
                where = f"{path}.{k}"
                if "propertyNames" in s:
                    self._check(k, s["propertyNames"], f"{path} key {k!r}", errors, refs, ids)
                if "x-key-id" in s:
                    self._define(ids, s["x-key-id"], k, where)
                if "x-key-ref" in s:
                    refs.append((s["x-key-ref"], k, where))
                if k in props:
                    self._check(v, props[k], where, errors, refs, ids)
                elif extra is False:
                    errors.append(f"{path}: unexpected {k!r}")
                elif isinstance(extra, dict):
                    self._check(v, extra, where, errors, refs, ids)
