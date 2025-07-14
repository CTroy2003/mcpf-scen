#!/usr/bin/env python3
"""
Verify that waypoint sequences are consistent across different N values.
"""

import sys

def parse_agent_line(line):
    """Parse an agent line and return (original_fields, waypoints)."""
    fields = line.strip().split('\t')
    if len(fields) < 10:
        return None, []
    
    # First 9 fields are original, then waypoint count, then waypoint coordinates
    original_fields = fields[:9]
    waypoint_count = int(fields[9])
    
    waypoints = []
    for i in range(waypoint_count):
        x = int(fields[10 + i*2])
        y = int(fields[10 + i*2 + 1])
        waypoints.append((x, y))
    
    return original_fields, waypoints

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 verify_waypoints.py <file1> <file2>")
        print("Example: python3 verify_waypoints.py scen-2wp.scen scen-4wp.scen")
        return 1
    
    file1_path = sys.argv[1]
    file2_path = sys.argv[2]
    
    print(f"Comparing {file1_path} and {file2_path}")
    
    # Read both files
    with open(file1_path, 'r') as f1, open(file2_path, 'r') as f2:
        lines1 = [line.strip() for line in f1.readlines()]
        lines2 = [line.strip() for line in f2.readlines()]
    
    # Find agent lines (skip header)
    agent_lines1 = [line for line in lines1 if line and not line.startswith('version')]
    agent_lines2 = [line for line in lines2 if line and not line.startswith('version')]
    
    if len(agent_lines1) != len(agent_lines2):
        print(f"Error: Different number of agents ({len(agent_lines1)} vs {len(agent_lines2)})")
        return 1
    
    matches = 0
    mismatches = 0
    
    for i, (line1, line2) in enumerate(zip(agent_lines1, agent_lines2)):
        original1, waypoints1 = parse_agent_line(line1)
        original2, waypoints2 = parse_agent_line(line2)
        
        if not original1 or not original2:
            continue
        
        # Check if original agent data matches
        if original1 != original2:
            print(f"Agent {i+1}: Original data mismatch")
            mismatches += 1
            continue
        
        # Check if first N waypoints of file2 match all waypoints of file1
        n1 = len(waypoints1)
        n2 = len(waypoints2)
        
        if n2 < n1:
            print(f"Agent {i+1}: File2 has fewer waypoints ({n2}) than File1 ({n1})")
            mismatches += 1
            continue
        
        # Compare first n1 waypoints
        first_n_waypoints2 = waypoints2[:n1]
        if waypoints1 == first_n_waypoints2:
            matches += 1
        else:
            print(f"Agent {i+1}: Waypoint mismatch")
            print(f"  File1: {waypoints1}")
            print(f"  File2 first {n1}: {first_n_waypoints2}")
            mismatches += 1
    
    total = matches + mismatches
    print(f"\nResults:")
    print(f"  Total agents: {total}")
    print(f"  Matches: {matches}")
    print(f"  Mismatches: {mismatches}")
    print(f"  Success rate: {matches/total*100:.1f}%")
    
    return 0 if mismatches == 0 else 1

if __name__ == "__main__":
    sys.exit(main()) 