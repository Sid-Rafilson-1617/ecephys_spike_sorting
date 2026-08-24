import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import argparse


from helpers import SpikeGLX_utils
from helpers import log_from_json
from helpers import run_one_probe
from helpers.build_run_specs import build_run_specs
from create_input_json import createInputJson


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------- USER CONFIG AREA ----------------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------



# ---------------------------
# -- SPECIFY DIRECTORIES ----
# ---------------------------


# Directory containing NPX data folders (e.g. r"/gpfs/data/buzsakilab/{user}/{session}")
NPX_DIR = r"/gpfs/data/buzsakilab/sid/IIT_M01_20260424"

# Directory to write output; will contain run/probe folders
DEST = os.path.join(NPX_DIR, 'preprocessing_output')
os.makedirs(DEST, exist_ok=True)

json_directory = os.path.join(DEST, 'preprocessing_json')
os.makedirs(json_directory, exist_ok=True)

# Name for log file for this pipeline run.
logName = 'pipeline_test_log.csv'

# Tag to append to CatGT output folders in pass 2
catGT_out_tag = 'supercat'

# cd to NPX_DIR to make relative paths simpler
os.chdir(NPX_DIR)
print(f"Current directory: {os.getcwd()}")



# ----------------
# Cleanup options
# ----------------
move_output_bin = False  # move the supercat binary files to the NPX_DIR. Doing this in MATLAB
delete_catgt = False     # delete intermediate catgt folders after processing



# ---------------------------
# -- CATGT PARAMS -----------
# ---------------------------

# Getting the run specs from the NPX_DIR
run_specs = build_run_specs(NPX_DIR)
print(f"Run specifications for concatenation: {run_specs}")

manual_run_sepcs = False
if manual_run_sepcs:
    # [run_name, gate_str, probe_str, brain_region_list]
    run_specs = [
    ['pre_sleep', '0', '0:3', ['hippocampus', 'hippocampus', 'hippocampus', 'hippocampus']],
    ['m_maze_novel_2', '0', '0:3', ['hippocampus', 'hippocampus', 'hippocampus', 'hippocampus']],
    ['post_sleep', '0', '0:3', ['hippocampus', 'hippocampus', 'hippocampus', 'hippocampus']]
]




# this will run the CatGT pass 1 and pass 2 (supercat) steps
run_catGT = True    # true to run pass_1
pass_1 = True       # trim edges, downsample to LFP
pass_2 = False      # concatenate sessions; false if only one session


skip_supercat = True # Use this if the session has only one run and you want to skip the supercat step and just use the pass 1 output for kilosort. If true, set pass_2 to false and pass_1 to true.
if skip_supercat:
	pass_1 = True
	pass_2 = False
	delete_catgt = False    # so that the output is not deleted
	catGT_out_tag = 'catgt' # change the output tag to reflect that this is just pass 1 output that will be used for kilosort, not supercat output. This will be part of the folder name for the catGT output that is used for kilosort
    

# Full path to CatGT executable
catgt = r'/gpfs/share/apps/anaconda3/gpu/2025.06/envs/kilosort/CatGT-linux/runit.sh'


# flag to process lf. The depth estimation module assumes lf has been processed.
# if selected, must also include a range for filtering in the catGT_cmd_string
process_lf = True

# factor by which to downsample ap data for lf and the target lfp sample rate
downsample_factor = 24
lfp_sample_rate = 1250


# NI and OBX STREAM PARAMS
ni_present = False
obx_present = True



# extract param string for psth events 
event_ex_param_str = ['-xd=2,0,384,6,500', '-xd=1,0,6,12,0'] # was -xd=1,0,8,12,0 for UDS_R01 but changed to extract digital input channel 6 for TTLs in Bilat_R02. Put the square (sync) channel first and the camera TTL second. 
skip_obx_on_pass1 = [0] # list of run indices to skip the -ob flag on pass 1


