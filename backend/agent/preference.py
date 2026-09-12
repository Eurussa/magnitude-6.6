"""Backend A owns selection persistence and preference ranking integration.
Target weights: preserve_booking, maximize_attractions, relaxed.
Only server-stored plan features may update weights; duplicate choices are idempotent.
"""
