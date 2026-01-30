import json
import re
from pathlib import Path
from markdown_tree_parser.parser import parse_string
from openai import AzureOpenAI
import time
import re
from pathlib import Path
from slither.slither import Slither
from collections import defaultdict, deque
from slither.core.declarations.function_contract import FunctionContract
from slither.core.declarations import Modifier
from slither.core.variables.state_variable import StateVariable
import copy
import os
import json
import subprocess
from slither.core.declarations import Event
from slither.slithir.operations.event_call import EventCall
from openai import AzureOpenAI
import re
import time
import traceback

def extract_json_from_response(response_text: str) -> dict:
    """
    Extracts JSON from response, handling fenced code blocks.
    """
    # Try to find JSON in fenced code block
    match = re.search(
        r"```json\s*\n(.*?)\n```",
        response_text,
        flags=re.DOTALL | re.IGNORECASE
    )
    if match:
        json_text = match.group(1).strip()
    else:
        # Assume entire response is JSON
        json_text = response_text.strip()
    
    return json.loads(json_text)


def ensure_solc_version(version):
    """Ensure the specified Solidity compiler version is installed and active."""
    try:
        result = subprocess.run(['solc-select', 'versions'], capture_output=True, text=True)
        if version not in result.stdout:
            print(f"Installing Solidity version {version}...")
            subprocess.run(['solc-select', 'install', version], check=True)
        
        subprocess.run(['solc-select', 'use', version], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error setting up Solidity version {version}: {e}")
        return False

def read_solidity_source(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()



def save_json(data: dict, output_path: str | Path) -> None:
    """
    Saves JSON data to a file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)



MAX_CONTRACTS_TO_PROCESS = 50
processed_count = 0

erc_text = """
---
eip: 20
title: Token Standard
author: Fabian Vogelsteller <fabian@ethereum.org>, Vitalik Buterin <vitalik.buterin@ethereum.org>
type: Standards Track
category: ERC
status: Final
created: 2015-11-19
---

## Simple Summary

A standard interface for tokens.


## Abstract

The following standard allows for the implementation of a standard API for tokens within smart contracts.
This standard provides basic functionality to transfer tokens, as well as allow tokens to be approved so they can be spent by another on-chain third party.


## Motivation

A standard interface allows any tokens on Ethereum to be re-used by other applications: from wallets to decentralized exchanges.

## Specification

### Methods

**NOTES**:
 - The following specifications use syntax from Solidity `0.4.17` (or above)
 - Callers MUST handle `false` from `returns (bool success)`.  Callers MUST NOT assume that `false` is never returned!


#### name

Returns the name of the token - e.g. `"MyToken"`.

OPTIONAL - This method can be used to improve usability,
but interfaces and other contracts MUST NOT expect these values to be present.


``` js
function name() public view returns (string)
```


#### symbol

Returns the symbol of the token. E.g. "HIX".

OPTIONAL - This method can be used to improve usability,
but interfaces and other contracts MUST NOT expect these values to be present.

``` js
function symbol() public view returns (string)
```



#### decimals

Returns the number of decimals the token uses - e.g. `8`, means to divide the token amount by `100000000` to get its user representation.

OPTIONAL - This method can be used to improve usability,
but interfaces and other contracts MUST NOT expect these values to be present.

``` js
function decimals() public view returns (uint8)
```


#### totalSupply

Returns the total token supply.

``` js
function totalSupply() public view returns (uint256)
```



#### balanceOf

Returns the account balance of another account with address `_owner`.

``` js
function balanceOf(address _owner) public view returns (uint256 balance)
```



#### transfer

Transfers `_value` amount of tokens to address `_to`, and MUST fire the `Transfer` event.
The function SHOULD `throw` if the message caller's account balance does not have enough tokens to spend.

*Note* Transfers of 0 values MUST be treated as normal transfers and fire the `Transfer` event.

``` js
function transfer(address _to, uint256 _value) public returns (bool success)
```



#### transferFrom

Transfers `_value` amount of tokens from address `_from` to address `_to`, and MUST fire the `Transfer` event.

The `transferFrom` method is used for a withdraw workflow, allowing contracts to transfer tokens on your behalf.
This can be used for example to allow a contract to transfer tokens on your behalf and/or to charge fees in sub-currencies.
The function SHOULD `throw` unless the `_from` account has deliberately authorized the sender of the message via some mechanism.

*Note* Transfers of 0 values MUST be treated as normal transfers and fire the `Transfer` event.

``` js
function transferFrom(address _from, address _to, uint256 _value) public returns (bool success)
```



#### approve

Allows `_spender` to withdraw from your account multiple times, up to the `_value` amount. If this function is called again it overwrites the current allowance with `_value`.

**NOTE**: To prevent attack vectors like the one [described here](https://docs.google.com/document/d/1YLPtQxZu1UAvO9cZ1O2RPXBbT0mooh4DYKjA_jp-RLM/) and discussed [here](https://github.com/ethereum/EIPs/issues/20#issuecomment-263524729),
clients SHOULD make sure to create user interfaces in such a way that they set the allowance first to `0` before setting it to another value for the same spender.
THOUGH The contract itself shouldn't enforce it, to allow backwards compatibility with contracts deployed before

``` js
function approve(address _spender, uint256 _value) public returns (bool success)
```


#### allowance

Returns the amount which `_spender` is still allowed to withdraw from `_owner`.

``` js
function allowance(address _owner, address _spender) public view returns (uint256 remaining)
```



### Events


#### Transfer

MUST trigger when tokens are transferred, including zero value transfers.

A token contract which creates new tokens SHOULD trigger a Transfer event with the `_from` address set to `0x0` when tokens are created.

``` js
event Transfer(address indexed _from, address indexed _to, uint256 _value)
```



#### Approval

MUST trigger on any successful call to `approve(address _spender, uint256 _value)`.

``` js
event Approval(address indexed _owner, address indexed _spender, uint256 _value)
```



## Implementation

There are already plenty of ERC20-compliant tokens deployed on the Ethereum network.
Different implementations have been written by various teams that have different trade-offs: from gas saving to improved security.

Example implementations are available at
- [OpenZeppelin implementation](../assets/eip-20/OpenZeppelin-ERC20.sol)
- [ConsenSys implementation](../assets/eip-20/Consensys-EIP20.sol)


## History

Historical links related to this standard:

- Original proposal from Vitalik Buterin: https://github.com/ethereum/wiki/wiki/Standardized_Contract_APIs/499c882f3ec123537fc2fccd57eaa29e6032fe4a
- Reddit discussion: https://www.reddit.com/r/ethereum/comments/3n8fkn/lets_talk_about_the_coin_standard/
- Original Issue #20: https://github.com/ethereum/EIPs/issues/20



## Copyright
Copyright and related rights waived via [CC0](../LICENSE.md).
"""
with open("common_contracts.json", "r", encoding="utf-8") as f:
    common_data = json.load(f)
common_contracts = set(common_data.get("common_contracts", []))

print(len(common_contracts))

base_dir = "etherscan_contracts_non_optional"
output_dir = "simple_out"


AZURE_OPENAI_API_KEY = ""
AZURE_OPENAI_ENDPOINT = ""
AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
MAX_TOKENS = "16384"
TEMP = "0.0"

client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT,api_key=AZURE_OPENAI_API_KEY,api_version=AZURE_OPENAI_API_VERSION)


with open("sample_contracts.json", 'r') as f:
    sample = json.load(f)
count = 0

for entry in os.listdir("reports"):
    try:
        if entry not in sample:
            continue

        count = count+1
        if not os.path.exists(os.path.join("eval", entry)):
            print("Here")
            continue
        
        if processed_count >= MAX_CONTRACTS_TO_PROCESS:
            print(f"Reached limit of 50 processed contracts. Stopping.")
            break
        output_path = os.path.join(output_dir, entry, "report.json")
        if os.path.exists(output_path):
            #print(f"Skipping {entry}: report already exists at {output_path}")
            processed_count = processed_count + 1
            continue    
        contract_dir = os.path.join(base_dir, entry)
        if not os.path.isdir(contract_dir):
            if not os.path.isdir(os.path.join("etherscan_contracts", entry)):
                continue
            else:
                contract_dir = os.path.join("etherscan_contracts", entry)
        src_path = os.path.join(contract_dir, "main.sol")
        metadata_path = os.path.join(contract_dir, "metadata.json")

        if not os.path.isfile(src_path) or not os.path.isfile(metadata_path):
            print("Here Now")
            continue
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        raw_version = metadata.get("CompilerVersion", "").lstrip("v")
        base_version = raw_version.split("-")[0].split("+")[0]
        if not base_version or not ensure_solc_version(base_version):
            print("Here Now Now")
            continue
        
        full_code = read_solidity_source(src_path) 

        SYSTEM_PROMPT = """
        You are a Solidity compliance verification assistant.

        Your goal is to verify whether a given Solidity smart contract implementation complies with a natural-language specification (such as an ERC standard).

        You analyze both the specification requirements and the actual code implementation to determine compliance status and provide actionable recommendations.
        """

        instruction_prompt = f"""
        You are given:

        Input A: A specification describing expected smart contract behavior.
        <<<
        {erc_text}
        >>>

        Input B: Solidity smart contract implementation.
        <<<
        {full_code}
        >>>

        Task:
        Verify whether the code implements requirements in the specification. Return one verification result per requirement or requirement category.

        Output (JSON array only):
        [
            {{
                "mode": "VERIFIED",
                "result": "PASS" | "FAIL" | "NOT_APPLICABLE",
                "reasoning": "<explanation of compliance status>",
                "evidence": "<specific functions, events, or patterns that support the result>",
                "recommendations": ["<fix suggestions if FAIL; empty list if PASS>"],
                "fixed_code": "<optional Solidity snippet or null>"
            }},
            ...
        ]

        Guidelines:
        - Create one entry per major requirement or requirement category
        - PASS: Requirement satisfied
        - FAIL: Requirement not satisfied
        - NOT_APPLICABLE: Code doesn't implement this requirement
        - Be specific: cite function names, events, state variables
        - Base assessment only on provided code

        Constraints:
        - Return valid JSON array only
        - Be concise
        - Don't assume missing code exists
        """

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": instruction_prompt}
        ]

        print("Sending verification request to LLM...")
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            max_tokens=int(MAX_TOKENS),
            temperature=float(TEMP)
        )
        
        response_text = response.choices[0].message.content
        print("Received response from LLM")
        
        # Extract and parse JSON
        reports = extract_json_from_response(response_text)
        
        # Ensure it's a list
        if not isinstance(reports, list):
            reports = [reports]
        output_path = os.path.join(output_dir, entry, "report.json")
        save_json(reports, output_path)
        processed_count = processed_count + 1
        time.sleep(15)
    except Exception as e:
        time.sleep(15)

print(processed_count)
print(count)
    	