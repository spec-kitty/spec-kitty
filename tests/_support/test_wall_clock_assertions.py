from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.unit]

from tests._support.wall_clock_assertions import (
    _ImportAliasMetrics,
    _collect_import_aliases,
    _wall_clock_scan_result_authenticator,
    find_wall_clock_assertion_violations,
    find_wall_clock_assertion_violations_cached,
    find_test_python_paths,
    format_wall_clock_assertion_violations,
)

pytestmark = [pytest.mark.fast]


@pytest.mark.parametrize(
    ("source", "expected", "expected_line"),
    [
        ("from datetime import datetime\n\ndef test_bad():\n    assert value == datetime.now().isoformat()\n", "datetime.now()", 4),
        ("from datetime import datetime\n\ndef test_bad():\n    assert value == datetime.utcnow().isoformat()\n", "datetime.utcnow()", 4),
        ("from datetime import datetime\n\ndef test_bad():\n    assert value == datetime.today().isoformat()\n", "datetime.today()", 4),
        ("from datetime import date\n\ndef test_bad():\n    assert value == date.today().isoformat()\n", "date.today()", 4),
        ("import datetime\n\ndef test_bad():\n    assert value == datetime.datetime.now().isoformat()\n", "datetime.datetime.now()", 4),
        ("import datetime\n\ndef test_bad():\n    assert value == datetime.date.today().isoformat()\n", "datetime.date.today()", 4),
        ("import datetime\n\ndef test_bad():\n    assert value == datetime.datetime.today().isoformat()\n", "datetime.datetime.today()", 4),
        ("import time\n\ndef test_bad():\n    assert value < time.time()\n", "time.time()", 4),
        ("from datetime import datetime as dt\n\ndef test_bad():\n    assert value == dt.now().isoformat()\n", "dt.now()", 4),
        ("from datetime import datetime as dt\n\ndef test_bad():\n    assert value == dt.today().isoformat()\n", "dt.today()", 4),
        ("import datetime as dt_mod\n\ndef test_bad():\n    assert value == dt_mod.datetime.now().isoformat()\n", "dt_mod.datetime.now()", 4),
        ("from time import time as wall_time\n\ndef test_bad():\n    assert value < wall_time()\n", "wall_time()", 4),
        ("from datetime import datetime\n\nwall_now = datetime.now\n\ndef test_bad():\n    assert wall_now().year == 2026\n", "wall_now()", 6),
        ("from datetime import datetime\n\nwall_today = datetime.today\n\ndef test_bad():\n    assert wall_today().year == 2026\n", "wall_today()", 6),
        ("from datetime import datetime\n\ndef test_bad():\n    wall_now = datetime.now\n    assert wall_now().year == 2026\n", "wall_now()", 5),
        ("from time import *\n\ndef test_bad():\n    assert time() > 0\n", "time()", 4),
        ("from datetime import *\n\ndef test_bad():\n    assert datetime.now().year == 2026\n", "datetime.now()", 4),
        ("import datetime\n\ndt = datetime.datetime\n\ndef test_bad():\n    assert dt.now().year == 2026\n", "dt.now()", 6),
        ("from datetime import datetime\n\ndt = datetime\n\ndef test_bad():\n    assert dt.now().year == 2026\n", "dt.now()", 6),
        ("from datetime import datetime\n\ndt = datetime\n\ndef test_bad():\n    assert dt.today().year == 2026\n", "dt.today()", 6),
        ("from datetime import date\n\nd = date\n\ndef test_bad():\n    assert d.today().year == 2026\n", "d.today()", 6),
        ("from datetime import *\n\ndt = datetime\n\ndef test_bad():\n    assert dt.now().year == 2026\n", "dt.now()", 6),
        ("import time\n\ntm = time\n\ndef test_bad():\n    assert tm.time() > 0\n", "tm.time()", 6),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    pass\n\n"
            "Holder.wall_now = datetime.now\n\n"
            "def test_bad():\n"
            "    assert Holder.wall_now().year == 2026\n",
            "Holder.wall_now()",
            9,
        ),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    wall_now = datetime.now\n\n"
            "def test_bad():\n"
            "    assert Holder.wall_now().year == 2026\n",
            "Holder.wall_now()",
            7,
        ),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    wall_now = datetime.now\n\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n",
            "self.wall_now()",
            7,
        ),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    wall_now = datetime.now\n\n"
            "    @classmethod\n"
            "    def test_bad(cls):\n"
            "        assert cls.wall_now().year == 2026\n",
            "cls.wall_now()",
            8,
        ),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    wall_now = datetime.now\n\n"
            "    @staticmethod\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n",
            "self.wall_now()",
            8,
        ),
        ("from datetime import datetime\n\nwall_now, other = datetime.now, object()\n\ndef test_bad():\n    assert wall_now().year == 2026\n", "wall_now()", 6),
        (
            "from datetime import datetime\n\n"
            "def test_bad(wall_now=datetime.now):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            4,
        ),
        (
            "from datetime import datetime\n\n"
            "def wrapper(clock=datetime.now):\n"
            "    return clock()\n\n"
            "def test_bad():\n"
            "    assert wrapper().year == 2026\n",
            "wrapper()",
            7,
        ),
        (
            "from datetime import datetime\n\n"
            "def test_bad():\n"
            "    assert (wall_now := datetime.now)().year == 2026\n",
            "wall_now()",
            4,
        ),
        (
            "from datetime import datetime\n\n"
            "def test_bad():\n"
            "    assert (lambda wall_now=datetime.now: wall_now())().year == 2026\n",
            "wall_now()",
            4,
        ),
        (
            "from datetime import datetime\n\n"
            "def test_bad():\n"
            "    assert False, datetime.now().isoformat()\n",
            "datetime.now()",
            4,
        ),
        (
            "from datetime import datetime\n\n"
            "def test_bad():\n"
            "    assert (dt := datetime).now().year == 2026\n",
            "dt.now()",
            4,
        ),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    wall_now = staticmethod(datetime.now)\n\n"
            "def test_bad():\n"
            "    assert Holder.wall_now().year == 2026\n",
            "Holder.wall_now()",
            7,
        ),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    wall_now = staticmethod(datetime.now)\n\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n",
            "self.wall_now()",
            7,
        ),
        (
            "from datetime import datetime\n\n"
            "def setup_module():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            8,
        ),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    pass\n\n"
            "def setup_module():\n"
            "    Holder.wall_now = datetime.now\n\n"
            "def test_bad():\n"
            "    assert Holder.wall_now().year == 2026\n",
            "Holder.wall_now()",
            10,
        ),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    pass\n\n"
            "def setup_module():\n"
            "    setattr(Holder, 'wall_now', datetime.now)\n\n"
            "def test_bad():\n"
            "    assert Holder.wall_now().year == 2026\n",
            "Holder.wall_now()",
            10,
        ),
        (
            "from datetime import datetime\n\n"
            "class TestClock:\n"
            "    def setup_method(self):\n"
            "        self.wall_now = datetime.now\n\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n",
            "self.wall_now()",
            8,
        ),
        (
            "from datetime import datetime\n\n"
            "class TestClock:\n"
            "    def setup_method(self):\n"
            "        setattr(self, 'wall_now', datetime.now)\n\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n",
            "self.wall_now()",
            8,
        ),
        (
            "from typing import TYPE_CHECKING\n"
            "from datetime import datetime\n\n"
            "if TYPE_CHECKING:\n"
            "    from fake_datetime import datetime\n\n"
            "def test_bad():\n"
            "    assert datetime.now().year == 2026\n",
            "datetime.now()",
            8,
        ),
        (
            "from datetime import datetime\n\n"
            "if False:\n"
            "    from fake_datetime import datetime\n\n"
            "def test_bad():\n"
            "    assert datetime.now().year == 2026\n",
            "datetime.now()",
            7,
        ),
        (
            "from datetime import datetime\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n\n"
            "wall_now = datetime.now\n",
            "wall_now()",
            4,
        ),
        (
            "from datetime import datetime\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n\n"
            "def setup_module():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n",
            "wall_now()",
            4,
        ),
        (
            "from datetime import datetime\n\n"
            "class TestClock:\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n\n"
            "TestClock.wall_now = datetime.now\n",
            "self.wall_now()",
            5,
        ),
        (
            "import typing as t\n"
            "from typing import TYPE_CHECKING as TC\n"
            "from datetime import datetime\n\n"
            "if t.TYPE_CHECKING:\n"
            "    from fake_datetime import datetime\n\n"
            "if TC:\n"
            "    from fake_datetime import datetime\n\n"
            "def test_bad():\n"
            "    assert datetime.now().year == 2026\n",
            "datetime.now()",
            12,
        ),
        (
            "import os\n"
            "from datetime import datetime\n\n"
            "if os.environ.get('USE_FAKE_CLOCK'):\n"
            "    from fake_datetime import datetime\n\n"
            "def test_bad():\n"
            "    assert datetime.now().year == 2026\n",
            "datetime.now()",
            8,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture(autouse=True)\n"
            "def wall_clock_fixture():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            10,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    pass\n\n"
            "@pytest.fixture(autouse=True)\n"
            "def clock_fixture():\n"
            "    Holder.wall_now = datetime.now\n\n"
            "def test_bad():\n"
            "    assert Holder.wall_now().year == 2026\n",
            "Holder.wall_now()",
            12,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    pass\n\n"
            "@pytest.fixture(autouse=True)\n"
            "def clock_fixture(monkeypatch):\n"
            "    monkeypatch.setattr('test_bad.Holder.wall_now', datetime.now)\n\n"
            "def test_bad():\n"
            "    assert Holder.wall_now().year == 2026\n",
            "Holder.wall_now()",
            12,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    pass\n\n"
            "@pytest.fixture(autouse=True)\n"
            "def clock_fixture(monkeypatch):\n"
            "    monkeypatch.setattr(Holder, 'wall_now', datetime.now)\n\n"
            "def test_bad():\n"
            "    assert Holder.wall_now().year == 2026\n",
            "Holder.wall_now()",
            12,
        ),
        (
            "import pytest as pt\n"
            "from datetime import datetime\n\n"
            "wall_now = lambda: 1\n\n"
            "@pt.fixture(autouse=True)\n"
            "def wall_clock_fixture():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            12,
        ),
        (
            "from pytest import fixture\n"
            "from datetime import datetime\n\n"
            "@fixture(autouse=True)\n"
            "def wall_clock_fixture():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            10,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture\n"
            "def wall_now():\n"
            "    return datetime.now\n\n"
            "def test_bad(wall_now):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            9,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture(params=[datetime.now])\n"
            "def wall_now(request):\n"
            "    return request.param\n\n"
            "def test_bad(wall_now):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            9,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "CLOCKS = [datetime.now]\n\n"
            "@pytest.fixture(params=CLOCKS)\n"
            "def wall_now(request):\n"
            "    return request.param\n\n"
            "def test_bad(wall_now):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            11,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture(params=[pytest.param(datetime.now)])\n"
            "def wall_now(request):\n"
            "    return request.param\n\n"
            "def test_bad(wall_now):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            9,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture\n"
            "def wall_now():\n"
            "    return lambda: datetime.now()\n\n"
            "def test_bad(wall_now):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            9,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture\n"
            "def wall_now():\n"
            "    yield datetime.now\n\n"
            "def test_bad(wall_now):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            9,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    wall_now = datetime.now\n\n"
            "@pytest.fixture\n"
            "def holder():\n"
            "    return Holder\n\n"
            "def test_bad(holder):\n"
            "    assert holder.wall_now().year == 2026\n",
            "holder.wall_now()",
            12,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture\n"
            "def holder():\n"
            "    class Holder:\n"
            "        pass\n"
            "    Holder.wall_now = datetime.now\n"
            "    return Holder\n\n"
            "def test_bad(holder):\n"
            "    assert holder.wall_now().year == 2026\n",
            "holder.wall_now()",
            12,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n"
            "from types import SimpleNamespace\n\n"
            "@pytest.fixture\n"
            "def holder():\n"
            "    return SimpleNamespace(wall_now=datetime.now)\n\n"
            "def test_bad(holder):\n"
            "    assert holder.wall_now().year == 2026\n",
            "holder.wall_now()",
            10,
        ),
        (
            "from datetime import datetime\n\n"
            "def helper():\n"
            "    return lambda: datetime.now()\n\n"
            "def test_bad():\n"
            "    wall_now = helper()\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            8,
        ),
        (
            "from datetime import datetime\n"
            "from types import SimpleNamespace\n\n"
            "def helper():\n"
            "    return SimpleNamespace(wall_now=datetime.now)\n\n"
            "def test_bad():\n"
            "    holder = helper()\n"
            "    assert holder.wall_now().year == 2026\n",
            "holder.wall_now()",
            9,
        ),
        (
            "from datetime import datetime\n"
            "from types import SimpleNamespace\n\n"
            "def make_holder(clock):\n"
            "    return SimpleNamespace(wall_now=clock)\n\n"
            "def test_bad():\n"
            "    holder = make_holder(datetime.now)\n"
            "    assert holder.wall_now().year == 2026\n",
            "holder.wall_now()",
            9,
        ),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    def __init__(self, clock):\n"
            "        self.wall_now = clock\n\n"
            "def test_bad():\n"
            "    holder = Holder(datetime.now)\n"
            "    assert holder.wall_now().year == 2026\n",
            "holder.wall_now()",
            9,
        ),
        (
            "from datetime import datetime\n\n"
            "def is_current_year():\n"
            "    return datetime.now().year == 2026\n\n"
            "def test_bad():\n"
            "    assert is_current_year()\n",
            "is_current_year()",
            7,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.mark.parametrize('wall_now', [datetime.now])\n"
            "def test_bad(wall_now):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            6,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "PARAMS = [datetime.now]\n\n"
            "@pytest.mark.parametrize('wall_now', PARAMS)\n"
            "def test_bad(wall_now):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            8,
        ),
        (
            "from pytest import mark, param\n"
            "from datetime import datetime\n\n"
            "@mark.parametrize('wall_now', [param(datetime.now)])\n"
            "def test_bad(wall_now):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            6,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture(autouse=True)\n"
            "def clock_fixture():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n"
            "    yield\n"
            "    wall_now = lambda: 1\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            12,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture(name='clock_alias')\n"
            "def wall_now():\n"
            "    return datetime.now\n\n"
            "def test_bad(clock_alias):\n"
            "    assert clock_alias().year == 2026\n",
            "clock_alias()",
            9,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture\n"
            "def wall_now():\n"
            "    return datetime.now\n\n"
            "@pytest.fixture\n"
            "def wrapper(wall_now):\n"
            "    return wall_now\n\n"
            "def test_bad(wrapper):\n"
            "    assert wrapper().year == 2026\n",
            "wrapper()",
            13,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture\n"
            "def clock_fixture():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n\n"
            "@pytest.mark.usefixtures('clock_fixture')\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            11,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "pytestmark = pytest.mark.usefixtures('clock_fixture')\n\n"
            "@pytest.fixture\n"
            "def clock_fixture():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            12,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture(name='clock_alias')\n"
            "def clock_fixture():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n\n"
            "def test_bad(clock_alias):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            10,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture\n"
            "def clock_fixture():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n\n"
            "@pytest.fixture\n"
            "def wrapper(clock_fixture):\n"
            "    pass\n\n"
            "def test_bad(wrapper):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            14,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "@pytest.fixture\n"
            "def clock_fixture():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n\n"
            "def test_bad(clock_fixture):\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            10,
        ),
        (
            "from datetime import datetime\n\n"
            "def setup_module():\n"
            "    def helper():\n"
            "        global wall_now\n"
            "        wall_now = datetime.now\n"
            "    helper()\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            10,
        ),
        (
            "from datetime import datetime\n\n"
            "def setup_module():\n"
            "    def helper():\n"
            "        global wall_now\n"
            "        wall_now = datetime.now\n"
            "    alias = helper\n"
            "    alias()\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            11,
        ),
        (
            "from datetime import datetime\n\n"
            "def setup_module():\n"
            "    def helper(source=datetime.now):\n"
            "        global wall_now\n"
            "        wall_now = source\n"
            "    helper()\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            10,
        ),
        (
            "from datetime import datetime\n\n"
            "def setup_module():\n"
            "    def helper(source):\n"
            "        global wall_now\n"
            "        wall_now = source\n"
            "    helper(source=datetime.now)\n\n"
            "def test_bad():\n"
            "    assert wall_now().year == 2026\n",
            "wall_now()",
            10,
        ),
        (
            "from datetime import datetime\n\n"
            "class TestClock:\n"
            "    def setup_method(self):\n"
            "        def helper():\n"
            "            self.wall_now = datetime.now\n"
            "        helper()\n\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n",
            "self.wall_now()",
            10,
        ),
        (
            "from datetime import datetime\n\n"
            "class TestClock:\n"
            "    def setup_method(self):\n"
            "        def helper(clock_holder):\n"
            "            clock_holder.wall_now = datetime.now\n"
            "        helper(self)\n\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n",
            "self.wall_now()",
            10,
        ),
        (
            "from datetime import datetime\n\n"
            "class TestClock:\n"
            "    def setup_method(self):\n"
            "        def helper(clock_holder):\n"
            "            clock_holder.wall_now = datetime.now\n"
            "        alias = helper\n"
            "        alias(self)\n\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n",
            "self.wall_now()",
            11,
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "class TestClock:\n"
            "    @pytest.fixture(autouse=True)\n"
            "    def clock_fixture(self):\n"
            "        self.wall_now = datetime.now\n\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n",
            "self.wall_now()",
            10,
        ),
        (
            "from datetime import datetime\n\n"
            "class TestClock:\n"
            "    def setup_method(self):\n"
            "        def helper(clock_holder, source=datetime.now):\n"
            "            clock_holder.wall_now = source\n"
            "        helper(self)\n\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n",
            "self.wall_now()",
            10,
        ),
        (
            "from datetime import datetime\n\n"
            "class TestClock:\n"
            "    def setup_method(self):\n"
            "        def helper(clock_holder, source):\n"
            "            clock_holder.wall_now = source\n"
            "        helper(clock_holder=self, source=datetime.now)\n\n"
            "    def test_bad(self):\n"
            "        assert self.wall_now().year == 2026\n",
            "self.wall_now()",
            10,
        ),
    ],
)
def test_find_wall_clock_assertion_violations_flags_direct_assert_calls(
    tmp_path: Path,
    source: str,
    expected: str,
    expected_line: int,
) -> None:
    test_file = tmp_path / "test_bad.py"
    test_file.write_text(source, encoding="utf-8")

    violations = find_wall_clock_assertion_violations([test_file])

    assert len(violations) == 1
    assert violations[0].call == expected
    assert violations[0].line == expected_line


