import pandas as pd
import os
import json

def main():
    base_dir = 'Abyssal_World'
    cells_path = os.path.join(base_dir, 'cells.csv')
    merged_path = 'merged.csv'

    if not os.path.exists(cells_path):
        print(f"Error: {cells_path} not found.")
        return

    print(f"Loading base file: {cells_path}")
    df_cells = pd.read_csv(cells_path)
    print(f"Base shape: {df_cells.shape}")

    # Map filename to column prefix
    csv_files = {
        'corals.csv': 'coral',
        'currents.csv': 'current',
        'hazards.csv': 'hazard',
        'life.csv': 'life',
        'poi.csv': 'poi',
        'resources.csv': 'resource'
    }

    for filename, prefix in csv_files.items():
        filepath = os.path.join(base_dir, filename)
        if not os.path.exists(filepath):
            print(f"Skipping {filename} (not found)")
            continue

        print(f"Processing {filename}...")
        try:
            df_other = pd.read_csv(filepath)
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            continue

        # Rename columns to avoid collisions, excluding join keys
        # We prefix all columns except 'row' and 'col'
        cols_to_rename = {c: f"{prefix}_{c}" for c in df_other.columns if c not in ['row', 'col']}
        df_other.rename(columns=cols_to_rename, inplace=True)

        # Check for duplicates on (row, col)
        if df_other.duplicated(subset=['row', 'col']).any():
            print(f"  Found duplicate entries for (row, col) in {filename}. Aggregating...")
            # Aggregate all value columns into lists
            # We select columns that are NOT row/col for aggregation
            value_cols = [c for c in df_other.columns if c not in ['row', 'col']]
            
            # Group by row, col and aggregate
            df_other = df_other.groupby(['row', 'col'])[value_cols].agg(lambda x: list(x)).reset_index()
            print(f"  Aggregated shape: {df_other.shape}")

        # Merge
        df_cells = pd.merge(df_cells, df_other, on=['row', 'col'], how='left')
        print(f"  Merged. Current shape: {df_cells.shape}")

    # Process food_web.csv (special case: merge on biome)
    food_web_path = os.path.join(base_dir, 'food_web.csv')
    if os.path.exists(food_web_path):
        print("Processing food_web.csv...")
        try:
            df_food = pd.read_csv(food_web_path)
            # Columns: predator, prey, interaction_strength, biome_overlap
            # We want to aggregate by 'biome_overlap' (which maps to 'biome' in cells)
            
            # Rename biome_overlap to match logic, or just keep as key
            group_col = 'biome_overlap'
            
            if group_col in df_food.columns:
                # Aggregate into lists
                df_food_agg = df_food.groupby(group_col).agg({
                    'predator': list,
                    'prey': list,
                    'interaction_strength': list
                }).reset_index()
                
                # Rename columns for the merge
                df_food_agg.rename(columns={
                    'predator': 'biome_predators',
                    'prey': 'biome_prey',
                    'interaction_strength': 'biome_interaction_strengths'
                }, inplace=True)
                
                # Merge with cells on cells.biome == food_web.biome_overlap
                df_cells = pd.merge(df_cells, df_food_agg, left_on='biome', right_on=group_col, how='left')
                
                # Drop the extra key column from the right side if it exists
                if group_col in df_cells.columns:
                    df_cells.drop(columns=[group_col], inplace=True)
                    
                print(f"  Merged food_web. Current shape: {df_cells.shape}")
            else:
                print(f"  Warning: {group_col} column not found in food_web.csv")
                
        except Exception as e:
            print(f"Error processing food_web.csv: {e}")

    # Save result
    print(f"Saving merged data to {merged_path}...")
    df_cells.to_csv(merged_path, index=False)
    print("Done.")

if __name__ == "__main__":
    main()

