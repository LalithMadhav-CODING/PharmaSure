#!/bin/bash
# Build script: generate candidates.json from EveryCure matrix-scores using DuckDB
set -e

echo "Installing DuckDB..."
pip install duckdb -q

echo "Downloading EveryCure matrix-scores parquet files..."
python3 << 'PYEOF'
from huggingface_hub import hf_hub_download
import glob, os

# Download all 11 parquet files
files = []
for i in range(11):
    fname = f'data/scores/train-{i:05d}-of-00011.parquet'
    path = hf_hub_download('everycure/matrix-scores', fname, repo_type='dataset')
    files.append(path)
print(f'Downloaded {len(files)} files')

# Build lookup
import duckdb, json
con = duckdb.connect()
file_list = ','.join([f"'{f}'" for f in files])

result = con.execute(f"""
    WITH ranked AS (
        SELECT target as disease_id, 
               source_ec_id as ec_id, 
               ROUND(untransformed_treat_score, 4) as score,
               ROW_NUMBER() OVER (PARTITION BY target ORDER BY untransformed_treat_score DESC) as rn
        FROM read_parquet([{file_list}])
        WHERE is_known_positive = false
        AND is_known_negative = false
        AND source_ec_id IS NOT NULL
        AND source_ec_id != ''
    )
    SELECT disease_id, ec_id, score FROM ranked WHERE rn <= 10
""").fetchall()

lookup = {}
for disease_id, ec_id, score in result:
    if disease_id not in lookup:
        lookup[disease_id] = {'c': [], 'k': []}
    lookup[disease_id]['c'].append([ec_id, score])

result2 = con.execute(f"""
    SELECT target as disease_id, source as drug_id
    FROM read_parquet([{file_list}])
    WHERE is_known_positive = true
    AND source IS NOT NULL
    AND source != ''
""").fetchall()

for disease_id, drug_id in result2:
    if disease_id not in lookup:
        lookup[disease_id] = {'c': [], 'k': []}
    lookup[disease_id]['k'].append(drug_id)

print(f'Diseases: {len(lookup)}')
os.makedirs('data', exist_ok=True)
with open('data/candidates.json', 'w') as f:
    json.dump(lookup, f, separators=(',', ':'))

import os
size = os.path.getsize('data/candidates.json')
print(f'candidates.json: {size / 1024 / 1024:.1f} MB')
PYEOF
echo "Build complete!"
