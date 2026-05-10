import os
import re

def refactor_codebase(root_dir="."):
    # Define which file types to scan
    target_extensions = ('.py', '.ipynb', '.yaml', '.yml', '.json', '.txt', '.md')
    
    # Exclude specific directories (e.g., git, environments)
    exclude_dirs = {'.git', 'venv', 'env', '__pycache__', '.ipynb_checkpoints', 'node_modules', 'oldData_need the scrape_time to update for it to work'}
    
    updated_files = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Modify dirnames in-place to skip excluded directories
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        
        for file in filenames:
            if not file.endswith(target_extensions):
                continue
                
            filepath = os.path.join(dirpath, file)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content
                
                # 1. Update module imports: ETL -> ETL
                new_content = re.sub(r'\bETl\b', 'ETL', new_content)
                
                # 2. Update data references: data/ -> data/
                new_content = re.sub(r'\bsrc_integrated[\\/]+data\b', 'data', new_content)
                
                # Write back only if changes were made
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    updated_files.append(filepath)
                    
            except UnicodeDecodeError:
                pass # Skip binary files or unrecognized encodings
            except Exception as e:
                print(f"Error processing {filepath}: {e}")

    print(f"\nRefactoring complete! Updated {len(updated_files)} files:")
    for f in updated_files:
        print(f" - {os.path.normpath(f)}")

if __name__ == "__main__":
    refactor_codebase()
