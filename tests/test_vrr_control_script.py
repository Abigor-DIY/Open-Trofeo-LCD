import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class VrrControlScriptTests(unittest.TestCase):
    def test_detects_capable_output_and_applies_requested_policy(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "trofeo_vrr.sh"
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            calls_path = temp / "calls.txt"
            fake = temp / "kscreen-doctor"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"${1:-}\" == \"-o\" ]]; then\n"
                "  printf 'Output: 1 HDMI-A-2\\n\\tVrr: incapable\\n'\n"
                "  printf 'Output: 2 DP-4\\n\\tVrr: Automatic\\n'\n"
                "else\n"
                "  printf '%s\\n' \"$*\" >> \"$VRR_TEST_CALLS\"\n"
                "fi\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = f"{temp_dir}:{env.get('PATH', '')}"
            env["VRR_TEST_CALLS"] = str(calls_path)

            status = subprocess.run(
                [str(script), "status"],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            applied = subprocess.run(
                [str(script), "never"],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(status.stdout.strip(), "DP-4: Automatic")
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(calls_path.read_text(encoding="utf-8").strip(), "output.DP-4.vrrpolicy.never")


if __name__ == "__main__":
    unittest.main()
