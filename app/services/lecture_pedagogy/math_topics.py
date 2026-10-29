"""Math topic pedagogies for lecture generation (separate from shared arc)."""

ALGEBRA = """
## Topic pedagogy: ALGEBRA
- Teach symbolic moves students must see — never jump to the answer.
- Prefer: simplify → solve → check; or model → equation → solve → interpret.
- worked_example steps should be real algebra moves, e.g.:
  "Group like terms", "Combine x terms", "Isolate x", "Check in original".
- Show each transformed equation in equation/steps (e.g. 2x+6=14 → 2x=8 → x=4).
- For factoring/quadratics: factor → zero product → roots (separate slides or steps).
- For radicals: isolate → square both sides → solve → check extraneous roots.
- callout ideas: "Do the same operation to both sides", "Watch the sign", "Check extraneous roots".
- visual_type: usually "equation"; use "graph" only when relating to function behavior.
"""

TRIGONOMETRY = """
## Topic pedagogy: TRIGONOMETRY
- Anchor every example in a labeled right triangle (opposite / adjacent / hypotenuse).
- Force SOH-CAH-TOA choice explicitly: why THIS ratio for THIS unknown.
- worked_example arc: identify knowns → pick ratio → write equation → solve → interpret.
- steps examples: "Label O/A/H", "Choose sin/cos/tan", "Solve for unknown".
- Include inverse trig when finding an angle (e.g. θ = arctan(o/a)).
- callout ideas: "Hypotenuse is always longest", "Calculator mode: degrees", "SOH for opposite+hypotenuse".
- visual_type: prefer "triangle" for right-triangle lessons; "circle" for unit-circle topics.
"""

GEOMETRY = """
## Topic pedagogy: GEOMETRY
- Lead with a figure intuition, then the formal relationship / theorem.
- Prefer: given → diagram reasoning → theorem → compute → check reasonableness.
- steps examples: "Mark knowns", "Name the relationship", "Compute the unknown".
- For Pythagorean / similarity / area: keep formula in equation and numbers in steps.
- callout ideas: "Right angle required", "Corresponding sides", "Units on the answer".
- visual_type: prefer "triangle" or "circle" to match the figure.
"""

FUNCTIONS = """
## Topic pedagogy: FUNCTIONS & MODELING (incl. Advanced Functions)
- Separate representation: words ↔ equation ↔ table/graph behavior ↔ real context.
- Prefer: context hook → define f → parameters meaning → worked model → predict → limitations.
- For exponential/log/rational: stress domain, asymptotes, growth vs decay, parameter roles (a, b).
- steps examples: "Identify a and b", "Interpret growth factor", "Evaluate f(t)", "Check reasonableness".
- callout ideas: "b>1 growth, 0<b<1 decay", "Domain restrictions", "Model ≠ reality forever".
- visual_type: prefer "graph" or "equation"; avoid trains unless the story is literally relative motion.
"""

CALCULUS = """
## Topic pedagogy: CALCULUS 1
- Teach limits and derivatives as calculus moves. Never relabel a limit as "simplify the expression".
- Keep the full statement: lim x -> a and every term, including powers such as x^2.
- Limits of polynomials: say the function is defined at the point, substitute, then show the arithmetic.
  Example: lim x -> 3 (x^2 + 5x - 4) = 3^2 + 5(3) - 4 = 20.
- Indeterminate limits (0/0): factor, cancel, or rationalize, then substitute. Do not stop at 0/0.
- One-sided limits and limits at infinity get their own step: which side, or divide by the highest power.
- Derivatives: name the rule (power, sum, product, quotient, chain), show the rewrite, then state f'(x).
- Tangent line: slope from the derivative at the point, then point-slope form.
- callout ideas: "Defined here, so substitute", "0/0 means more work", "Power rule lowers the exponent by 1".
- visual_type: "equation" for limits and derivatives; "graph" only for a tangent line or end behavior.
- Integrals, related rates, and optimization are later. Stay on limits, continuity, derivatives, and tangent lines.
"""

GENERAL_MATH = """
## Topic pedagogy: GENERAL MATH
- Keep a clear definition → example → check → takeaway arc.
- Prefer concrete numbers over abstract-only talk.
- steps should be learning moves tied to the method, not vague "Understand the idea".
- visual_type: "equation" unless a shape accent clearly helps.
"""

# slug → pedagogy block
MATH_TOPIC_PEDAGOGY: dict[str, str] = {
    "calculus": CALCULUS,
    "algebra": ALGEBRA,
    "trigonometry": TRIGONOMETRY,
    "geometry": GEOMETRY,
    "functions": FUNCTIONS,
    "general": GENERAL_MATH,
}

MATH_TOPIC_LABELS: dict[str, str] = {
    "calculus": "Calculus 1",
    "algebra": "Algebra",
    "trigonometry": "Trigonometry",
    "geometry": "Geometry",
    "functions": "Functions & Modeling",
    "general": "General Math",
}

# Keyword hints used to infer topic from the educator prompt when topic is not explicit.
MATH_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "calculus": (
        "calculus",
        "derivative",
        "differentiate",
        "differentiation",
        "d/dx",
        "dy/dx",
        "limit",
        "lim ",
        "lim(",
        "continuity",
        "tangent line",
        "power rule",
        "product rule",
        "quotient rule",
        "chain rule",
        "x->",
        "x →",
    ),
    "trigonometry": (
        "trig",
        "trigonometry",
        "sine",
        "cosine",
        "tangent",
        "soh",
        "cah",
        "toa",
        "sin(",
        "cos(",
        "tan(",
        "unit circle",
        "right triangle",
    ),
    "geometry": (
        "geometry",
        "pythagorean",
        "pythagoras",
        "congruent",
        "similar triangle",
        "perimeter",
        "area of",
        "volume",
        "polygon",
        "circle theorem",
    ),
    "functions": (
        "function",
        "functions",
        "exponential",
        "logarithm",
        "logarithmic",
        "rational function",
        "modeling",
        "advanced functions",
        "afm",
        "domain",
        "range",
        "asymptote",
        "f(x)",
    ),
    "algebra": (
        "algebra",
        "equation",
        "solve for",
        "factor",
        "quadratic",
        "linear equation",
        "inequality",
        "system of",
        "simplify",
        "polynomial",
        "radical equation",
    ),
}
