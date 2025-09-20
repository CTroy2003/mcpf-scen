# Multi-Agent Pathfinding Scenario Waypoint Generation Project

## Overview

This project is a sophisticated waypoint generation system for multi-agent pathfinding (MAPF) research. The core purpose is to augment existing pathfinding scenario files with strategically placed waypoints that agents must visit during their journey from start to goal positions. This enhances scenario complexity and creates more realistic multi-agent navigation challenges.

## What the Project Does

### Primary Objective
Generate waypoint-augmented scenario files from original pathfinding scenarios, where each agent receives a set of intermediate waypoints that must be visited while navigating from their start position to their goal position.

### Key Features
1. **Terrain-Aware Waypoint Placement**: Only places waypoints on passable terrain by parsing `.map` files
2. **Reachability Analysis**: Uses BFS to ensure all waypoints are reachable from each agent's start position
3. **Position Validation & Correction**: Automatically fixes invalid agent positions (out-of-bounds or on obstacles)
4. **Hierarchical Waypoint Consistency**: Ensures that waypoints are consistent across different waypoint counts (e.g., first 2 waypoints of a 4-waypoint scenario match those in a 2-waypoint scenario)
5. **Global Uniqueness**: Prevents waypoint conflicts by ensuring no two agents share the same waypoint coordinates
6. **Multi-Output Generation**: Creates separate scenario files for different waypoint counts (0, 1, 2, 4, 8) simultaneously

## Directory Structure & File Organization

### Expected Input Structure
```
mcpfScenFiles/
├── maps/                           # Map files (.map format)
│   ├── brc202d.map                # Various pathfinding benchmark maps
│   ├── random-32-32-20.map       # Grid-based maps with obstacles
│   ├── warehouse-20-40-10-2-1.map # Warehouse environment maps
│   └── [other .map files]
│
├── scen-random/                   # Original scenario files (input)
│   ├── brc202d/                   # Scenarios for brc202d map
│   │   ├── brc202d-random-1.scen
│   │   ├── brc202d-random-2.scen
│   │   └── [25 total scenarios]
│   ├── warehouse20-40-10-2-1/    # Note: directory name differs from map
│   │   ├── warehouse-20-40-10-2-1-random-1.scen
│   │   └── [25 total scenarios]
│   └── [other map scenario folders]
│
└── gen_waypoints.py              # Main waypoint generation script
```

### Generated Output Structure
```
scen-waypoints-[suffix]/          # Generated waypoint scenarios (output)
├── mapname_0wp/                  # Scenarios with 0 waypoints (baseline)
│   ├── mapname-random-1.scen
│   └── [all original scenarios]
├── mapname_1wp/                  # Scenarios with 1 waypoint
├── mapname_2wp/                  # Scenarios with 2 waypoints
├── mapname_4wp/                  # Scenarios with 4 waypoints
├── mapname_8wp/                  # Scenarios with 8 waypoints
└── [repeat for all maps]
```

## Core Script Functionality (`gen_waypoints.py`)

### Architecture & Design Patterns

#### 1. **Map Parsing (`load_map_free_cells`)**
- Parses `.map` files in standard Moving AI format
- Extracts grid dimensions and identifies passable cells (marked with '.')
- Returns both free cell list and full grid for BFS operations
- Handles malformed map files gracefully

#### 2. **Reachability Analysis (`bfs_reachable`)**
- Implements 4-directional breadth-first search
- Determines all cells reachable from a given start position
- Ensures waypoints are only placed in locations the agent can actually reach
- Critical for preventing impossible scenarios

#### 3. **Position Validation (`fix_agent_position`)**
- Clamps agent coordinates to map boundaries
- Moves agents from obstacle cells to nearest passable cell using Manhattan distance
- Maintains data integrity when processing imperfect input scenarios
- Reports all fixes for transparency

#### 4. **Hierarchical Waypoint Generation (`process_scenario_file_multiple`)**
- **Two-Pass Algorithm**:
  - **Pass 1**: Collect agent data, fix positions, compute reachable cells
  - **Pass 2**: Generate waypoints using agent-specific random generators
- **Hierarchical Consistency**: Generates maximum waypoints first, then subsets for smaller counts
- **Global Uniqueness**: Tracks used waypoints to prevent conflicts
- **Agent-Specific Seeding**: Uses `hash((seed, agent_id, scenario_path))` for reproducible per-agent randomness

### Coordinate System Handling

#### Map vs Scenario Coordinate Systems
- **Map files**: Use (row, col) indexing for grid access
- **Scenario files**: Use (x, y) coordinates where x=column, y=row
- **Critical conversion**: `fields[4]` = x-coordinate (column), `fields[5]` = y-coordinate (row)
- The script carefully maintains this distinction to prevent coordinate bugs

#### Scenario File Format
```
# Original format (9 fields):
bucket map_name width height start_x start_y goal_x goal_y optimal_length

# Augmented format (9 + 1 + 2N fields):
bucket map_name width height start_x start_y goal_x goal_y optimal_length waypoint_count wp1_x wp1_y wp2_x wp2_y ... wpN_x wpN_y
```