def test_find_wall_clock_assertion_violations_allows_injected_now(tmp_path: Path) -> None:
    test_file = tmp_path / "test_good.py"
    test_file.write_text(
        "from datetime import UTC, datetime\n\n"
        "def test_good():\n"
        "    now = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)\n"
        "    result = build_payload(now=now)\n"
        "    assert result['created_at'] == now.isoformat()\n",
        encoding="utf-8",
    )

    assert find_wall_clock_assertion_violations([test_file]) == []


def test_find_wall_clock_assertion_violations_allows_freshness_bounds(tmp_path: Path) -> None:
    test_file = tmp_path / "test_bounds.py"
    test_file.write_text(
        "from datetime import UTC, datetime\n\n"
        "def test_bounds():\n"
        "    before = datetime.now(UTC)\n"
        "    event = make_event()\n"
        "    after = datetime.now(UTC)\n"
        "    assert before <= event.timestamp <= after\n",
        encoding="utf-8",
    )

    assert find_wall_clock_assertion_violations([test_file]) == []


@pytest.mark.parametrize(
    "source",
    [
        (
            "from datetime import datetime\n\n"
            "class FakeDateTime:\n"
            "    @classmethod\n"
            "    def now(cls):\n"
            "        return 1\n\n"
            "def test_good():\n"
            "    datetime = FakeDateTime\n"
            "    assert datetime.now() == 1\n"
        ),
        (
            "from datetime import datetime\n\n"
            "def helper():\n"
            "    wall_now = datetime.now\n"
            "    return wall_now\n\n"
            "def test_good():\n"
            "    wall_now = lambda: 1\n"
            "    assert wall_now() == 1\n"
        ),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    wall_now = datetime.now\n\n"
            "    def test_good(self):\n"
            "        wall_now = lambda: 1\n"
            "        assert wall_now() == 1\n"
        ),
        (
            "from datetime import datetime\n"
            "from fake_datetime import datetime\n\n"
            "def test_good():\n"
            "    assert datetime.now() == 1\n"
        ),
        (
            "from datetime import datetime as dt\n"
            "from fake_datetime import datetime as dt\n\n"
            "def test_good():\n"
            "    assert dt.now() == 1\n"
        ),
        (
            "from datetime import datetime\n"
            "from fake_datetime import *\n\n"
            "def test_good():\n"
            "    assert datetime.now() == 1\n"
        ),
        (
            "from datetime import datetime\n\n"
            "class Holder:\n"
            "    pass\n\n"
            "Holder.wall_now = datetime.now\n\n"
            "class Fake:\n"
            "    @staticmethod\n"
            "    def wall_now():\n"
            "        return 1\n\n"
            "Holder = Fake\n\n"
            "def test_good():\n"
            "    assert Holder.wall_now() == 1\n"
        ),
        (
            "from datetime import datetime\n\n"
            "class FakeDateTime:\n"
            "    @staticmethod\n"
            "    def now():\n"
            "        return 1\n\n"
            "def test_good():\n"
            "    assert (lambda datetime: datetime.now())(FakeDateTime) == 1\n"
        ),
        (
            "from datetime import datetime\n\n"
            "values = [type('FakeDateTime', (), {'now': staticmethod(lambda: 1)})]\n\n"
            "def test_good():\n"
            "    assert [datetime.now() for datetime in values] == [1]\n"
        ),
        (
            "from datetime import datetime\n\n"
            "wall_now = lambda: 1\n\n"
            "def helper():\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n\n"
            "def test_good():\n"
            "    assert wall_now() == 1\n"
        ),
        (
            "from datetime import datetime\n\n"
            "class TestClock:\n"
            "    def setup_method(self):\n"
            "        self.wall_now = datetime.now\n"
            "        self.wall_now = lambda: 1\n\n"
            "    def test_good(self):\n"
            "        assert self.wall_now() == 1\n"
        ),
        (
            "from datetime import datetime\n\n"
            "class TestClock:\n"
            "    def setup_method(self):\n"
            "        def helper():\n"
            "            self.wall_now = datetime.now\n\n"
            "    def test_good(self):\n"
            "        self.wall_now = lambda: 1\n"
            "        assert self.wall_now() == 1\n"
        ),
        (
            "import pytest\n"
            "from datetime import datetime\n\n"
            "wall_now = lambda: 1\n\n"
            "@pytest.fixture(autouse=True)\n"
            "def clock_fixture():\n"
            "    yield\n"
            "    global wall_now\n"
            "    wall_now = datetime.now\n\n"
            "def test_good():\n"
            "    assert wall_now() == 1\n"
        ),
    ],
)
def test_find_wall_clock_assertion_violations_respects_local_shadowing(tmp_path: Path, source: str) -> None:
    test_file = tmp_path / "test_good.py"
    test_file.write_text(source, encoding="utf-8")

    assert find_wall_clock_assertion_violations([test_file]) == []


