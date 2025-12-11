# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import re

def strip_jinja(sql: str) -> str:
    """
    Removes Jinja2 syntax from SQL logic to allow parsing by sqlglot.
    
    Strategies:
    1. {{ ... }} expressions -> /* jinja_expr */
    2. {% ... %} blocks -> Replaced with whitespace to preserve line numbers.
    3. {# ... #} comments -> Replaced with whitespace.
    """
    if not sql:
        return ""

    # Replace variables {{ ... }} with comment placeholder
    # Using non-greedy match
    sql = re.sub(r"\{\{.*?\}\}", "/* jinja_expr */", sql, flags=re.DOTALL)

    # Replace blocks {% ... %} with whitespace of same length
    # This is tricky to do exactly same length with regex sub, 
    # but replacing with spaces + keeping newlines is key.
    
    def repl_whitespace(match):
        s = match.group(0)
        # Create a string of same length composed of spaces, but keeping newlines
        return ''.join(['\n' if c == '\n' else ' ' for c in s])

    sql = re.sub(r"\{%.*?%\}", repl_whitespace, sql, flags=re.DOTALL)
    
    # Replace comments {# ... #} with whitespace
    sql = re.sub(r"\{#.*?#\}", repl_whitespace, sql, flags=re.DOTALL)

    return sql