# PROCESSING PARAMS
# Notes:
# - Keep each item as a separate string; argparse/subprocess handles quoting
# - Modify as needed (e.g., remove '-prb_fld' if you did not use probe folders)
PROCESS_PARAMS = [
    "-t=0,0",
    "-prb_fld",
    "-ap",
    "-ob",  # One box streams
    "-obx=0",
    "-out_prb_fld",
    "-gblcar",
    #"-apfilter=butter,4,300,10000", Leave unfiltered and filter in KS4
    "-lffilter=butter,4,0.1,450",
    "-pass1_force_ni_ob_bin",
    f"-dest={DEST}",
]

PROCESS_PARAMS.extend(event_ex_param_str)

if process_lf:
    PROCESS_PARAMS.append("-lf")
    PROCESS_PARAMS.append(f"-ap2lf_dwnsmp={downsample_factor}")


if ni_present:
    PROCESS_PARAMS.append("-ni")




# SUPERCAT SOURCES (order matters—these correspond to pass 1 outputs)
# Each element is (root_dir, catgt_output_folder_name)
# The folder names follow CatGT's convention: catgt_<run>_g<g>

SUPERCAT_SOURCES = [(DEST, f'catgt_{spec[0]}_g0') for spec in run_specs]
SUPERCATDEST = os.path.join(DEST, f'supercat')
os.makedirs(SUPERCATDEST, exist_ok=True)
SUPERCATDEST = DEST

# SUPERCAT PARAMS
SUPERCAT_PARAMS = [
    "-ap",
    "-ob",
    "-obx=0",
    "-supercat_trim_edges",
    "-prb_fld",
    "-out_prb_fld",
    f"-dest={SUPERCATDEST}",
]

if process_lf:
    SUPERCAT_PARAMS.append("-lf")

if ni_present:
    SUPERCAT_PARAMS.append("-ni")

SUPERCAT_PARAMS.extend(event_ex_param_str)



# ---------------
# Modules List
# ---------------
# List of modules to run per probe; CatGT and TPrime are called once for each run,
# and should not be included here.
modules = [            
            'ks4_helper',
            'kilosort_postprocessing',
            #'noise_templates', #I got an error for this module
            #'mean_waveforms',
            #'quality_metrics'
			]




# ----------------------
# C_Waves snr radius, um
# ----------------------
c_Waves_snr_um = 160



# -----------------
# TPrime parameters
# -----------------
create_aux_timepoints = False  #set create_aux_timepoints to true to make a file of timepoints for aux data (ni, obx) which can be corrected to match a neural stream. Only useful if toStream_sync_params is an imec stream AND you need to map analog values fromthe aux data to times in the neural stream.
runTPrime = True   # set to False if not using TPrime
sync_period = 1.0   # true for SYNC wave generated by imec basestation
toStream_sync_params = 'imec0' # should be ni, imec<probe index>. or obx<obx index>   CHECK SLACK WHERE TO SINK THIS






# ---------------------------
# -- SPECIFY SPIKE SORTING --
# ---------------------------


# ks_ver  sets up the output tag and threshold values.
ks_ver = '4'  # needs to be one of: '2.0', '2.5', '3.0', or '4'
ksTag_dict = {'2.0':'ks2', '2.5':'ks25', '3.0':'ks3', '4':'ks4'}
ks_output_tag = ksTag_dict[ks_ver]
ks_doFilter = 1 # set to 1 to do the bandpass filtering in KS4; 0 to skip filtering (if already filtered in CatGT)


# threshold values appropriate for KS4.0
ksTh_dict = {'default':'[8,9]', 'cortex':'[8,9]', 'hippocampus':'[8,9]', 'thalamus':'[8,9]'} # threshold values

# refractory periods for quality metrics
refPerMS_dict = {'default': 2.0, 'cortex': 2.0, 'hippocampus': 2.0, 'thalamus': 2.0} # refractory period in ms



# KS2, KS2.5, KS3 parameters
ks_remDup = 0       # used by KS2, 2.5, 3
ks_saveRez = 1      # used by KS2, 2.5, 3
ks_copy_fproc = 0   # used by 2.5, 3, to save drift corrected binary
ks_templateRadius_um = 163    # used by KS2, 2.5, 3
ks_whiteningRadius_um = 163   # used by KS2, 2,5 2.5, 3
ks_minfr_goodchannels = 0.1   # used by KS2, 2.5, 3; set to 0 for KS2.5 and 3


