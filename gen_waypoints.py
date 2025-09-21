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
    Legacy function for backwards compatibility.
    Returns number of agents processed.
    """
    output_paths = {n_waypoints: output_path}
    waypoint_counts = [n_waypoints]
    return process_scenario_file_multiple(scen_path, output_paths, free_cells, grid, waypoint_counts, height, width, seed=0)


def process_scenario_file_multiple(scen_path, output_paths, free_cells, grid, waypoint_counts, height, width, seed=0):
    """
    Process a single .scen file, generating multiple output files with hierarchical waypoints.
    output_paths: dict mapping waypoint count to output path
    waypoint_counts: list of waypoint counts (e.g., [2, 4, 8])
    Returns number of agents processed.
    """
    try:
        with open(scen_path, 'r') as f:
            lines = [line.rstrip('\n\r') for line in f.readlines()]
    except Exception as e:
        print(f"Warning: Could not read {scen_path}: {e}")
        return 0
    
    if not lines:
        # Empty file, create empty outputs
        for output_path in output_paths.values():
            with open(output_path, 'w') as f:
                pass
        return 0
    
    max_waypoints = max(waypoint_counts)
    agents_processed = 0
    agents_fixed = 0
    
    # Check if first line is a header
    header_line = None
    start_idx = 0
    if lines and (lines[0].startswith('version') or lines[0].startswith('Version')):
        header_line = lines[0]
        start_idx = 1
    
    # First pass: collect all agents and their reachable cells
    agent_data = []

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

            if len(reachable_cells) < max_waypoints:
                print(f"  Warning: Agent {i} has only {len(reachable_cells)} reachable cells, need {max_waypoints}")

            agent_data.append({
                'line_num': i,
                'fields': fields,
                'reachable_cells': reachable_cells,
                'original_line': line,
                'agent_id': i  # Add agent ID for seeding
            })

        except (ValueError, IndexError) as e:
            print(f"  Warning: Could not parse agent {i}: {e}")
            agent_data.append({
                'line_num': i,
                'fields': None,
                'reachable_cells': [],
                'original_line': line,
                'agent_id': i
            })

    agents_processed = len([a for a in agent_data if a['fields'] is not None])
    max_waypoints = max(waypoint_counts)

    # Second pass: generate hierarchical waypoints for max_waypoints, then subset for each count
    all_agent_waypoints = {}  # Maps agent line number to list of waypoints

    for agent_info in agent_data:
        if agent_info['fields'] is None:
            continue

        i = agent_info['line_num']
        reachable_cells = agent_info['reachable_cells']

        # Generate waypoints for this agent using agent-specific seeding
        waypoint_cells = []
        if max_waypoints > 0 and len(reachable_cells) > 0:
            # Create agent-specific random generator for hierarchical consistency
            agent_seed = hash((seed, agent_info['agent_id'], scen_path))
            agent_rng = random.Random(agent_seed)

            if len(reachable_cells) >= max_waypoints:
                # Sample from reachable cells
                waypoint_cells = agent_rng.sample(reachable_cells, max_waypoints)
            else:
                # Use all available reachable cells
                waypoint_cells = reachable_cells[:max_waypoints]

        all_agent_waypoints[i] = waypoint_cells

    # Generate waypoint assignments with per-position uniqueness and hierarchical consistency
    global_assignments = {}  # Maps (agent_id, n_waypoints) -> list of waypoints

    # Process each waypoint position to ensure uniqueness within each position
    max_waypoints = max(waypoint_counts) if waypoint_counts else 0

    # For each waypoint position, resolve conflicts
    for pos in range(max_waypoints):
        used_at_position = set()

        # Sort agents by conflict potential at this position (deterministic order)
        agents_at_position = []
        for agent_info in agent_data:
            if agent_info['fields'] is None:
                continue
            i = agent_info['line_num']
            if i in all_agent_waypoints and pos < len(all_agent_waypoints[i]):
                agents_at_position.append((i, agent_info))

        # Process agents in deterministic order (by agent line number)
        agents_at_position.sort(key=lambda x: x[0])

        for i, agent_info in agents_at_position:
            hierarchical_waypoint = all_agent_waypoints[i][pos]
            reachable_cells = agent_info['reachable_cells']

            if hierarchical_waypoint not in used_at_position:
                # Can use the hierarchical waypoint
                final_waypoint = hierarchical_waypoint
            else:
                # Need alternative - find one that's not used at this position
                agent_seed = hash((seed, agent_info['agent_id'], scen_path, pos))
                agent_rng = random.Random(agent_seed)

                available = [cell for cell in reachable_cells if cell not in used_at_position]
                if available:
                    agent_rng.shuffle(available)
                    final_waypoint = available[0]
                else:
                    # If no alternatives, keep the hierarchical waypoint (rare case)
                    final_waypoint = hierarchical_waypoint

            # Update the waypoint at this position
            all_agent_waypoints[i][pos] = final_waypoint
            used_at_position.add(final_waypoint)

    # Now generate output files with simple hierarchical slicing
    for n_waypoints in waypoint_counts:
        for agent_info in agent_data:
            if agent_info['fields'] is not None:
                i = agent_info['line_num']
                if i in all_agent_waypoints:
                    waypoints = all_agent_waypoints[i][:n_waypoints]
                else:
                    waypoints = []
                global_assignments[(i, n_waypoints)] = waypoints

    # Generate output files for each waypoint count
    for n_waypoints in waypoint_counts:
        output_lines = []

        # Add header if present
        if header_line:
            output_lines.append(header_line)

        # Process each line to generate output
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

            # Get final waypoint assignment for this agent and waypoint count
            waypoint_cells = global_assignments.get((i, n_waypoints), [])

            # Build the output line
            tail = [str(len(waypoint_cells))]
            for r, c in waypoint_cells:
                tail.extend([str(c), str(r)])  # x-coordinate (column), y-coordinate (row)

            output_line = '\t'.join(fields + tail)
            output_lines.append(output_line)

        # Write output for this waypoint count
        output_path = output_paths[n_waypoints]
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
    parser.add_argument('--n', type=int, help='Number of waypoints per agent (legacy mode, generates only one file)')
    parser.add_argument('--seed', type=int, default=0, help='Random seed (default: 0)')
    
    args = parser.parse_args()
    
    # Set random seed
    random.seed(args.seed)
    
    # Determine mode: legacy (single file) or new (multiple files)
    if args.n is not None:
        # Legacy mode: single waypoint count
        waypoint_counts = [args.n]
        print(f"Running in legacy mode with {args.n} waypoints")
    else:
        # New mode: multiple waypoint counts
        waypoint_counts = [0, 1, 2, 4, 8, 16, 24, 32]
        print(f"Running in multi-file mode with waypoint counts: {waypoint_counts}")
    
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
        
        max_waypoints = max(waypoint_counts)
        if len(free_cells) < max_waypoints:
            print(f"Error: Map {map_name} has only {len(free_cells)} free cells, need {max_waypoints}")
            return 1
        
        # Create destination subdirectories
        dst_subdirs = {}
        if args.n is not None:
            # Legacy mode: use original directory structure
            dst_subdir = dst_dir / map_name
            dst_subdir.mkdir(exist_ok=True)
            dst_subdirs[args.n] = dst_subdir
        else:
            # New mode: create separate directories for each waypoint count
            for n_waypoints in waypoint_counts:
                dst_subdir = dst_dir / f"{map_name}_{n_waypoints}wp"
                dst_subdir.mkdir(exist_ok=True)
                dst_subdirs[n_waypoints] = dst_subdir
        
        # Process all .scen files in this subdirectory
        for scen_file in src_subdir.glob('*.scen'):
            # Create output paths for each waypoint count
            output_paths = {}
            for n_waypoints in waypoint_counts:
                output_paths[n_waypoints] = dst_subdirs[n_waypoints] / scen_file.name
            
            if args.n is not None:
                print(f"Processing {scen_file.name} with {args.n} waypoints...")
            else:
                print(f"Processing {scen_file.name} for {waypoint_counts} waypoints...")
            
            agents = process_scenario_file_multiple(scen_file, output_paths, free_cells, grid, waypoint_counts, height, width, args.seed)
            total_agents += agents
            if args.n is not None:
                total_files += 1  # Legacy mode: one file per scenario
            else:
                total_files += len(waypoint_counts)  # New mode: multiple files per scenario
    
    print(f"\nGenerated {total_files} waypoint files.")
    print(f"Total agents processed: {total_agents}.")
    print(f"Waypoint configurations: {waypoint_counts}.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 