"""Bounded pure envelope mathematics, not an occurrence governor or runtime proof."""

_I64_MIN = -(1 << 63)
_U64_MAX = (1 << 64) - 1
_WORK_LIMIT = 1048576
_COLLECTION_LIMIT = 65536
_DEPTH_LIMIT = 64


class RecordingRefusal(ValueError):
    """A calculator refusal with a read-only public reason."""

    __slots__ = ("_reason",)

    def __init__(self, reason):
        self._reason = reason
        super().__init__(reason)

    @property
    def reason(self):
        return self._reason


class _Budget:
    def __init__(self):
        self.remaining = _WORK_LIMIT

    def take(self, amount):
        if amount > self.remaining:
            raise RecordingRefusal("capacity")
        self.remaining -= amount


def _require(condition, reason):
    if not condition:
        raise RecordingRefusal(reason)


def _keys(value, names, reason):
    _require(type(value) is dict and value.keys() == set(names), reason)


def _bounded(value, lower, upper, reason):
    _require(type(value) is int and lower <= value <= upper, reason)


def _scan(value, reason, budget, depth=1, active=None):
    """Validate a physical JSON tree and charge exactly its logical W."""
    if depth > _DEPTH_LIMIT:
        raise RecordingRefusal("capacity")
    kind = type(value)
    _require(value is None or any(kind is known for known in (bool, int, str, list, dict)), reason)
    if kind is str:
        budget.take(1 + len(value))
        _require(not any(55296 <= ord(char) <= 57343 for char in value), reason)
        return
    if kind is not list and kind is not dict:
        budget.take(1)
        if kind is int:
            _bounded(value, _I64_MIN, _U64_MAX, reason)
        return
    if len(value) > _COLLECTION_LIMIT:
        raise RecordingRefusal("capacity")
    budget.take(1)
    if active is None:
        active = set()
    identity = id(value)
    _require(identity not in active, reason)
    active.add(identity)
    try:
        if kind is dict:
            for key, item in value.items():
                _require(type(key) is str, reason)
                _scan(key, reason, budget, depth + 1, active)
                _scan(item, reason, budget, depth + 1, active)
        else:
            for item in value:
                _scan(item, reason, budget, depth + 1, active)
    finally:
        active.remove(identity)


def _selector(value, reason):
    _require(type(value) is str and 1 <= len(value) <= 256, reason)
    _require(all(ord(character) <= 127 for character in value), reason)


def _validate_rule(rule, reason):
    _keys(rule, ("unit", "minimum", "maximum", "alphabet_ranges"), reason)
    unit = rule["unit"]
    _require(
        type(unit) is str
        and unit in ("ascii_code_units", "unicode_scalar_values", "utf16_code_units"),
        reason,
    )
    _bounded(rule["minimum"], 0, _U64_MAX, reason)
    _bounded(rule["maximum"], rule["minimum"], _U64_MAX, reason)
    _require(type(rule["alphabet_ranges"]) is list, reason)
    previous = -1
    for interval in rule["alphabet_ranges"]:
        _keys(interval, ("lo", "hi"), reason)
        _bounded(interval["lo"], 0, 1114111, reason)
        _bounded(interval["hi"], interval["lo"], 1114111, reason)
        lower, upper = interval["lo"], interval["hi"]
        _require(previous < lower, reason)
        _require(upper < 55296 or lower > 57343, reason)
        if unit == "ascii_code_units":
            _require(upper <= 127, reason)
        previous = upper


def _validate_expression(expr, source_rules):
    reason = "expression"
    _require(type(expr) is dict and type(expr.get("kind")) is str, reason)
    kind = expr["kind"]
    if kind == "literal":
        _keys(expr, ("kind", "value"), reason)
    elif kind == "integer":
        _keys(expr, ("kind", "lo", "hi"), reason)
        _bounded(expr["lo"], _I64_MIN, _U64_MAX, reason)
        _bounded(expr["hi"], expr["lo"], _U64_MAX, reason)
    elif kind == "string":
        fields = ("unit", "minimum", "maximum", "alphabet_ranges")
        _keys(expr, ("kind", *fields, "source_selector"), reason)
        declared = {name: expr[name] for name in fields}
        _validate_rule(declared, reason)
        _selector(expr["source_selector"], reason)
        _require(expr["source_selector"] in source_rules, reason)
        _require(_equal(declared, source_rules[expr["source_selector"]]), reason)
        # Well-typed unused source rules need not have a realizable string.
        # This actual expression must, without expanding a prospective string.
        _string_envelope(expr, source_rules)
    elif kind in ("one_of", "array"):
        _keys(expr, ("kind", "items"), reason)
        _require(type(expr["items"]) is list, reason)
        _require(kind != "one_of" or len(expr["items"]) > 0, reason)
        for item in expr["items"]:
            _validate_expression(item, source_rules)
    elif kind == "record":
        _keys(expr, ("kind", "fields"), reason)
        _require(type(expr["fields"]) is list, reason)
        seen = set()
        for pair in expr["fields"]:
            _require(type(pair) is list and len(pair) == 2, reason)
            key, item = pair
            _require(type(key) is str and key not in seen, reason)
            seen.add(key)
            _validate_expression(item, source_rules)
    else:
        raise RecordingRefusal(reason)


