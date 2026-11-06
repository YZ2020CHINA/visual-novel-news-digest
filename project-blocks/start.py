"""Standalone launcher copied into each project."""
from pathlib import Path
import importlib.util
import json
import webbrowser

root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('project_blocks_launcher',root/'runtime.py')
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
with helper.project_lock(root):
    result=helper.start(root)
print(json.dumps(result,ensure_ascii=False))
webbrowser.open(result['url'])
