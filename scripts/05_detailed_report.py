import json
import pathlib
import sqlite3
import pandas as pd
from datetime import datetime
import re
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def extract_code_from_llm_output(content):
    """Extract actual code from LLM output that may contain markdown blocks"""
    # Look for code blocks
    code_block_pattern = r'```(?:python|go|typescript|js|ts)?\n(.*?)```'
    matches = re.findall(code_block_pattern, content, re.DOTALL | re.IGNORECASE)
    
    if matches:
        # Return the first code block found
        return matches[0].strip()
    else:
        # If no code blocks, return the content as-is
        return content.strip()

def analyze_file_issues(file_path):
    """Analyze specific issues in a file"""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Check for common license-related patterns
        license_patterns = [
            (r'copyright', 'Copyright notice found'),
            (r'license', 'License mention found'),
            (r'mit\s+license', 'MIT License reference'),
            (r'apache', 'Apache License reference'),
            (r'gpl', 'GPL License reference'),
            (r'bsd', 'BSD License reference'),
            (r'@author', 'Author attribution'),
            (r'@copyright', 'Copyright annotation'),
            (r'\(c\)', 'Copyright symbol'),
            (r'all rights reserved', 'Rights reservation clause'),
            (r'permission is hereby granted', 'Permission statement'),
        ]
        
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            for pattern, description in license_patterns:
                if re.search(pattern, line_lower):
                    issues.append({
                        'line_number': line_num,
                        'line_content': line.strip(),
                        'issue_type': description,
                        'pattern_matched': pattern
                    })
        
        # Check for long copied code blocks (potential copy-paste)
        if len(lines) > 100:
            issues.append({
                'line_number': 'N/A',
                'line_content': f'File has {len(lines)} lines',
                'issue_type': 'Large file - potential code reuse',
                'pattern_matched': 'file_size'
            })
        
        # Check for markdown formatting (indicates LLM output not cleaned)
        markdown_patterns = [
            (r'^```', 'Code block marker'),
            (r'Here is', 'LLM explanation text'),
            (r'This code', 'LLM description text'),
            (r'Note that', 'LLM note text'),
        ]
        
        for line_num, line in enumerate(lines, 1):
            for pattern, description in markdown_patterns:
                if re.search(pattern, line):
                    issues.append({
                        'line_number': line_num,
                        'line_content': line.strip(),
                        'issue_type': f'LLM output formatting: {description}',
                        'pattern_matched': pattern
                    })
    
    except Exception as e:
        issues.append({
            'line_number': 'N/A',
            'line_content': f'Error reading file: {str(e)}',
            'issue_type': 'File read error',
            'pattern_matched': 'error'
        })
    
    return issues

