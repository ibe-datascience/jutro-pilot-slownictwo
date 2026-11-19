"""Load an official Wuggy language plugin from a local folder (not from site-packages).

Wuggy 1.1.2 normally downloads official plugins into
<site-packages>/wuggy/plugins/language_data/<name>/ and imports them from there.
The official plugin .py files use the relative import
`from ...baselanguageplugin import BaseLanguagePlugin`, so they cannot be imported
as plain top-level modules. This helper executes the UNMODIFIED official .py file under
its official module name (so the relative import resolves) and hands an instance to
`WuggyGenerator.load(name, local_language_plugin=...)`. Wuggy then reads the lexicon
(.txt) from the directory of that .py file.

Usage:
    from load_local_plugin import load_generator
    g = load_generator("orthographic_polish")
    g.generate_classic(["komora"], ncandidates_per_sequence=5)
"""
import importlib.util
import os
import sys

from wuggy import WuggyGenerator

PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))


def load_plugin_class(name: str, plugin_root: str = PLUGIN_ROOT):
    path = os.path.join(plugin_root, name, f"{name}.py")
    module_name = f"wuggy.plugins.language_data.{name}.{name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    # inspect.getfile(cls) (used by WuggyGenerator.load) looks the module up in sys.modules
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.OfficialLanguagePlugin


def load_generator(name: str = "orthographic_polish", plugin_root: str = PLUGIN_ROOT) -> WuggyGenerator:
    g = WuggyGenerator()
    g.load(name, local_language_plugin=load_plugin_class(name, plugin_root)())
    return g
