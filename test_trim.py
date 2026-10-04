import pytest
from trim import trim


def m(i, role, tokens, **kw):
    return {"id": i, "role": role, "tokens": tokens, **kw}


def ids(msgs):
    return [x["id"] for x in msgs]


BASIC = [m(0, "system", 10), m(1, "user", 30), m(2, "assistant", 30),
         m(3, "user", 30), m(4, "assistant", 30)]


# part 1
def test_basic_fit():
    assert ids(trim(BASIC, 70)) == [0, 3, 4]

def test_one_short():
    assert ids(trim(BASIC, 69)) == [0, 4]

def test_no_skipping():
    msgs = [m(0, "system", 10), m(1, "user", 5), m(2, "assistant", 100), m(3, "user", 5)]
    assert ids(trim(msgs, 50)) == [0, 3]

def test_system_too_big():
    with pytest.raises(ValueError):
        trim(BASIC, 5)

def test_everything_fits():
    assert ids(trim(BASIC, 1000)) == [0, 1, 2, 3, 4]


# part 2
def test_pinned():
    msgs = [m(0, "system", 10), m(1, "user", 20, pinned=True), m(2, "assistant", 30),
            m(3, "user", 30), m(4, "assistant", 30)]
    assert ids(trim(msgs, 60)) == [0, 1, 4]


# part 3
def test_tool_pair():
    msgs = [m(0, "system", 10), m(1, "user", 10),
            m(2, "assistant", 10, tool_call_id="a"), m(3, "tool", 50, tool_call_id="a"),
            m(4, "assistant", 10)]
    assert ids(trim(msgs, 70)) == [0, 4]
