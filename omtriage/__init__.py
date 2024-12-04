"""
Photo Importer Package

A tool for organizing photos and videos from camera SD cards into structured directories.
"""


from importlib.metadata import version

try:
    __version__ = version("omtriage")
except Exception:
    __version__ = "undefined"
