#!/usr/bin/env python3
"""
Generate waypoint-augmented scenario files from original scenarios.
Only places waypoints on passable terrain by parsing map files.
"""

import argparse
import os
import random
import sys
from pathlib import Path
from collections import deque


def load_map_free_cells(map_path):
    """
    Load a .map file and return list of free cells [(r,c), ...].
    Returns (height, width, free_cells, grid) tuple.
    """
    try:
        with open(map_path, 'r') as f:
            lines = [line.rstrip('\n\r') for line in f.readlines()]
        
        # Parse header
        if len(lines) < 4:
            raise ValueError(f"Map file {map_path} has insufficient header lines")
        
        # Line 0: type octile
        # Line 1: height H
        # Line 2: width W  
        # Line 3: map
        height = int(lines[1].split()[1])
        width = int(lines[2].split()[1])
        
        # Read grid data
        grid = []
        for i in range(4, 4 + height):
            if i < len(lines):
                grid.append(lines[i])
            else:
                raise ValueError(f"Map file {map_path} has insufficient grid lines")
        
        # Find free cells (passable terrain)
        free_cells = []
        for r in range(height):
            for c in range(width):
                if r < len(grid) and c < len(grid[r]) and grid[r][c] == '.':
                    free_cells.append((r, c))
        
        return height, width, free_cells, grid
        
    except Exception as e:
        print(f"Error loading map {map_path}: {e}")
        return None, None, [], []


def bfs_reachable(grid, start):
    """Return set of cells reachable from `start`."""
    height, width = len(grid), len(grid[0]) if grid else 0
    start_r, start_c = start
    
    # Check if start is valid and passable
    if (start_r < 0 or start_r >= height or 
        start_c < 0 or start_c >= width or 
        grid[start_r][start_c] != '.'):
        return set()
    
    visited = set()
    queue = deque([start])
    visited.add(start)
    
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    
    while queue:
        r, c = queue.popleft()
        
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if (0 <= nr < height and 0 <= nc < width and 
                (nr, nc) not in visited and grid[nr][nc] == '.'):
                visited.add((nr, nc))
                queue.append((nr, nc))
    
    return visited


def fix_agent_position(s_row, s_col, height, width, grid, free_cells):
    """
    Fix an agent's position if it's invalid.
    Returns (fixed_row, fixed_col, was_fixed).
    """
    # First, clamp to map bounds
    fixed_row = max(0, min(s_row, height - 1))
    fixed_col = max(0, min(s_col, width - 1))
    was_clamped = (fixed_row != s_row or fixed_col != s_col)
    
    # Check if the position is on passable terrain
    if grid[fixed_row][fixed_col] == '.':
        return fixed_row, fixed_col, was_clamped
    
    # Position is on obstacle, find nearest passable cell
    if not free_cells:
        return fixed_row, fixed_col, True  # No free cells available
    
    # Find closest free cell using Manhattan distance
    best_distance = float('inf')
    best_cell = free_cells[0]
    
    for r, c in free_cells:
        distance = abs(r - fixed_row) + abs(c - fixed_col)
        if distance < best_distance:
            best_distance = distance
            best_cell = (r, c)
    
    return best_cell[0], best_cell[1], True


