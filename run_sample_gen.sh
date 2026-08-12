#!/bin/bash
#SBATCH --job-name=sample_gen
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=sample_gen_%j.log

# 1. Load Python
module purge
module load release/2026 GCCcore/14.2.0 Python/3.13.1

# 2. Go to your tool directory
cd /data/horse/ws/pele579g-dnb_novel/pele579g-dnb_novel-1769817765/Marina/epub_unpack_pro_parallel_version/

# 3. Activate environment and ensure pandas is installed
source venv/bin/activate
pip install pandas --quiet

# 4. Run the scripts 
python create_sample_version.py Ebook_metadata.tsv sample_data_version.tsv

# 5. Collect the files
python collect_sample_jsons.py sample_data_version.tsv /data/horse/ws/pele579g-dnb_novel/pele579g-dnb_novel-1769817765/Marina/extracted_json/json_final /data/horse/ws/pele579g-dnb_novel/pele579g-dnb_novel-1769817765/Marina/extracted_json/sample_jsons_only

# 6. Compress for transfer
tar -czf sample_jsons.tar.gz -C /data/horse/ws/pele579g-dnb_novel/pele579g-dnb_novel-1769817765/Marina/extracted_json/ sample_jsons_only

echo "Done! You can now download sample_jsons.tar.gz"
