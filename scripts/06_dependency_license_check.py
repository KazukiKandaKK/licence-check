#!/usr/bin/env python3
"""
Dependency License Checker
Analyzes import statements and detects potential GPL and other problematic licenses.
"""

import os
import re
import sys
import json
import argparse
import subprocess
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional

# Known problematic licenses
PROBLEMATIC_LICENSES = {
    'GPL': ['GPL-2.0', 'GPL-3.0', 'LGPL-2.1', 'LGPL-3.0', 'AGPL-3.0'],
    'Copyleft': ['EPL-1.0', 'EPL-2.0', 'MPL-2.0'],
    'Commercial': ['Commercial', 'Proprietary'],
    'Restricted': ['CC-BY-NC', 'CC-BY-SA']
}

# Known packages with problematic licenses
KNOWN_PROBLEMATIC_PACKAGES = {
    # Python packages
    'python': {
        'mysql-python': 'GPL-2.0',
        'readline': 'GPL-3.0',
        'pyqt5': 'GPL-3.0',
        'pyqt6': 'GPL-3.0',
        'pyside2': 'LGPL-3.0',
        'pyside6': 'LGPL-3.0',
        'wxpython': 'wxWindows',
        'gpl': 'GPL-3.0',
        'copyleft': 'GPL-2.0',
    },
    # JavaScript/TypeScript packages  
    'javascript': {
        'gpl': 'GPL-3.0',
        'copyleft': 'GPL-2.0',
        'jquery-ui': 'GPL-2.0',
        'angular-ui-bootstrap': 'GPL-3.0',
    },
    # Go packages
    'go': {
        'gpl': 'GPL-3.0',
        'copyleft': 'GPL-2.0',
        'mysql': 'GPL-2.0',
    }
}

class Colors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def colorize(text, color):
    """Add color to text if terminal supports it"""
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.END}"
    return text

def extract_python_imports(content: str) -> Set[str]:
    """Extract Python import statements"""
    imports = set()
    
    # Standard import patterns
    import_patterns = [
        r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)',
        r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s+import',
    ]
    
    for line in content.split('\n'):
        for pattern in import_patterns:
            match = re.match(pattern, line)
            if match:
                module_name = match.group(1).split('.')[0]
                imports.add(module_name)
    
    return imports

def extract_javascript_imports(content: str) -> Set[str]:
    """Extract JavaScript/TypeScript import statements"""
    imports = set()
    
    # JavaScript/TypeScript import patterns
    import_patterns = [
        r'^\s*import\s+.*?from\s+[\'"]([^\'\"]+)[\'"]',
        r'^\s*import\s+[\'"]([^\'\"]+)[\'"]',
        r'^\s*const\s+.*?=\s+require\s*\(\s*[\'"]([^\'\"]+)[\'"]',
        r'^\s*var\s+.*?=\s+require\s*\(\s*[\'"]([^\'\"]+)[\'"]',
        r'^\s*let\s+.*?=\s+require\s*\(\s*[\'"]([^\'\"]+)[\'"]',
    ]
    
    for line in content.split('\n'):
        for pattern in import_patterns:
            match = re.search(pattern, line)
            if match:
                module_name = match.group(1)
                # Remove relative path indicators and get base package name
                if not module_name.startswith('.'):
                    package_name = module_name.split('/')[0]
                    if package_name.startswith('@'):
                        # Handle scoped packages like @angular/core
                        parts = module_name.split('/')
                        if len(parts) >= 2:
                            package_name = f"{parts[0]}/{parts[1]}"
                    imports.add(package_name)
    
    return imports

def extract_go_imports(content: str) -> Set[str]:
    """Extract Go import statements"""
    imports = set()
    
    # Go import patterns
    import_patterns = [
        r'^\s*import\s+[\'"]([^\'\"]+)[\'"]',
        r'^\s*import\s*\(\s*[\'"]([^\'\"]+)[\'"]',
        r'^\s*[\'"]([^\'\"]+)[\'"]',  # Inside import block
    ]
    
    in_import_block = False
    for line in content.split('\n'):
        line = line.strip()
        
        if line.startswith('import ('):
            in_import_block = True
            continue
        elif line == ')' and in_import_block:
            in_import_block = False
            continue
        
        if in_import_block:
            match = re.match(r'^[\'"]([^\'\"]+)[\'"]', line)
            if match:
                imports.add(match.group(1))
        else:
            for pattern in import_patterns:
                match = re.match(pattern, line)
                if match:
                    imports.add(match.group(1))
    
    return imports

def check_package_license(package_name: str, language: str) -> Optional[str]:
    """Check if a package has a known problematic license"""
    known_packages = KNOWN_PROBLEMATIC_PACKAGES.get(language, {})
    return known_packages.get(package_name.lower())