def test_find_wall_clock_assertion_violations_resolves_cross_file_clock_aliases(tmp_path: Path) -> None:
    tests_root = tmp_path / "tests"
    helper_file = tests_root / "helpers" / "clock.py"
    direct_import_file = tests_root / "test_direct_import.py"
    module_import_file = tests_root / "test_module_import.py"
    package_import_file = tests_root / "test_package_import.py"
    class_import_file = tests_root / "test_class_import.py"
    star_import_file = tests_root / "test_star_import.py"
    wrapper_import_file = tests_root / "test_wrapper_import.py"
    helper_file.parent.mkdir(parents=True)
    helper_file.write_text(
        "from datetime import datetime\n\n"
        "wall_now = datetime.now\n\n"
        "class Holder:\n"
        "    wall_now = datetime.now\n\n"
        "def wrapper_now():\n"
        "    return datetime.now()\n",
        encoding="utf-8",
    )
    direct_import_file.write_text(
        "from helpers.clock import wall_now\n\n"
        "def test_bad():\n"
        "    assert wall_now().year == 2026\n",
        encoding="utf-8",
    )
    module_import_file.write_text(
        "import helpers.clock as clock\n\n"
        "def test_bad():\n"
        "    assert clock.wall_now().year == 2026\n",
        encoding="utf-8",
    )
    package_import_file.write_text(
        "from helpers import clock\n\n"
        "def test_bad():\n"
        "    assert clock.wall_now().year == 2026\n",
        encoding="utf-8",
    )
    class_import_file.write_text(
        "from helpers.clock import Holder\n\n"
        "def test_bad():\n"
        "    assert Holder.wall_now().year == 2026\n",
        encoding="utf-8",
    )
    star_import_file.write_text(
        "from helpers.clock import *\n\n"
        "def test_bad():\n"
        "    assert Holder.wall_now().year == 2026\n",
        encoding="utf-8",
    )
    wrapper_import_file.write_text(
        "from helpers.clock import wrapper_now\n\n"
        "def test_bad():\n"
        "    assert wrapper_now().year == 2026\n",
        encoding="utf-8",
    )

    violations = find_wall_clock_assertion_violations(
        [
            helper_file,
            direct_import_file,
            module_import_file,
            package_import_file,
            class_import_file,
            star_import_file,
            wrapper_import_file,
        ]
    )

    assert [(violation.path.name, violation.call, violation.line) for violation in violations] == [
        ("test_class_import.py", "Holder.wall_now()", 4),
        ("test_direct_import.py", "wall_now()", 4),
        ("test_module_import.py", "clock.wall_now()", 4),
        ("test_package_import.py", "clock.wall_now()", 4),
        ("test_star_import.py", "Holder.wall_now()", 4),
        ("test_wrapper_import.py", "wrapper_now()", 4),
    ]


