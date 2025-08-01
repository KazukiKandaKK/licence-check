import json
import pathlib
import sqlite3
import pandas as pd
from collections import defaultdict
import os
from datetime import datetime

# Initialize database connection
db = sqlite3.connect('results.sqlite')

# Create licenses table if it doesn't exist
db.execute("""
    CREATE TABLE IF NOT EXISTS licenses(
        file_path TEXT,
        license_key TEXT,
        license_name TEXT,
        lang TEXT,
        model TEXT,
        score REAL
    )
""")

print("Processing ScanCode results...")

# Process ScanCode JSON results
scancode_results_found = False
for j in pathlib.Path('scans/scancode_output').glob('*.json'):
    if j.exists():
        try:
            js = json.load(open(j))
            lang = j.stem
            
            print(f"Processing {lang} scan results...")
            scancode_results_found = True
            
            # Get list of generated files for this language to determine model
            generated_files = sorted(list(pathlib.Path(f'generated/{lang}').glob('*')))
            
            for f in js.get('files', []):
                file_path = f.get('path', '')
                
                # Extract filename from path
                filename = pathlib.Path(file_path).name
                
                # Find matching generated file and determine model
                model = 'unknown'
                try:
                    matching_files = [gf for gf in generated_files if gf.name == filename]
                    if matching_files:
                        file_index = generated_files.index(matching_files[0])
                        model = 'openai' if file_index % 2 == 0 else 'claude'
                except:
                    pass
                
                # Process detected licenses
                licenses_found = f.get('licenses', [])
                if licenses_found:
                    for lic in licenses_found:
                        license_key = lic.get('spdx_license_key', 'unknown')
                        license_name = lic.get('name', 'unknown')
                        score = lic.get('score', 0.0)
                        
                        db.execute(
                            "INSERT INTO licenses VALUES (?,?,?,?,?,?)",
                            (file_path, license_key, license_name, lang, model, score)
                        )
                else:
                    # Insert record for files with no licenses detected
                    db.execute(
                        "INSERT INTO licenses VALUES (?,?,?,?,?,?)",
                        (file_path, 'none', 'No license detected', lang, model, 0.0)
                    )
        except Exception as e:
            print(f"Error processing {j}: {e}")

if not scancode_results_found:
    print("Warning: No ScanCode results found. Run ./scripts/02_scan.sh first.")

db.commit()

print("Generating summary report...")

# Create output directory
output_dir = pathlib.Path('results')
output_dir.mkdir(exist_ok=True)

# Generate timestamp for filenames
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

try:
    # All license detection results
    all_licenses_df = pd.read_sql_query("""
        SELECT file_path, license_key, license_name, lang, model, score
        FROM licenses 
        ORDER BY lang, model, file_path
    """, db)
    
    if not all_licenses_df.empty:
        # Save all results
        all_results_file = output_dir / f"all_results_{timestamp}.csv"
        all_licenses_df.to_csv(all_results_file, index=False)
        print(f"All results saved to {all_results_file}")
        
        # High-confidence license detection summary
        high_conf_df = all_licenses_df[all_licenses_df['score'] > 0.8]
        
        if not high_conf_df.empty:
            # License detection summary by model and language
            license_summary = high_conf_df.groupby(['lang', 'model', 'license_key']).size().reset_index(name='count')
            license_summary_file = output_dir / f"license_summary_{timestamp}.csv"
            license_summary.to_csv(license_summary_file, index=False)
            print(f"High-confidence license summary saved to {license_summary_file}")
            
            # Create pivot table for license detection
            license_pivot = license_summary.pivot_table(
                values='count', 
                index=['lang', 'license_key'], 
                columns='model', 
                fill_value=0,
                aggfunc='sum'
            )
            license_pivot_file = output_dir / f"license_pivot_{timestamp}.csv"
            license_pivot.to_csv(license_pivot_file)
            print(f"License pivot table saved to {license_pivot_file}")
            print("\nHigh-confidence License Detection Summary:")
            print(license_pivot)
        else:
            print("No high-confidence license matches found (score > 0.8)")
        
        # File count summary by model and language
        file_summary = all_licenses_df.groupby(['lang', 'model']).agg({
            'file_path': 'nunique',
            'score': ['mean', 'max']
        }).round(3)
        file_summary.columns = ['file_count', 'avg_score', 'max_score']
        file_summary_file = output_dir / f"file_summary_{timestamp}.csv"
        file_summary.to_csv(file_summary_file)
        print(f"File summary saved to {file_summary_file}")
        print("\nFile Summary by Model and Language:")
        print(file_summary)
    
    # Similarity analysis summary (if available)
    try:
        similarity_df = pd.read_sql_query("""
            SELECT file, lang, model, score
            FROM similarity
            ORDER BY lang, model, file
        """, db)
        
        if not similarity_df.empty:
            similarity_file = output_dir / f"similarity_results_{timestamp}.csv"
            similarity_df.to_csv(similarity_file, index=False)
            print(f"Similarity results saved to {similarity_file}")
            
            similarity_summary = similarity_df.groupby(['lang', 'model']).agg({
                'score': ['mean', 'max', 'count']
            }).round(3)
            similarity_summary.columns = ['avg_score', 'max_score', 'file_count']
            similarity_summary_file = output_dir / f"similarity_summary_{timestamp}.csv"
            similarity_summary.to_csv(similarity_summary_file)
            print(f"Similarity summary saved to {similarity_summary_file}")
            print("\nSimilarity Analysis Summary:")
            print(similarity_summary)
        else:
            print("No similarity data available")
            
    except Exception as e:
        print(f"Similarity analysis not available: {e}")
    
    # Overall statistics
    try:
        total_files = db.execute("SELECT COUNT(DISTINCT file_path) FROM licenses").fetchone()[0]
        files_with_licenses = db.execute("SELECT COUNT(DISTINCT file_path) FROM licenses WHERE score > 0.8").fetchone()[0]
        
        # Statistics by language and model
        stats_df = pd.read_sql_query("""
            SELECT 
                lang,
                model,
                COUNT(DISTINCT file_path) as total_files,
                COUNT(DISTINCT CASE WHEN score > 0.8 THEN file_path END) as files_with_licenses,
                AVG(score) as avg_score,
                MAX(score) as max_score
            FROM licenses
            GROUP BY lang, model
            ORDER BY lang, model
        """, db)
        
        stats_df['license_detection_rate'] = (stats_df['files_with_licenses'] / stats_df['total_files'] * 100).round(1)
        stats_file = output_dir / f"overall_stats_{timestamp}.csv"
        stats_df.to_csv(stats_file, index=False)
        print(f"Overall statistics saved to {stats_file}")
        
        print(f"\nOverall Statistics:")
        print(f"Total files analyzed: {total_files}")
        print(f"Files with detected licenses (>0.8 score): {files_with_licenses}")
        print(f"License detection rate: {files_with_licenses/total_files*100:.1f}%" if total_files > 0 else "N/A")
        print("\nDetailed Statistics by Language and Model:")
        print(stats_df.to_string(index=False))
        
    except Exception as e:
        print(f"Error calculating overall statistics: {e}")
    
except Exception as e:
    print(f"Error generating summary: {e}")

db.close()
print(f"\nAggregation complete! Results saved to results.sqlite")
print(f"CSV reports saved in ./results/ directory with timestamp {timestamp}")