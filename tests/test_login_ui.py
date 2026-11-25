"""Authentication UI checks without loading or writing production data."""
import ast
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from .support import APP


def login_test_source():
    tree = ast.parse(APP.read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'_get_password','require_login'}]
    return 'import os\nimport streamlit as st\n' + '\n'.join(ast.unparse(n) for n in nodes) + '\nrequire_login()\nst.text("AUTHENTICATED_TEST_VIEW")\n'


class LoginUiTests(unittest.TestCase):
    def test_input_wrong_password_then_correct_button(self):
        at=AppTest.from_string(login_test_source(),default_timeout=40)
        at.secrets['DASHBOARD_PASSWORD']='test-only-login-password'
        at.run()
        self.assertFalse(at.exception)
        self.assertEqual(at.text_input[0].label,'パスワード')
        # Text entry reruns alone do not authenticate (same as the original non-form UI).
        at.text_input[0].input('test-only-login-password').run()
        self.assertFalse(at.text)
        at.text_input[0].input('incorrect').run()
        at.button[0].click().run()
        self.assertEqual(at.error[0].value,'パスワードが違います。')
        self.assertFalse(at.text)
        at.text_input[0].input('test-only-login-password').run()
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertTrue(at.session_state['auth_ok'])
        self.assertEqual(at.text[0].value,'AUTHENTICATED_TEST_VIEW')
        self.assertFalse(at.text_input)
        self.assertFalse(any('st-key-login_panel' in m.value for m in at.markdown))

    def test_authenticated_session_has_no_login_css(self):
        at=AppTest.from_string(login_test_source(),default_timeout=40)
        at.secrets['DASHBOARD_PASSWORD']='test-only-login-password'
        at.session_state['auth_ok']=True
        at.run()
        self.assertFalse(at.exception)
        self.assertFalse(at.text_input)
        self.assertFalse(at.markdown)
        self.assertEqual(at.text[0].value,'AUTHENTICATED_TEST_VIEW')

    def test_unconfigured_password_keeps_existing_warning(self):
        with patch.dict(os.environ,{'DASHBOARD_PASSWORD':''}):
            at=AppTest.from_string(login_test_source(),default_timeout=40)
            at.secrets['DASHBOARD_PASSWORD']=''
            at.run()
        self.assertFalse(at.exception)
        self.assertIn('ログインパスワードが未設定',at.warning[0].value)
        self.assertFalse(at.text_input)
        self.assertEqual(at.text[0].value,'AUTHENTICATED_TEST_VIEW')
