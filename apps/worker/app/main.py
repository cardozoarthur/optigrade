from __future__ import annotations

import os
import time

import ray
import requests


@ray.remote(num_cpus=1)
def ping_api(api_url: str) -> dict[str, str]:
    response = requests.get(f"{api_url}/health", timeout=5)
    response.raise_for_status()
    return response.json()


def main() -> None:
    api_url = os.getenv("OPTIGRADE_API_URL", "http://localhost:8000")
    ray.init(ignore_reinit_error=True)
    print("OptiGrade worker online")
    while True:
        result = ray.get(ping_api.remote(api_url))
        print({"api": result})
        time.sleep(30)


if __name__ == "__main__":
    main()