def _prepare(expr, source_rules):
    budget = _Budget()
    _scan(source_rules, "source_rules", budget)
    _require(type(source_rules) is dict, "source_rules")
    for selector, rule in source_rules.items():
        _selector(selector, "source_rules")
        _validate_rule(rule, "source_rules")
    _scan(expr, "expression", budget)
    _validate_expression(expr, source_rules)
    return budget


def _string_width(value):
    width = 2
    for character in value:
        point = ord(character)
        if point in (8, 9, 10, 12, 13, 34, 92):
            width += 2
        elif 32 <= point <= 126:
            width += 1
        elif point <= 65535:
            width += 6
        else:
            width += 12
    return width


def _json_width(value):
    if value is None:
        return 4
    if type(value) is bool:
        return 4 if value else 5
    if type(value) is int:
        return len(str(value))
    if type(value) is str:
        return _string_width(value)
    if type(value) is list:
        return 2 + max(len(value) - 1, 0) + sum(map(_json_width, value))
    if type(value) is dict:
        return (
            2
            + max(len(value) - 1, 0)
            + sum(_string_width(key) + 1 + _json_width(item) for key, item in value.items())
        )
    raise RecordingRefusal("expression")


def _fresh(value):
    if type(value) is dict:
        return {key: _fresh(item) for key, item in value.items()}
    if type(value) is list:
        return [_fresh(item) for item in value]
    return value


def _equal(expected, actual):
    if type(expected) is not type(actual):
        return False
    if type(expected) is dict:
        return expected.keys() == actual.keys() and all(
            _equal(expected[key], actual[key]) for key in expected
        )
    if type(expected) is list:
        return len(expected) == len(actual) and all(
            _equal(left, right) for left, right in zip(expected, actual, strict=False)
        )
    return expected == actual


def _string_envelope(expr, source_rules):
    fields = ("unit", "minimum", "maximum", "alphabet_ranges")
    declared = {name: expr[name] for name in fields}
    if not _equal(declared, source_rules[expr["source_selector"]]):
        raise RecordingRefusal("expression")
    classes = (
        (0, 7, 6),
        (8, 10, 2),
        (11, 11, 6),
        (12, 13, 2),
        (14, 31, 6),
        (32, 33, 1),
        (34, 34, 2),
        (35, 91, 1),
        (92, 92, 2),
        (93, 126, 1),
        (127, 55295, 6),
        (57344, 65535, 6),
        (65536, 1114111, 12),
    )
    representatives = {}
    for interval in expr["alphabet_ranges"]:
        for lower, upper, escaped_width in classes:
            point = max(interval["lo"], lower)
            if point > min(interval["hi"], upper):
                continue
            cost = 2 if expr["unit"] == "utf16_code_units" and point > 65535 else 1
            candidate = (escaped_width, -point)
            if cost not in representatives or candidate > representatives[cost]:
                representatives[cost] = candidate
    minimum, maximum = expr["minimum"], expr["maximum"]
    counts = []
    if expr["unit"] != "utf16_code_units":
        if representatives:
            counts = [(1, maximum)]
        elif minimum:
            raise RecordingRefusal("expression")
    elif 2 in representatives:
        pairs, remainder = divmod(maximum, 2)
        if remainder and 1 not in representatives:
            remainder = 0
        if 2 * pairs + remainder < minimum:
            raise RecordingRefusal("expression")
        counts = [(2, pairs), (1, remainder)]
    elif 1 in representatives:
        counts = [(1, maximum)]
    elif minimum:
        raise RecordingRefusal("expression")
    runs = [[-representatives[cost][1], count] for cost, count in counts if count]
    width = 2 + sum(representatives[cost][0] * count for cost, count in counts if count)
    return width, {"kind": "string_runs", "runs": runs}