# KS2, KS2.5, KS3, KS4 parameters
ks_CAR = 0          # CAR already done in catGT
ks_nblocks = 6      # for KS2.5 KS3, and KS4; 1 for rigid registration in drift correction, 
                    # higher numbers to allow different drift for different 'blocks' of the probe


# KS4 specific parameters -- these are the default values
ks4_duplicate_spike_ms = 0.25
ks4_min_template_size_um = 10


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------ END USER CONFIG  ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------



def parse_args():
    parser = argparse.ArgumentParser(
        description="Sid's SpikeGLX preprocessing pipeline (CatGT, Kilosort, TPrime)."
    )
    parser.add_argument(
        "--stage",
        choices=["all", "catgt", "kilosort", "tprime_cleanup"],
        default="all",
        help=(
            "Which stage of the pipeline to run:\n"
            "  all            = CatGT + Kilosort + TPrime + cleanup\n"
            "  catgt          = CatGT only (pass1 + supercat)\n"
            "  kilosort       = Kilosort + postproc on one or all probes\n"
            "  tprime_cleanup = TPrime + delete CatGT intermediates"
        ),
    )
    parser.add_argument(
        "--probe-index",
        type=int,
        default=None,
        help=(
            "Index into the probe list for Kilosort stage. "
            "If omitted, Kilosort runs on all probes. "
            "Used by Slurm to parallelize across GPUs."
        ),
    )
    return parser.parse_args()



