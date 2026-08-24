# Preprocessing pipeline for multiple neuropixels recordings in the Buzsaki Lab
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

### 1. Define paths and parameters in run scripts
Once the data is transfered this can be varified with the HPC GUI [Open OnDemand](https://ondemand.hpc.nyumc.org/). Using either the Virtual Desktop or Files dropdown the files can be inspected and edited. Navigate to the [main run bash script]()