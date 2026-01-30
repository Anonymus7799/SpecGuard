import json
import numpy as np

def load_grammar_data(json_file="complete_dependencies.json"):
    """Load the grammar dependency data from JSON file"""
    with open(json_file, 'r') as f:
        return json.load(f)

def calculate_depths(adj_list, root="sourceUnit"):
    """
    Calculate depth of each node from the root.
    Depth is the minimum distance from root via parser rule dependencies.
    """
    depths = {}
    visited = set()
    
    def dfs(node, current_depth):
        if node in visited:
            if current_depth < depths.get(node, float('inf')):
                depths[node] = current_depth
            else:
                return
        else:
            visited.add(node)
            depths[node] = current_depth
        
        # Follow parser rules to dependencies
        if node in adj_list:
            for dep in adj_list[node].get("parser_rules", []):
                if dep in adj_list:  # Only follow if it's a known node
                    dfs(dep, current_depth + 1)
    
    # Start DFS from root
    if root in adj_list:
        dfs(root, 0)
    
    # For any nodes not reached, estimate depth from their dependents
    for node in adj_list:
        if node not in depths:
            min_depth_from_dependents = float('inf')
            
            # Find nodes that reference this node
            for other_node, other_data in adj_list.items():
                if node in other_data.get("parser_rules", []):
                    if other_node in depths:
                        min_depth_from_dependents = min(
                            min_depth_from_dependents, 
                            depths[other_node] + 1
                        )
            
            if min_depth_from_dependents != float('inf'):
                depths[node] = min_depth_from_dependents
            else:
                # Isolated node, assign a high depth
                depths[node] = 10
    
    return depths

def calculate_problem_scores(adj_list):
    """
    Calculate problem scores for each node based on depth-aware fan-out analysis.
    
    Problem Score = (Fan-out / (Depth + 1)) * sqrt(Depth + 1)
    """
    # First calculate depths
    depths = calculate_depths(adj_list)
    
    problem_scores = {}
    
    for node, data in adj_list.items():
        depth = depths.get(node, 10)
        
        # Calculate fan-out (outgoing dependencies)
        parser_fan_out = len(set(data.get("parser_rules", [])))
        lexer_fan_out = len(set(data.get("lexer_tokens", [])))
        total_fan_out = parser_fan_out + lexer_fan_out
        
        # Calculate in-degree (how many nodes reference this one)
        in_degree = 0
        for other_node, other_data in adj_list.items():
            if node in other_data.get("parser_rules", []):
                in_degree += 1
        
        # Calculate fan-out-to-depth ratio
        # Adding 1 to depth to avoid division by zero for root
        if depth + 1 > 0:
            fan_out_depth_ratio = total_fan_out / (depth + 1)
        else:
            fan_out_depth_ratio = total_fan_out
        
        # Calculate problem score
        # Higher score = more problematic (high fan-out at depth)
        problem_score = fan_out_depth_ratio * np.sqrt(depth + 1)
        
        # Additional penalty for nodes with high fan-out AND high in-degree
        # These are "hub" nodes deep in the tree
        if depth > 2 and in_degree > 3:
            problem_score *= 1.5
        
        problem_scores[node] = {
            "depth": depth,
            "parser_fan_out": parser_fan_out,
            "lexer_fan_out": lexer_fan_out,
            "total_fan_out": total_fan_out,
            "in_degree": in_degree,
            "fan_out_depth_ratio": round(fan_out_depth_ratio, 2),
            "problem_score": round(problem_score, 2),
            "is_problematic": problem_score > 2.0 and depth > 2,
            "problem_severity": classify_severity(problem_score, depth)
        }
    
    return problem_scores

def classify_severity(problem_score, depth):
    """Classify problem severity based on score and depth"""
    if depth <= 2:
        return "low"  # Root nodes can have high fan-out
    
    if problem_score > 5:
        return "critical"
    elif problem_score > 3:
        return "high"
    elif problem_score > 2:
        return "medium"
    elif problem_score > 1:
        return "low"
    else:
        return "normal"

