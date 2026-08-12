#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=8:00:00
#SBATCH --job-name=epx_full
#SBATCH --output=epx_full_%j.out
#SBATCH --error=epx_full_%j.err


# --- Environment Setup ---
module purge
module load release/2026 GCCcore/14.2.0 Python/3.13.1

# Navigate to tool directory
#cd $SLURM_SUBMIT_DIR
cd /projects/p_dnbnovel/data/pele579g-dnb_novel-1769817765/Marina/epub_unpack_pro/

# Activate the virtual environment
source venv/bin/activate

# --- Execution ---
srun epx bulk-process /projects/p_dnbnovel/data/pele579g-dnb_novel-1769817765/E-Books/E-Pub/ /data/horse/ws/pele579g-dnb_novel/pele579g-dnb_novel-1769817765/Marina/extracted_json --model-path classifier/testing/classifier --skip-existing

