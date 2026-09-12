"""Backend B owns feasibility checks and ranking.
Never move booking=true or movable=false items silently.
Use fixture travel minutes, check overlaps, flag infeasible candidates.
"""
