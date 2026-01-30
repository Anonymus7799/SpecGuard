from antlr4 import FileStream, CommonTokenStream
from ANTLRv4Lexer import ANTLRv4Lexer
from ANTLRv4Parser import ANTLRv4Parser
from ANTLRv4ParserVisitor import ANTLRv4ParserVisitor
import json

class CompleteDependencyExtractor(ANTLRv4ParserVisitor):
    """
    Extracts both parser rule and lexer token dependencies.
    Creates adjacency list with both types of dependencies.
    """
    
    def __init__(self):
        self.graph = {}  # rule -> {'parser_rules': [...], 'lexer_tokens': [...]}
        self.current_rule = None
        
    def visitParserRuleSpec(self, ctx):
        """Visit parser rule definition"""
        self.current_rule = ctx.RULE_REF().getText()
        
        # Initialize node with both types of dependencies
        self.graph[self.current_rule] = {
            'parser_rules': [],
            'lexer_tokens': []
        }
        
        # Visit rule body
        return self.visitChildren(ctx)
    
    def visitRuleref(self, ctx):
        """Visit parser rule reference"""
        if self.current_rule is None:
            return
        
        target_rule = ctx.RULE_REF().getText()
        
        # Add parser rule dependency (avoid duplicates)
        if target_rule not in self.graph[self.current_rule]['parser_rules']:
            self.graph[self.current_rule]['parser_rules'].append(target_rule)
        
        return self.visitChildren(ctx)
    
    def visitTerminalDef(self, ctx):
        """Visit terminal (lexer token) reference"""
        if self.current_rule is None:
            return
        
        # Get token name
        token_name = None
        if ctx.TOKEN_REF():
            token_name = ctx.TOKEN_REF().getText()
        elif ctx.STRING_LITERAL():
            # String literals like '+', 'function', etc.
            token_name = ctx.STRING_LITERAL().getText()
        
        if token_name:
            # Add lexer token dependency (avoid duplicates)
            if token_name not in self.graph[self.current_rule]['lexer_tokens']:
                self.graph[self.current_rule]['lexer_tokens'].append(token_name)
        
        return self.visitChildren(ctx)


def build_complete_graph(parser_grammar_file):
    """
    Build complete dependency graph including lexer tokens.
    
    Returns:
        dict: graph[rule] = {'parser_rules': [...], 'lexer_tokens': [...]}
    """
    extractor = CompleteDependencyExtractor()
    
    # Parse parser grammar
    print(f"Parsing {parser_grammar_file}...")
    parser_input = FileStream(parser_grammar_file)
    lexer = ANTLRv4Lexer(parser_input)
    tokens = CommonTokenStream(lexer)
    parser = ANTLRv4Parser(tokens)
    parser_tree = parser.grammarSpec()
    extractor.visit(parser_tree)
    
    return extractor.graph


def print_graph_summary(graph):
    """Print summary statistics of the graph"""
    print(f"\n=== Complete Dependency Graph ===")
    print(f"Total parser rules: {len(graph)}")
    
    total_parser_deps = sum(len(v['parser_rules']) for v in graph.values())
    total_token_deps = sum(len(v['lexer_tokens']) for v in graph.values())
    
    print(f"Total parser rule dependencies: {total_parser_deps}")
    print(f"Total lexer token dependencies: {total_token_deps}")
    print(f"Total dependencies: {total_parser_deps + total_token_deps}")
    
    # Find most connected nodes (by parser rules)
    by_parser_degree = sorted(graph.items(), key=lambda x: len(x[1]['parser_rules']), reverse=True)
    print(f"\nTop 10 rules by parser rule dependencies:")
    for i, (name, deps) in enumerate(by_parser_degree[:10], 1):
        print(f"  {i}. {name}: {len(deps['parser_rules'])} parser rules")
    
    # Find rules using most tokens
    by_token_count = sorted(graph.items(), key=lambda x: len(x[1]['lexer_tokens']), reverse=True)
    print(f"\nTop 10 rules by lexer token usage:")
    for i, (name, deps) in enumerate(by_token_count[:10], 1):
        print(f"  {i}. {name}: {len(deps['lexer_tokens'])} tokens")
    
    # Find leaf rules (no parser rule dependencies)
    leaf_rules = [name for name, deps in graph.items() if len(deps['parser_rules']) == 0]
    print(f"\nLeaf rules (no parser rule dependencies): {len(leaf_rules)}")
    if leaf_rules[:5]:
        print(f"  Examples: {', '.join(leaf_rules[:5])}")
    
    # Find recursive rules
    recursive_rules = [rule for rule, deps in graph.items() if rule in deps['parser_rules']]
    print(f"\nRecursive rules: {len(recursive_rules)}")
    if recursive_rules[:5]:
        print(f"  Examples: {', '.join(recursive_rules[:5])}")


def export_graph_to_json(graph, output_file):
    """Export complete graph to JSON file"""
    with open(output_file, 'w') as f:
        json.dump(graph, f, indent=2)
    print(f"\nExported complete dependency graph to {output_file}")