def analyze_file_imports(file_path: Path) -> Dict[str, List[Tuple[str, str]]]:
    """Analyze imports in a file and detect problematic licenses"""
    results = defaultdict(list)
    
    try:
        content = file_path.read_text(encoding='utf-8')
        file_ext = file_path.suffix.lower()
        
        imports = set()
        language = None
        
        if file_ext == '.py':
            imports = extract_python_imports(content)
            language = 'python'
        elif file_ext in ['.js', '.ts', '.jsx', '.tsx']:
            imports = extract_javascript_imports(content)
            language = 'javascript'
        elif file_ext == '.go':
            imports = extract_go_imports(content)
            language = 'go'
        else:
            return results
        
        for package in imports:
            license_info = check_package_license(package, language)
            if license_info:
                severity = 'CRITICAL'
                for license_type, licenses in PROBLEMATIC_LICENSES.items():
                    if license_info in licenses:
                        results[severity].append((package, license_info))
                        break
                else:
                    results['HIGH'].append((package, license_info))
    
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
    
    return results

def scan_directory(directory: Path, exclude_dirs: Set[str] = None) -> Dict[str, Dict[str, List[Tuple[str, str, str]]]]:
    """Scan directory for files with problematic dependencies"""
    if exclude_dirs is None:
        exclude_dirs = {'.git', 'node_modules', '__pycache__', '.pytest_cache', 'dist', 'build', '.venv', 'venv'}
    
    results = defaultdict(lambda: defaultdict(list))
    
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            # Skip excluded directories
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue
            
            # Only analyze code files
            if file_path.suffix.lower() in ['.py', '.js', '.ts', '.jsx', '.tsx', '.go']:
                file_results = analyze_file_imports(file_path)
                
                for severity, issues in file_results.items():
                    for package, license_info in issues:
                        results[str(file_path)][severity].append((package, license_info, str(file_path)))
    
    return results

def print_results(results: Dict[str, Dict[str, List[Tuple[str, str, str]]]], summary_only: bool = False):
    """Print scan results with color coding"""
    total_files = len(results)
    total_issues = sum(len(issues) for file_results in results.values() for issues in file_results.values())
    
    if total_issues == 0:
        print(colorize("✓ No problematic licenses detected in dependencies", Colors.GREEN))
        return 0
    
    print(colorize(f"\n⚠ Found {total_issues} potential license issues in {total_files} files", Colors.YELLOW))
    print("=" * 60)
    
    severity_counts = defaultdict(int)
    
    for file_path, file_results in results.items():
        has_critical = any(severity == 'CRITICAL' for severity in file_results.keys())
        
        if not summary_only:
            print(f"\n{colorize('FILE:', Colors.BOLD)} {file_path}")
            
            for severity, issues in file_results.items():
                if issues:
                    color = Colors.RED if severity == 'CRITICAL' else Colors.YELLOW
                    print(f"  {colorize(f'{severity}:', color)}")
                    
                    for package, license_info, _ in issues:
                        print(f"    • {package} ({license_info})")
                        severity_counts[severity] += 1
        else:
            for severity, issues in file_results.items():
                severity_counts[severity] += len(issues)
    
    print("\n" + "=" * 60)
    print(colorize("SUMMARY:", Colors.BOLD))
    
    for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        if severity_counts[severity] > 0:
            color = Colors.RED if severity == 'CRITICAL' else Colors.YELLOW
            print(f"  {colorize(f'{severity}:', color)} {severity_counts[severity]} issues")
    
    # Return exit code based on severity
    if severity_counts['CRITICAL'] > 0:
        return 2
    elif severity_counts['HIGH'] > 0:
        return 1
    else:
        return 0

def save_csv_report(results: Dict[str, Dict[str, List[Tuple[str, str, str]]]], output_file: Path):
    """Save results to CSV file"""
    import csv
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['File', 'Severity', 'Package', 'License', 'Description'])
        
        for file_path, file_results in results.items():
            for severity, issues in file_results.items():
                for package, license_info, _ in issues:
                    description = f"Potentially problematic license: {license_info}"
                    writer.writerow([file_path, severity, package, license_info, description])

def main():
    parser = argparse.ArgumentParser(description='Check dependencies for problematic licenses')
    parser.add_argument('directory', nargs='?', default='.', help='Directory to scan (default: current directory)')
    parser.add_argument('--summary-only', action='store_true', help='Show only summary')
    parser.add_argument('--output', '-o', help='Output CSV file')
    parser.add_argument('--exclude', help='Comma-separated list of directories to exclude')
    
    args = parser.parse_args()
    
    directory = Path(args.directory).resolve()
    if not directory.exists():
        print(f"Error: Directory {directory} does not exist")
        return 1
    
    exclude_dirs = {'.git', 'node_modules', '__pycache__', '.pytest_cache', 'dist', 'build', '.venv', 'venv'}
    if args.exclude:
        exclude_dirs.update(args.exclude.split(','))
    
    print(f"Scanning {directory} for dependency license issues...")
    results = scan_directory(directory, exclude_dirs)
    
    exit_code = print_results(results, args.summary_only)
    
    if args.output:
        save_csv_report(results, Path(args.output))
        print(f"\nDetailed report saved to: {args.output}")
    
    return exit_code

if __name__ == '__main__':
    sys.exit(main())