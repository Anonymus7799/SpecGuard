import json
import re
from pathlib import Path
from markdown_tree_parser.parser import parse_string
from openai import AzureOpenAI
import time
import re
from pathlib import Path

def extract_yaml_from_response(response_text: str) -> str:
    """
    Extracts the YAML content from a ```yaml ... ``` fenced block.
    Raises ValueError if no such block is found.
    """
    match = re.search(
        r"```yaml\s*\n(.*?)\n```",
        response_text,
        flags=re.DOTALL | re.IGNORECASE
    )
    if not match:
        raise ValueError("No fenced YAML block found in response.")

    return match.group(1).strip()


def save_yaml(yaml_text: str, output_path: str | Path) -> None:
    """
    Saves YAML text to a file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml_text + "\n", encoding="utf-8")


def get_all_paths(section):
    """
    Recursively get all paths from a section.
    Returns a list of strings, each representing a complete path.
    """
    if section is None:
        return []
    
    # Base case: if no subsections, return current section
    if len(list(section)) == 0:
        return [section.text + ": " + section.source]
    
    # Recursive case: get all paths from subsections
    cur_paths = []
    for subsection in section:
        sub_paths = get_all_paths(subsection)
        for path in sub_paths:
            cur_paths.append(section.text + ": "+ "\n" + section.source + "->" + path)
    
    return cur_paths


def get_section_content(tree, section_name):
    """
    Find a section by name and return its header + content.
    Returns empty string if not found.
    """
    for section in tree:
        if section.text == section_name:
            return f"{section.text}:\n{section.source.strip()}"
    return ""






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

tree = parse_string(erc_text)

preamble = """
---
eip: 20
title: Token Standard
author: Fabian Vogelsteller <fabian@ethereum.org>, Vitalik Buterin <vitalik.buterin@ethereum.org>
type: Standards Track
category: ERC
status: Final
created: 2015-11-19
---
"""
abstract_content = get_section_content(tree, "Abstract")
motivation_content = get_section_content(tree, "Motivation")


specification_section = None
for section in tree:
    if section.text == "Specification":
        specification_section = section
        break

if not specification_section:
    print("ERROR: Specification section not found!")
    exit(1)

# Get all paths from Specification section
paths = get_all_paths(specification_section)


# ------------------------------------------------------------
# 5. Create context prefix (Abstract + Motivation)
# ------------------------------------------------------------
context_prefix = f"""{preamble}

{abstract_content}

{motivation_content}

---
"""

AZURE_OPENAI_API_KEY = ""
AZURE_OPENAI_ENDPOINT = ""
AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
MAX_TOKENS = "16384"
TEMP = "0.0"

SYSTEM_PROMPT = """ 
You are an assistant that specializes in translating natural-language technical specifications into structured, implementation-oriented intermediate representations.

Your goal is to preserve the semantics of the specification while making control flow, state changes, observable effects, and failure conditions explicit in a form suitable for later program generation or verification.

You operate under externally supplied constraints that define the allowed representation vocabulary and output format.
"""
client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT,api_key=AZURE_OPENAI_API_KEY,api_version=AZURE_OPENAI_API_VERSION)

with open("components.json", "r", encoding="utf-8") as f:
    grammar = f.read()

count = 0
for path in paths:
    full_content = context_prefix + path
    instruction_prompt = f"""
    You are given:
    1) A natural-language requirement/specification snippet (“Spec”).
    2) A JSON file that represents an adjacency list of grammar concepts (“GrammarGraphJSON”). It lists nonterminals (keys) and the concepts they can expand to (values).

    Your task:
    Convert the Spec into an implementation-oriented intermediate representation (IR) that is:
    - Natural language, but constrained to ONLY use concept names that appear as keys in GrammarGraphJSON (e.g., functionDefinition, emitStatement, revertStatement, parameterList, typeName, mappingType, ifStatement, etc.).
    - Explicit about control-flow, state changes, events, and errors.
    - Suitable to guide later code generation or verification.

    Rules:
    A) You MUST produce the output as valid YAML enclosed in a fenced code block using ```yaml ... ```. The fenced block MUST contain only the YAML document and no explanatory text.
    B) In each IR field, you may use free-form English, but every sentence must reference at least one concept name from GrammarGraphJSON.
    C) You MUST NOT invent any concept names not present in GrammarGraphJSON.
    D) If the Spec implies something you cannot represent with the available concepts (e.g., an expression rule not in the graph), you must still capture it using the closest available concepts and add it to `gaps`.
    E) Keep it concise: 6–14 total bullets across all sections.

    YAML output schema (must follow exactly):

    ir:
    scope:
        - <bullets describing where this lives using concepts like sourceCode/contractDefinition/functionDefinition>
    normativity:
        - <MUST | SHOULD | MAY | OPTIONAL, with justification referencing spec language>
    signature:
        - <bullets using functionDefinition, parameterList, returnParameters, typeName, visibility, stateMutability>
    required_behavior:
        - <bullets describing must-do actions referencing block, statement, simpleStatement, variableDeclarationStatement, emitStatement, returnStatement>
    guards_and_failures:
        - <bullets referencing ifStatement/tryStatement/catchClause/revertStatement to capture failure conditions>
    state_effects:
        - <bullets referencing stateVariableDeclaration, mappingType, variableDeclaration, typeName>
    observables:
        - <bullets referencing eventDefinition, eventParameter, emitStatement, callArgument>
    gaps:
        - <bullets listing what cannot be precisely expressed with this GrammarGraphJSON (e.g., missing expression/assignment nodes), and how you approximated it>

    Now do the task.

    Inputs:
    Spec:
    <<<
    {full_content}
    >>>

    GrammarGraphJSON:
    <<<
    {grammar}
    >>>
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT},{"role": "user","content": instruction_prompt}]

    response = client.chat.completions.create(model=AZURE_OPENAI_DEPLOYMENT,messages=messages,max_tokens=int(MAX_TOKENS),temperature=float(TEMP))

    response_text = response.choices[0].message.content

    yaml_text = extract_yaml_from_response(response_text)

    print(yaml_text)

    save_yaml(yaml_text,"Rules/"+str(count)+".yaml")

    count = count+1

    time.sleep(10)