def test_find_wall_clock_assertion_violations_resolves_conftest_fixture_returns(tmp_path: Path) -> None:
    tests_root = tmp_path / "tests"
    conftest_file = tests_root / "conftest.py"
    test_file = tests_root / "test_uses_conftest.py"
    tests_root.mkdir()
    conftest_file.write_text(
        "import pytest\n"
        "from datetime import datetime\n\n"
        "@pytest.fixture\n"
        "def wall_now():\n"
        "    return datetime.now\n",
        encoding="utf-8",
    )
    test_file.write_text(
        "def test_bad(wall_now):\n"
        "    assert wall_now().year == 2026\n",
        encoding="utf-8",
    )

    violations = find_wall_clock_assertion_violations([conftest_file, test_file])

    assert [(violation.path.name, violation.call, violation.line) for violation in violations] == [
        ("test_uses_conftest.py", "wall_now()", 2)
    ]


def test_find_wall_clock_assertion_violations_resolves_conftest_autouse_helper_mutation(tmp_path: Path) -> None:
    tests_root = tmp_path / "tests"
    helper_file = tests_root / "helpers" / "clock.py"
    conftest_file = tests_root / "conftest.py"
    test_file = tests_root / "test_uses_conftest_helper.py"
    helper_file.parent.mkdir(parents=True)
    helper_file.write_text(
        "class Holder:\n"
        "    pass\n",
        encoding="utf-8",
    )
    conftest_file.write_text(
        "import pytest\n"
        "from datetime import datetime\n"
        "import helpers.clock as clock\n\n"
        "@pytest.fixture(autouse=True)\n"
        "def clock_fixture():\n"
        "    clock.Holder.wall_now = datetime.now\n",
        encoding="utf-8",
    )
    test_file.write_text(
        "import helpers.clock as clock\n\n"
        "def test_bad():\n"
        "    assert clock.Holder.wall_now().year == 2026\n",
        encoding="utf-8",
    )

    violations = find_wall_clock_assertion_violations([helper_file, conftest_file, test_file])

    assert [(violation.path.name, violation.call, violation.line) for violation in violations] == [
        ("test_uses_conftest_helper.py", "clock.Holder.wall_now()", 4)
    ]