def run_subprocess(cmd: list[str], log_file: Path) -> None:
    """
    Run a subprocess, tee stdout/stderr to console and append to a log file.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"\n\n[{ts}] Running command:\n{' '.join(cmd)}\n"
    print(header)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8", newline="") as f:
        f.write(header)
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            f.write(line)
    ret = proc.wait()
    footer = f"\n[exit code: {ret}]\n"
    print(footer)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(footer)
    if ret != 0:
        raise RuntimeError(f"Command failed with exit code {ret}: {' '.join(cmd)}")


def build_pass1_commands(catgt_exe: str) -> list[list[str]]:
    """
    Build CatGT commands for pass 1.
    """
    jobs = [(NPX_DIR, spec[0], spec[1], spec[2]) for spec in run_specs]
    commands: list[list[str]] = []
    for d, r, g, prb in jobs:
        cmd = [catgt_exe, f"-dir={d}", f"-run={r}", f"-g={g}", f"-prb={prb}", *PROCESS_PARAMS]
        commands.append(cmd)
    return commands


def build_supercat_command(catgt_exe: str) -> list[str]:
    """
    Build one CatGT supercat command for pass 2.

    The -supercat argument takes a brace-enclosed list of elements:
      {root_dir,catgt_run_gX}{root_dir,catgt_run_gX}{...}
    """
    # Join elements like {Z:/path,catgt_run_g0}{Z:/path,catgt_run_g0}{...}
    supercat_elems = "".join(
        "{" + f"{root},{folder}" + "}" for (root, folder) in SUPERCAT_SOURCES
    )
    return [catgt_exe, f"-supercat={supercat_elems}", f"-prb={run_specs[0][2]}", *SUPERCAT_PARAMS]


def do_pass1(catgt_exe: str, log_file: Path) -> None:
    print("=== Starting CatGT Pass 1 ===")
    cmds = build_pass1_commands(catgt_exe)
    n_runs = len(cmds)
    for i, cmd in enumerate(cmds, start=1):
        print(f"\n--- Pass 1 Run {i}/{n_runs} ---")

        # if i == 0 remove the -xd flags 
        if i in skip_obx_on_pass1:
            cmd = [c for c in cmd if not c.startswith('-ob')]
            print(cmd)

        run_subprocess(cmd, log_file)

    print("=== Pass 1 complete. See log for details. ===")


def do_pass2(catgt_exe: str, log_file: Path) -> None:
    print("=== Starting CatGT Pass 2 (supercat) ===")
    cmd = build_supercat_command(catgt_exe)
    run_subprocess(cmd, log_file)
    print("=== Pass 2 complete. See log for details. ===")






#---------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------- MAIN FUNCTION -------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------------------------

def main(stage: str = 'all', probe_index: int | None = None):

	# RUN CATGT AND SUPERCAT
	if stage in ('catgt', 'all'):
		if not run_catGT:
			print("Warning: stage requests CatGT but run_catGT is False in config")
			   
		# set passes
		if pass_1 and not pass_2:
			which_pass = '1'
		elif pass_2 and not pass_1:
			which_pass = '2'
		elif not pass_1 and not pass_2:
			which_pass = 'none'
		else:
			which_pass = 'both'
	

		log_file = Path(os.path.join(DEST, logName))

		try:
			if which_pass in ("1", "both"):
				do_pass1(catgt, log_file)
			if which_pass in ("2", "both"):
				do_pass2(catgt, log_file)
			if which_pass == 'none':
				print('skipping CatGT pass 1 and 2')
		except Exception as e:
			print(f"\nFATAL: {e}", file=sys.stderr)
			sys.exit(2)
	else:
		print(f"Skipping CatGT because stage='{stage}'")




	# --------------------------------------------------------
	# KILOSORT + POSTPROCESSING ON SUPERCAT OUTPUT
	# --------------------------------------------------------
	# We build the JSONs and path info for ks/tprime in all
	# stages except pure CatGT-only runs.
	if stage in ("kilosort", "tprime_cleanup", "all"):
		print("\n\n=== Preparing Kilosort / postprocessing inputs ===\n")

		# check for existence of log file, create if not there
		logFullPath = os.path.join(DEST, logName)
		if not os.path.isfile(logFullPath):
			# create the log file, write header
			log_from_json.writeHeader(logFullPath)

		spec = run_specs[0]
		session_base_id = spec[0]

		# Make list of probes from the probe string
		prb_list = SpikeGLX_utils.ParseProbeStr(spec[2])

		[first_gate, last_gate] = SpikeGLX_utils.ParseGateStr(spec[1])

		# e.g. run_folder_name = "pre_homecage_g0"
		run_folder_name = session_base_id + '_g' + repr(first_gate)
		# e.g. prb0_fld_name = "pre_homecage_g0_imec0"
		prb0_fld_name = run_folder_name + '_imec' + prb_list[0]
		# e.g. /gpfs/.../testing/pre_homecage_g0/pre_homecage_g0_imec0
		prb0_fld = os.path.join(NPX_DIR, run_folder_name, prb0_fld_name)

		first_trig, last_trig = SpikeGLX_utils.ParseTrigStr('start,end', prb_list[0], str(first_gate), prb0_fld,)

	
		if last_gate > first_gate:
			# loop over other gates to check ranges of triggers 
			for gate_index in range(first_gate + 1, last_gate + 1):
				run_folder_name = session_base_id + '_g' + repr(gate_index)
				prb0_fld_name = run_folder_name + '_imec' + prb_list[0]
				prb0_fld = os.path.join(NPX_DIR, run_folder_name, prb0_fld_name)

				curr_first, curr_last = SpikeGLX_utils.ParseTrigStr('start,end', prb_list[0], str(gate_index), prb0_fld)
				if curr_first < first_trig:
					first_trig = curr_first
				if curr_last > last_trig:
					last_trig = curr_last
	
		trigger_str = repr(first_trig) + ',' + repr(last_trig)

		# initialize lists for jsons and data dirs
		catGT_input_json = []
		catGT_output_json = []
		module_input_json = []
		session_ids = []
		data_directory = []

		# This variable will hold the meta path and ks output path
		# for the *last* probe, used later by TPrime.
		input_meta_fullpath = None
		continuous_file = None
		kilosort_output_dir = None

		# ----------------------------------------------------
		# Build JSON files and paths per probe (no KS yet)
		# ----------------------------------------------------
		for i, prb in enumerate(prb_list):
			print('Creating json file for CatGT on probe: ' + prb)
			catGT_input_json.append(os.path.join(json_directory, session_base_id + prb + '_CatGT' + '-input.json'))
			catGT_output_json.append(os.path.join(json_directory, session_base_id + prb + '_CatGT' + '-output.json'))
			
			if i == 0 and ni_present:
			    catGT_stream_string = '-ap -ni'
			else:
			    catGT_stream_string = '-ap'
			
			if process_lf:
			    catGT_stream_string = catGT_stream_string + ' -lf'
			
			run_str = session_base_id + '_g' + str(first_gate)         
			prb_folder = run_str + '_imec' + prb

			run_folder =  catGT_out_tag + '_' + run_str
			input_data_directory = os.path.join(DEST, run_folder, prb_folder)
			fileName = run_str + '_tcat.imec' + prb + '.ap.bin'
			continuous_file = os.path.join(input_data_directory, fileName)
			metaName = run_str + '_tcat.imec' + prb + '.ap.meta'
			input_meta_fullpath = os.path.join(input_data_directory, metaName)
			
			print(input_meta_fullpath)
			
			_info_cat = createInputJson(
			    catGT_input_json[i],
			    npx_directory=NPX_DIR, 
			    continuous_file=continuous_file,
			    kilosort_output_directory=DEST,
			    input_meta_path=input_meta_fullpath,
			    catGT_run_name=session_base_id,
			    trigger_string=trigger_str,
			    probe_string=prb,
			    catGT_stream_string=catGT_stream_string,
			    catGT_cmd_string=' ',  # extract_string was empty
			    extracted_data_directory=DEST,
			    lfp_sample_rate=lfp_sample_rate,
			    ks_doFilter=ks_doFilter,
			)

			# create json files for the other modules
			print('Creating json file for sorting on probe: ' + prb) 
			session_ids.append(session_base_id + '_imec' + prb)
			module_input_json.append(os.path.join(json_directory, session_ids[i] + '-input.json'))
			
			run_str = session_base_id + '_g' + str(first_gate)
			run_folder = catGT_out_tag + '_' + run_str
			prb_folder = run_str + '_imec' + prb
			data_directory.append(os.path.join(DEST, run_folder, prb_folder))
			fileName = run_str + '_tcat.imec' + prb + '.ap.bin'
			continuous_file = os.path.join(data_directory[i], fileName)

			outputName = 'Kilosort_imec' + prb + '_' + ks_output_tag

			if ('kilosort_postprocessing' in modules) or ('noise_templates' in modules):
			    ks_make_copy = True
			else:
			    ks_make_copy = False

			kilosort_output_dir = os.path.join(data_directory[i], outputName)
			print('Kilosort output directory: ' + kilosort_output_dir)

			ks_Th = ksTh_dict.get(spec[3][i])
			refPerMS = refPerMS_dict.get(spec[3][i])
			print('ks_Th: ' + repr(ks_Th) + ' ,refPerMS: ' + repr(refPerMS))

			_info_mod = createInputJson(
			    module_input_json[i],
			    npx_directory=NPX_DIR, 
			    continuous_file=continuous_file,
			    input_meta_path=input_meta_fullpath,
			    kilosort_output_directory=kilosort_output_dir,
			    ks_make_copy=ks_make_copy,
			    noise_template_use_rf=False,
			    catGT_run_name=session_ids[i],
			    probe_string=spec[2],
			    ks_ver=ks_ver,
			    ks_remDup=ks_remDup,                   
			    ks_finalSplits=1,
			    ks_labelGood=1,
			    ks_saveRez=ks_saveRez,
			    ks_copy_fproc=ks_copy_fproc,
			    ks_helper_noise_threshold=20,
			    ks_minfr_goodchannels=ks_minfr_goodchannels,                  
			    ks_whiteningRadius_um=ks_whiteningRadius_um,
			    ks_Th=ks_Th,
			    ks_CSBseed=1,
			    ks_LTseed=1,
			    ks_templateRadius_um=ks_templateRadius_um,
			    ks_nblocks=ks_nblocks,
			    ks_CAR=ks_CAR,
			    extracted_data_directory=data_directory[i],
			    event_ex_param_str=event_ex_param_str,
			    c_Waves_snr_um=c_Waves_snr_um,
			    c_Waves_calc_half=False,
			    qm_isi_thresh=refPerMS/1000,
			    ks4_duplicate_spike_ms=ks4_duplicate_spike_ms,
			    ks4_min_template_size_um=ks4_min_template_size_um,
			    include_pc_metrics=True,
			    lfp_sample_rate=lfp_sample_rate,
			)

		# ---------------------------------------
		# Actually RUN Kilosort (maybe per probe)
		# ---------------------------------------
		if stage in ("kilosort", "all"):
			print("\n\n=== Now running kilosort and postprocessing on supercat output ===\n")

			for i, prb in enumerate(prb_list):
			    # If probe_index is set, only run that specific probe
			    if probe_index is not None and i != probe_index:
			        continue

			    print(f"Running Kilosort on probe index {i} (prb={prb})")
			    run_one_probe.runOne(
			        session_ids[i],
			        json_directory,
			        data_directory[i],
			        False,  # do not run CatGT; already done
			        catGT_input_json[i],
			        catGT_output_json[i],
			        modules,
			        module_input_json[i],
			        logFullPath,
			    )
		else:
			print(f"Skipping Kilosort because stage='{stage}'")
	else:
		# Stage is pure catgt
		prb_list = []
		input_meta_fullpath = None
		continuous_file = None
		kilosort_output_dir = None

        
      


    # ------------------------------
    # RUN TPRIME AND CLEANUP
    # ------------------------------
	if stage in ("tprime_cleanup", "all") and runTPrime:
		spec = run_specs[0]  # reuse
		print('\n\n=== Now running TPrime on session: ' + spec[0] + ' ===\n')

		if create_aux_timepoints:
		    if ni_present:            
		        SpikeGLX_utils.CreateAuxTimeEvents(spec[0], str(first_gate), DEST, stream='ni')
		    if obx_present:
		        obx_list = SpikeGLX_utils.ParseProbeStr(spec[2])
		        for obx_ind in obx_list:
		            SpikeGLX_utils.CreateAuxTimeEvents(spec[0], str(first_gate), DEST, stream=f'obx{obx_ind}')  
		
		session_id_tprime = spec[0] + '_TPrime'
		input_json = os.path.join(json_directory, session_id_tprime + '-input.json')
		output_json = os.path.join(json_directory, session_id_tprime + '-output.json')

		print('input meta file: ' + str(input_meta_fullpath))
		extracted_data_directory = os.path.join(DEST, catGT_out_tag + '_' + spec[0] + '_g' + str(first_gate))
		print('Extracted data directory: ' + extracted_data_directory)
		print('kilosort output directory: ' + str(kilosort_output_dir))

		str_event_ex_param_str = ' '.join(event_ex_param_str)
		_info_tp = createInputJson(
		    input_json,
		    npx_directory=NPX_DIR, 
		    continuous_file=continuous_file,
		    input_meta_path=input_meta_fullpath,
		    catGT_run_name=spec[0],
		    gate_string=spec[1],
		    kilosort_output_directory=kilosort_output_dir,
		    extracted_data_directory=DEST,                                           
		    event_ex_param_str='',
		    sync_period=1.0,
		    toStream_sync_params=toStream_sync_params,
		    ks_output_tag=ks_output_tag,
		    catGT_out_tag=catGT_out_tag,
		    lfp_sample_rate=lfp_sample_rate,
		)
		
		command = (
		    sys.executable
		    + " -W ignore -m ecephys_spike_sorting.modules.tPrime_helper"
		    + " --input_json " + input_json
		    + " --output_json " + output_json
		)
		subprocess.check_call(command.split(' ')) 
	else:
		print(f"Skipping TPrime because stage='{stage}' or runTPrime=False")

	# delete catgt intermediate folders if needed
	if stage in ("tprime_cleanup", "all") and delete_catgt:
		for spec in run_specs:
		    [first_gate, last_gate] = SpikeGLX_utils.ParseGateStr(spec[1])
		    for gate_index in range(first_gate, last_gate+1):
		        run_str = spec[0] + '_g' + repr(gate_index)
		        run_folder =  'catgt_' + run_str
		        run_path = os.path.join(DEST, run_folder)
		        print('Deleting CatGT intermediate folder: ' + run_path)
		        shutil.rmtree(run_path)












if __name__ == "__main__":
    args = parse_args()
    main(stage=args.stage, probe_index=args.probe_index)

	





























