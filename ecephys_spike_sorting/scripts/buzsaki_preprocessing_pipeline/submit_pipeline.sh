#!/usr/bin/env bash
set -euo pipefail

########################
# USER CONFIG SECTION  #
########################

ACCOUNT="ser9475"            # Slurm account
CPU_PARTITION="cpu_short"          # CPU partition
GPU_PARTITION="gpu8_medium"          # GPU partition
MAIL_USER="ser9475@nyu.edu"  # set "" to disable notifications

CODE_DIR="/gpfs/home/ser9475/Documents/ecephys_spike_sorting"
PIPELINE_SCRIPT="ecephys_spike_sorting/scripts/sglx_sids_pipeline.py"
N_PROBES=1                   # number of probes / GPUs

mkdir -p logs

######################################
# 1) CATGT JOB SCRIPT + SUBMISSION  #
######################################

echo "Submitting CatGT job..."

CATGT_SCRIPT=$(mktemp)
cat > "$CATGT_SCRIPT" <<'EOS'
#!/usr/bin/env bash
#SBATCH --job-name=catgt_preproc
#SBATCH --partition=CPU_PARTITION_PLACEHOLDER
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=logs/catgt_%j.out
#SBATCH --error=logs/catgt_%j.err

module load condaenvs/gpu/kilosort
cd CODE_DIR_PLACEHOLDER
export PYTHONPATH=CODE_DIR_PLACEHOLDER:CODE_DIR_PLACEHOLDER/ecephys_spike_sorting/scripts:$PYTHONPATH

python PIPELINE_SCRIPT_PLACEHOLDER --stage catgt
EOS

sed -i "s/ACCOUNT_PLACEHOLDER/$ACCOUNT/" "$CATGT_SCRIPT"
sed -i "s/CPU_PARTITION_PLACEHOLDER/$CPU_PARTITION/" "$CATGT_SCRIPT"
sed -i "s|CODE_DIR_PLACEHOLDER|$CODE_DIR|g" "$CATGT_SCRIPT"
sed -i "s|PIPELINE_SCRIPT_PLACEHOLDER|$PIPELINE_SCRIPT|g" "$CATGT_SCRIPT"

CATGT_JOBID=$(sbatch --parsable "$CATGT_SCRIPT")

if [[ -n "$MAIL_USER" ]]; then
  scontrol update JobId="$CATGT_JOBID" MailType=END,FAIL MailUser="$MAIL_USER"
fi

echo "CatGT job submitted with JobID: $CATGT_JOBID"

###############################
#2)       KILOSORT           #
##############################

echo "Submitting Kilosort GPU job (N_PROBES=$N_PROBES)..."

KS_SCRIPT=$(mktemp)
cat > "$KS_SCRIPT" <<'EOS'
#!/usr/bin/env bash
#SBATCH --job-name=ks4_sort
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=256G
#SBATCH --time=12:00:00
#SBATCH --array=0-N_LAST_PROBE_PLACEHOLDER
#SBATCH --output=logs/ks4_%A_%a.out
#SBATCH --error=logs/ks4_%A_%a.err

module load condaenvs/gpu/kilosort
cd CODE_DIR_PLACEHOLDER
export PYTHONPATH=CODE_DIR_PLACEHOLDER:CODE_DIR_PLACEHOLDER/ecephys_spike_sorting/scripts:$PYTHONPATH

# Array index = probe index
PROBE_INDEX=$SLURM_ARRAY_TASK_ID
export CUDA_VISIBLE_DEVICES=0

python PIPELINE_SCRIPT_PLACEHOLDER \
  --stage kilosort \
  --probe-index $PROBE_INDEX
EOS

sed -i "s/GPU_PARTITION_PLACEHOLDER/$GPU_PARTITION/" "$KS_SCRIPT"
sed -i "s/N_LAST_PROBE_PLACEHOLDER/$((N_PROBES-1))/g" "$KS_SCRIPT"
sed -i "s|CODE_DIR_PLACEHOLDER|$CODE_DIR|g" "$KS_SCRIPT"
sed -i "s|PIPELINE_SCRIPT_PLACEHOLDER|$PIPELINE_SCRIPT|g" "$KS_SCRIPT"
sed -i 's/\r$//' "$KS_SCRIPT"   # protects against CRLF

KS_JOBID=$(sbatch --parsable --dependency=afterok:$CATGT_JOBID "$KS_SCRIPT")

if [[ -n "$MAIL_USER" ]]; then
  scontrol update JobId="$KS_JOBID" MailType=END,FAIL MailUser="$MAIL_USER"
fi

echo "Kilosort job submitted with JobID: $KS_JOBID (after CatGT)"

########################################
# 3) TPRIME + CLEANUP JOB SCRIPT       #
########################################

echo "Submitting TPrime + cleanup job..."

TP_SCRIPT=$(mktemp)
cat > "$TP_SCRIPT" <<'EOS'
#!/usr/bin/env bash
#SBATCH --job-name=tprime_cleanup
#SBATCH --partition=CPU_PARTITION_PLACEHOLDER
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --mem=256Gb
#SBATCH --time=6:00:00
#SBATCH --output=logs/tprime_%j.out
#SBATCH --error=logs/tprime_%j.err

module load condaenvs/gpu/kilosort
cd CODE_DIR_PLACEHOLDER
export PYTHONPATH=CODE_DIR_PLACEHOLDER:CODE_DIR_PLACEHOLDER/ecephys_spike_sorting/scripts:$PYTHONPATH

export GIT_PYTHON_REFRESH=quiet
python PIPELINE_SCRIPT_PLACEHOLDER --stage tprime_cleanup
EOS

sed -i "s/ACCOUNT_PLACEHOLDER/$ACCOUNT/" "$TP_SCRIPT"
sed -i "s/CPU_PARTITION_PLACEHOLDER/$CPU_PARTITION/" "$TP_SCRIPT"
sed -i "s|CODE_DIR_PLACEHOLDER|$CODE_DIR|g" "$TP_SCRIPT"
sed -i "s|PIPELINE_SCRIPT_PLACEHOLDER|$PIPELINE_SCRIPT|g" "$TP_SCRIPT"

TPRIME_JOBID=$(sbatch --parsable --dependency=afterok:$KS_JOBID "$TP_SCRIPT")

if [[ -n "$MAIL_USER" ]]; then
  scontrol update JobId="$TPRIME_JOBID" MailType=END,FAIL MailUser="$MAIL_USER"
fi

echo "TPrime/cleanup job submitted with JobID: $TPRIME_JOBID (after Kilosort)"
echo
echo "Pipeline submission complete."
echo "  CatGT job    : $CATGT_JOBID"
echo "  KS4 job      : $KS_JOBID"
echo "  TPrime/clean : $TPRIME_JOBID"
