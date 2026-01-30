import requests
import time

GUMLOOP_API_KEY = "8556c06b71de440d965718fd8e19d352"
GUMLOOP_USER_ID = "hx5C9Y6io9enVlAg3TKHaB2gdvJ3"
GUMLOOP_PIPELINE_ID = "6oKS6Ca67hQdgqnXDVhYDL"

def start_pipeline(query: str) -> dict:
    """Start the Gumloop pipeline with the research query."""
    url = "https://api.gumloop.com/api/v1/start_pipeline"
    params = {
        "api_key": GUMLOOP_API_KEY,
        "user_id": GUMLOOP_USER_ID,
        "saved_item_id": GUMLOOP_PIPELINE_ID
    }
    payload = {
        "pipeline_inputs": [
            {"input_name": "input", "value": query}
        ]
    }

    response = requests.post(url, params=params, json=payload)
    return response.json()

def get_pipeline_run(run_id: str) -> dict:
    """Get the status/result of a pipeline run."""
    url = f"https://api.gumloop.com/api/v1/get_pl_run"
    params = {
        "api_key": GUMLOOP_API_KEY,
        "user_id": GUMLOOP_USER_ID,
        "run_id": run_id
    }

    response = requests.get(url, params=params)
    return response.json()

def main():
    query = input("What can I help you research? ")

    print(f"\nStarting research on: {query}")
    print("-" * 50)

    # Start the pipeline
    result = start_pipeline(query)
    print(f"Pipeline started: {result}")

    # If we get a run_id, poll for results
    if "run_id" in result:
        run_id = result["run_id"]
        print(f"Run ID: {run_id}")
        print("Waiting for results...")

        # Poll for completion
        for _ in range(60):  # Max 60 attempts (2 minutes)
            time.sleep(2)
            status = get_pipeline_run(run_id)
            state = status.get("state", "unknown")
            print(f"Status: {state}")

            if state == "DONE":
                print("\n" + "=" * 50)
                print("RESEARCH RESULTS:")
                print("=" * 50)
                outputs = status.get("outputs", {})
                for key, value in outputs.items():
                    print(f"\n{key}:")
                    print(value)
                break
            elif state in ["FAILED", "ERROR"]:
                print(f"Pipeline failed: {status}")
                break
    else:
        print(f"Response: {result}")

if __name__ == "__main__":
    main()
