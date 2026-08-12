# Epub_unpack (epx-pro)

Epub_unpack is an optimized, integrated pipeline designed for large-scale conversion of German dime novel EPUBs into JSON. It consolidates extraction, semantic tagging, and narrative classification into a single high-performance workflow with robust monitoring.

Epub_unpack was developped by Lennart Keller and the classifier by Thora Hagen. The tool was enhanced and made ready for HPC infrastructure by Marina Spielberg.

## Key Features
- **Integrated Pipeline:** Runs extraction, type inference, and classification in one pass.
- **Bulk Processing:** Efficiently handles thousands of books via the `bulk-process` command.
- **Monitoring & Reporting:** Generates a detailed `bulk_processing_report.json` tracking the success/failure of every book at every stage.
- **Smart Skipping:** Use `--skip-existing` to pick up where you left off without reprocessing finished books.
- **Multi-Platform:** Designed to run locally on a laptop or in parallel on HPC clusters.

## Installation (All Platforms)

### Prerequisites
- Python 3.12+
- Java (for Saxon XSLT processor)

### Setup
1. Clone or copy the `epub_unpack_pro_parallel_version` directory to your machine.
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the application:
   ```bash
   pip install setuptools
   pip install -e .
   ```

---

## Local Usage (Linux)

For processing a directory of ebooks directly on your machine.

### Run Command
```bash
epx bulk-process <INPUT_DIR> <OUTPUT_DIR> --model-path <PATH_TO_CLASSIFIER> [OPTIONS]
```

### Example
```bash
# Processes all ebooks in the folder './my_ebooks'
epx bulk-process ./my_ebooks ./output --model-path classifier/testing/classifier --skip-existing
```

#### Common Options:
- `--model-path`: (Required) Path to the trained classifier model (e.g., `classifier/testing/classifier`).
- `--skip-existing`: Skip books that already have a final JSON output.
- `--log-path`: Save detailed processing logs to a specific file.
- `--ignore-images`: Do not extract images from the EPUBs.
- `--strict`: Stop the entire process if an extraction error occurs.

---

##  HPC Usage (Parallel Cluster)

Designed for ZIH Dresden or other Slurm-based clusters. This version uses parallel job arrays for massive throughput.

### 1. Initial Setup (One-time only)
After transfering the `epub_unpack_pro_parallel_version` folder to the HPC:
```bash
cd /path/to/your/epub_unpack_pro_parallel_version/
module load release/2026 GCCcore/14.2.0 Python/3.13.1
python3 -m venv venv
source venv/bin/activate
pip install setuptools
pip install -e .
```

### 2. Parallel Workflow (SLURM Job Arrays)

Unlike local usage, parallel processing requires a `todo.txt` file containing the paths to all books you want to process.

1.  **Prepare the file list (`todo.txt`):**
    ```bash
    # Generate absolute paths for all EPUB files
    find /absolute/path/to/epubs -name "*.epub" > todo.txt
    ```

2.  **Configure the SLURM script (`epub_unpack_pro_parallel.sh`):**
    *   Update `#SBATCH --array=1-X%20` where `X` is the number of lines in `todo.txt`.
    *   Set the `OUTPUT_DIR` and `MODEL_PATH` variables.
    *   Note: The script uses `$SLURM_SUBMIT_DIR` to automatically find your current directory.

3.  **Submit the job:**
    ```bash
    mkdir -p logs  # Folder for worker logs
    sbatch epub_unpack_pro_parallel.sh
    ```

### 3. Success Tracking & Final Reporting
Parallel workers do not write a single consolidated report. To generate one:
1. Wait for all jobs to finish.
2. Run the tool once on the entire input directory with `--skip-existing`. It will skip finished books and write the final `bulk_processing_report.json`.

```bash
epx bulk-process /path/to/epubs /path/to/output --model-path classifier/testing/classifier --skip-existing
```

---

## Understanding the Pipeline
Each book goes through four distinct stages:
1. **Extraction:** Converts the EPUB into raw text/XML data.
2. **Type Inference:** Labels sections (e.g., `chapter`, `cover`, `novel`, `toc`) based on titles.
3. **Classification:** Uses a trained model to label text segments as `narrative` or `non-narrative`.
4. **Serialization:** Writes the completed data and images to the output directory.

## Monitoring Results
After a run, the `<OUTPUT_DIR>` will contain:
- **`json_final/`**: Subdirectories for each book containing the `.json` file and an `imgs/` folder.
- **`bulk_processing_report.json`**: A master report showing success/failure and specific error messages.

# Slurm Reference (HPC Specific)
see ZIH documentation: https://compendium.hpc.tu-dresden.de/

- **$SLURM_SUBMIT_DIR:** This environment variable points to the directory where you executed the `sbatch` command. Our scripts use this to avoid hardcoded paths.
- **srun:** Executes the application on allocated resources.
- **salloc:** Used for interactive testing (e.g., `salloc --ntasks=1 --cpus-per-task=4 --mem=8G --time=01:00:00`).
- **sbatch:** Submits a script for background execution.

## HPC Usage Summary for Independent Parallel Version (Quick Start)
1. **Transfer the folder:** Copy `epub_unpack_pro_parallel_version` to HPC.
2. **Setup Environment:** (See Setup section above).
3. **Prepare Job:** Generate `todo.txt` and adjust `epub_unpack_pro_parallel.sh`.
4. **Submit Job:** `mkdir -p logs && sbatch epub_unpack_pro_parallel.sh`
5. **Monitor:** Use `squeue --me` to check status.