def _evaluate(expr, source_rules):
    kind = expr["kind"]
    if kind == "literal":
        return _json_width(expr["value"]), {"kind": "value", "value": _fresh(expr["value"])}
    if kind == "integer":
        lower, upper = expr["lo"], expr["hi"]
        selected = upper if len(str(upper)) > len(str(lower)) else lower
        return len(str(selected)), {"kind": "value", "value": selected}
    if kind == "string":
        return _string_envelope(expr, source_rules)
    if kind == "one_of":
        branches = [_evaluate(item, source_rules) for item in expr["items"]]
        selected = max(range(len(branches)), key=lambda index: branches[index][0])
        width, witness = branches[selected]
        return width, {"kind": "one_of", "selected_index": selected, "witness": witness}
    if kind == "record":
        fields = []
        width = 2 + max(len(expr["fields"]) - 1, 0)
        for key, child in expr["fields"]:
            child_width, witness = _evaluate(child, source_rules)
            width += _string_width(key) + 1 + child_width
            fields.append([key, witness])
        return width, {"kind": "record", "fields": fields}
    if kind == "array":
        children = [_evaluate(item, source_rules) for item in expr["items"]]
        width = 2 + max(len(children) - 1, 0) + sum(child[0] for child in children)
        return width, {"kind": "array", "items": [child[1] for child in children]}
    raise RecordingRefusal("expression")


def _literal_match(expected, actual, budget):
    budget.take(1)
    if type(expected) is not type(actual):
        return False
    if type(expected) is str:
        budget.take(len(expected) + len(actual))
        return expected == actual
    if type(expected) is dict:
        return expected.keys() == actual.keys() and all(
            _literal_match(expected[key], actual[key], budget) for key in sorted(expected)
        )
    if type(expected) is list:
        return len(expected) == len(actual) and all(
            _literal_match(left, right, budget)
            for left, right in zip(expected, actual, strict=False)
        )
    return expected == actual


def _in_ranges(point, ranges):
    lower, upper = 0, len(ranges)
    while lower < upper:
        middle = (lower + upper) // 2
        interval = ranges[middle]
        if point < interval["lo"]:
            upper = middle
        elif point > interval["hi"]:
            lower = middle + 1
        else:
            return True
    return False


def _fits(expr, actual, budget):
    budget.take(1)
    kind = expr["kind"]
    if kind == "literal":
        return _literal_match(expr["value"], actual, budget)
    if kind == "integer":
        return type(actual) is int and expr["lo"] <= actual <= expr["hi"]
    if kind == "string":
        if type(actual) is not str:
            return False
        budget.take(len(actual))
        units = 0
        for character in actual:
            point = ord(character)
            if not _in_ranges(point, expr["alphabet_ranges"]):
                return False
            units += 2 if expr["unit"] == "utf16_code_units" and point > 65535 else 1
        return expr["minimum"] <= units <= expr["maximum"]
    if kind == "one_of":
        return any(_fits(item, actual, budget) for item in expr["items"])
    if kind == "record":
        keys = [key for key, _child in expr["fields"]]
        return (
            type(actual) is dict
            and actual.keys() == set(keys)
            and all(_fits(child, actual[key], budget) for key, child in expr["fields"])
        )
    if kind == "array":
        return (
            type(actual) is list
            and len(actual) == len(expr["items"])
            and all(
                _fits(child, item, budget)
                for child, item in zip(expr["items"], actual, strict=False)
            )
        )
    return False


def evaluate_envelope(expr, *, source_rules):
    """Return the admitted envelope's width and compact synthetic witness."""
    _prepare(expr, source_rules)
    width, witness = _evaluate(expr, source_rules)
    return {"upper_ascii_bytes": width, "witness": witness}


def check_actual(expr, actual, *, source_rules):
    """Check strict membership while retaining the whole envelope upper width."""
    input_budget = _prepare(expr, source_rules)
    _scan(actual, "actual", input_budget)
    width, _witness = _evaluate(expr, source_rules)
    if not _fits(expr, actual, _Budget()):
        raise RecordingRefusal("actual")
    return {"actual_ascii_bytes": _json_width(actual), "upper_ascii_bytes": width}
