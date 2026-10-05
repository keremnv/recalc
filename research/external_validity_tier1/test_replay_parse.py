#!/usr/bin/env python3
"""Focused regression tests for Tier 1 replay/miner parsing (stdlib only).

Run: python3 research/external_validity_tier1/test_replay_parse.py
Covers remap/split_step/extract_python behaviors that already broke once
during the study (double-remap, quoted paths, dash-heredoc, greedy -c).
"""
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from mine_layerm import extract_python  # noqa: E402
from replay_layer import remap, remap_action, remap_catom, remap_py, split_step, step_cwd  # noqa: E402

W = Path("/tmp/t1replay/R/base")


class RemapTest(unittest.TestCase):
    def test_mnt_data(self):
        self.assertEqual(
            remap("load_workbook('/mnt/spreadsheet_data/x.xlsx')", W),
            f"load_workbook('{W}/data/x.xlsx')")

    def test_tmp_unquoted(self):
        self.assertEqual(remap("cat > /tmp/a.py", W), f"cat > {W}/tmp/a.py")

    def test_tmp_quoted(self):
        self.assertEqual(remap('wb.save("/tmp/n.xlsx")', W), f'wb.save("{W}/tmp/n.xlsx")')

    def test_escaped_space(self):
        self.assertEqual(
            remap("cd /mnt/spreadsheet_data/spreadsheet/11_Project\\ Switchgear", W),
            f"cd {W}/data/spreadsheet/11_Project\\ Switchgear")

    def test_other_absolute(self):
        self.assertEqual(remap("unzip -o /calc.xlsx", W), f"unzip -o {W}/abs/calc.xlsx")

    def test_dev_null_passthrough(self):
        self.assertEqual(remap("cd /x 2>/dev/null || mkdir -p /y", W),
                         f"cd {W}/abs/x 2>/dev/null || mkdir -p {W}/abs/y")

    def test_relative_untouched(self):
        self.assertEqual(remap("open('xl/sheet1.xml')", W), "open('xl/sheet1.xml')")

    def test_division_untouched(self):
        self.assertEqual(remap("x = a/b + c", W), "x = a/b + c")

    def test_no_double_remap(self):
        once = remap("cat > /tmp/audit.py", W)
        self.assertEqual(remap(once, W), once)


class ExtractTest(unittest.TestCase):
    def test_dash_heredoc(self):
        bodies = extract_python("python3 - << 'EOF'\nprint(1)\nEOF\n")
        self.assertEqual(bodies, ["print(1)"])

    def test_plain_heredoc(self):
        bodies = extract_python("python3 << 'EOF'\nprint(2)\nEOF\n")
        self.assertEqual(bodies, ["print(2)"])

    def test_c_stops_before_shell(self):
        bodies = extract_python('python3 -c "print(1)" && soffice --headless x')
        self.assertEqual(bodies, ["print(1)"])

    def test_c_with_redirect_pipe(self):
        bodies = extract_python('python3 -c "import uno" 2>&1 | tail -1')
        self.assertEqual(bodies, ["import uno"])

    def test_cat_creator(self):
        bodies = extract_python("cat > /tmp/x.py << 'EOF'\nprint(3)\nEOF\n")
        self.assertEqual(bodies, ["print(3)"])


class SplitTest(unittest.TestCase):
    def test_combined_creator_exec(self):
        parts = split_step("cat > /tmp/a.py << 'EOF'\nprint(1)\nEOF\npython3 /tmp/a.py")
        kinds = [k for k, _ in parts]
        self.assertEqual(kinds, ["catshell", "pyfile"])

    def test_prefix_suffix(self):
        parts = split_step("cd /tmp && python3 -c \"print(1)\" && echo done")
        kinds = [k for k, _ in parts]
        self.assertEqual(kinds, ["shell", "pycode", "shell"])

    def test_soffice_suffix_survives(self):
        parts = split_step("cd /tmp && python3 -c \"print(1)\" && rm -rf x && soffice --headless f")
        suffix = [t for k, t in parts if k == "shell"][-1]
        self.assertIn("soffice", suffix)


class CwdUnescapeTest(unittest.TestCase):
    def test_escaped_space_cd(self):
        self.assertEqual(
            step_cwd("cd /mnt/spreadsheet_data/spreadsheet/11_Project\\ Switchgear && python3 -c \"print(1)\"", W),
            W / "data/spreadsheet/11_Project Switchgear")

    def test_chained_cd_last_wins(self):
        self.assertEqual(
            step_cwd("cd /mnt/spreadsheet_output 2>/dev/null || mkdir -p /x; cd /tmp && cat > a.py << 'EOF'\n1\nEOF", W),
            W / "tmp")


class DashCUnescapeTest(unittest.TestCase):
    def test_double_quote_unescape(self):
        parts = split_step("python3 -c \"print(\\\"hi\\\")\"")
        self.assertEqual(parts, [("pycode", 'print("hi")')])

    def test_backslash_quote_preserved_shape(self):
        parts = split_step("cd /d && python3 -c \"\nprint('BG!' in v or \\\"BG\\\" in v)\n\"")
        code = [p for k, p in parts if k == "pycode"][0]
        self.assertIn('or "BG" in v', code)
        compile(code, "<t>", "exec")


class RemapPyTest(unittest.TestCase):
    def test_xml_close_tag_untouched(self):
        body = "re.findall(r'<c r=\"([A-Z]+\\d+)\"[^>]*>(.*?)</c>', xml)"
        self.assertEqual(remap_py(body, W), body)

    def test_division_formula_untouched(self):
        body = "f'=IF(A2=\"\",\"\",\"Q\"&ROUNDUP(MONTH(A2)/3,0))'"
        self.assertEqual(remap_py(body, W), body)

    def test_slash_string_check_untouched(self):
        body = "if '/0' in cell_value:"
        self.assertEqual(remap_py(body, W), body)

    def test_known_prefixes_map(self):
        body = "open('/mnt/spreadsheet_data/x.xlsx'); open('/tmp/a.txt')"
        self.assertEqual(remap_py(body, W),
                         f"open('{W}/data/x.xlsx'); open('{W}/tmp/a.txt')")


class RemapShellXmlTest(unittest.TestCase):
    def test_grep_close_tag_untouched(self):
        self.assertEqual(remap("grep -o '<v>17[5-8]</v>' $f", W),
                         "grep -o '<v>17[5-8]</v>' $f")

    def test_genuine_other_absolute_maps(self):
        self.assertEqual(remap("unzip -o /calc.xlsx", W), f"unzip -o {W}/abs/calc.xlsx")


class CatomTest(unittest.TestCase):
    def test_header_shell_body_py(self):
        text = "cat > /tmp/a.py << 'EOF'\nprint('</c>', 1/2)\nEOF"
        self.assertEqual(remap_catom(text, W),
                         f"cat > {W}/tmp/a.py << 'EOF'\nprint('</c>', 1/2)\nEOF")

    def test_action_preserves_glue(self):
        text = "cd /tmp && cat > a.py << 'EOF'\nx=1/2\nEOF\ncat > b.py << 'EOF'\ny=2\nEOF"
        out = remap_action(text, W)
        self.assertIn(f"cd {W}/tmp && cat > a.py", out)
        self.assertIn("x=1/2", out)
        self.assertIn("EOF\ncat > b.py", out)


if __name__ == "__main__":
    unittest.main(verbosity=1)
