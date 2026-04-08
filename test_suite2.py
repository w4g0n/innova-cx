"""Run only Suite 2 from test_recurrence.py"""
import sys, asyncio
sys.path.insert(0, "/app")
# Import helpers from the main test file
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("tr", "/app/test_recurrence.py")
mod  = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
asyncio.run(mod.test_open_status_definitions())
