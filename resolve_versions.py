import json
import os

def resolve_duplicates():
    workspace = r"c:\Users\mohan\OneDrive\Desktop\Wise Purchaser"
    with open(os.path.join(workspace, 'ast_analysis_output.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    all_nodes = data['all_nodes']
    by_name = {}
    
    # We will build an active list
    active_nodes = []
    
    for node in all_nodes:
        name = node['name']
        if name not in by_name:
            by_name[name] = []
        by_name[name].append(node)
        
    for name, nodes_list in by_name.items():
        if len(nodes_list) == 1:
            active_nodes.append(nodes_list[0])
            continue
            
        # We have duplicates. We need to select the newest, most robust.
        # 1. Prefer ones NOT in 'oldData_need the scrape_time to update for it to work'
        # 2. Prefer the one with the latest modification time.
        
        best_node = None
        best_time = -1
        
        for node in nodes_list:
            file_path = node['file_path']
            # penalty for old folder
            is_old = 'oldData_need the scrape_time' in file_path
            
            try:
                mtime = os.path.getmtime(file_path)
            except:
                mtime = 0
                
            score = mtime
            if is_old:
                score -= 1e10 # Huge penalty
                
            if score > best_time:
                best_time = score
                best_node = node
                
        if best_node:
            active_nodes.append(best_node)

    # Let's save the active nodes
    output_path = os.path.join(workspace, 'active_nodes_graph.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({'active_nodes': active_nodes}, f, indent=2)
        
    print(f"Resolved versions. Active nodes count: {len(active_nodes)}")
    
    # Let's also group active nodes by directory/component to help with PROTOCOL 2
    components = {}
    for node in active_nodes:
        # Get relative path
        rel_path = os.path.relpath(node['file_path'], workspace)
        # First level directory as component name roughly
        parts = rel_path.split(os.sep)
        if len(parts) > 1:
            comp_name = parts[0]
        else:
            comp_name = "Root"
            
        if comp_name not in components:
            components[comp_name] = []
        components[comp_name].append(node['name'])
        
    print("\nComponents Found:")
    for comp, items in components.items():
        print(f" - {comp}: {len(items)} active nodes")

if __name__ == '__main__':
    resolve_duplicates()
