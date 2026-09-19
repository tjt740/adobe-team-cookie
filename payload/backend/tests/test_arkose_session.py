import base64
import json

import pytest

from app.services.arkose_session import (
    HarvestSeed,
    UnknownQuestion,
    not_retryable,
    solve_session,
)
from app.services.arkose_session.classify import (
    classification_payload,
    parse_classification_solution,
    wave_index,
)
from app.services.arkose_session.crypt import decrypt_arkose, encrypt_arkose
from app.services.arkose_session.questions import (
    FALLBACK_COMMENT,
    YES_GENERIC_MATCHKEY,
    classification_question,
    official_yes_question,
    yes_question_known,
)
from app.services.arkose_session.solver import SessionSolver
from app.services.arkose_session.util import form_encode


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

TOKEN = (
    "abc.def|r=ap-southeast-1|pk=436DD567-5435-4B14-89A6-2F1188E11334|"
    "surl=https://arks-client.adobe.com|at=40"
)


def test_classification_payload_shape():
    data = classification_payload(b"png", "Pick the penguin")
    assert data["type"] == "FunCaptchaClassification"
    assert data["question"] == "Pick the penguin"
    assert "image" in data
    for ban in (
        "body", "imgType", "comment", "websitePublicKey", "websiteURL",
        "rows", "columns", "proxy", "softID",
    ):
        assert ban not in data


def test_parse_classification_objects_as_is():
    objects = parse_classification_solution(
        {"objects": [4], "labels": ["parrot", "panda", "octopus", "owl", "bread", "dog"]}
    )
    assert objects == [4]
    zero = parse_classification_solution({"objects": [0]})
    assert zero == [0]
    assert wave_index(objects) == 4


def test_parse_classification_rejects_token():
    with pytest.raises(Exception, match="token"):
        parse_classification_solution({"token": "sess|pk=x"})
    with pytest.raises(Exception, match="objects"):
        parse_classification_solution({"objects": []})


def test_classification_question_priority():
    claw = classification_question("claw_machine", "claw_machine")
    assert claw == (
        "find the image that has the prize on the left held by the claw "
        "in the machine on the right"
    )
    assert classification_question("Pick the penguin", "claw_machine") == "Pick the penguin"
    assert classification_question("diceico", "diceico") == official_yes_question("diceico")
    assert official_yes_question(YES_GENERIC_MATCHKEY) == ""
    assert classification_question(YES_GENERIC_MATCHKEY, "claw_machine") == official_yes_question(
        "claw_machine"
    )
    assert classification_question(YES_GENERIC_MATCHKEY, "hoople") == "hoople"
    assert not yes_question_known(YES_GENERIC_MATCHKEY)
    assert official_yes_question("hoople") == ""
    assert classification_question("hoople", "hoople") == "hoople"
    assert yes_question_known("hoople")
    human = "Use the arrows to match the hoop to the example on the left"
    assert classification_question(human, "hoople") == human
    assert not yes_question_known(FALLBACK_COMMENT)
    assert classification_question("no_such_variant", "") not in (
        FALLBACK_COMMENT, YES_GENERIC_MATCHKEY,
    )
    assert classification_question("", "") == ""


def test_encrypt_arkose_roundtrip():
    blob = encrypt_arkose('[{"index":4}]', "session-token")
    assert " " not in blob
    assert decrypt_arkose(blob, "session-token") == '[{"index":4}]'


def test_form_encode_percent_encodes_slash():
    body = form_encode("guess", "abc/def+g")
    assert "guess=abc%2Fdef%2Bg" == body


def test_solve_session_suppressed_skips_classify():
    def harvest(**kw):
        return HarvestSeed(
            token=TOKEN + "|sup=1",
            cookies=[{"name": "ARID", "value": "arid-1"}],
            arid="arid-1",
            suppressed=True,
        )

    res = solve_session(
        api_key="k", website_url="https://auth.services.adobe.com/", blob="BLOB",
        harvest_fn=harvest,
    )
    assert res.suppressed is True
    assert "sup=1" in res.token


def test_unknown_question_is_not_retryable():
    assert not_retryable(UnknownQuestion("hoople-generic"))
    assert not_retryable(RuntimeError("ERROR_ZERO_BALANCE"))
    assert not not_retryable(RuntimeError("answered but not solved"))


class _FakeHTTP:
    def __init__(self):
        self.calls = []

    def set_cookie(self, *a, **k):
        return None

    def do(self, method, url, body=None, headers=None):
        self.calls.append((method, url))
        if "/pows/setup" in url:
            return 400, b"no pow", {}
        if "/fc/gfct/" in url:
            game = {
                "session_token": "ch.tok",
                "challengeID": "gid",
                "game_data": {
                    "gameType": 4,
                    "waves": 1,
                    "game_difficulty": 5,
                    "instruction_string": "diceico",
                    "game_variant": "diceico",
                    "customGUI": {
                        "_challenge_imgs": ["https://arks-client.adobe.com/img/1"],
                    },
                },
            }
            return 200, json.dumps(game).encode(), {}
        if "/img/1" in url:
            return 200, TINY_PNG, {}
        if "/fc/ca/" in url:
            return 200, json.dumps({"response": "answered", "solved": True}).encode(), {}
        return 200, b"{}", {}


def test_session_continue_classifies_and_accepts_same_token():
    http = _FakeHTTP()
    seen = {}

    def classify(img, spec, tiles, instruction, variant, prev):
        seen["tiles"] = tiles
        seen["variant"] = variant
        seen["img"] = img[:8]
        return 4, "task-1"

    solver = SessionSolver(
        api_key="k", http=http, classify=classify,
        pow_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("pow should skip")),
        tguess_fn=lambda *a, **k: "",
    )
    seed = HarvestSeed(
        token=TOKEN, cookies=[{"name": "ARID", "value": "arid-1"}],
        arid="arid-1", pow=False,
    )
    res = solver.continue_session(seed)
    assert res.token == TOKEN
    assert res.suppressed is False
    assert seen["tiles"] == 5
    assert seen["variant"] == "diceico"
    assert any("/fc/gfct/" in u for _, u in http.calls)
    assert any("/fc/ca/" in u for _, u in http.calls)
    assert not any("/pows/check" in u for _, u in http.calls)
