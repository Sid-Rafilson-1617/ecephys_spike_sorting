import os
from pathlib import Path




def build_run_specs(DIR: str, region: str = 'hippocampus'):
    """
    Build run specifications for CatGT and supercat based on the folders in spikeGLX  data directory

    Each run specification is a list:
      [run_name, gate_str, probe_str, brain_region_list]

    Returns a list of run specifications.
    """
    run_specs = []
    folders = [f.name for f in Path(DIR).iterdir() if f.is_dir()]
    for f in folders:

        # Checking for obx meta files. If they exist, this is a run folder and the meta file contains the necessary information for the concatenation order (fileCreateTime)
        metafile = [sf.name for sf in Path(os.path.join(DIR, f)).iterdir() if sf.name.endswith('.meta')]
        if metafile:

            # get gate value
            g = f[-1]

            # counting number of subdirectories that end in imec{number}
            imec_dirs = [d for d in Path(os.path.join(DIR, f)).iterdir() if d.is_dir() and d.name.startswith(f"{f}_imec")]

            # read the meta files to get the creation time
            meta_info = []
            for mf in metafile:
                meta_path = os.path.join(DIR, f, mf)
                with open(meta_path, 'r') as file:
                    lines = file.readlines()
                    for line in lines:
                        if line.startswith('fileCreateTime'):
                            # Extract the timestamp value
                            timestamp = line.split('=')[1].strip() # this is of the form year-day-monthThour:minute:second (2025-06-13T16:25:34)
                            meta_info.append((mf, timestamp))

            run_name = f[:-3]  # remove _gX to get run name
            n_probes = len(imec_dirs)
            probe_str = f'0:{n_probes - 1}'
            run_specs.append([run_name, g, probe_str, [region] * n_probes, meta_info])

    # reorder by meta_info timestamp
    run_specs.sort(key=lambda x: x[4][0][1])  # sort by the timestamp of the first meta file

    # check if any duplicate run names. This is when there are multiple gates for the same run. In this case create a g list for the run name and add it and remove the old runs
    run_names = [spec[0] for spec in run_specs]
    duplicates = [name for name in set(run_names) if run_names.count(name) > 1]
    for dup in duplicates:
        g_list = []
        probe_str = ''
        meta_info = []
        for spec in run_specs:
            if spec[0] == dup:
                g_list.append(spec[1])
                probe_str = spec[2]  # assuming same probe str for all gates
                meta_info.extend(spec[4])
                brain_regions = spec[3]  # assuming same brain regions for all gates
        # create new spec
        new_spec = [dup, ','.join(g_list), probe_str, brain_regions, meta_info]
        # remove old specs
        run_specs = [spec for spec in run_specs if spec[0] != dup]
        # add new spec
        run_specs.append(new_spec)

    # remove the meta_info from the specs
    for spec in run_specs:
        spec.pop(4)

    return run_specs
