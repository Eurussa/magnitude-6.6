"""Backend B owns plan validation, impact, features and preference ranking.

The planning LLM generates candidate itineraries. This module derives or validates
their comparable facts and applies deterministic preference scoring so repeated
inputs have a stable order. Raw scores remain internal; callers receive ordered
plans and a recommended plan id. Runtime, weather fetching, and user-facing
recommendation explanations remain outside this module.
"""
