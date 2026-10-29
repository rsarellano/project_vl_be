"""Rules for solving sin/cos/tan equations, shared by math prompts."""

TRIG_EQUATION_PEDAGOGY = """\
- **Trig equations:** when a step reaches ``sin(x) = a``, ``cos(x) = a``, or ``tan(x) = a``, \
list every solution in one full turn ``[0°, 360°)``, then the general solution. \
Do not stop at the first-quadrant angle. Do not draw a right triangle for this.
- ``cos(x) = 1/2`` → ``x = 60°`` and ``x = 300°`` (because cosine is positive in quadrant IV: \
``360° − 60°``). General solution: ``x = 60° + 360°k`` and ``x = 300° + 360°k``.
- ``cos(x) = a`` with ``0 < a < 1``: reference angle ``θ`` and ``360° − θ``. \
``cos(x) = 1`` → ``0°`` only. ``cos(x) = -1`` → ``180°`` only. ``cos(x) = 0`` → ``90°`` and ``270°``. \
``cos(x) = -1/2`` → ``120°`` and ``240°``.
- ``sin(x) = 1/2`` → ``30°`` and ``150°`` (``180° − θ``). ``sin(x) = 1`` → ``90°`` only. \
``sin(x) = -1`` → ``270°`` only. ``sin(x) = 0`` → ``0°`` and ``180°``.
- ``tan(x) = a``: one base angle, general form ``x = θ + 180°k``.
- The last box must include every family. Put a space on both sides of the word ``or``.
"""
