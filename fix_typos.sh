#!/bin/bash
#SBATCH --job-name=fix_json_typos
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=fix_typos_%j.log

# 1. Load Python module
module purge
module load release/2026 GCCcore/14.2.0 Python/3.13.1

# 2. Location of the fixer script
cd /data/horse/ws/pele579g-dnb_novel/pele579g-dnb_novel-1769817765/Marina/epub_unpack_pro_parallel_version

# 3. The script will recursively find all .json files inside this folder
python fix_typos.py /data/horse/ws/pele579g-dnb_novel/pele579g-dnb_novel-1769817765/Marina/extracted_json/json_final