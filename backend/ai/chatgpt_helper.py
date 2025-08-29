import json
import os
import requests

from dotenv import load_dotenv

load_dotenv()


OPENAI_KEY = os.environ.get("OPENAI_KEY")
TESTING = os.environ.get("TESTING") or False


def ml_process(
    input_data: {},
    initial_prompt: str,
    additional_prompts: str = "",
    model_override=None,
):  # pragma: no cover
    """
    Processes the ML query
    - Basically sends out the request and stores the result

    - URLs, initial prompt, ending prompt
    """
    global TESTING
    if not OPENAI_KEY:
        raise Exception("No OPENAI_KEY set.  Please correct in .env")

    base_url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_KEY}",
    }

    data = {
        "model": "gpt-5-mini",
        "messages": [{"role": "system", "content": initial_prompt}],
    }

    if model_override:
        data["model"] = model_override

    if additional_prompts:
        data["messages"].append({"role": "user", "content": f"{additional_prompts}"})

    data["messages"].append({"role": "user", "content": f"{input_data}"})

    if TESTING:
        return data
    return requests.post(base_url, headers=headers, json=data)
