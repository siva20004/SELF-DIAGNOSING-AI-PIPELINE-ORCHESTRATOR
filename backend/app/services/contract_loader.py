import os
from typing import Dict, Any
import yaml


DEFAULT_CONTRACT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "contracts", "sales_contract_v1.yaml"
)


def load_contract(contract_path: str = DEFAULT_CONTRACT_PATH) -> Dict[str, Any]:
    """
    Loads and parses the YAML data contract.
    """
    if not os.path.exists(contract_path):
        # Fallback to root or current dir
        alt_paths = [
            os.path.join(os.getcwd(), "backend", "app", "contracts", "sales_contract_v1.yaml"),
            os.path.join(os.getcwd(), "sales_contract_v1.yaml"),
            "sales_contract_v1.yaml",
        ]
        for p in alt_paths:
            if os.path.exists(p):
                contract_path = p
                break

    if not os.path.exists(contract_path):
        raise FileNotFoundError(f"Contract file not found at {contract_path}")

    with open(contract_path, "r", encoding="utf-8") as f:
        contract_data = yaml.safe_load(f)

    if not contract_data or "schema" not in contract_data:
        raise ValueError("Invalid contract: missing 'schema' definition.")

    return contract_data
