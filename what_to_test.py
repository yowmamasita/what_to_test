#!/usr/bin/env python3

import argparse
import sys
from collections import defaultdict
import fnmatch
import subprocess

COVERAGE_FILE = 'coverage'

def generate_coverage_file():
    """
    Generates the Go coverage profile by running `go test -coverprofile=COVERAGE_FILE ./...`.
    """
    try:
        subprocess.run(['go', 'test', '-coverprofile=' + COVERAGE_FILE, './...'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to generate coverage profile: {e}", file=sys.stderr)
        sys.exit(1)

def parse_coverage_file(file_path, excluded_patterns):
    """
    Parses the Go coverage profile and returns a dictionary with coverage data per file,
    excluding files that match any of the excluded patterns.
    """
    coverage_data = defaultdict(lambda: {'total': 0, 'covered': 0, 'uncovered_blocks': []})

    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('mode:'):
                    continue  # Skip header and empty lines
                try:
                    parts = line.split()
                    file_range = parts[0]
                    counts = parts[1:]

                    file_path_extracted = file_range.split(':')[0]

                    if is_excluded(file_path_extracted, excluded_patterns):
                        continue  # Skip excluded files

                    statements = int(counts[0])
                    count = int(counts[1])

                    coverage_data[file_path_extracted]['total'] += statements
                    if count > 0:
                        coverage_data[file_path_extracted]['covered'] += statements
                    else:
                        coverage_data[file_path_extracted]['uncovered_blocks'].append(file_range)
                except (IndexError, ValueError) as e:
                    print(f"Warning: Skipping malformed line: {line}", file=sys.stderr)
                    continue
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)

    return coverage_data

def is_excluded(file_path, excluded_patterns):
    """
    Determines if a file should be excluded based on the provided patterns.
    """
    return any(fnmatch.fnmatch(file_path, pattern) for pattern in excluded_patterns)

def calculate_coverage(coverage_data):
    """
    Calculates coverage percentage for each file.
    """
    coverage_percent = {}
    for file, data in coverage_data.items():
        if data['total'] == 0:
            coverage = 100.0
        else:
            coverage = (data['covered'] / data['total']) * 100
        coverage_percent[file] = coverage
    return coverage_percent

def compute_impact_score(coverage, total_statements, num_uncovered_blocks):
    """
    Computes an impact score based on coverage percentage, total statements, and number of uncovered blocks.
    Higher scores indicate higher impact.
    """
    return (100 - coverage) * total_statements * num_uncovered_blocks

def provide_recommendations(file, coverage, uncovered_blocks):
    """
    Provides recommendations based on coverage percentage and uncovered code blocks.
    """
    recommendations = []
    if coverage < 50:
        recommendations.append("🔴 Critical Coverage: Prioritize adding comprehensive unit tests for all major functionalities and edge cases.")
    elif coverage < 70:
        recommendations.append("🟠 Low Coverage: Review existing tests and add tests for uncovered functions and error handling paths.")
    elif coverage < 80:
        recommendations.append("🟡 Moderate Coverage: Add additional unit tests focusing on less-covered code paths and edge cases.")
    else:
        recommendations.append("🟢 High Coverage: Maintain existing tests and consider adding tests for any remaining uncovered blocks.")

    if uncovered_blocks:
        recommendations.append(f"   - **Uncovered Code Blocks:** {len(uncovered_blocks)} blocks not covered. Review the following locations:")
        for block in uncovered_blocks[:5]:  # Limit to first 5 for brevity
            recommendations.append(f"     - `{block}`")
        if len(uncovered_blocks) > 5:
            recommendations.append(f"     - ...and {len(uncovered_blocks) - 5} more.")

    return "\n".join(recommendations)

def report_top_low_coverage(coverage_percent, coverage_data, threshold, top_n):
    """
    Reports the top N files with the highest impact based on low coverage.
    """
    low_coverage_files = {file: perc for file, perc in coverage_percent.items() if perc < threshold}

    if not low_coverage_files:
        print(f"✅ All files have coverage above {threshold}%. Great job!")
        return

    impact_scores = []
    for file, perc in low_coverage_files.items():
        total_statements = coverage_data[file]['total']
        num_uncovered_blocks = len(coverage_data[file]['uncovered_blocks'])
        impact = compute_impact_score(perc, total_statements, num_uncovered_blocks)
        impact_scores.append((file, perc, coverage_data[file]['uncovered_blocks'], impact))

    impact_scores_sorted = sorted(impact_scores, key=lambda x: x[3], reverse=True)
    top_impact_files = impact_scores_sorted[:top_n]

    print(f"📉 Top {top_n} Most Impactful Files with Coverage below {threshold}%:")
    print("-------------------------------------------------------------")
    for idx, (file, perc, uncovered_blocks, impact) in enumerate(top_impact_files, start=1):
        print(f"\n### {idx}. {file}: {perc:.2f}% Coverage")
        recommendations = provide_recommendations(file, perc, uncovered_blocks)
        print(recommendations)

def main():
    parser = argparse.ArgumentParser(
        description="Identify top low coverage files from Go coverage profile, excluding specified paths, and provide recommendations."
    )
    parser.add_argument('-t', '--threshold', type=float, default=80.0,
                        help="Coverage threshold percentage (default: 80.0)")
    parser.add_argument('-n', '--top', type=int, default=5,
                        help="Number of top impactful files to display (default: 5)")
    parser.add_argument('-e', '--exclude', type=str, nargs='*', default=[],
                        help="Glob patterns to exclude from analysis (e.g., 'data-core-service/gen/go/*' 'mock_*.go')")

    args = parser.parse_args()

    default_exclusions = [
        '*/gen/go/*',  # Exclude all files in data-core-service/gen/go/
        '*mock_*.go',  # Exclude any file starting with mock_ and ending with .go
        '*.sql.go',    # Exclude any file ending with .sql.go
        '*.pb.go',     # Exclude any file ending with .pb.go
        '*/cmd/*',     # Exclude all files in cmd/
    ]

    excluded_patterns = default_exclusions + args.exclude

    generate_coverage_file()

    coverage_data = parse_coverage_file(COVERAGE_FILE, excluded_patterns)
    coverage_percent = calculate_coverage(coverage_data)
    report_top_low_coverage(coverage_percent, coverage_data, args.threshold, args.top)

if __name__ == "__main__":
    main()