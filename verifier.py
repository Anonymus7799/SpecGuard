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


def find_slice(contract, comp, visited):
    if visited.get(comp.name, False):
        return []

    visited[comp.name] = True
    comp_slice = [comp] 
    if isinstance(comp,FunctionContract):
        for call in comp.all_internal_calls():
            comp_slice.append(call.function)

        for func in contract.functions:
            if func.name != comp.name:
                for call in func.all_internal_calls():
                    if call.function.name == comp.name:
                        comp_slice.append(call.function)
    
        state_vars = comp.state_variables_read + comp.state_variables_written
        comp_slice.extend(state_vars)
        for state_var in state_vars:
            comp_slice.extend(contract.get_functions_reading_from_variable(state_var))
            comp_slice.extend(contract.get_functions_writing_to_variable(state_var))

        for modifier in comp.modifiers:
            comp_slice.append(modifier)

        for node in comp.nodes:
            for ir in node.irs:
                if isinstance(ir, EventCall):
                    for event in contract.events:
                        if event.name == ir.name:
                            comp_slice.append(event)


    if isinstance(comp,StateVariable):
        comp_slice.extend(contract.get_functions_reading_from_variable(comp))
        comp_slice.extend(contract.get_functions_writing_to_variable(comp))

    if isinstance(comp,Event):
        for function in contract.functions:
            for node in function.nodes:
                for ir in node.irs:
                    if isinstance(ir, EventCall) and comp.name == ir.name:
                        comp_slice.append(function)


    for target in comp_slice:
        if target.name not in visited:
            cur_slice = find_slice(contract, target, visited)
            comp_slice.extend(cur_slice)

    

    return comp_slice



def slice_to_source_text_sorted_by_line(code_slice):
    # Remove duplicates and sort by line number
    unique_slice = list(set(code_slice))
    filtered_slice = [x for x in unique_slice if x.source_mapping and x.source_mapping.start is not None]
    sorted_slice = sorted(filtered_slice, key=lambda x: x.source_mapping.start)

    result = []
    for obj in sorted_slice:
        try:
            src = obj.source_mapping.content
            result.append(f"{src}")
        except Exception as e:
            print(f"Could not extract source for {obj}: {e}")
    return "\n\n".join(result)


def get_func_code_slice(name,target):
    
    for function in target.functions:
        if function.name != name:
            continue
        visited = {}
        code_slice = find_slice(target,function,visited)
        
        return code_slice
        #slice_text[function.name] = slice_to_source_text_sorted_by_line(code_slice)
    return[]
    

def get_state_var_code_slice(name,target):
    
    for state_var in target.state_variables:
        if state_var.name != name:
            continue
        visited = {}
        code_slice = find_slice(target,state_var,visited)
        
        
        return code_slice
        #slice_text[state_var.name] = slice_to_source_text_sorted_by_line(code_slice)
    return []

def get_event_code_slice(name,target):
    
    for event in target.events:
        if event.name != name:
            continue
        visited = {}
        code_slice = find_slice(target,event,visited)
        
        return code_slice
        #slice_text[function.name] = slice_to_source_text_sorted_by_line(code_slice)
    return[]


