import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from label_reports import startup_failures


class StartupLabels(unittest.TestCase):
    def test_only_overlay_tracebacks_become_collection_labels(self):
        trace = 'Traceback (most recent call last):\n  File "/src/json.py", line 1\nRuntimeError: shadow\n'
        tests = {'test_a':0,'test_b':1}
        self.assertEqual(startup_failures(trace,1,'/src',tests),{0,1})
        for text,code in [(trace,0),(trace,4),(trace.replace('/src/','/other/'),1),('usage: pytest',2)]:
            self.assertIsNone(startup_failures(text,code,'/src',tests))

    @unittest.skipUnless(importlib.util.find_spec('pytest'), 'pytest not installed')
    def test_real_pytest_shadow_import_fails_before_plugin_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory,'json.py').write_text('raise RuntimeError("shadow module")\n')
            r = subprocess.run([sys.executable,'-m','pytest','--version'],cwd=directory,
                               env=dict(os.environ,PYTHONPATH=directory),capture_output=True,text=True)
            self.assertEqual(startup_failures(r.stdout+r.stderr,r.returncode,directory,{'test_a':0}),{0})
