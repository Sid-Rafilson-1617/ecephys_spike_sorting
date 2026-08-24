# Preprocessing pipeline for multiple NeuroPixels recordings in the Buzsaki Lab
### last modified: 8/24/2026
***Sidney Rafilson***

Sid.Rafilson@nyu.edu

## Description
This is the first part of the preprocessing pipeline which concatenates within sessions recordings (for example: pre_sleep -> behavior -> post_sleep) runs the spike sorting, and runs TPrime for aligning spike times across probes. After running this pipeline the data will be ready for the [second part of preprocessing](https://github.com/Sid-Rafilson-1617/CellExplorer/blob/main/pipeline_sr.m) where the data is loaded into CellExplorer and formatted according to Buzsaki Lab data standardization.


## Instructions

### 1. Clone repository on HPC
An account with the [BigPurple HPC](https://hpcmed.org/guide/get-started) should be set up prior to running this pipeline. SSH on to the cluster (For windows use [PuTTY](https://putty.org/index.html)) and clone this repository into your Home Directory


1. `cd /gpfs/home/{userName}`

2. `git clone -b hpc https://github.com/Sid-Rafilson-1617/ecephys_spike_sorting.git'`

### 2. Transfer raw data to the HPC
Data transfer from the Buzsaki lab share `\research-cifs.nyumc.org\research` to Big Purple `bigpurple.nyumc.org` is easy with [WinSCP](https://winscp.net/eng/download.php). The data should be moved to `/gpfs/data/buzsakilab/{userName}`

### 3. Define paths and parameters in run scripts
Once the data is transfered this can be varified with the HPC GUI [Open OnDemand](https://ondemand.hpc.nyumc.org/). Using either the Virtual Desktop or Files dropdown the files can be inspected and edited. Navigate to the [main run bash script](/ecephys_spike_sorting/scripts/buzsaki_preprocessing_pipeline/submit_pipeline.sh) and rename the following variables under USER CONFIG SECTION

1. Set your HPC account name on line 8 `ACCOUNT="{userName}"`
2. Ensure line 13 points to the repository you cloned on the HPC `CODE_DIR="/gpfs/home/{userName}/Documents/ecephys_spike_sorting"`
3. Set the number of probes on line 15 `N_PROBES=1`

Now navigate to the [main python script](/ecephys_spike_sorting/scripts/buzsaki_preprocessing_pipeline/sglx_sids_pipeline.py) and rename the following variables under SPECIFY DIRECTORIES

1. Set the path to the raw data on line 30 `NPX_DIR = r"/gpfs/data/buzsakilab/sid/testing_data`
2. A function was written to get required specifications for CatGT but sometimes it does not work if the data was saved with incorrect naming conventions. If this is the case then on line 67 set `manual_run_specs = True` and edit the run_specs list below.
3. On line 113 a parameter string is defined for extracting TTL times and other digitial inputs. This may need to be adjusted if a different channel is being used for the acquisition. `event_ex_param_str = ['-xd=2,0,384,6,500', '-xd=1,0,6,12,0']`
4. There are many more paramters that can changed, examine the code if necessary 

### 4. Run the bash script to execute the preprocessing pipeline
1. SSH on to the cluster
2. Load the module which activates the conda envirnment 

    `module load condaenvs/gpu/ser9475`

3. Move to the codebase directory

    `cd /gpfs/home/{userName}/Documents/ecephys_spike_sorting`

4. Add this repository to the python path

    `export PYTHONPATH=/gpfs/home/{userName}/Documents/ecephys_spike_sorting:/gpfs/home/{userName}/Documents/ecephys_spike_sorting/ecephys_spike_sorting/scripts:$PYTHONPATH`

5. run the main run bash script

    `bash ecephys_spike_sorting/scripts/submit_pipeline.sh`