def read_solidity_source(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()



def is_concrete(contract) -> bool:
    return (
        not contract.is_interface
        and not contract.is_library
        and not contract.is_abstract
    )


def concrete_root_contracts(src_path: str, metadata_path: str):
    # Load compiler version
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    raw_version = metadata.get("CompilerVersion", "").lstrip("v")
    base_version = raw_version.split("-")[0].split("+")[0]
    if not base_version or not ensure_solc_version(base_version):
        return False

    sl = Slither(src_path)
    contracts = list(sl.contracts)
    by_name = {c.name: c for c in contracts}

    # Compute indegree (number of children inheriting from this contract)
    indegree = defaultdict(int)
    for c in contracts:
        indegree[c.name] = 0

    for derived in contracts:
        for base in derived.inheritance:
            if base.name in by_name:
                indegree[base.name] += 1

    # Count concrete contracts with indegree == 0
    concrete_roots = [
        c for c in contracts
        if is_concrete(c) and indegree[c.name] == 0
    ]

    return concrete_roots

def get_skeleton(src_path,contract_name):
    
    slither = Slither(src_path)
    data = {}
    for contract in slither.contracts:
        if contract.name == contract_name:
            data["state_vars"] = []
            for state_var in contract.state_variables:
                data["state_vars"].append({
                    "name": state_var.name,
                    "canonical_name": state_var.canonical_name,
                    "source": state_var.source_mapping.content
                })

            data["events"] = []
            for event in contract.events:
                data["events"].append({
                    "name": event.name,
                    "canonical_name": event.canonical_name,
                    "source": event.source_mapping.content
                })
            
            data["functions"] = []    
            for function in contract.functions:
                if not function.is_shadowed:
                    data["functions"].append({
                        "name": function.name,
                        "id": function.id,
                        "canonical_name": function.canonical_name,
                        "signature": function.solidity_signature
                    })
            

            
            return data
        



def get_merged_skeleton(contract_skeleton_pair):
    
    merged = {
        "state_vars": [],
        "events": [],
        "functions": []
    }

    seen = {
        "state_vars": set(),
        "events": set(),
        "functions": set()
    }

    for contract, sk in contract_skeleton_pair:
        if not sk:
            continue

        for bucket in ("state_vars", "events", "functions"):
            for item in sk.get(bucket, []):
                cname = item.get("canonical_name")
                if not cname:
                    continue  # or raise if you want strict invariants

                if cname not in seen[bucket]:
                    seen[bucket].add(cname)
                    merged[bucket].append({
                        **item,
                        "contract": contract.name
                    })

    return merged


def get_slithir_string(function):
    """
    Get SlithIR as a single string for a function
    """
    ir_string_list = []
    
    for node in function.nodes:
        for operation in node.all_slithir_operations():  # ← Changed
            ir_string_list.append(str(operation))
    
    return "\n".join(ir_string_list)


def build_full_contract_structured_output(roots):
    """
    Build structured output for ALL functions/modifiers/state_vars/events across all root contracts
    """
    result = {
        "functions": [],
        "modifiers": [],
    }
    
    for contract in roots:
        # Add all functions
        for func in contract.functions:
            if not func.is_shadowed:
                result["functions"].append({
                    "name": func.name,
                    "contract": contract.name,
                    "source": func.source_mapping.content if func.source_mapping else "",
                    "slithir": get_slithir_string(func)
                })
        
        # Add all modifiers
        for modifier in contract.modifiers:
            result["modifiers"].append({
                "name": modifier.name,
                "contract": contract.name,
                "source": modifier.source_mapping.content if modifier.source_mapping else "",
                "slithir": get_slithir_string(modifier)
            })
    
    return result

def build_structured_slice_output(slices):
    """
    Build simple structured output organized by category
    """
    
    result = {
        "functions": [],
        "modifiers": [],
        "state_vars": [],
        "events": []
    }
    
    for elem in slices:
        if isinstance(elem, FunctionContract):
            result["functions"].append({
                "name": elem.name,
                "source": elem.source_mapping.content if elem.source_mapping else "",
                "slithir": get_slithir_string(elem)  # ← Use your function
            })
        
        elif isinstance(elem, Modifier):
            result["modifiers"].append({
                "name": elem.name,
                "source": elem.source_mapping.content if elem.source_mapping else "",
                "slithir": get_slithir_string(elem)  # ← Use your function
            })
        
        elif isinstance(elem, StateVariable):
            result["state_vars"].append({
                "name": elem.name,
                "source": elem.source_mapping.content if elem.source_mapping else ""
            })
        
        elif isinstance(elem, Event):
            result["events"].append({
                "name": elem.name,
                "source": elem.source_mapping.content if elem.source_mapping else ""
            })
    
    return result



AZURE_OPENAI_API_KEY = ""
AZURE_OPENAI_ENDPOINT = ""
AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
MAX_TOKENS = "16384"
TEMP = "0.0"

client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT,api_key=AZURE_OPENAI_API_KEY,api_version=AZURE_OPENAI_API_VERSION)