def test_find_test_python_paths_includes_helper_modules(tmp_path: Path) -> None:
    tests_root = tmp_path / "tests"
    helper_file = tests_root / "helpers" / "bad_helper.py"
    test_file = tests_root / "test_uses_helper.py"
    helper_file.parent.mkdir(parents=True)
    helper_file.write_text("def helper():\n    pass\n", encoding="utf-8")
    test_file.write_text("def test_uses_helper():\n    pass\n", encoding="utf-8")

    assert find_test_python_paths(tests_root) == [helper_file, test_file]


def test_format_wall_clock_assertion_violations_names_injection_pattern(tmp_path: Path) -> None:
    test_file = tmp_path / "test_bad.py"
    test_file.write_text(
        "from datetime import datetime\n\n"
        "def test_bad():\n"
        "    assert datetime.now().year == 2026\n",
        encoding="utf-8",
    )
    violations = find_wall_clock_assertion_violations([test_file])

    message = format_wall_clock_assertion_violations(violations)

    assert "Inject a stable `now=`/clock" in message
    assert "test_bad.py:4: datetime.now()" in message


def _write_alias_chain(root: Path, size: int) -> list[Path]:
    paths: list[Path] = []
    for index in range(size):
        path = root / f"m{index:03d}.py"
        source = (
            "from datetime import datetime\nresult = datetime.now\n"
            if index == 0
            else f"from m{index - 1:03d} import result as upstream\nresult = upstream\n"
        )
        path.write_text(source, encoding="utf-8")
        paths.append(path)
    return paths


