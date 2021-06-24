from typing import Optional

import pytest

from webcheck.page import check_regex

html = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
"https://www.w3.org/TR/html4/loose.dtd">
<html>
 <head>
  <title>Example page</title>
  <meta http-equiv="Content-Type" content="text/html; charset=windows-1252">
 </head>
 <body>
  <h1>This is a heading</h1>
  <p>This is an <b>example</b> of a basic HTML page.</p>
 </body>
</html>"""


@pytest.mark.parametrize(
    "text,regex,expected",
    [
        (html, "example", True),
        (html, "not-a-match", False),
        (html, None, None),
    ],
)
def test_regex(text, regex: Optional[str], expected: bool):
    assert check_regex(text=text, regex=regex) == expected
