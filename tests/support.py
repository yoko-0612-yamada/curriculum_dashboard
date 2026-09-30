"""Load current production functions without executing Streamlit startup or I/O.

The AST harness deliberately skips imports, decorators and executable top-level
statements. Literal constants are retained; every CSV/JSON path is redirected to
an automatically cleaned TemporaryDirectory. This is not a test of UI wiring.
"""
import ast
import calendar as cal
import datetime as dt
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd

APP = Path(__file__).resolve().parents[1] / "dashboard.py"


class Stopped(BaseException):
    """Like Streamlit's stop: not caught by except Exception."""


class RegressionCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="dashboard-regression-")
        self.addCleanup(tmp.cleanup)
        self.data = Path(tmp.name)
        self.messages = []

        def stop():
            raise Stopped()

        self.state = {}
        st = SimpleNamespace(
            error=self.messages.append, warning=self.messages.append, stop=stop,
            session_state=self.state,
            cache_data=SimpleNamespace(clear=lambda: None),
        )
        ns = dict(pd=pd, np=np, dt=dt, date=date, datetime=datetime, Path=Path,
                  json=json, os=os, re=re, secrets=secrets, tempfile=tempfile,
                  cal=cal, st=st)
        tree = ast.parse(APP.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        ns[target.id] = value
        # Redirect all path constants, including paths referenced by extracted
        # functions that tests do not currently exercise. No production DATA_DIR.
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id.endswith(("_CSV", "_JSON")):
                suffix = ".json" if node.id.endswith("_JSON") else ".csv"
                ns[node.id] = self.data / (node.id.lower() + suffix)
        ns["DATA_DIR"] = self.data
        ns["BASE_DIR"] = self.data
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        for node in functions:
            node.decorator_list = []
        module = ast.Module(body=[ast.ImportFrom(
            module="__future__", names=[ast.alias(name="annotations")], level=0
        )] + functions, type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(APP), "exec"), ns)
        self.ns = ns

    def call(self, name, *args, **kwargs):
        return self.ns[name](*args, **kwargs)