def _cached_scan_worker(test_file: str, cache_root: str, results: Any) -> None:
    violations = find_wall_clock_assertion_violations_cached(
        [Path(test_file)],
        Path(cache_root),
    )
    results.put((os.getpid(), [violation.render() for violation in violations]))


def test_import_alias_worklist_scales_approximately_linearly_with_common_names(tmp_path: Path) -> None:
    small_root = tmp_path / "small"
    large_root = tmp_path / "large"
    small_root.mkdir()
    large_root.mkdir()
    small_paths = _write_alias_chain(small_root, 20)
    large_paths = _write_alias_chain(large_root, 40)
    small_metrics = _ImportAliasMetrics()
    large_metrics = _ImportAliasMetrics()

    small = _collect_import_aliases(small_paths, _metrics=small_metrics)
    large = _collect_import_aliases(large_paths, _metrics=large_metrics)

    assert small["m019"][("result",)] == ("datetime", "datetime", "now")
    assert large["m039"][("result",)] == ("datetime", "datetime", "now")
    assert small_metrics.module_visits <= 3 * len(small_paths)
    assert large_metrics.module_visits <= 3 * len(large_paths)
    assert large_metrics.module_visits <= small_metrics.module_visits * 2.5


def test_cached_scan_repairs_corruption_and_invalidates_on_source_change(tmp_path: Path) -> None:
    test_file = tmp_path / "test_bad.py"
    cache_root = tmp_path / "cache"
    test_file.write_text(
        "from datetime import datetime\n\ndef test_bad():\n    assert datetime.now().year == 2026\n",
        encoding="utf-8",
    )

    first = find_wall_clock_assertion_violations_cached([test_file], cache_root)
    cache_files = list(cache_root.glob("*.json"))
    assert [(row.line, row.call) for row in first] == [(4, "datetime.now()")]
    assert len(cache_files) == 1
    cache_files[0].write_text("corrupt", encoding="utf-8")

    repaired = find_wall_clock_assertion_violations_cached([test_file], cache_root)
    assert repaired == first
    assert cache_files[0].read_text(encoding="utf-8").startswith("{")

    payload = json.loads(cache_files[0].read_text(encoding="utf-8"))
    payload["violations"] = []
    cache_files[0].write_text(json.dumps(payload), encoding="utf-8")
    assert find_wall_clock_assertion_violations_cached([test_file], cache_root) == first

    payload = json.loads(cache_files[0].read_text(encoding="utf-8"))
    payload["violations"][0]["call"] = "time.time()"
    cache_files[0].write_text(json.dumps(payload), encoding="utf-8")
    assert find_wall_clock_assertion_violations_cached([test_file], cache_root) == first

    payload = json.loads(cache_files[0].read_text(encoding="utf-8"))
    payload["violations"] = []
    payload["result_sha256"] = _wall_clock_scan_result_authenticator(
        payload["digest"],
        payload["violations"],
    )
    cache_files[0].write_text(json.dumps(payload), encoding="utf-8")
    assert find_wall_clock_assertion_violations_cached([test_file], cache_root) == first
    assert json.loads(cache_files[0].read_text(encoding="utf-8"))["violations"]

    test_file.write_text("def test_good():\n    assert 1 == 1\n", encoding="utf-8")
    assert find_wall_clock_assertion_violations_cached([test_file], cache_root) == []
    assert len(list(cache_root.glob("*.json"))) == 2


@pytest.mark.stress
def test_cached_scan_is_published_and_read_by_distinct_processes(tmp_path: Path) -> None:
    test_file = tmp_path / "test_bad.py"
    cache_root = tmp_path / "cache"
    test_file.write_text(
        "from datetime import datetime\n\ndef test_bad():\n    assert datetime.now().year == 2026\n",
        encoding="utf-8",
    )
    context = multiprocessing.get_context("spawn")
    results = context.Queue()

    publisher = context.Process(
        target=_cached_scan_worker,
        args=(str(test_file), str(cache_root), results),
    )
    publisher.start()
    publisher.join(timeout=10)
    assert publisher.exitcode == 0

    reader = context.Process(
        target=_cached_scan_worker,
        args=(str(test_file), str(cache_root), results),
    )
    reader.start()
    reader.join(timeout=10)
    assert reader.exitcode == 0

    first_pid, first_rows = results.get(timeout=1)
    second_pid, second_rows = results.get(timeout=1)
    assert first_pid != second_pid
    assert first_rows == second_rows
    assert len(first_rows) == 1
    assert len(list(cache_root.glob("*.json"))) == 1
    assert (cache_root / "authority.key").stat().st_size == 32