def export_parser_only_adjacency_list(graph, output_file):
    """
    Export simple adjacency list with parser rules only.
    
    Format:
    {
      "expression": ["term", "factor"],
      "statement": ["block", "expression"]
    }
    """
    simple_graph = {}
    for rule, deps in graph.items():
        simple_graph[rule] = deps['parser_rules']
    
    with open(output_file, 'w') as f:
        json.dump(simple_graph, f, indent=2)
    print(f"Exported parser-only adjacency list to {output_file}")


def export_graph_to_dot(graph, output_file):
    """Export graph to Graphviz DOT format (both parser rules and tokens)"""
    with open(output_file, 'w') as f:
        f.write("digraph CompleteDependencies {\n")
        f.write("  rankdir=LR;\n")
        f.write("  \n")
        
        # Define node styles
        f.write("  // Parser rules (blue boxes)\n")
        f.write("  node [shape=box, fillcolor=lightblue, style=filled];\n")
        for rule_name in graph.keys():
            f.write(f'  "{rule_name}";\n')
        
        f.write("\n  // Lexer tokens (green ovals)\n")
        f.write("  node [shape=oval, fillcolor=lightgreen, style=filled];\n")
        all_tokens = set()
        for deps in graph.values():
            all_tokens.update(deps['lexer_tokens'])
        for token in sorted(all_tokens):
            f.write(f'  "{token}";\n')
        
        # Parser rule edges (solid)
        f.write("\n  // Parser rule dependencies (solid arrows)\n")
        for source, deps in graph.items():
            for target in deps['parser_rules']:
                # Mark recursive edges differently
                if source == target:
                    f.write(f'  "{source}" -> "{target}" [color=red, penwidth=2];\n')
                else:
                    f.write(f'  "{source}" -> "{target}";\n')
        
        # Lexer token edges (dashed)
        f.write("\n  // Lexer token dependencies (dashed arrows)\n")
        for source, deps in graph.items():
            for token in deps['lexer_tokens']:
                f.write(f'  "{source}" -> "{token}" [style=dashed, color=gray];\n')
        
        f.write("}\n")
    
    print(f"Exported DOT to {output_file}")
    print(f"Generate image with: dot -Tpng {output_file} -o complete_graph.png")


def export_parser_only_dot(graph, output_file):
    """Export graph to Graphviz DOT format (parser rules only)"""
    with open(output_file, 'w') as f:
        f.write("digraph ParserRuleDependencies {\n")
        f.write("  rankdir=LR;\n")
        f.write("  node [shape=box, fillcolor=lightblue, style=filled];\n\n")
        
        # Edges
        for source, deps in graph.items():
            for target in deps['parser_rules']:
                # Mark recursive edges differently
                if source == target:
                    f.write(f'  "{source}" -> "{target}" [color=red, penwidth=2];\n')
                else:
                    f.write(f'  "{source}" -> "{target}";\n')
        
        f.write("}\n")
    
    print(f"Exported parser-only DOT to {output_file}")
    print(f"Generate image with: dot -Tpng {output_file} -o parser_graph.png")


def print_rule_details(graph, rule_name):
    """Print detailed information about a specific rule"""
    if rule_name not in graph:
        print(f"Rule '{rule_name}' not found in graph")
        return
    
    deps = graph[rule_name]
    
    print(f"\n=== Rule: {rule_name} ===")
    print(f"Total parser rule dependencies: {len(deps['parser_rules'])}")
    print(f"Total lexer token dependencies: {len(deps['lexer_tokens'])}")
    
    if deps['parser_rules']:
        print("\nParser Rules:")
        for target in deps['parser_rules']:
            recursive_marker = " (RECURSIVE)" if target == rule_name else ""
            print(f"  → {target}{recursive_marker}")
    else:
        print("\nParser Rules: (none - leaf rule)")
    
    if deps['lexer_tokens']:
        print("\nLexer Tokens:")
        for token in deps['lexer_tokens']:
            print(f"  → {token}")
    else:
        print("\nLexer Tokens: (none)")


# Main usage
if __name__ == "__main__":
    # Build the complete dependency graph
    graph = build_complete_graph('SolidityParser.g4')
    
    # Print summary
    print_graph_summary(graph)
    
    # Export complete graph to JSON
    export_graph_to_json(graph, 'complete_dependencies.json')
    
    # Export parser-only adjacency list
    export_parser_only_adjacency_list(graph, 'parser_adjacency_list.json')
    
    # Export complete graph to DOT
    export_graph_to_dot(graph, 'complete_graph.dot')
    
    # Export parser-only graph to DOT
    export_parser_only_dot(graph, 'parser_graph.dot')
    
    # Example: Print details for specific rules
    print_rule_details(graph, 'expression')
    print_rule_details(graph, 'functionDefinition')
    print_rule_details(graph, 'sourceUnit')
    print_rule_details(graph, 'pragmaDirective')