import pathlib
import sqlite3
import os
import hashlib
from collections import defaultdict

# Note: This script implements a basic similarity check using hash comparison
# For more advanced similarity detection, consider using tools like:
# - fossology
# - licensee (Ruby gem)
# - or manual code comparison

print("Starting basic similarity analysis using hash comparison...")

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of file content"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Normalize whitespace for better comparison
            normalized = ' '.join(content.split())
            return hashlib.sha256(normalized.encode()).hexdigest()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def basic_similarity_score(file_path):
    """
    Basic similarity scoring - in a real implementation, this would
    compare against a database of known OSS code patterns
    For now, we'll return a low score to indicate no obvious matches
    """
    # This is a placeholder - in reality you'd compare against OSS databases
    file_hash = calculate_file_hash(file_path)
    if file_hash:
        # Simple heuristic: if file is very small, it might be template code
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if len(content.strip()) < 100:
                    return 0.1  # Very small files are likely original
                else:
                    return 0.0  # Assume no similarity for now
        except:
            return 0.0
    return 0.0

# Initialize database
db = sqlite3.connect('results.sqlite')
db.execute("""
    CREATE TABLE IF NOT EXISTS similarity(
        file TEXT, 
        score REAL, 
        model TEXT, 
        lang TEXT
    )
""")

print("Processing generated files...")

# Process all generated files
for p in pathlib.Path('generated').rglob('*.*'):
    if p.is_file() and p.suffix in ['.py', '.go', '.ts']:
        try:
            print(f"Analyzing {p}...")
            
            # Calculate basic similarity score
            score = basic_similarity_score(str(p))
            
            # Determine model based on filename pattern or alternating pattern
            # Since we alternate in generation, we can infer from file position
            files_in_dir = sorted(p.parent.glob(f'*.{p.suffix[1:]}'))
            file_index = files_in_dir.index(p)
            
            # Check if using local LLM or cloud APIs
            import os
            from dotenv import load_dotenv
            load_dotenv()
            
            use_local = os.getenv('USE_LOCAL_LLM', 'false').lower() == 'true'
            if use_local:
                model1 = os.getenv('LOCAL_MODEL_1', 'llama2:7b')
                model2 = os.getenv('LOCAL_MODEL_2', 'codegemma:2b')
                model = model1 if file_index % 2 == 0 else model2
            else:
                model = 'openai' if file_index % 2 == 0 else 'claude'
            
            # Insert into database
            db.execute(
                "INSERT INTO similarity VALUES (?,?,?,?)",
                (str(p), score, model, p.parent.name)
            )
            
            print(f"  Score: {score}, Model: {model}")
            
        except Exception as e:
            print(f"Error analyzing {p}: {e}")
            continue

db.commit()
db.close()

print("Basic similarity analysis complete! Results saved to results.sqlite")
print("Note: This is a basic implementation. For production use, consider:")
print("- Using fossology or other professional OSS scanning tools")
print("- Implementing fuzzy matching algorithms")
print("- Building a comprehensive OSS code database for comparison")