### Operating Modes

#### 1. **Legacy Mode (`--n` specified)**
- Generates single waypoint count
- Uses original directory structure
- Backwards compatible with existing workflows

#### 2. **Multi-File Mode (default)**
- Generates multiple waypoint counts simultaneously: [0, 1, 2, 4, 8]
- Creates separate subdirectories for each count
- Ensures hierarchical consistency across all files
- Preferred mode for research requiring multiple configurations

## Key Algorithms & Data Structures

### 1. **Hierarchical Waypoint Assignment**
```python
# Generate max waypoints per agent using agent-specific seeding
agent_seed = hash((global_seed, agent_id, scenario_path))
agent_rng = random.Random(agent_seed)

# Sample from reachable cells not globally used
available_cells = [cell for cell in reachable_cells if cell not in used_waypoints]
waypoint_cells = agent_rng.sample(available_cells, max_waypoints)

# For each output file, take first N waypoints
for n_waypoints in [2, 4, 8]:
    agent_waypoints = waypoint_cells[:n_waypoints]
```

### 2. **Global Uniqueness Enforcement**
- Maintains `used_waypoints` set across all agents
- Prioritizes available (unused) cells over reachable cells
- Falls back to allowing some overlap only when necessary
- Ensures no conflicts in multi-agent pathfinding

### 3. **Breadth-First Search for Reachability**
- Standard BFS with 4-directional movement
- Validates start position before search
- Returns complete reachable set for waypoint sampling
- Handles disconnected map regions gracefully

## Usage Patterns & Command Line Interface

### Basic Usage
```bash
# Multi-file mode (generates 0,1,2,4,8 waypoint files)
python3 gen_waypoints.py --maps maps/ --src scen-random/ --dst scen-waypoints/ --seed 123

# Legacy mode (single waypoint count)
python3 gen_waypoints.py --maps maps/ --src scen-random/ --dst scen-waypoints/ --n 4 --seed 123

# Process specific maps only
python3 gen_waypoints.py --maps maps/ --src temp_specific_maps/ --dst scen-waypoints-subset/ --seed 123
```

### Key Parameters
- `--maps`: Directory containing `.map` files
- `--src`: Root directory of scenario folders
- `--dst`: Output directory for waypoint scenarios
- `--n`: (Optional) Single waypoint count for legacy mode
- `--seed`: Random seed for reproducibility

## Quality Assurance & Verification

### Built-in Validation
- Position fixing with detailed reporting
- Reachability verification for all waypoints
- Consistency checks between map and scenario names
- Graceful handling of malformed files

### Verification Tools (`verify_waypoints.py`)
- Compares waypoint sequences across different N values
- Ensures hierarchical consistency is maintained
- Reports success rates and specific mismatches
- Critical for validating algorithm correctness

### Common Issues & Solutions

#### 1. **Map/Scenario Name Mismatches**
- **Problem**: Directory names don't match map file names (e.g., `warehouse20-40-10-2-1` vs `warehouse-20-40-10-2-1.map`)
- **Solution**: Create temporary directory structure with corrected names

#### 2. **Invalid Agent Positions**
- **Problem**: Agents placed on obstacles or out-of-bounds
- **Solution**: Automatic position fixing with detailed reporting

#### 3. **Insufficient Reachable Cells**
- **Problem**: Small maps or disconnected regions limit waypoint options
- **Solution**: Graceful degradation and clear warnings

## Research Applications

### Multi-Agent Pathfinding Research
- **Waypoint-Constrained MAPF**: Adds intermediate objectives to pathfinding problems
- **Algorithm Benchmarking**: Provides standardized waypoint scenarios for comparing algorithms
- **Complexity Analysis**: Studies how waypoint count affects solution difficulty

### Reproducibility Features
- **Deterministic Generation**: Fixed seeds ensure identical waypoint placement
- **Hierarchical Consistency**: Enables fair comparison across waypoint counts
- **Version Control Friendly**: Text-based output format for easy diff tracking

## Technical Considerations

### Performance Characteristics
- **Time Complexity**: O(agents × max_waypoints × map_size) for BFS operations
- **Memory Usage**: Stores full grid and reachable sets per agent
- **Scalability**: Handles thousands of agents across large maps efficiently

### Error Handling Philosophy
- **Fail Gracefully**: Continue processing when individual agents/scenarios fail
- **Detailed Reporting**: Log all fixes and warnings for transparency
- **Data Preservation**: Copy malformed lines unchanged rather than dropping them

### Future Enhancement Points
- **Custom Waypoint Distributions**: Non-uniform waypoint placement strategies
- **Multi-Map Scenarios**: Agents moving between different map environments
- **Dynamic Waypoint Generation**: Runtime waypoint assignment based on traffic patterns
- **Parallel Processing**: Multi-threaded processing for large scenario sets

This project represents a robust, research-grade tool for enhancing multi-agent pathfinding scenarios with intermediate waypoints, designed with reproducibility, scalability, and data integrity as core principles.