def process_scenario_file(scen_path, output_path, free_cells, grid, n_waypoints, height, width):
    """
    Process a single .scen file, adding waypoints to each agent line.
    Returns number of agents processed.
    """
    try:
        with open(scen_path, 'r') as f:
            lines = [line.rstrip('\n\r') for line in f.readlines()]
    except Exception as e:
        print(f"Warning: Could not read {scen_path}: {e}")
        return 0
    
    if not lines:
        # Empty file, create empty output
        with open(output_path, 'w') as f:
            pass
        return 0
    
    output_lines = []
    agents_processed = 0
    agents_fixed = 0
    
    # Check if first line is a header
    header_line = None
    start_idx = 0
    if lines and (lines[0].startswith('version') or lines[0].startswith('Version')):
        header_line = lines[0]
        start_idx = 1
        output_lines.append(header_line)
    
    # First pass: collect all agents and their reachable cells
    agent_data = []
    used_waypoints = set()  # Track globally used waypoints
    
    for i, line in enumerate(lines[start_idx:], start_idx + 1):
        if not line.strip():
            continue
            
        fields = line.split('\t')
        if len(fields) != 9:
            continue
        
        try:
            # Parse agent coordinates (field 4 = x-coordinate/column, field 5 = y-coordinate/row)
            s_col = int(fields[4])  # start x-coordinate (column)
            s_row = int(fields[5])  # start y-coordinate (row)
            
            # Fix agent position if necessary
            fixed_row, fixed_col, was_fixed = fix_agent_position(s_row, s_col, height, width, grid, free_cells)
            
            if was_fixed:
                agents_fixed += 1
                if s_row < 0 or s_row >= height or s_col < 0 or s_col >= width:
                    print(f"  Fixed out-of-bounds agent {i}: ({s_col},{s_row}) -> ({fixed_col},{fixed_row})")
                else:
                    print(f"  Fixed agent {i} on obstacle: ({s_col},{s_row}) -> ({fixed_col},{fixed_row})")
                
                # Update the fields with fixed coordinates
                fields[4] = str(fixed_col)  # x-coordinate
                fields[5] = str(fixed_row)  # y-coordinate
            
            # Find reachable cells from the (possibly fixed) start position
            reachable = bfs_reachable(grid, (fixed_row, fixed_col))
            reachable_cells = [(r, c) for (r, c) in free_cells if (r, c) in reachable]
            
            if len(reachable_cells) < n_waypoints:
                print(f"  Warning: Agent {i} has only {len(reachable_cells)} reachable cells, need {n_waypoints}")
            
            agent_data.append({
                'line_num': i,
                'fields': fields,
                'reachable_cells': reachable_cells,
                'original_line': line
            })
            
        except (ValueError, IndexError) as e:
            print(f"  Warning: Could not parse agent {i}: {e}")
            agent_data.append({
                'line_num': i,
                'fields': None,
                'reachable_cells': [],
                'original_line': line
            })
    
    # Second pass: assign unique waypoints to each agent
    for i, line in enumerate(lines[start_idx:], start_idx + 1):
        if not line.strip():
            output_lines.append(line)
            continue
            
        fields = line.split('\t')
        if len(fields) != 9:
            # Not a standard agent line, copy as-is
            output_lines.append(line)
            continue
        
        # Find corresponding agent data
        agent_info = None
        for agent in agent_data:
            if agent['line_num'] == i:
                agent_info = agent
                break
        
        if not agent_info or agent_info['fields'] is None:
            output_lines.append(line)  # Copy as-is
            continue
        
        fields = agent_info['fields']
        reachable_cells = agent_info['reachable_cells']
        
        # Find available waypoints (reachable cells not already used)
        available_cells = [cell for cell in reachable_cells if cell not in used_waypoints]
        
        if len(available_cells) < n_waypoints:
            if len(reachable_cells) < n_waypoints:
                # Use all available reachable cells
                waypoint_cells = available_cells
            else:
                # If we have enough reachable cells but many are used, allow some overlap
                waypoint_cells = random.sample(reachable_cells, n_waypoints)
        else:
            # Sample from available cells
            waypoint_cells = random.sample(available_cells, n_waypoints)
        
        # Mark these waypoints as used
        for cell in waypoint_cells:
            used_waypoints.add(cell)
        
        # Build the output line
        tail = [str(len(waypoint_cells))]
        for r, c in waypoint_cells:
            tail.extend([str(c), str(r)])  # x-coordinate (column), y-coordinate (row)
        
        output_line = '\t'.join(fields + tail)
        output_lines.append(output_line)
        agents_processed += 1
    
    # Write output
    try:
        with open(output_path, 'w') as f:
            for line in output_lines:
                f.write(line + '\n')
    except Exception as e:
        print(f"Warning: Could not write {output_path}: {e}")
        return 0
    
    if agents_fixed > 0:
        print(f"  -> Processed {agents_processed} agents, fixed {agents_fixed} invalid positions")
    else:
        print(f"  -> Processed {agents_processed} agents")
    
    return agents_processed


def main():
    parser = argparse.ArgumentParser(description='Generate waypoint-augmented scenario files')
    parser.add_argument('--maps', required=True, help='Directory containing .map files')
    parser.add_argument('--src', required=True, help='Root directory of original scenario folders')
    parser.add_argument('--dst', required=True, help='Root directory for new waypoint scenarios')
    parser.add_argument('--n', type=int, required=True, help='Number of waypoints per agent')
    parser.add_argument('--seed', type=int, default=0, help='Random seed (default: 0)')
    
    args = parser.parse_args()
    
    # Set random seed
    random.seed(args.seed)
    
    # Validate directories
    maps_dir = Path(args.maps)
    src_dir = Path(args.src)
    dst_dir = Path(args.dst)
    
    if not maps_dir.exists():
        print(f"Error: Maps directory {maps_dir} does not exist")
        return 1
    
    if not src_dir.exists():
        print(f"Error: Source directory {src_dir} does not exist")
        return 1
    
    # Create destination directory
    dst_dir.mkdir(parents=True, exist_ok=True)
    
    # Load all maps
    maps = {}
    for map_file in maps_dir.glob('*.map'):
        map_name = map_file.stem
        height, width, free_cells, grid = load_map_free_cells(map_file)
        if height is not None:
            maps[map_name] = (height, width, free_cells, grid)
            print(f"Loaded map {map_file.name}: {height}x{width}, {len(free_cells)} free cells")
    
    if not maps:
        print("Error: No valid map files found")
        return 1
    
    # Process scenario folders
    total_files = 0
    total_agents = 0
    
    for src_subdir in src_dir.iterdir():
        if not src_subdir.is_dir():
            continue
            
        map_name = src_subdir.name
        if map_name not in maps:
            print(f"Warning: No map file found for {map_name}, skipping")
            continue
        
        height, width, free_cells, grid = maps[map_name]
        
        if len(free_cells) < args.n:
            print(f"Error: Map {map_name} has only {len(free_cells)} free cells, need {args.n}")
            return 1
        
        # Create destination subdirectory
        dst_subdir = dst_dir / map_name
        dst_subdir.mkdir(exist_ok=True)
        
        # Process all .scen files in this subdirectory
        for scen_file in src_subdir.glob('*.scen'):
            output_file = dst_subdir / scen_file.name
            print(f"Processing {scen_file.name}...")
            
            agents = process_scenario_file(scen_file, output_file, free_cells, grid, args.n, height, width)
            total_agents += agents
            total_files += 1
    
    print(f"\nGenerated {total_files} waypoint files.")
    print(f"Total agents processed: {total_agents}.")
    print(f"Waypoints per agent: {args.n}.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 