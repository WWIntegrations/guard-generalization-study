import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from guardstudy.cli import main
class CLITests(unittest.TestCase):
    def test_help_no_model_import(self):
        p=subprocess.run([sys.executable,'-B','-c','import sys; from guardstudy.cli import main;\ntry: main(["--help"])\nexcept SystemExit: pass\nassert not any(x.startswith(("mlx","pyarrow","transformers")) for x in sys.modules)'],capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr.decode())
    def test_safe_error(self):
        self.assertEqual(main(['verify','--recorded-dir',str(Path(tempfile.mkdtemp())/'PRIVATE_SENTINEL')]),2)