def generate_detailed_report():
    """Generate detailed report with file-level issue analysis"""
    
    print("Generating detailed issue report...")
    
    # Create output directory
    output_dir = pathlib.Path('results')
    output_dir.mkdir(exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Initialize database
    db = sqlite3.connect('results.sqlite')
    
    # Scan generated files directly
    files = []
    for lang_dir in pathlib.Path('generated').iterdir():
        if lang_dir.is_dir():
            for file_path in lang_dir.glob('*'):
                if file_path.is_file():
                    files.append({
                        'file_path': str(file_path),
                        'lang': lang_dir.name
                    })
    files_df = pd.DataFrame(files)
    
    if files_df.empty:
        print("No files found for analysis")
        return
    
    all_issues = []
    
    for _, row in files_df.iterrows():
        file_path = row['file_path']
        lang = row['lang']
        
        print(f"Analyzing {file_path}...")
        
        # Get file info
        try:
            file_stat = pathlib.Path(file_path).stat()
            file_size = file_stat.st_size
        except:
            file_size = 0
        
        # Determine model
        try:
            file_name = pathlib.Path(file_path).name
            lang_files = sorted(list(pathlib.Path(f'generated/{lang}').glob('*')))
            matching_files = [f for f in lang_files if f.name == file_name]
            
            if matching_files:
                file_index = lang_files.index(matching_files[0])
                use_local = os.getenv('USE_LOCAL_LLM', 'false').lower() == 'true'
                if use_local:
                    model1 = os.getenv('LOCAL_MODEL_1', 'llama2:7b')
                    model2 = os.getenv('LOCAL_MODEL_2', 'codegemma:2b')
                    model = model1 if file_index % 2 == 0 else model2
                else:
                    model = 'openai' if file_index % 2 == 0 else 'claude'
            else:
                model = 'unknown'
        except:
            model = 'unknown'
        
        # Get license detection results
        try:
            license_results = pd.read_sql_query("""
                SELECT license_key, license_name, score
                FROM licenses
                WHERE file_path = ?
                ORDER BY score DESC
            """, db, params=[file_path])
        except:
            license_results = pd.DataFrame()
        
        # Get similarity results
        try:
            similarity_results = pd.read_sql_query("""
                SELECT score
                FROM similarity
                WHERE file = ?
            """, db, params=[file_path])
            similarity_score = similarity_results['score'].iloc[0] if not similarity_results.empty else 0.0
        except:
            similarity_score = 0.0
        
        # Analyze file issues
        file_issues = analyze_file_issues(file_path)
        
        # Add context to each issue
        for issue in file_issues:
            all_issues.append({
                'file_path': file_path,
                'language': lang,
                'model': model,
                'file_size_bytes': file_size,
                'similarity_score': similarity_score,
                'line_number': issue['line_number'],
                'line_content': issue['line_content'],
                'issue_type': issue['issue_type'],
                'pattern_matched': issue['pattern_matched'],
                'high_confidence_licenses': '; '.join(license_results[license_results['score'] > 0.8]['license_key'].tolist()) if not license_results.empty else 'none',
                'max_license_score': license_results['score'].max() if not license_results.empty else 0.0
            })
    
    # Create detailed issues dataframe
    issues_df = pd.DataFrame(all_issues)
    
    if not issues_df.empty:
        # Save detailed issues report
        detailed_report_file = output_dir / f"detailed_issues_{timestamp}.csv"
        issues_df.to_csv(detailed_report_file, index=False)
        print(f"Detailed issues report saved to {detailed_report_file}")
        
        # Generate summary by issue type
        issue_summary = issues_df.groupby(['issue_type', 'language', 'model']).size().reset_index(name='count')
        issue_summary_file = output_dir / f"issue_summary_{timestamp}.csv"
        issue_summary.to_csv(issue_summary_file, index=False)
        print(f"Issue summary saved to {issue_summary_file}")
        
        # Generate file-level summary
        file_summary = issues_df.groupby(['file_path', 'language', 'model']).agg({
            'issue_type': 'count',
            'similarity_score': 'first',
            'max_license_score': 'first',
            'high_confidence_licenses': 'first'
        }).rename(columns={'issue_type': 'total_issues'}).reset_index()
        
        file_summary_file = output_dir / f"file_issues_summary_{timestamp}.csv"
        file_summary.to_csv(file_summary_file, index=False)
        print(f"File summary saved to {file_summary_file}")
        
        # Print summary statistics
        print(f"\n=== DETAILED ISSUE ANALYSIS SUMMARY ===")
        print(f"Total files analyzed: {issues_df['file_path'].nunique()}")
        print(f"Total issues found: {len(issues_df)}")
        
        print(f"\nIssue types found:")
        issue_counts = issues_df['issue_type'].value_counts()
        for issue_type, count in issue_counts.items():
            print(f"  - {issue_type}: {count}")
        
        print(f"\nFiles with most issues:")
        file_issue_counts = issues_df['file_path'].value_counts().head(5)
        for file_path, count in file_issue_counts.items():
            print(f"  - {file_path}: {count} issues")
        
        print(f"\nIssues by model:")
        model_issue_counts = issues_df['model'].value_counts()
        for model, count in model_issue_counts.items():
            print(f"  - {model}: {count} issues")
        
        # Highlight high-risk files
        high_risk_files = file_summary[
            (file_summary['total_issues'] > 5) | 
            (file_summary['max_license_score'] > 0.8) |
            (file_summary['similarity_score'] > 0.8)
        ]
        
        if not high_risk_files.empty:
            print(f"\n=== HIGH RISK FILES ===")
            for _, row in high_risk_files.iterrows():
                print(f"File: {row['file_path']}")
                print(f"  Model: {row['model']}")
                print(f"  Issues: {row['total_issues']}")
                print(f"  Max License Score: {row['max_license_score']}")
                print(f"  Similarity Score: {row['similarity_score']}")
                if row['high_confidence_licenses'] != 'none':
                    print(f"  Detected Licenses: {row['high_confidence_licenses']}")
                print()
    else:
        print("No issues found in analyzed files")
    
    db.close()
    print(f"\nDetailed analysis complete! Reports saved with timestamp {timestamp}")

if __name__ == "__main__":
    generate_detailed_report()