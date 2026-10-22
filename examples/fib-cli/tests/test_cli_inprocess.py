import runpy
import sys

import pytest

from fib.cli import main


def test_main_single_value(capsys):
    assert main(["90"]) == 0
    assert capsys.readouterr().out == "2880067194370816120\n"


def test_main_range(capsys):
    assert main(["--range", "0", "5", "--method", "iterative"]) == 0
    assert capsys.readouterr().out.split() == ["0", "1", "1", "2", "3", "5"]


@pytest.mark.parametrize("argv,fragment", [
    (["-3"], "non-negative"),
    (["abc"], "integer"),
    (["--range", "9", "2"], "start (9) must not exceed end (2)"),
    ([], "n is required"),
    (["4", "--range", "1", "2"], "not both"),
    (["--method", "magic", "3"], "magic"),
])
def test_main_errors_exit_2(argv, fragment, capsys):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert fragment in captured.err


def test_module_entry_point_runs_main(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["fib", "10"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("fib", run_name="__main__")
    assert exc.value.code == 0
    assert capsys.readouterr().out == "55\n"
