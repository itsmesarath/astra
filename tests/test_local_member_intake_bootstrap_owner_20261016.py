"""Independent finite pure bootstrap-owner tests; no producer/native qualification.

All helper calls occur in testcase bodies through the NIE-only RED wrapper.
The evidence graph covers declared small fake objects and aliases, never interpreter
tracebacks, function globals, arbitrary heaps, native resources, or ownership cleanup.
"""

import copy
import importlib.util
import json
import types
from pathlib import Path

import pytest

from tests import local_member_intake_bootstrap_owner_oracles_20261016 as oracle

_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "scripts/local_member_intake_bootstrap_owner_20261016_1.py"
)
_POSITIONS = (-1, 0, 16, 32)
_SLOT_IDS = ("constructor", "lookup00", "lookup16", "lookup32")
_REFERENCE_FIELDS = (
    "raw_return",
    "raw_error",
    "conversion_error",
    "conversion_result",
    "pending_record",
    "committed_record",
    "cut_ref",
)
_HOOKS = []


class _Resource:
    def __init__(self, label):
        self.label = label


class _FakeError(Exception):
    def __str__(self):
        _HOOKS.append("exception.str")
        raise AssertionError("raw fake error must not be stringified")

    def __repr__(self):
        _HOOKS.append("exception.repr")
        raise AssertionError("raw fake error must not be repr'd")


class _Escaped(BaseException):
    pass


class _Hostile:
    def __eq__(self, other):
        _HOOKS.append("eq")
        raise AssertionError("hostile equality entered")

    def __hash__(self):
        _HOOKS.append("hash")
        return 937

    def __repr__(self):
        _HOOKS.append("repr")
        raise AssertionError("hostile repr entered")

    def __str__(self):
        _HOOKS.append("str")
        raise AssertionError("hostile str entered")

    def __call__(self, *args, **kwargs):
        _HOOKS.append("call")
        raise AssertionError("hostile callback entered")


class _String(str):
    def __eq__(self, other):
        _HOOKS.append("string.eq")
        raise AssertionError("string subclass equality entered")

    def __hash__(self):
        _HOOKS.append("string.hash")
        return str.__hash__(self)

    def __str__(self):
        _HOOKS.append("string.str")
        raise AssertionError("string subclass coercion entered")


class _Dictionary(dict):
    pass


class _Tuple(tuple):
    pass


class _TrapMeta(type):
    def __eq__(cls, other):
        _HOOKS.append("metaclass.eq")
        raise AssertionError("metaclass equality entered")

    def __hash__(cls):
        _HOOKS.append("metaclass.hash")
        return 941


class _TrapClass(metaclass=_TrapMeta):
    pass


class _MethodHolder:
    def method(self):
        _HOOKS.append("method.call")
        raise AssertionError("bound method entered")


