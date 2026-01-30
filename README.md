# SpecGuard

A grammar-grounded approach to verifying smart contract compliance with natural-language specifications using Large Language Models.

## Overview

SpecGuard addresses the challenge of verifying software compliance against natural-language specifications by constraining LLM-based interpretation through programming language grammar. The system achieves 85.56% violation detection on ERC-20 smart contracts, outperforming direct LLM prompting by 1.38×.

## Key Features

- **Grammar-Constrained Specification Processing**: Transforms natural-language requirements into structured intermediate representations grounded in Solidity grammar constructs
- **Dependency-Aware Code Slicing**: Isolates compliance-critical implementation fragments using static analysis
- **LLM-Based Compliance Verification**: Systematically assesses whether localized implementations satisfy structured requirements
- **Structured Reporting**: Generates actionable compliance reports with evidence, reasoning, and remediation suggestions

## Project Structure

```
SpecGuard/
├── dataset/              # Smart contract evaluation dataset
├── generate_req.py       # Requirement extraction and processing
├── verifier.py          # Main compliance verification engine
├── simple_verifier.py   # Baseline direct prompting verifier
├── reports/             # Grammar-grounded verification results
├── reports_baseline/    # Direct prompting baseline results
├── Rules/               # Grammar-constrained requirement specifications
└── Rule_Dep/            # Grammar Dep Graph extraction
```

## Requirements

- Python 3.8+
- GPT-4o API access (Azure OpenAI Service)
- [Slither](https://github.com/crytic/slither) for static analysis
- Solidity compiler (solc)

## Evaluation Results

Tested on 500 deployed ERC-20 contracts:
- **Overall Detection Rate**: 85.56% (1375/1607 violations)
- **Missing Return Values**: 56.46% - 95.82%
- **Missing Events**: 98.68%
- **Missing Metadata Functions**: 97.44% - 99.32%