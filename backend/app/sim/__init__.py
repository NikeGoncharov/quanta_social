"""The live simulation layer: the world loop, its DB writer, and the sim/inspector API.

This is the impure shell around the pure `adsim` engine — it owns the single asyncio world
loop, materializes engine output into DB buckets/samples, and streams it to the cabinet
over SSE. The engine itself never imports anything from here.
"""
