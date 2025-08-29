import json
import os
from ai import main

def test_main():
    with open(os.path.join("ai", "sample_input.json")) as f:
        sample_input = json.load(f)

    with open(os.path.join("ai", "sample_output.json")) as f:
        sample_output = json.load(f)

    assert json.loads(main.process_dashboard(sample_input)) == sample_output