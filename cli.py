import asyncio
import os
import os.path as osp
from typing import List, Tuple

import click

from utilities import override_sys_out, try_hook_uvloop, _self_path
from pipeline import ErcWorkspace, _20mya_cutoff, _30mya_cutoff


FASTA_ENDINGS = [".fa", ".faa", ".fs", ".fasta"]


@click.command()
@click.option("--timetree", default=osp.join(_self_path(), "data", "finished_mam_timetree.nwk"),
              help="The time-scaled species phylogeny in newick format. Defaults to mammalian tree")
@click.option("--sequences", default=".", help="The directory to search for sequences in.")
@click.option("--align-pair", nargs=2, type=str, multiple=True,
              help="Instead of specifying a directory of alignments, you can specify individual pairs of alignments to run")
@click.option("--wd", default=".", help="The working directory to write files to.")
@click.option("--erc-type", type=click.Choice(['original', 'bt', "20my", "30my"], case_sensitive=False), default="original",
              help="The type of ERC to calculate. Note that the 20MY and 30MY ERC calculations expect the mammalian "
                   "data presented in Varela et al (2021).")
@click.option("--segment", is_flag=True, help="If passed, split trimmed alignment into pieces are run ERCs on these pieces")
@click.option("--kmer", default=10, type=int, help="The kmer sized pieces to run segmented ERCs on.")
@click.option("--slide", is_flag=True,
              help="If passed, segmented ERCs are run with a sliding window (of the size passed in --kmer) instead of naively splitting alignments into kmers.")
@click.option("--skip-align", is_flag=True, help="Assume the sequences have already been aligned.")
@click.option("--skip-trim", is_flag=True, help="Assume the sequences have already been trimmed.")
@click.option("--id2name", default=None,
              help="Pass a tab-separated file with 2 columns representing: 'alignment_identifier' and 'readable_name', respectively, including a header line. This is used for exporting the resultant matrix.")
def main(timetree: str, sequences: str, align_pair: List[Tuple[str, str]], wd: str, erc_type: str, segment: bool,
         kmer: int, slide: bool, skip_align: bool, skip_trim: bool, id2name: str):
    try_hook_uvloop()
    override_sys_out("ERC")

    assert osp.exists(timetree)

    arg_mods = dict()
    if erc_type == "bt":
        arg_mods['time_corrected'] = True
    elif erc_type == "20my":
        arg_mods['taxon_set'] = _20mya_cutoff
    elif erc_type == "30my":
        arg_mods['taxon_set'] = _30mya_cutoff

    if segment:
        arg_mods['segmented'] = segment
        arg_mods['segment_size'] = kmer
        if slide:
            arg_mods['sliding_window'] = True

    if skip_align:
        arg_mods["skip_align"] = skip_align
    if skip_trim:
        arg_mods["skip_trim"] = skip_trim

    if id2name:
        assert osp.exists(id2name)
        id2name_dict = dict()
        with open(id2name, 'r') as f:
            first = True
            for l in f:
                if first:
                    first = False
                    continue
                split = l.strip().split("\t")
                if len(split) < 2:
                    continue
                id2name_dict[split[0].strip()] = split[1].strip()
        arg_mods["id2name"] = id2name_dict

    print("Starting up...")

    workspace = ErcWorkspace(wd, timetree, **arg_mods)

    if not align_pair:
        for f in os.listdir(sequences):
            if osp.isdir(f):
                continue
            if f.split(".")[-1].lower() not in FASTA_ENDINGS:
                print(f"WARNING: Skipping alignment file {f}! It does not have a fasta file ending!")
                continue
            workspace.add_alignment(osp.join(sequences, f))
    else:
        for pair in align_pair:
            workspace.add_alignment(pair[0], pair[1])

    asyncio.get_event_loop().run_until_complete(workspace.run())

    if not segment:
        workspace.export_results("all2all_matrix.xlsx")
        print("Saved data to all2all_matrix.xlsx")

    print("Completed!")


if __name__ == "__main__":
    main()
