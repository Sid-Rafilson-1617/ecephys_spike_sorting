#!/usr/bin/env bash
set -euo pipefail

ACCOUNT="ser9475"
CPU_PARTITION="cpu_long"
CODE_DIR="/gpfs/home/ser9475/Documents/ecephys_spike_sorting"
PIPELINE_SCRIPT="ecephys_spike_sorting/scripts/sglx_sids_pipeline.py"
MAIL_USER="ser9475@nyu.edu"

mkdir -p logs

echo "Submitting TPrime + cleanup job..."

TP_SCRIPT=$(mktemp)
cat > "$TP_SCRIPT" <<'EOS'
#!/usr/bin/env bash
#SBATCH --job-name=tprime_cleanup
#SBATCH --partition=CPU_PARTITION_PLACEHOLDER
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=6:00:00
#SBATCH --output=logs/tprime_%j.out
#SBATCH --error=logs/tprime_%j.err

module load condaenvs/gpu/kilosort
cd CODE_DIR_PLACEHOLDER
export PYTHONPATH=CODE_DIR_PLACEHOLDER:CODE_DIR_PLACEHOLDER/ecephys_spike_sorting/scripts:$PYTHONPATH
export GIT_PYTHON_REFRESH=quiet

python PIPELINE_SCRIPT_PLACEHOLDER --stage tprime_cleanup
EOS

sed -i "s/CPU_PARTITION_PLACEHOLDER/$CPU_PARTITION/" "$TP_SCRIPT"
sed -i "s|CODE_DIR_PLACEHOLDER|$CODE_DIR|g" "$TP_SCRIPT"
sed -i "s|PIPELINE_SCRIPT_PLACEHOLDER|$PIPELINE_SCRIPT|g" "$TP_SCRIPT"

TPRIME_JOBID=$(sbatch --parsable "$TP_SCRIPT")

if [[ -n "$MAIL_USER" ]]; then
  scontrol update JobId="$TPRIME_JOBID" MailType=END,FAIL MailUser="$MAIL_USER"
fi

echo "TPrime/cleanup job submitted with JobID: $TPRIME_JOBID"

