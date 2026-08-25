# Preprocessing pipeline for multiple NeuroPixels recordings in the Buzsaki Lab
### last modified: 8/24/2026
***Sidney Rafilson***

Sid.Rafilson@nyu.edu

## Description
This is the first part of the preprocessing pipeline which runs CatGT and SuperCat to trims and concatenates within sessions recordings (for example: pre_sleep -> behavior -> post_sleep), runs the kilosort spike sorting, and runs TPrime for aligning spike times across probes. When using multiple neuropixels probes (even when they are connected to the same headstage) the recording stops at different times for each probe. As such, CatGT crops the length of each probe recording so that they are all the same length before SuperCat concatentates everything into a single session. A further complication is introduced When recording data across multiple headstages (which inevitably have slightly different sampling rates) since the samples will not be aligned in time. We run Tprime to map spike times to a global clock which is kept by a 1Hz digital square wave. For more information about this pipeline see the [original repository]('https://github.com/jenniferColonell/ecephys_spike_sorting') written by **Jennifer Colonell** at the Allen Institute.

After running this pipeline the data will be ready for the [second part of preprocessing](https://github.com/Sid-Rafilson-1617/CellExplorer/blob/main/pipeline_sr.m) where the data is loaded into CellExplorer and formatted according to Buzsaki Lab data standardization.


Note that since Tprime is here only ran on spike times, the LFPs and additional LFP detected events (ripples, sleep states, etc) will still need to be aligned across probes with different headstages. This can be achieved using the buzcode function [bz_alignEvents](temp_path_no_function_yet). This is a critical step since small sampling rate differences across headtsages lead to misalignment on the order of seconds.


## Instructions



### 1. Clone repository on HPC
An account with the [BigPurple HPC](https://hpcmed.org/guide/get-started) should be set up prior to running this pipeline. SSH on to the cluster `{KID}@bigpurple.nyumc.org` (For windows use [PuTTY](https://putty.org/index.html)) and clone this repository into your Home Directory


1. `cd /gpfs/home/{KID}`

2. `git clone 'https://github.com/Sid-Rafilson-1617/ecephys_spike_sorting.git'`



### 2. Transfer raw data to the HPC
Data transfer from the Buzsaki lab share `\research-cifs.nyumc.org\research` to Big Purple `bigpurple.nyumc.org` is easy with [WinSCP](https://winscp.net/eng/download.php), or for Mac users [Cyberduck](https://cyberduck.io/). The data should be moved to `/gpfs/data/buzsakilab/{KID}`.

Testing data can be found at `"Z:\Buzsakilabspace\Datasets\RafilsonS\testing-datasets\testing-multi-NPX-SGLX"`



### 3. Define paths and parameters in run scripts
Once the data is transfered this can be varified with the HPC GUI [Open OnDemand](https://ondemand.hpc.nyumc.org/). Using either the Virtual Desktop or Files dropdown the files can be inspected and edited. Navigate to  [submit_pipeline.sh](/ecephys_spike_sorting/scripts/buzsaki_preprocessing_pipeline/submit_pipeline.sh) and rename the following variables under USER CONFIG SECTION

1. Set your HPC account name on line 8 `ACCOUNT="{KID}"`
2. Ensure line 13 points to the repository you cloned on the HPC `CODE_DIR="/gpfs/home/{KID}/ecephys_spike_sorting"`
3. Set the number of probes on line 15 `N_PROBES=2`

Now navigate to [sglx_sids_pipeline.py](/ecephys_spike_sorting/scripts/buzsaki_preprocessing_pipeline/sglx_sids_pipeline.py) and rename the following variables under SPECIFY DIRECTORIES

1. Set the path to the raw data on line 30 `NPX_DIR = r"/gpfs/data/buzsakilab/sid/testing_data`
2. A function was written to get required specifications for CatGT but sometimes it does not work if the data was saved with incorrect naming conventions. If this is the case then on line 67 set `manual_run_specs = True` and edit the run_specs list below.
3. On line 113 a parameter string is defined for extracting TTL times and other digitial inputs. This may need to be adjusted if a different channel is being used for the acquisition. `event_ex_param_str = ['-xd=2,0,384,6,500', '-xd=1,0,6,12,0']`
4. There are many more paramters that can changed, examine the code if necessary 

Finally, navigate to [create_input_json.py](/ecephys_spike_sorting/scripts/create_input_json.py) and rename the following variables under createInputJson
1. Ensure line 87 points to your copy `ecephys_directory = r'/gpfs/home/{KID}/ecephys_spike_sorting'`
2. Line 107 should point to your folder kilosort_output_tmp = r"/gpfs/data/buzsakilab/{userName}/kilosort_data_temp"



### 4. Run the bash script to execute the preprocessing pipeline
1. SSH on to the cluster
2. Load the module which activates the conda envirnment 

    `module load condaenvs/gpu/ser9475`

3. Move to the codebase directory

    `cd /gpfs/home/{KID}/ecephys_spike_sorting`

4. Add this repository to the python path


    `export PYTHONPATH=/gpfs/home/{KID}/ecephys_spike_sorting:/gpfs/home/{KID}/ecephys_spike_sorting/ecephys_spike_sorting/scripts:$PYTHONPATH`

5. run the main run bash script

    `bash ecephys_spike_sorting/scripts/buzsaki_preprocessing_pipeline/submit_pipeline.sh`


### 5. Watching progress and debugging
1. To see what resources are being used and which are waiting for use type the command `squeue -u {KID}`

2. To cancel the jobs (especially in the case of an error) type `scancel -u {KID}`

2. To check log files navigate to the [logs folder](/logs/). This is where you will find any error messages.

