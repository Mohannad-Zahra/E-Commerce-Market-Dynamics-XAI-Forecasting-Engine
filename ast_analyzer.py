import ast
import os
import json
from collections import defaultdict
import dataclasses

@dataclasses.dataclass
class NodeInfo:
    file_path: str
    type: str
    name: str
    args: list
    returns: str
    docstring: str
    line_start: int
    line_end: int

    def to_dict(self):
        return dataclasses.asdict(self)

def get_annotation_name(node):
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Constant):
        return str(node.value)
    elif isinstance(node, ast.Subscript):
        value = get_annotation_name(node.value)
        slice_val = get_annotation_name(node.slice)
        return f"{value}[{slice_val}]"
    elif isinstance(node, ast.Attribute):
        value = get_annotation_name(node.value)
        return f"{value}.{node.attr}"
    return type(node).__name__

class ASTVisitor(ast.NodeVisitor):
    def __init__(self, file_path):
        self.file_path = file_path
        self.nodes = []
        self.current_class = None

    def visit_ClassDef(self, node):
        docstring = ast.get_docstring(node)
        self.nodes.append(NodeInfo(
            file_path=self.file_path,
            type='class',
            name=node.name,
            args=[get_annotation_name(b) for b in node.bases],
            returns=None,
            docstring=docstring,
            line_start=node.lineno,
            line_end=node.end_lineno
        ))
        
        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        return self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node):
        return self._visit_function(node, is_async=True)
        
    def _visit_function(self, node, is_async):
        docstring = ast.get_docstring(node)
        args = []
        for arg in node.args.args:
            args.append({
                'name': arg.arg,
                'type': get_annotation_name(arg.annotation)
            })
            
        returns = get_annotation_name(node.returns)
        
        node_type = 'method' if self.current_class else 'function'
        name = f"{self.current_class}.{node.name}" if self.current_class else node.name
        
        self.nodes.append(NodeInfo(
            file_path=self.file_path,
            type=node_type,
            name=name,
            args=args,
            returns=returns,
            docstring=docstring,
            line_start=node.lineno,
            line_end=node.end_lineno
        ))
        self.generic_visit(node)

def analyze_directory(root_dir):
    all_nodes = []
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip hidden directories and specific virtual envs or cache
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ('__pycache__', 'venv', 'env', 'node_modules')]
        
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            
            if filename.endswith('.py'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    tree = ast.parse(content)
                    visitor = ASTVisitor(file_path)
                    visitor.visit(tree)
                    all_nodes.extend(visitor.nodes)
                except Exception as e:
                    pass
            elif filename.endswith('.ipynb'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        nb_data = json.load(f)
                        
                    content_lines = []
                    for cell in nb_data.get('cells', []):
                        if cell.get('cell_type') == 'code':
                            source = cell.get('source', [])
                            if isinstance(source, list):
                                content_lines.extend(source)
                            else:
                                content_lines.append(source)
                            content_lines.append('\n')
                    
                    content = "".join(content_lines)
                    # Some cells might have magic commands like !pip or %matplotlib, we need to filter them out for AST parsing
                    filtered_content = []
                    for line in content.split('\n'):
                        if line.strip().startswith('!') or line.strip().startswith('%'):
                            filtered_content.append('# ' + line)
                        else:
                            filtered_content.append(line)
                            
                    clean_content = '\n'.join(filtered_content)
                    
                    tree = ast.parse(clean_content)
                    visitor = ASTVisitor(file_path)
                    visitor.visit(tree)
                    all_nodes.extend(visitor.nodes)
                except Exception as e:
                    pass
                    
    return all_nodes

def main():
    workspace = r"c:\Users\mohan\OneDrive\Desktop\Wise Purchaser"
    nodes = analyze_directory(workspace)
    
    # Organize by name to find duplicates
    by_name = defaultdict(list)
    for node in nodes:
        if not node.name.endswith('__init__'):
            by_name[node.name].append(node.to_dict())
        
    duplicates = {name: items for name, items in by_name.items() if len(items) > 1}
    
    output = {
        'all_nodes': [node.to_dict() for node in nodes],
        'duplicates': duplicates,
        'summary': {
            'total_nodes': len(nodes),
            'unique_names': len(by_name),
            'names_with_duplicates': len(duplicates)
        }
    }
    
    with open(os.path.join(workspace, 'ast_analysis_output.json'), 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

if __name__ == '__main__':
    main()
