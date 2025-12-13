# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import re

def strip_jinja(sql: str) -> str:
    """
    Removes Jinja2 syntax from SQL logic to allow parsing by sqlglot.
    
    Strategies:
    1. {{ ... }} expressions -> smarter replacements:
       - ref('model') -> model
       - source('src','table') -> table
       - everything else -> /* jinja_expr */
    2. {% ... %} blocks -> Replaced with whitespace to preserve line numbers.
    3. {# ... #} comments -> Replaced with whitespace.
    """
    if not sql:
        return ""

    def replace_curly(match: re.Match) -> str:
        expr = match.group(1).strip()

        # Handle common dbt macros to preserve table names for relationship parsing
        ref_match = re.search(r"ref\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", expr, flags=re.IGNORECASE)
        if ref_match:
            # If package/name provided, prefer the model name (second group), else first
            return ref_match.group(2) or ref_match.group(1)

        source_match = re.search(r"source\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", expr, flags=re.IGNORECASE)
        if source_match:
            # Keep table name (matches how entities are named in the indexer)
            return source_match.group(2)

        return "/* jinja_expr */"

    # Replace variables {{ ... }} with identifier/comment placeholder
    # Using non-greedy match to keep scope tight
    sql = re.sub(r"\{\{\s*(.*?)\s*\}\}", replace_curly, sql, flags=re.DOTALL)

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