base_dir = "dir3"
output_base_dir = "reports"

for entry in os.listdir(base_dir):
    contract_dir = os.path.join(base_dir, entry)
    if not os.path.isdir(contract_dir):
        continue

    src_path = os.path.join(contract_dir, "main.sol")
    metadata_path = os.path.join(contract_dir, "metadata.json")

    if not os.path.isfile(src_path) or not os.path.isfile(metadata_path):
        continue

    try:
        roots = concrete_root_contracts(src_path,metadata_path)
        contract_skeleton_pair = []
        for contract in roots:
            skeleton = get_skeleton(src_path,contract.name)
            contract_skeleton_pair.append((contract, skeleton))

        merged_skeleton = get_merged_skeleton(contract_skeleton_pair)

        SEED_GEN_SYSTEM_PROMPT = """ 
        You are a Solidity static-analysis assistant.
        Given a rule in YAML and a smart-contract element inventory, select a minimal set of seed anchors that enables downstream static analysis to extract all code relevant to verifying the rule.
        """

        for f in os.listdir("Rules"):
            if f.endswith((".yaml", ".yml")):
                with open(os.path.join("Rules", f)) as file:
                    rule = file.read()
                
                rule_name = os.path.splitext(f)[0]

                out_dir = os.path.join(output_base_dir, entry)
                os.makedirs(out_dir, exist_ok=True)

                out_path = os.path.join(out_dir, f"{rule_name}_report.json")

                if os.path.isfile(out_path):
                    print(f"Report already exists: {out_path}, skipping...")
                    continue

                seed_gen_instruction_prompt = f"""
                    You are given:
                    Input A: A rule or requirement (YAML).
                    <<<
                    {rule}
                    >>>
                    Input B: A smart-contract element inventory (JSON).
                    The inventory lists contract elements (state variables, events, functions, structs).
                    <<<
                    {merged_skeleton}
                    >>>

                    Task:
                    Return a FILTERED VERSION of the inventory containing ***ALL*** elements relevant to the rule.
                    The filtered inventory will be used as seed input to a downstream static-analysis engine,
                    which will expand dependencies automatically.

                    Requirements:
                    - Include ALL functions whose name matches any function mentioned in the rule (including overloads/variants).
                    - Include getter/setter functions for state mentioned in "state_effects" or "required_behavior".
                    - Include events mentioned in "observables" section.
                    - Include state variables explicitly mentioned or implied by "state_effects".
                    - Prefer seeds with explicit links (reads/writes/emits/calls).
                    - Preserve the original inventory structure and field names exactly.
                    - Do not modify elements; only remove irrelevant ones.
                    - If the rule is OPTIONAL and the inventory does not contain evidence that the feature exists,
                      return the inventory structure with empty lists.
                    - Do not add new fields, annotations, or invent elements.

                    **IMPORTANT: It is acceptable to include extra elements (false positives), but you MUST NOT miss any relevant elements (false negatives). When in doubt, include the element.**

                    Output:
                    - Return valid JSON only.
                    - The output must have the same top-level keys as the input inventory.
                    - Elements not relevant to the rule must be omitted.
                """

                messages = [{"role": "system", "content": SEED_GEN_SYSTEM_PROMPT},{"role": "user","content": seed_gen_instruction_prompt}]

                response = client.chat.completions.create(model=AZURE_OPENAI_DEPLOYMENT,messages=messages,max_tokens=int(MAX_TOKENS),temperature=float(TEMP))

                response_text = response.choices[0].message.content

                time.sleep(10)
                
                filtered_skeleton = json.loads(re.sub(r"^```json\s*|\s*```$", "", response_text.strip(), flags=re.DOTALL))
                
                if (isinstance(filtered_skeleton, dict) and filtered_skeleton and all(isinstance(v, list) and not v for v in filtered_skeleton.values())):
                    print("filtered_skeleton is empty")

                    EMPTY_SEED_VERIFIER_SYSTEM_PROMPT = """
                    You are a Solidity compliance auditor.

                    Context:
                    A prior rule-guided seed-selection step was executed over a static-analysis inventory
                    (functions, state variables, and events). The resulting filtered inventory was
                    structurally valid but EMPTY, meaning no rule-relevant anchors were identified.
                    This may indicate that the rule is OPTIONAL and the feature is absent, that the
                    feature is absent despite being required, or that the feature is not exposed by
                    the extracted inventory.

                    Your task:
                    Perform a final, end-to-end compliance analysis using:
                    - the rule (YAML), and
                    - the full Solidity source code.

                    Decision policy:
                    - If the rule is OPTIONAL and the feature is absent in the code, return NOT_APPLICABLE.
                    - If the rule requirements are satisfied, return PASS.
                    - Otherwise, return FAIL.

                    Return valid JSON only.
                    """
                    full_code = read_solidity_source(src_path) 
                    empty_seed_verifier_instruction_prompt = f"""

                    Input A: Rule (YAML)
                    <<<
                    {rule}
                    >>>

                    Input B: Full Solidity source code
                    <<<
                    {full_code}
                    >>>

                    Output (JSON only):
                    {{
                      "mode": "VERIFIED",
                      "result": "PASS" | "FAIL" | "NOT_APPLICABLE",
                      "reasoning": "<brief explanation>",
                      "evidence": "<specific functions, state variables, events, or patterns>",
                      "recommendations": ["<fix suggestions if FAIL; else empty list>"],
                      "fixed_code": "<optional Solidity snippet or null>"
                    }}

                    Constraints:
                    - Do not re-run seed selection.
                    - Do not assume missing code exists.
                    - Be concise and concrete.
                    """

                    messages = [{"role": "system", "content": EMPTY_SEED_VERIFIER_SYSTEM_PROMPT},{"role": "user","content": empty_seed_verifier_instruction_prompt}]

                    response = client.chat.completions.create(model=AZURE_OPENAI_DEPLOYMENT,messages=messages,max_tokens=int(MAX_TOKENS),temperature=float(TEMP))

                    response_text = response.choices[0].message.content

                    report = json.loads(re.sub(r"^```json\s*|\s*```$", "", response_text.strip(), flags=re.DOTALL))
                    print(report)
                    time.sleep(10)
                    with open(out_path, "w", encoding="utf-8") as fp:
                        json.dump(report, fp, indent=2)
                    continue

                slices = set()
                for category, items in filtered_skeleton.items():
                    for item in items:
                        name = item.get("name")
                        if not name:
                            continue
                        contract_name = item.get("contract")
                        if not contract_name:
                            continue

                        contract = next((con for con in roots if con.name == contract_name), None)

                        if contract is None:
                            continue

                        if category == "functions":
                            cur_slice = get_func_code_slice(name,contract)
                            slices.update(cur_slice)
                        elif category == "state_vars":
                            cur_slice = get_state_var_code_slice(name,contract)
                            slices.update(cur_slice)
                        elif category == "events":
                            cur_slice = get_event_code_slice(name,contract)
                            slices.update(cur_slice)

                slice_json = build_structured_slice_output(slices)
                VERIFIER_SYSTEM_PROMPT = """
                    You are a Solidity compliance assistant.

                    Your goal is to judge whether the given code satisfies a requirement/rule using the available evidence.
                    When issues are found, suggest how they could be fixed.
                    If the available code is not enough to decide, clearly say that more code is needed.
                """ 

                verifier_instruction_prompt = f"""
                    You are given:

                    Input A: A structured rule describing expected behavior.
                    <<<
                    {rule}
                    >>>

                    Input B: A slice of Solidity code that is likely relevant.
                    <<<
                    {slice_json}
                    >>>

                    Task:
                    Decide whether the code slice satisfies the rule.

                    Guidelines:
                    - Use the structured rule as guidance, but feel free to infer intent when appropriate.
                    - Base your decision only on the code shown.
                    - Use SlithIR to reason about control flow, state reads/writes, reverts, and event emissions when helpful.
                    - If you can confidently decide compliance or non-compliance from the slice, report it.
                    - If you cannot decide with confidence, ask for more code instead of guessing.

                    Output:
                    Return exactly ONE JSON object.

                    If you can decide from the slice:
                    {{
                      "mode": "VERIFIED",
                      "result": "PASS" | "FAIL",
                      "reasoning": "<brief explanation>",
                      "recommendations": [
                        "<how the issue could be fixed, if any>"
                      ],
                      "evidence": "<brief reference to relevant functions, state, events, or IR behavior>",
                      "fixed_code": "<optional Solidity snippet if an obvious local fix exists, otherwise omit or null>"
                    }}

                    If you cannot decide from the slice:
                    {{
                      "mode": "NEED_FULL_CODE",
                      "reason": "<why the slice is insufficient>",
                      "what_to_provide": "<what additional code would allow verification>"
                    }}

                    Constraints:
                    - Return valid JSON only.
                    - Be concise.
                    - Do not assume missing code exists.

                """        
                
                messages = [{"role": "system", "content": VERIFIER_SYSTEM_PROMPT},{"role": "user","content": verifier_instruction_prompt}]

                response = client.chat.completions.create(model=AZURE_OPENAI_DEPLOYMENT,messages=messages,max_tokens=int(MAX_TOKENS),temperature=float(TEMP))

                response_text = response.choices[0].message.content

                report = json.loads(re.sub(r"^```json\s*|\s*```$", "", response_text.strip(), flags=re.DOTALL))
                print(report)
                time.sleep(10)
                if report["mode"] == "NEED_FULL_CODE":
                    print("Need full code")
                    full_code = read_solidity_source(src_path)  # your existing helper
                    full_code_ir = build_full_contract_structured_output(roots)
                    verifier_instruction_full = f"""
                        You are given:

                        Input A: A structured rule describing expected behavior.
                        <<<
                        {rule}
                        >>>

                        Input B: Full Solidity code (more complete context than the slice).
                        <<<
                        {full_code}
                        >>>

                        Input C: SlithIR for functions and modifiers.
                        <<<
                        {json.dumps(full_code_ir, indent=2)}
                        >>>

                        Task:
                        Decide whether the code satisfies the rule.

                        Guidelines:
                        - Use the structured rule as guidance, but feel free to infer intent when appropriate.
                        - Use Solidity source for understanding the complete contract context.
                        - Use SlithIR to reason about control flow, state reads/writes, reverts, and event emissions.
                        - If you can decide compliance or non-compliance, report it.
                        - Provide recommendations to fix failures, and include fixed code if an obvious local fix exists.

                        Output:
                        Return exactly ONE JSON object:
                        {{
                          "mode": "VERIFIED",
                          "result": "PASS" | "FAIL",
                          "reasoning": "<brief explanation>",
                          "recommendations": [
                            "<how the issue could be fixed, if any>"
                          ],
                          "evidence": "<brief reference to relevant functions, state, events, or IR behavior>",
                          "fixed_code": "<optional Solidity snippet if an obvious local fix exists, otherwise omit or null>"
                        }}

                        Constraints:
                        - Return valid JSON only.
                        - Be concise.
                        - Do not assume missing code exists.
                        """

                    messages = [{"role": "system", "content": VERIFIER_SYSTEM_PROMPT},{"role": "user", "content": verifier_instruction_full}]

                    response = client.chat.completions.create(model=AZURE_OPENAI_DEPLOYMENT,messages=messages,max_tokens=int(MAX_TOKENS),temperature=float(TEMP))

                    response_text = response.choices[0].message.content
                    report = json.loads(re.sub(r"^```json\s*|\s*```$", "", response_text.strip(), flags=re.DOTALL))
                    print(report)
                    with open(out_path, "w", encoding="utf-8") as fp:
                        json.dump(report, fp, indent=2)
                    time.sleep(10)
                else:
                    with open(out_path, "w", encoding="utf-8") as fp:
                        json.dump(report, fp, indent=2)
    except Exception as contract_err:
        print(f"[CONTRACT ERROR] {entry}")
        print(contract_err)
        traceback.print_exc()
                    