@pytest.fixture(scope="module")
def owner_module():
    # Loading the expressly registered new pure helper is not a fake callback.
    spec = importlib.util.spec_from_file_location("pure_bootstrap_owner_subject", _SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _exact(actual, expected, reference=False):
    """Closed explicit assertions never format hostile runtime values."""
    if reference:
        if actual is not expected:
            raise AssertionError("bootstrap owner exact reference mismatch")
        return
    if type(actual) is not type(expected):
        raise AssertionError("bootstrap owner exact type mismatch")
    if type(expected) is dict:
        if any(type(key) is not str for key in actual):
            raise AssertionError("bootstrap owner unexpected output key domain")
        if set(actual) != set(expected):
            raise AssertionError("bootstrap owner exact key roster mismatch")
        for key in expected:
            _exact(actual[key], expected[key], key in _REFERENCE_FIELDS)
    elif type(expected) in (list, tuple):
        if len(actual) != len(expected):
            raise AssertionError("bootstrap owner exact sequence length mismatch")
        for index in range(len(expected)):
            _exact(actual[index], expected[index])
    elif type(expected) in (str, int, bool, float, bytes) or expected is None:
        if actual != expected:
            raise AssertionError("bootstrap owner exact scalar mismatch")
    elif actual is not expected:
        raise AssertionError("bootstrap owner exact opaque reference mismatch")


def _graph(value, functions=None, owner=None):
    """Complete declared fake graph, with explicit opaque runtime/code exclusions."""
    functions = {} if functions is None else functions
    nodes = []
    seen = {}

    def visit(item):
        cls = type(item)
        if item is None or cls is bool or cls is int or cls is str:
            return {"scalar": item}
        identity = id(item)
        if identity in seen:
            return {"ref": seen[identity]}
        index = len(nodes)
        seen[identity] = index
        node = {"id": index}
        nodes.append(node)
        if item is owner and owner is not None:
            node.update(kind="public_owner_identity")
        elif cls is list or cls is tuple:
            node.update(kind="list" if cls is list else "tuple", items=[visit(v) for v in item])
        elif cls is dict or cls is _Dictionary:
            node.update(
                kind="dict" if cls is dict else "dict_subclass",
                items=[[visit(k), visit(v)] for k, v in dict.items(item)],
            )
        elif cls is _Resource:
            node.update(
                kind="resource", attributes=visit(object.__getattribute__(item, "__dict__"))
            )
        elif cls is _FakeError or cls is _Escaped:
            attrs = object.__getattribute__(item, "__dict__")
            args = BaseException.args.__get__(item, cls)
            cause = BaseException.__cause__.__get__(item, cls)
            context = BaseException.__context__.__get__(item, cls)
            notes_present = "__notes__" in attrs
            node.update(
                kind="fake_error" if cls is _FakeError else "escaped_base_exception",
                args=visit(args),
                attributes=visit(attrs),
                cause=visit(cause),
                context=visit(context),
                notes_state="present" if notes_present else "absent",
                notes=visit(attrs["__notes__"]) if notes_present else {"scalar": None},
            )
        elif cls is types.FunctionType:
            declaration = functions.get(identity)
            if declaration is None:
                raise AssertionError("undeclared test function graph edge")
            node.update(kind="exact_function_factory", declaration=visit(declaration))
        elif cls is types.BuiltinFunctionType:
            if item is not len:
                raise AssertionError("undeclared builtin test function")
            node.update(kind="declared_builtin_function", factory="len")
        elif cls is types.MethodType:
            node.update(
                kind="declared_bound_method",
                factory="MethodHolder.method",
                owner=visit(item.__self__),
            )
        elif cls is _String:
            node.update(kind="str_subclass", codepoints=[ord(v) for v in str.__str__(item)])
        elif cls is _Tuple:
            node.update(kind="tuple_subclass", items=[visit(v) for v in tuple.__iter__(item)])
        elif cls is _Hostile or cls is _MethodHolder:
            node.update(
                kind="declared_hostile" if cls is _Hostile else "method_holder",
                attributes=visit(object.__getattribute__(item, "__dict__")),
            )
        elif item is _TrapClass:
            node.update(kind="declared_class_factory", factory="TrapClass")
        else:
            raise AssertionError("undeclared constructed object in finite test graph")
        return {"ref": index}

    root = visit(value)
    return {"root": root, "nodes": nodes}


def _capture(label, value):
    print(label + " " + json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def _api(module, name, *args, **kwargs):
    try:
        return getattr(module, name)(*args, **kwargs)
    except NotImplementedError as error:
        _capture(
            "OWNER_MISSING_BEHAVIOR",
            {
                "operation": name,
                "expected": "implemented pure owner behavior",
                "actual_result": "unavailable:NotImplementedError",
                "callback_outcome": "not observed by this wrapper",
            },
        )
        raise AssertionError("pure bootstrap owner behavior is unimplemented") from error


def _step(**changes):
    value = oracle.empty_step()
    value.update(changes)
    return value


def _slot_label(index):
    return "constructor" if index == -1 else "lookup" + str(index).zfill(2)


class _Case:
    def __init__(self, module, scenario):
        self.module = module
        self.carrier = {"initialization": [], "binding_initialization": []}
        self.initialization = self.carrier["initialization"]
        self.bindings = self.carrier["binding_initialization"]
        self.expected_initialization = []
        self.expected_bindings = []
        self.expected = oracle.expected_owner()
        self.functions = {}
        self.calls = []
        self.records = []
        self.owner = None
        _HOOKS.clear()
        _capture(
            "OWNER_CASE_INPUT",
            {
                "scenario": scenario,
                "complete_pending_literals": [oracle.pending_record(i) for i in range(-1, 33)],
                "complete_success_literals": [oracle.committed_record(i) for i in range(-1, 33)],
                "complete_error_literals": [
                    oracle.committed_record(i, "raised") for i in range(-1, 33)
                ],
                "carrier_graph": _graph(self.carrier),
                "initial_expected_view": self.expected,
                "initial_expected_paths": oracle.expected_paths(False),
            },
        )
        self.owner = _api(module, "new_owner", self.carrier)

    def view(self):
        return _api(self.module, "inspect_owner", self.owner)

    def selected(self):
        return _api(self.module, "select_paths", self.owner)

    def expected_with(self, index, step, *, in_progress, stopped=None, next_lookup=None):
        updates = {i: row for i, row in enumerate(self.expected["lookups"])}
        constructor = self.expected["constructor"]
        if index == -1:
            constructor = step
        else:
            updates[index] = step
        return oracle.expected_owner(
            next_lookup=self.expected["next_lookup"] if next_lookup is None else next_lookup,
            stopped=self.expected["stopped"] if stopped is None else stopped,
            in_progress=in_progress,
            constructor=constructor,
            lookup_updates=updates,
        )

    def fakes(
        self,
        index,
        *,
        outcome="returned",
        mode="complete",
        proposal=None,
        raw=None,
        observe=False,
        escaped=None,
        reentrant=None,
        pending=None,
        record=None,
        none_return=False,
        conversion_error=None,
    ):
        pending = oracle.pending_record(index) if pending is None else pending
        record = oracle.committed_record(index, outcome) if record is None else record
        raw = (
            (
                _Resource("return:" + _slot_label(index))
                if outcome == "returned"
                else _FakeError("invoke", _slot_label(index))
            )
            if raw is None
            else raw
        )
        if none_return:
            raw = None
        if proposal is None:
            if mode == "complete":
                proposal = (
                    "complete_success" if outcome == "returned" else "complete_error",
                    record,
                )
            elif mode in ("unsupported", "oversize"):
                proposal = (mode, None)
        conversion_error = (
            _FakeError("conversion", _slot_label(index))
            if conversion_error is None
            else conversion_error
        )
        counts = {"invoke": 0, "convert": 0}
        expected_counts = {"invoke": 0, "convert": 0}
        observations = []
        expected_observations = []
        seen = []
        expected_seen = []
        entry = {
            "slot": index,
            "pending": pending,
            "record": record,
            "raw": raw,
            "proposal": proposal,
            "conversion_error": conversion_error,
            "counts": counts,
            "expected_counts": expected_counts,
            "observations": observations,
            "expected_observations": expected_observations,
            "seen": seen,
            "expected_seen": expected_seen,
            "proposal_graph_before": _graph(proposal),
        }
        reserved = _step(
            call_state="entered", record_state="reserved", attempts=1, pending_record=pending
        )
        outcome_step = _step(
            call_state=outcome,
            record_state="reserved",
            attempts=1,
            pending_record=pending,
            raw_return=raw if outcome == "returned" else None,
            raw_error=raw if outcome == "raised" else None,
        )
        entered_view = self.expected_with(index, reserved, in_progress=True)
        outcome_view = self.expected_with(index, outcome_step, in_progress=True)

        def invoke():
            counts["invoke"] += 1
            if observe:
                observations.append(
                    {"phase": "invoke", "view": self.module.inspect_owner(self.owner)}
                )
            if reentrant is not None and reentrant[0] == "invoke":
                reentrant[1]()
            if escaped is not None and escaped[0] == "invoke":
                raise escaped[1]
            if outcome == "raised":
                raise raw
            return raw

        def convert(call_state, raw_object):
            counts["convert"] += 1
            seen.append({"call_state": call_state, "raw": raw_object})
            if observe:
                observations.append(
                    {"phase": "convert", "view": self.module.inspect_owner(self.owner)}
                )
            if reentrant is not None and reentrant[0] == "convert":
                reentrant[1]()
            if escaped is not None and escaped[0] == "convert":
                raise escaped[1]
            if mode == "exception":
                raise conversion_error
            return proposal

        entry.update(
            invoke=invoke, convert=convert, entered_view=entered_view, outcome_view=outcome_view
        )
        self.functions[id(invoke)] = {
            "factory": "invoke",
            "slot": index,
            "outcome": outcome,
            "raw": raw,
            "counts": counts,
            "observations": observations,
            "escaped": None if escaped is None else escaped[1],
            "owner": self.owner,
            "reentrant_callback": None if reentrant is None else reentrant[1],
        }
        self.functions[id(convert)] = {
            "factory": "convert",
            "slot": index,
            "mode": mode,
            "proposal": proposal,
            "counts": counts,
            "seen": seen,
            "observations": observations,
            "conversion_error": conversion_error,
            "escaped": None if escaped is None else escaped[1],
            "owner": self.owner,
            "reentrant_callback": None if reentrant is None else reentrant[1],
        }
        self.calls.append(entry)
        self.records.extend(((pending, copy.deepcopy(pending)), (record, copy.deepcopy(record))))
        return entry

    def run(
        self,
        index,
        *,
        outcome="returned",
        mode="complete",
        phase=None,
        proposal=None,
        raw=None,
        observe=True,
        escaped=None,
        reentrant=None,
        none_return=False,
        conversion_error=None,
        cut_sentinel=None,
    ):
        entry = self.fakes(
            index,
            outcome=outcome,
            mode=mode,
            proposal=proposal,
            raw=raw,
            observe=observe,
            escaped=escaped,
            reentrant=reentrant,
            none_return=none_return,
            conversion_error=conversion_error,
        )
        sentinel = (
            (_Resource("cut:" + str(phase)) if cut_sentinel is None else cut_sentinel)
            if phase is not None
            else None
        )
        cut = None if phase is None else (phase, sentinel)
        entry["cut"] = cut
        entry["expected_counts"]["invoke"] = 0 if phase == "before_entry" else 1
        calls_convert = phase not in ("before_entry", "after_outcome")
        entry["expected_counts"]["convert"] = int(calls_convert)
        if observe and phase != "before_entry":
            entry["expected_observations"].append(
                {"phase": "invoke", "view": entry["entered_view"]}
            )
        if calls_convert:
            entry["expected_seen"].append({"call_state": outcome, "raw": entry["raw"]})
            if observe:
                entry["expected_observations"].append(
                    {"phase": "convert", "view": entry["outcome_view"]}
                )
        if observe:
            _capture(
                "OWNER_OPERATION_INPUT_GRAPH",
                _graph(
                    {
                        "owner": self.owner,
                        "prior_expected_view": self.expected,
                        "carrier": self.carrier,
                        "pending": entry["pending"],
                        "invoke": entry["invoke"],
                        "convert": entry["convert"],
                        "cut": cut,
                    },
                    self.functions,
                    self.owner,
                ),
            )
        if index == -1:
            result = _api(
                self.module,
                "run_constructor",
                self.owner,
                entry["pending"],
                entry["invoke"],
                entry["convert"],
                cut=cut,
            )
            self.expected_initialization.append(entry["pending"])
        else:
            result = _api(
                self.module,
                "run_lookup",
                self.owner,
                oracle.APIS[index],
                entry["pending"],
                entry["invoke"],
                entry["convert"],
                cut=cut,
            )
            self.expected_bindings.append(entry["pending"])
        if observe:
            _capture(
                "OWNER_OPERATION_ACTUAL_GRAPH",
                _graph(
                    {
                        "result": result,
                        "view": self.view(),
                        "carrier": self.carrier,
                        "counts": entry["counts"],
                        "observations": entry["observations"],
                        "seen": entry["seen"],
                        "invoke": entry["invoke"],
                        "convert": entry["convert"],
                    },
                    self.functions,
                    self.owner,
                ),
            )
        if escaped is not None:
            raise AssertionError("safe BaseException was swallowed")
        step = _step(pending_record=entry["pending"])
        next_lookup = self.expected["next_lookup"]
        stopped = True
        if phase == "before_entry":
            step.update(record_state="unqualified", reason="cut_before_entry", cut_ref=sentinel)
        else:
            step.update(
                call_state=outcome,
                record_state="unqualified",
                attempts=1,
                raw_return=entry["raw"] if outcome == "returned" else None,
                raw_error=entry["raw"] if outcome == "raised" else None,
            )
            if phase == "after_outcome":
                step.update(reason="cut_after_outcome", cut_ref=sentinel)
            elif mode == "exception":
                step.update(
                    reason="conversion_exception", conversion_error=entry["conversion_error"]
                )
            else:
                step["conversion_result"] = entry["proposal"]
                if mode in ("unsupported", "oversize", "conversion_protocol"):
                    step["reason"] = mode
                elif phase == "before_commit":
                    step.update(reason="cut_before_commit", cut_ref=sentinel)
                else:
                    committed = entry["proposal"][1]
                    step.update(record_state="committed", committed_record=committed)
                    if index == -1:
                        self.expected_initialization[-1] = committed
                    else:
                        self.expected_bindings[-1] = committed
                    if outcome == "returned":
                        stopped = False
                        if index >= 0:
                            next_lookup += 1
                    else:
                        step["reason"] = "complete_error"
                    if phase == "after_commit":
                        step.update(reason="cut_after_commit", cut_ref=sentinel)
                        stopped = True
        self.expected = self.expected_with(
            index, step, in_progress=False, stopped=stopped, next_lookup=next_lookup
        )
        _capture("OWNER_STEP_EXPECTED", _graph(step, self.functions, self.owner))
        _capture("OWNER_STEP_ACTUAL", _graph(result, self.functions, self.owner))
        _exact(result, step)
        return entry

    def finish(self, *, check_carrier=True):
        actual = self.view()
        paths = self.selected()
        _capture(
            "OWNER_SUPPLIED_GRAPH",
            _graph(
                {
                    "original_carrier": self.carrier,
                    "original_initialization_array": self.initialization,
                    "original_binding_array": self.bindings,
                    "callbacks": [[c["invoke"], c["convert"]] for c in self.calls],
                    "pending_records": [c["pending"] for c in self.calls],
                    "proposals": [c["proposal"] for c in self.calls],
                    "raw_outcomes": [c["raw"] for c in self.calls],
                },
                self.functions,
                self.owner,
            ),
        )
        complete = (
            self.expected["next_lookup"] == 33
            and self.expected["stopped"] is False
            and self.expected["in_progress"] is False
        )
        expected_paths = oracle.expected_paths(complete)
        actual_calls = [
            {
                "slot": c["slot"],
                "counts": c["counts"],
                "seen": c["seen"],
                "observations": c["observations"],
            }
            for c in self.calls
        ]
        expected_calls = [
            {
                "slot": c["slot"],
                "counts": c["expected_counts"],
                "seen": c["expected_seen"],
                "observations": c["expected_observations"],
            }
            for c in self.calls
        ]
        expected_carrier = (
            {
                "initialization": self.expected_initialization,
                "binding_initialization": self.expected_bindings,
            }
            if check_carrier
            else self.carrier
        )
        expected_frame = {
            "view": self.expected,
            "paths": expected_paths,
            "carrier": expected_carrier,
            "calls": expected_calls,
        }
        actual_frame = {
            "view": actual,
            "paths": paths,
            "carrier": self.carrier,
            "calls": actual_calls,
        }
        _capture("OWNER_EXPECTED", _graph(expected_frame, self.functions, self.owner))
        _capture("OWNER_ACTUAL", _graph(actual_frame, self.functions, self.owner))
        _exact(actual, self.expected)
        _exact(paths, expected_paths)
        _exact(actual_calls, expected_calls)
        if check_carrier:
            if (
                self.carrier["initialization"] is not self.initialization
                or self.carrier["binding_initialization"] is not self.bindings
            ):
                raise AssertionError("caller array identity was replaced")
            for actual_rows, wanted in (
                (self.initialization, self.expected_initialization),
                (self.bindings, self.expected_bindings),
            ):
                if len(actual_rows) != len(wanted):
                    raise AssertionError("caller array complete row count mismatch")
                for actual_row, wanted_row in zip(actual_rows, wanted, strict=True):
                    if actual_row is not wanted_row:
                        raise AssertionError("caller array exact row identity mismatch")
        for record, before in self.records:
            _exact(record, before)
        for entry in self.calls:
            _exact(_graph(entry["proposal"]), entry["proposal_graph_before"])
        _exact(_HOOKS, [])


def _prefix(module, count, scenario):
    case = _Case(module, scenario)
    case.run(-1, observe=count == 0)
    for index in range(count):
        case.run(index, observe=index == count - 1)
    return case


def _prepare(module, index, scenario):
    return _Case(module, scenario) if index == -1 else _prefix(module, index, scenario)


def _raw_run(case, operation, pending, invoke, convert, cut=None, name=None):
    if operation == "constructor":
        return _api(case.module, "run_constructor", case.owner, pending, invoke, convert, cut=cut)
    return _api(
        case.module,
        "run_lookup",
        case.owner,
        oracle.APIS[0] if name is None else name,
        pending,
        invoke,
        convert,
        cut=cut,
    )


def _refuse(case, operation, pending, invoke, convert, reason, cut=None, name=None):
    _capture(
        "OWNER_RUN_GUARD_INPUT",
        _graph(
            {
                "owner": case.owner,
                "operation": operation,
                "api_name": name,
                "pending": pending,
                "invoke": invoke,
                "convert": convert,
                "cut": cut,
            },
            case.functions,
            case.owner,
        ),
    )
    before = _graph({"view": case.view(), "carrier": case.carrier}, case.functions, case.owner)
    _capture("OWNER_REFUSAL_EXPECTED", {"reason": reason, "before": before})
    refusal = None
    try:
        returned = _raw_run(case, operation, pending, invoke, convert, cut=cut, name=name)
    except case.module.OwnerRefusal as error:
        refusal = error
        _exact(type(error.reason), str)
        _exact(error.reason, reason)
    else:
        _capture(
            "OWNER_REFUSAL_UNEXPECTED_RETURN",
            _graph(
                {
                    "returned": returned,
                    "view": case.view(),
                    "carrier": case.carrier,
                    "all_declared_calls": case.calls,
                },
                case.functions,
                case.owner,
            ),
        )
        raise AssertionError("bootstrap owner refusal missing")
    after = _graph({"view": case.view(), "carrier": case.carrier}, case.functions, case.owner)
    _capture("OWNER_REFUSAL_ACTUAL", {"reason": refusal.reason, "after": after})
    _exact(after, before)
    return refusal


def _plain_refusal(module, operation, args, reason):
    _HOOKS.clear()
    before = _graph(list(args))
    _capture("OWNER_GUARD_INPUT", {"operation": operation, "graph": before})
    _capture("OWNER_GUARD_EXPECTED", {"reason": reason})
    try:
        _api(module, operation, *args)
    except module.OwnerRefusal as error:
        actual = {"reason": error.reason}
    else:
        raise AssertionError("bootstrap owner refusal missing")
    _capture("OWNER_GUARD_ACTUAL", actual)
    _exact(actual, {"reason": reason})
    after = _graph(list(args))
    _capture("OWNER_GUARD_AFTER", after)
    _exact(after, before)
    _exact(_HOOKS, [])


def test_publication_retains_original_arrays_and_all_initial_slots(owner_module):
    case = _Case(owner_module, "publication")
    _exact(case.view(), oracle.expected_owner())
    _exact(case.selected(), oracle.expected_paths(False))
    case.run(-1)
    case.run(0)
    case.finish()


@pytest.mark.parametrize(
    "count", tuple(range(34)), ids=tuple("lookups" + str(i).zfill(2) for i in range(34))
)
def test_supported_constructor_and_every_lookup_prefix(owner_module, count):
    case = _prefix(owner_module, count, "successful-prefix")
    case.finish()


@pytest.mark.parametrize(
    "index",
    tuple(range(-1, 33)),
    ids=("constructor",) + tuple("lookup" + str(i).zfill(2) for i in range(33)),
)
def test_complete_error_stops_at_each_source_slot(owner_module, index):
    case = _prepare(owner_module, index, "complete-error")
    case.run(index, outcome="raised")
    case.finish()


_FAILURE_CASES = tuple(
    (slot, outcome, mode)
    for slot in _POSITIONS
    for outcome in ("returned", "raised")
    for mode in ("unsupported", "oversize", "exception")
)


@pytest.mark.parametrize(
    "index,outcome,mode",
    _FAILURE_CASES,
    ids=tuple(_slot_label(s) + "-" + o + "-" + m for s, o, m in _FAILURE_CASES),
)
def test_conversion_failure_retains_raw_outcome(owner_module, index, outcome, mode):
    case = _prepare(owner_module, index, "conversion-failure")
    case.run(index, outcome=outcome, mode=mode)
    case.finish()


@pytest.mark.parametrize("index", (-1, 0), ids=("constructor", "lookup00"))
def test_None_return_is_not_unentered(owner_module, index):
    case = _prepare(owner_module, index, "None-return")
    case.run(index, none_return=True)
    case.finish()


_CUT_CASES = tuple(
    (slot, phase, outcome)
    for slot in _POSITIONS
    for phase, outcome in (
        ("before_entry", "returned"),
        ("after_outcome", "returned"),
        ("after_outcome", "raised"),
        ("before_commit", "returned"),
        ("before_commit", "raised"),
        ("after_commit", "returned"),
        ("after_commit", "raised"),
    )
)


@pytest.mark.parametrize(
    "index,phase,outcome",
    _CUT_CASES,
    ids=tuple(_slot_label(s) + "-" + p + "-" + o for s, p, o in _CUT_CASES),
)
def test_all_reached_synchronous_cuts_keep_exact_retained_state(
    owner_module, index, phase, outcome
):
    case = _prepare(owner_module, index, "synchronous-cut")
    case.run(index, outcome=outcome, phase=phase)
    case.finish()


_PROTOCOL_IDS = (
    "list",
    "tuple1",
    "tuple3",
    "tuplesubclass",
    "status_subclass",
    "status_hostile",
    "status_unknown",
    "record_pending",
    "record_subclass",
    "success_raised",
    "error_returned",
    "unsupported_record",
    "error_none",
    "oversize_record",
)


def _bad_proposal(identity, pending, record):
    table = {
        "list": ["complete_success", record],
        "tuple1": ("complete_success",),
        "tuple3": ("complete_success", record, None),
        "tuplesubclass": _Tuple(("complete_success", record)),
        "status_subclass": (_String("complete_success"), record),
        "status_hostile": (_Hostile(), record),
        "status_unknown": ("unknown", record),
        "record_pending": ("complete_success", pending),
        "record_subclass": ("complete_success", _Dictionary(record)),
        "success_raised": ("complete_success", record),
        "error_returned": ("complete_error", record),
        "unsupported_record": ("unsupported", record),
        "error_none": ("complete_error", None),
        "oversize_record": ("oversize", record),
    }
    return table[identity]


@pytest.mark.parametrize(
    "index,identity",
    tuple((s, p) for s in (-1, 16) for p in _PROTOCOL_IDS),
    ids=tuple(_slot_label(s) + "-" + p for s in (-1, 16) for p in _PROTOCOL_IDS),
)
def test_conversion_protocol_refuses_malformed_proposals_without_retry(
    owner_module, index, identity
):
    case = _prepare(owner_module, index, "conversion-protocol")
    outcome = "raised" if identity in ("success_raised", "error_none") else "returned"
    pending = oracle.pending_record(index)
    record = oracle.committed_record(index, outcome)
    proposal = _bad_proposal(identity, pending, record)
    entry = case.fakes(
        index,
        outcome=outcome,
        mode="conversion_protocol",
        proposal=proposal,
        pending=pending,
        record=record,
        observe=True,
    )
    _HOOKS.clear()
    _capture(
        "OWNER_OPERATION_INPUT_GRAPH",
        _graph(
            {
                "owner": case.owner,
                "prior_expected_view": case.expected,
                "carrier": case.carrier,
                "pending": entry["pending"],
                "invoke": entry["invoke"],
                "convert": entry["convert"],
            },
            case.functions,
            case.owner,
        ),
    )
    result = _raw_run(
        case,
        "constructor" if index == -1 else "lookup",
        entry["pending"],
        entry["invoke"],
        entry["convert"],
        name=None if index == -1 else oracle.APIS[index],
    )
    entry["expected_counts"].update(invoke=1, convert=1)
    entry["expected_seen"].append({"call_state": outcome, "raw": entry["raw"]})
    entry["expected_observations"].extend(
        (
            {"phase": "invoke", "view": entry["entered_view"]},
            {"phase": "convert", "view": entry["outcome_view"]},
        )
    )
    step = _step(
        call_state=outcome,
        record_state="unqualified",
        attempts=1,
        pending_record=entry["pending"],
        conversion_result=entry["proposal"],
        raw_return=entry["raw"] if outcome == "returned" else None,
        raw_error=entry["raw"] if outcome == "raised" else None,
        reason="conversion_protocol",
    )
    if index == -1:
        case.expected_initialization.append(entry["pending"])
    else:
        case.expected_bindings.append(entry["pending"])
    case.expected = case.expected_with(index, step, in_progress=False, stopped=True)
    _capture("OWNER_STEP_EXPECTED", _graph(step, case.functions, case.owner))
    _capture("OWNER_STEP_ACTUAL", _graph(result, case.functions, case.owner))
    _capture(
        "OWNER_OPERATION_ACTUAL_GRAPH",
        _graph(
            {
                "result": result,
                "view": case.view(),
                "carrier": case.carrier,
                "counts": entry["counts"],
                "observations": entry["observations"],
                "seen": entry["seen"],
            },
            case.functions,
            case.owner,
        ),
    )
    _exact(result, step)
    case.finish()


_OWNER_OPERATIONS = ("run_constructor", "run_lookup", "inspect_owner", "select_paths")


@pytest.mark.parametrize(
    "operation,bad",
    tuple((op, b) for op in _OWNER_OPERATIONS for b in ("None", "dict", "hostile", "metaclass")),
    ids=tuple(
        op + "-" + b for op in _OWNER_OPERATIONS for b in ("None", "dict", "hostile", "metaclass")
    ),
)
def test_invalid_owner_domain_refuses_without_hooks(owner_module, operation, bad):
    value = {"None": None, "dict": {}, "hostile": _Hostile(), "metaclass": _TrapClass}[bad]
    if operation in ("inspect_owner", "select_paths"):
        args = (value,)
    else:
        # A valid exact function is never called; no framework fixture owns a helper call.
        def forbidden():
            _HOOKS.append("forbidden")
            raise AssertionError("invalid owner invoked callback")

        args = (
            (value, oracle.pending_record(), forbidden, forbidden)
            if operation == "run_constructor"
            else (value, oracle.APIS[0], oracle.pending_record(0), forbidden, forbidden)
        )
        # Capture this closed forbidden function as a declared factory, without globals.
        declaration = {id(forbidden): {"factory": "forbidden", "hooks": _HOOKS}}
        _HOOKS.clear()
        before = _graph(args, declaration)
        _capture("OWNER_GUARD_INPUT", {"operation": operation, "complete_args": before})
        _capture("OWNER_GUARD_EXPECTED", {"reason": "owner"})
        try:
            _api(owner_module, operation, *args)
        except owner_module.OwnerRefusal as error:
            _capture("OWNER_GUARD_ACTUAL", {"reason": error.reason})
            _exact(error.reason, "owner")
        else:
            raise AssertionError("bootstrap owner refusal missing")
        after = _graph(args, declaration)
        _capture("OWNER_GUARD_AFTER", after)
        _exact(after, before)
        _exact(_HOOKS, [])
        return
    _plain_refusal(owner_module, operation, args, "owner")


_CARRIER_IDS = (
    "not_dict",
    "dict_subclass",
    "missing",
    "extra",
    "key_subclass",
    "key_hostile",
    "init_tuple",
    "binding_tuple",
    "same_lists",
    "init_nonempty",
    "binding_nonempty",
    "wrong_both",
)


@pytest.mark.parametrize("identity", _CARRIER_IDS, ids=_CARRIER_IDS)
def test_new_owner_carrier_admission_and_guard_precedence(owner_module, identity):
    carrier = {"initialization": [], "binding_initialization": []}
    if identity == "not_dict":
        carrier = None
    elif identity == "dict_subclass":
        carrier = _Dictionary(carrier)
    elif identity == "missing":
        del carrier["initialization"]
    elif identity == "extra":
        carrier["extra"] = []
    elif identity == "key_subclass":
        carrier = {_String("initialization"): [], "binding_initialization": []}
    elif identity == "key_hostile":
        carrier = {_Hostile(): [], "binding_initialization": []}
    elif identity == "init_tuple":
        carrier["initialization"] = ()
    elif identity == "binding_tuple":
        carrier["binding_initialization"] = ()
    elif identity == "same_lists":
        carrier["binding_initialization"] = carrier["initialization"]
    elif identity == "init_nonempty":
        carrier["initialization"].append({})
    elif identity == "binding_nonempty":
        carrier["binding_initialization"].append({})
    elif identity == "wrong_both":
        carrier = {"wrong": [None], "keys": [None]}
    _plain_refusal(owner_module, "new_owner", (carrier,), "carrier")


_IDENTITY_MUTATIONS = ("replace_init", "replace_bindings", "clone_row", "extra_row", "remove_row")


@pytest.mark.parametrize(
    "operation,mutation",
    tuple((op, m) for op in ("constructor", "lookup") for m in _IDENTITY_MUTATIONS),
    ids=tuple(op + "-" + m for op in ("constructor", "lookup") for m in _IDENTITY_MUTATIONS),
)
def test_run_carrier_identity_precedes_order_and_never_coerces(owner_module, operation, mutation):
    case = _prefix(owner_module, 1, "carrier-identity")
    if mutation == "replace_init":
        case.carrier["initialization"] = list(case.initialization)
    elif mutation == "replace_bindings":
        case.carrier["binding_initialization"] = list(case.bindings)
    elif mutation == "clone_row":
        case.bindings[0] = dict(case.bindings[0])
    elif mutation == "extra_row":
        case.bindings.append(oracle.pending_record(1))
    elif mutation == "remove_row":
        case.bindings.pop()
    entry = case.fakes(-1 if operation == "constructor" else 1)
    _refuse(
        case,
        operation,
        entry["pending"],
        entry["invoke"],
        entry["convert"],
        "carrier",
        name=oracle.APIS[1],
    )
    case.finish(check_carrier=False)


@pytest.mark.parametrize(
    "operation,bad",
    tuple((op, b) for op in ("constructor", "lookup") for b in ("none", "list", "subclass")),
    ids=tuple(
        op + "-" + b for op in ("constructor", "lookup") for b in ("none", "list", "subclass")
    ),
)
def test_pending_dict_guard_precedes_callback_cut_and_order(owner_module, operation, bad):
    case = _prefix(owner_module, 0, "pending-guard")
    pending = {"none": None, "list": [], "subclass": _Dictionary()}[bad]
    hostile = _Hostile()
    _refuse(case, operation, pending, hostile, hostile, "pending_record", cut=["invalid"])
    case.finish()


@pytest.mark.parametrize(
    "operation,which,bad",
    tuple(
        (op, w, b)
        for op in ("constructor", "lookup")
        for w in ("invoke", "convert")
        for b in ("callable", "builtin", "method")
    ),
    ids=tuple(
        op + "-" + w + "-" + b
        for op in ("constructor", "lookup")
        for w in ("invoke", "convert")
        for b in ("callable", "builtin", "method")
    ),
)
def test_function_callbacks_are_exact_and_guard_before_cut(owner_module, operation, which, bad):
    case = _prefix(owner_module, 0, "callback-guard")
    entry = case.fakes(-1 if operation == "constructor" else 0)
    bad_callback = {"callable": _Hostile(), "builtin": len, "method": _MethodHolder().method}[bad]
    invoke = bad_callback if which == "invoke" else entry["invoke"]
    convert = bad_callback if which == "convert" else entry["convert"]
    _refuse(case, operation, entry["pending"], invoke, convert, "callback", cut=["bad"])
    case.finish()


_BAD_CUT_IDS = (
    "list",
    "tuple1",
    "tuple3",
    "tuple_subclass",
    "phase_subclass",
    "phase_hostile",
    "phase_unknown",
)


@pytest.mark.parametrize(
    "operation,identity",
    tuple((op, c) for op in ("constructor", "lookup") for c in _BAD_CUT_IDS),
    ids=tuple(op + "-" + c for op in ("constructor", "lookup") for c in _BAD_CUT_IDS),
)
def test_cut_guard_precedes_stopped_and_order(owner_module, operation, identity):
    case = _Case(owner_module, "cut-guard")
    case.run(-1, mode="unsupported")
    entry = case.fakes(-1 if operation == "constructor" else 0)
    sentinel = _Resource("unused-cut")
    cuts = {
        "list": ["before_entry", sentinel],
        "tuple1": ("before_entry",),
        "tuple3": ("before_entry", sentinel, None),
        "tuple_subclass": _Tuple(("before_entry", sentinel)),
        "phase_subclass": (_String("before_entry"), sentinel),
        "phase_hostile": (_Hostile(), sentinel),
        "phase_unknown": ("unknown", sentinel),
    }
    _refuse(
        case,
        operation,
        entry["pending"],
        entry["invoke"],
        entry["convert"],
        "cut",
        cut=cuts[identity],
    )
    case.finish()


@pytest.mark.parametrize(
    "bad", ("subclass", "hostile", "none"), ids=("subclass", "hostile", "none")
)
def test_lookup_name_is_exact_before_value_or_order(owner_module, bad):
    case = _prefix(owner_module, 0, "lookup-name")
    entry = case.fakes(0)
    name = {"subclass": _String(oracle.APIS[0]), "hostile": _Hostile(), "none": None}[bad]
    _capture(
        "OWNER_RUN_GUARD_INPUT",
        _graph(
            {
                "owner": case.owner,
                "api_name": name,
                "pending": entry["pending"],
                "invoke": entry["invoke"],
                "convert": entry["convert"],
            },
            case.functions,
            case.owner,
        ),
    )
    # None must be submitted literally, not the _raw_run convenience default.
    before = _graph({"view": case.view(), "carrier": case.carrier}, case.functions, case.owner)
    _capture("OWNER_REFUSAL_EXPECTED", {"reason": "order", "before": before})
    try:
        _api(
            owner_module,
            "run_lookup",
            case.owner,
            name,
            entry["pending"],
            entry["invoke"],
            entry["convert"],
        )
    except owner_module.OwnerRefusal as error:
        _capture("OWNER_GUARD_ACTUAL", {"reason": error.reason})
        _exact(error.reason, "order")
    else:
        raise AssertionError("bootstrap owner refusal missing")
    after = _graph({"view": case.view(), "carrier": case.carrier}, case.functions, case.owner)
    _capture("OWNER_REFUSAL_ACTUAL", {"reason": "order", "after": after})
    _exact(after, before)
    case.finish()


_ORDER_IDS = (
    "before_constructor",
    "duplicate_constructor",
    "wrong_lookup",
    "duplicate_lookup",
    "stopped_constructor",
    "stopped_lookup",
    "completed_constructor",
    "completed_lookup",
)


@pytest.mark.parametrize("identity", _ORDER_IDS, ids=_ORDER_IDS)
def test_operation_order_and_stopped_gates_never_invoke_again(owner_module, identity):
    if identity == "before_constructor":
        case = _Case(owner_module, identity)
        operation = "lookup"
        index = 0
        reason = "order"
    elif identity.startswith("stopped"):
        case = _Case(owner_module, identity)
        case.run(-1, mode="unsupported")
        operation = "constructor" if identity.endswith("constructor") else "lookup"
        index = -1 if operation == "constructor" else 0
        reason = "stopped"
    elif identity.startswith("completed"):
        case = _prefix(owner_module, 33, identity)
        operation = "constructor" if identity.endswith("constructor") else "lookup"
        index = -1 if operation == "constructor" else 32
        reason = "order"
    elif identity == "duplicate_lookup":
        case = _prefix(owner_module, 1, identity)
        operation = "lookup"
        index = 0
        reason = "order"
    else:
        case = _prefix(owner_module, 0, identity)
        operation = "constructor" if identity == "duplicate_constructor" else "lookup"
        index = -1 if operation == "constructor" else 1
        reason = "order"
    entry = case.fakes(index)
    _refuse(
        case,
        operation,
        entry["pending"],
        entry["invoke"],
        entry["convert"],
        reason,
        name=None if index == -1 else oracle.APIS[index],
    )
    case.finish()


@pytest.mark.parametrize(
    "phase,nested",
    tuple((p, o) for p in ("invoke", "convert") for o in ("constructor", "lookup")),
    ids=tuple(p + "-" + o for p in ("invoke", "convert") for o in ("constructor", "lookup")),
)
def test_reentrant_operations_refuse_inside_invoke_and_convert(owner_module, phase, nested):
    case = _Case(owner_module, "reentrant")
    nested_calls = {"entered": 0}
    nested_pending = oracle.pending_record(-1 if nested == "constructor" else 0)

    def forbidden(*args):
        nested_calls["entered"] += 1
        raise AssertionError("reentrant fake must never run")

    def attempt():
        try:
            _raw_run(case, nested, nested_pending, forbidden, forbidden)
        except owner_module.OwnerRefusal as error:
            if error.reason != "reentrant":
                raise AssertionError("wrong reentrant refusal") from error
        else:
            raise AssertionError("reentrant refusal absent")

    case.functions[id(forbidden)] = {"factory": "reentrant-forbidden", "counts": nested_calls}
    case.functions[id(attempt)] = {
        "factory": "reentrant-attempt",
        "owner": case.owner,
        "pending": nested_pending,
        "forbidden": forbidden,
        "counts": nested_calls,
    }
    case.run(-1, reentrant=(phase, attempt))
    _capture("OWNER_REENTRANT_COUNTER", nested_calls)
    _exact(nested_calls, {"entered": 0})
    case.finish()


@pytest.mark.parametrize(
    "phase,index",
    tuple((p, i) for p in ("invoke", "convert") for i in (-1, 16)),
    ids=tuple(p + "-" + _slot_label(i) for p in ("invoke", "convert") for i in (-1, 16)),
)
def test_safe_BaseException_propagates_without_fabricated_commit(owner_module, phase, index):
    case = _prepare(owner_module, index, "excluded-BaseException")
    escaped = _Escaped("safe excluded sentinel")
    entry = case.fakes(index, escaped=(phase, escaped), observe=True)
    try:
        _raw_run(
            case,
            "constructor" if index == -1 else "lookup",
            entry["pending"],
            entry["invoke"],
            entry["convert"],
            name=None if index == -1 else oracle.APIS[index],
        )
    except _Escaped as caught:
        if caught is not escaped:
            raise AssertionError("safe BaseException exact identity lost") from caught
    else:
        raise AssertionError("safe BaseException was swallowed")
    view = case.view()
    slot = view["constructor"] if index == -1 else view["lookups"][index]
    _capture(
        "OWNER_EXCLUDED_CONSTRAINTS",
        {
            "same_escaped_reference": True,
            "no_fabricated_commit": True,
            "no_retry": {"invoke": 1, "convert": int(phase == "convert")},
            "record_state_cleanup_transition": "not promised",
        },
    )
    _capture(
        "OWNER_EXCLUDED_ACTUAL",
        _graph(
            {
                "view": view,
                "carrier": case.carrier,
                "entry": {
                    "counts": entry["counts"],
                    "observations": entry["observations"],
                    "seen": entry["seen"],
                    "pending": entry["pending"],
                    "escaped": escaped,
                    "invoke": entry["invoke"],
                    "convert": entry["convert"],
                    "proposal": entry["proposal"],
                    "raw": entry["raw"],
                },
                "paths": case.selected(),
            },
            case.functions,
            case.owner,
        ),
    )
    if slot["committed_record"] is not None or slot["record_state"] == "committed":
        raise AssertionError("excluded BaseException fabricated committed observation")
    _exact(entry["counts"], {"invoke": 1, "convert": int(phase == "convert")})
    _exact(case.selected(), oracle.expected_paths(False))
    # No reserved->unqualified, stopped or in_progress final-state guarantee is invented.
    _exact(_HOOKS, [])


def test_inspection_views_do_not_mutate_owner_scalars(owner_module):
    case = _prefix(owner_module, 0, "view-copy")
    view = case.view()
    view["next_lookup"] = 99
    view["constructor"]["call_state"] = "fabricated"
    view["lookups"][0]["reason"] = "fabricated"
    case.finish()


def _declared_reference_fixture():
    library = _Resource("library")
    callable_ref = _Resource("callable")
    shared = ["shared"]
    cause = _FakeError("cause")
    context = _FakeError("context")
    primary = _FakeError("primary")
    primary.shared = shared
    primary.library = library
    primary.__notes__ = ["note"]
    primary.__cause__ = cause
    primary.__context__ = context
    conversion = _FakeError("conversion")
    conversion.original = primary
    conversion.shared = shared
    cut = _Resource("cut")
    cut.shared = shared
    return [library, callable_ref, primary, conversion, cut]


def _assert_declared_graph(fixture, index, variant, phase, *, allow_primary_context=False):
    allowed = [oracle.DECLARED_REFERENCE_GRAPH]
    if allow_primary_context:
        allowed.append(oracle.DECLARED_REFERENCE_GRAPH_WITH_PRIMARY_CONTEXT)
    actual = _graph(fixture)
    _capture(
        "OWNER_DECLARED_GRAPH_EXPECTED",
        {
            "slot": index,
            "variant": variant,
            "phase": phase,
            "allowed_complete_graphs": allowed,
        },
    )
    _capture(
        "OWNER_DECLARED_GRAPH_ACTUAL",
        {
            "slot": index,
            "variant": variant,
            "phase": phase,
            "complete_graph": actual,
        },
    )
    for expected in allowed:
        try:
            _exact(actual, expected)
        except AssertionError:
            continue
        break
    else:
        raise AssertionError("declared raw-reference graph changed outside exact allowed literals")


@pytest.mark.parametrize("index", (-1, 0), ids=("constructor", "lookup00"))
def test_raw_reference_and_record_body_are_not_walked_or_mutated(owner_module, index):
    for variant in ("success", "raised-primary", "raised-primary-conversion-error", "reached-cut"):
        case = _prepare(owner_module, index, "declared-fake-graph:" + variant)
        fixture = _declared_reference_fixture()
        _assert_declared_graph(fixture, index, variant, "before")
        if variant == "success":
            case.run(index, raw=fixture[0] if index == -1 else fixture[1])
        elif variant == "raised-primary":
            case.run(index, outcome="raised", raw=fixture[2])
        elif variant == "raised-primary-conversion-error":
            case.run(
                index,
                outcome="raised",
                mode="exception",
                raw=fixture[2],
                conversion_error=fixture[3],
            )
        else:
            case.run(
                index,
                raw=fixture[0] if index == -1 else fixture[1],
                phase="before_commit",
                cut_sentinel=fixture[4],
            )
        case.finish()
        _assert_declared_graph(
            fixture,
            index,
            variant,
            "after",
            allow_primary_context=variant == "raised-primary-conversion-error",
        )


def test_refusal_reason_is_ordinary_mutable_attribute(owner_module):
    case = _prefix(owner_module, 0, "mutable-refusal")
    entry = case.fakes(-1)
    error = _refuse(
        case, "constructor", entry["pending"], entry["invoke"], entry["convert"], "order"
    )
    error.reason = "ordinary-test-change"
    _capture("OWNER_REFUSAL_MUTABILITY", {"reason": error.reason})
    _exact(error.reason, "ordinary-test-change")
    case.finish()


def test_conversion_is_trusted_not_a_P3_validator(owner_module):
    case = _Case(owner_module, "trusted-nonvalidator")
    pending = oracle.pending_record()
    record = oracle.committed_record()
    record["completed"] = False
    record["exposed_handle_u64"] = 0
    proposal = ("complete_success", record)
    counts = {"invoke": 0, "convert": 0}

    def invoke():
        counts["invoke"] += 1
        return None

    def convert(state, raw):
        counts["convert"] += 1
        return proposal

    case.functions[id(invoke)] = {"factory": "trusted-invalid-invoke", "counts": counts}
    case.functions[id(convert)] = {
        "factory": "trusted-invalid-convert",
        "proposal": proposal,
        "counts": counts,
    }
    _capture(
        "OWNER_SUPPLIED_GRAPH",
        _graph(
            {
                "pending": pending,
                "proposal": proposal,
                "invoke": invoke,
                "convert": convert,
            },
            case.functions,
            case.owner,
        ),
    )
    result = _api(owner_module, "run_constructor", case.owner, pending, invoke, convert)
    step = _step(
        call_state="returned",
        record_state="committed",
        attempts=1,
        pending_record=pending,
        committed_record=record,
        conversion_result=proposal,
    )
    case.expected_initialization.append(record)
    case.expected = case.expected_with(-1, step, in_progress=False, stopped=False)
    _capture(
        "OWNER_NONVALIDATOR_SCOPE",
        {"P3_semantics_validated": False, "fit_or_native_success_proved": False},
    )
    _capture("OWNER_STEP_EXPECTED", _graph(step, case.functions, case.owner))
    _capture("OWNER_STEP_ACTUAL", _graph(result, case.functions, case.owner))
    _exact(result, step)
    _exact(counts, {"invoke": 1, "convert": 1})
    case.finish()