def print_problem_analysis(problem_scores):
    """Print analysis of problem nodes"""
    print("=" * 100)
    print("SOLIDITY GRAMMAR PROBLEM NODE ANALYSIS")
    print("=" * 100)
    
    # Sort nodes by problem score (highest first)
    sorted_nodes = sorted(
        problem_scores.items(),
        key=lambda x: x[1]["problem_score"],
        reverse=True
    )
    
    # Print summary statistics
    total_nodes = len(problem_scores)
    problematic_nodes = sum(1 for _, stats in sorted_nodes 
                           if stats["is_problematic"])
    
    print(f"\n📊 SUMMARY")
    print(f"   Total Nodes: {total_nodes}")
    print(f"   Problematic Nodes: {problematic_nodes} ({problematic_nodes/total_nodes*100:.1f}%)")
    
    # Print critical nodes
    print(f"\n🚨 CRITICAL PROBLEM NODES (Score > 5)")
    print("-" * 100)
    critical_count = 0
    for node, stats in sorted_nodes:
        if stats["problem_severity"] == "critical":
            critical_count += 1
            print(f"  {node:30} | Depth: {stats['depth']:2d} | "
                  f"Fan-out: {stats['total_fan_out']:3d} | "
                  f"Score: {stats['problem_score']:6.2f}")
    
    if critical_count == 0:
        print("  (No critical nodes found)")
    
    # Print high priority nodes
    print(f"\n⚠️  HIGH PRIORITY NODES (Score 3-5)")
    print("-" * 100)
    high_count = 0
    for node, stats in sorted_nodes:
        if stats["problem_severity"] == "high":
            high_count += 1
            print(f"  {node:30} | Depth: {stats['depth']:2d} | "
                  f"Fan-out: {stats['total_fan_out']:3d} | "
                  f"Score: {stats['problem_score']:6.2f}")
    
    if high_count == 0:
        print("  (No high priority nodes found)")
    
    # Print all nodes sorted by depth
    print(f"\n📈 NODES BY DEPTH (with problem scores)")
    print("-" * 100)
    
    # Group by depth
    nodes_by_depth = {}
    for node, stats in sorted_nodes:
        depth = stats["depth"]
        if depth not in nodes_by_depth:
            nodes_by_depth[depth] = []
        nodes_by_depth[depth].append((node, stats))
    
    for depth in sorted(nodes_by_depth.keys()):
        print(f"\nDepth {depth}:")
        print(f"{'Node':30} {'Fan-out':>8} {'In-degree':>10} {'Score':>8} {'Severity':>12}")
        print("-" * 80)
        
        for node, stats in nodes_by_depth[depth]:
            severity_icon = ""
            if stats["problem_severity"] == "critical":
                severity_icon = "🔴"
            elif stats["problem_severity"] == "high":
                severity_icon = "🟠"
            elif stats["problem_severity"] == "medium":
                severity_icon = "🟡"
            elif stats["problem_severity"] == "low":
                severity_icon = "🟢"
            else:
                severity_icon = "⚪"
            
            print(f"{severity_icon} {node:28} {stats['total_fan_out']:8d} "
                  f"{stats['in_degree']:10d} {stats['problem_score']:8.2f} "
                  f"{stats['problem_severity'].upper():>10}")
    
    # Print recommendations
    print(f"\n🎯 GROUPING RECOMMENDATIONS")
    print("-" * 100)
    
    recommendations = []
    for node, stats in sorted_nodes:
        if stats["is_problematic"]:
            if stats["problem_severity"] == "critical":
                rec = f"  🔴 GROUP IMMEDIATELY: {node} (depth {stats['depth']}, score {stats['problem_score']:.2f})"
            elif stats["problem_severity"] == "high":
                rec = f"  🟠 HIGH PRIORITY: {node} (depth {stats['depth']}, score {stats['problem_score']:.2f})"
            elif stats["problem_severity"] == "medium":
                rec = f"  🟡 MEDIUM PRIORITY: {node} (depth {stats['depth']}, score {stats['problem_score']:.2f})"
            else:
                continue
            recommendations.append((stats["problem_score"], rec))
    
    if recommendations:
        # Sort by score (highest first)
        recommendations.sort(key=lambda x: x[0], reverse=True)
        for _, rec in recommendations[:10]:  # Show top 10
            print(rec)
    else:
        print("  No major grouping recommendations - grammar looks well-structured!")

def save_problem_scores(problem_scores, filename="problem_scores.json"):
    """Save problem scores to JSON file"""
    with open(filename, 'w') as f:
        json.dump(problem_scores, f, indent=2)
    print(f"\n✅ Problem scores saved to {filename}")

def generate_csv_report(problem_scores, filename="problem_scores.csv"):
    """Generate a CSV report of problem scores"""
    import csv
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Node', 'Depth', 'Parser_Fan_Out', 'Lexer_Fan_Out', 
            'Total_Fan_Out', 'In_Degree', 'Fan_Out_Depth_Ratio', 
            'Problem_Score', 'Is_Problematic', 'Severity'
        ])
        
        for node, stats in problem_scores.items():
            writer.writerow([
                node,
                stats['depth'],
                stats['parser_fan_out'],
                stats['lexer_fan_out'],
                stats['total_fan_out'],
                stats['in_degree'],
                stats['fan_out_depth_ratio'],
                stats['problem_score'],
                stats['is_problematic'],
                stats['problem_severity']
            ])
    
    print(f"✅ CSV report saved to {filename}")

# Main execution
if __name__ == "__main__":
    # Load your grammar data
    print("Loading grammar data...")
    data = load_grammar_data()  # Or pass your data directly
    
    # Calculate problem scores
    print("Calculating problem scores...")
    problem_scores = calculate_problem_scores(data)
    
    # Print analysis
    print_problem_analysis(problem_scores)
    
    # Save results
    save_problem_scores(problem_scores, "solidity_grammar_problem_scores.json")
    generate_csv_report(problem_scores, "solidity_grammar_problem_scores.csv")
    
    print("\n" + "=" * 100)
    print("ANALYSIS COMPLETE")
    print("=" * 100)
    
    # Quick summary
    critical_nodes = [n for n, s in problem_scores.items() 
                     if s["problem_severity"] == "critical"]
    high_nodes = [n for n, s in problem_scores.items() 
                  if s["problem_severity"] == "high"]
    
    print(f"\n📋 Quick Summary:")
    print(f"   Critical nodes ({len(critical_nodes)}): {', '.join(critical_nodes[:3])}{'...' if len(critical_nodes) > 3 else ''}")
    print(f"   High priority nodes ({len(high_nodes)}): {', '.join(high_nodes[:3])}{'...' if len(high_nodes) > 3 else ''}")