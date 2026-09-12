"""Backend B owns feasibility checks, impact, features and preference ranking.
Never move booking=true or movable=false items silently.
Use fixture travel minutes, check overlaps, flag infeasible candidates.
Receive typed preferences and weather from A; do not read/write runtime data,
fetch external weather, or generate user-facing recommendation explanations here.
Implementation is intentionally left to Backend B.
"""
