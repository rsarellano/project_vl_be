"""Coding subtypes — edit code_solution, code_explain, loop_trace, or general."""

from . import code_explain, code_solution, general, loop_trace

SUBTYPES = {
    "code_solution": code_solution,
    "code_explain": code_explain,
    "loop_trace": loop_trace,
    "general": general,
}

DOMAIN = "coding"
DEFAULT_SUBTYPE = "code_solution"
