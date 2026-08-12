#!/bin/bash
#SBATCH --job-name=epx_full_parallel
#SBATCH --time=8:00:00               
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=2G
#SBATCH --array=1-35089%20             # Adjust to the exact number in todo.txt== number of ebooks to process
#SBATCH --output=logs/slurm-%A_%a.out 

# --- 1. Load modules and activate environment ---
module purge
module load release/2026 GCCcore/14.2.0 Python/3.13.1

# Activate your virtual environment
#source /projects/p_dnbnovel/data/pele579g-dnb_novel-1769817765/Marina/epub_unpack_pro/venv/bin/activate
source venv/bin/activate

# Navigate to the parallel processing tool directory
#- cd /projects/p_dnbnovel/data/pele579g-dnb_novel-1769817765/Marina/epub_unpack_pro_parallel_version
cd $SLURM_SUBMIT_DIR

# --- 2. Grab the specific file for this task ---
INPUT_FILE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" todo.txt)

# --- 3. Pass the file to the tool ---
echo "Task $SLURM_ARRAY_TASK_ID processing $INPUT_FILE"

# REAL OUTPUT PATH
OUTPUT_DIR="/data/horse/ws/pele579g-dnb_novel/pele579g-dnb_novel-1769817765/Marina/extracted_json"
MODEL_PATH="classifier/testing/classifier"

PYTHONPATH=. srun python -m extractor.cli bulk-process "$INPUT_FILE" "$OUTPUT_DIR" \
    --model-path "$MODEL_PATH" \
    --skip-existing \
    --no-report
