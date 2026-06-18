#!/usr/bin/env python3
import argparse
from collections import defaultdict
from pathlib import Path

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_SIM = "../../tmp/hgcal_photon_50gev_eta2_phi90_GEN-SIM.root"
DEFAULT_REF = "/eos/geant4/fastSim/CMS_HGCal/gamma_hex/discrete_50GeV_HGCal_showers50.h5"
DEFAULT_STEPS = "hgcal_g4steps.root"
DEFAULT_LABELS = (
    ("g4SimHits", "HGCHitsEE", "SIM"),
    ("g4SimHits", "HGCHitsHEfront", "SIM"),
    ("g4SimHits", "HGCHitsHEback", "SIM"),
)


def parse_label(value):
    parts = value.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("labels must be module:instance:process")
    return tuple(parts)


def finite(values):
    values = np.asarray(values, dtype=np.float64)
    return values[np.isfinite(values)]


def finite_positive(values):
    values = finite(values)
    return values[values > 0.0]


def hist_range(arrays):
    clean = [finite(values) for values in arrays]
    clean = [values for values in clean if values.size]
    if not clean:
        return None
    combined = np.concatenate(clean)
    lo, hi = np.percentile(combined, [0.5, 99.5])
    if not np.isfinite(lo) or not np.isfinite(hi) or lo == hi:
        lo, hi = combined.min(), combined.max()
    if lo == hi:
        lo -= 0.5
        hi += 0.5
    return float(lo), float(hi)


def hist_kwargs(density):
    return {"density": density}


def y_label(kind, density):
    return "Density" if density else kind


def read_root_simhits(path, labels, max_events=None):
    from DataFormats.FWLite import Events, Handle

    events = Events(str(path))
    handle = Handle("std::vector<PCaloHit>")
    n_hits = []
    n_cells = []
    total_energy = []
    cell_total_energy = []
    hit_energy = []
    cell_energy = []
    hit_multiplicity = []

    for event_index, event in enumerate(events):
        if max_events is not None and event_index >= max_events:
            break

        event_n_hits = 0
        event_total_energy = 0.0
        event_cell_counts = {}
        event_cell_energy = {}
        for label in labels:
            event.getByLabel(*label, handle)
            hits = handle.product()
            event_n_hits += len(hits)
            for hit in hits:
                energy = float(hit.energy())
                detid = int(hit.id())
                event_total_energy += energy
                hit_energy.append(energy)
                event_cell_counts[detid] = event_cell_counts.get(detid, 0) + 1
                event_cell_energy[detid] = event_cell_energy.get(detid, 0.0) + energy

        n_hits.append(event_n_hits)
        n_cells.append(len(event_cell_energy))
        total_energy.append(event_total_energy)
        cell_total_energy.append(sum(event_cell_energy.values()))
        cell_energy.extend(event_cell_energy.values())
        hit_multiplicity.extend(event_cell_counts.values())

    return {
        "n_hits": np.asarray(n_hits, dtype=np.float64),
        "n_cells": np.asarray(n_cells, dtype=np.float64),
        "total_energy": np.asarray(total_energy, dtype=np.float64),
        "cell_total_energy": np.asarray(cell_total_energy, dtype=np.float64),
        "hit_energy": np.asarray(hit_energy, dtype=np.float64),
        "cell_energy": np.asarray(cell_energy, dtype=np.float64),
        "hit_multiplicity": np.asarray(hit_multiplicity, dtype=np.float64),
    }


def read_hgcalchallenge(path, dataset, max_events=None):
    n_cells = []
    total_energy = []
    cell_energy_parts = []

    with h5py.File(path, "r") as infile:
        showers = infile[dataset]
        n_events = showers.shape[0] if max_events is None else min(max_events, showers.shape[0])
        for event_index in range(n_events):
            shower = np.asarray(showers[event_index], dtype=np.float64)
            values = shower[shower > 0.0]
            n_cells.append(values.size)
            total_energy.append(values.sum())
            if values.size:
                cell_energy_parts.append(values)

    cell_energy = np.concatenate(cell_energy_parts) if cell_energy_parts else np.asarray([], dtype=np.float64)
    return {
        "n_cells": np.asarray(n_cells, dtype=np.float64),
        "total_energy": np.asarray(total_energy, dtype=np.float64),
        "cell_energy": cell_energy,
        "hit_multiplicity": np.ones(cell_energy.size, dtype=np.float64),
    }


def step_tree_names(root_file):
    names = set()
    for key in root_file.GetListOfKeys():
        if key.GetClassName() == "TTree" and key.GetName().startswith("HGCStepPointCloud"):
            names.add(key.GetName())
    return sorted(names)


def read_stepcloud(path, max_events=None, energy="pcalohit"):
    import ROOT

    energy_branch = "edep_pcalohit_GeV" if energy == "pcalohit" else "edep_GeV"
    events = defaultdict(lambda: {"cell_counts": {}, "cell_energy": {}, "n_steps": 0, "total": 0.0, "step_energy": []})

    root_file = ROOT.TFile.Open(str(path))
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Could not open {path}")

    try:
        trees = step_tree_names(root_file)
        if not trees:
            raise RuntimeError(f"No HGCStepPointCloud trees found in {path}")

        for tree_name in trees:
            rdf = ROOT.RDataFrame(tree_name, str(path))
            available = {str(name) for name in rdf.GetColumnNames()}
            branch = energy_branch if energy_branch in available else "edep_GeV"
            arrays = rdf.AsNumpy(["event", "cell_id", branch])

            for event_id, ids, energies in zip(arrays["event"], arrays["cell_id"], arrays[branch]):
                event = events[int(event_id)]
                for detid, edep in zip(ids, energies):
                    edep = float(edep)
                    if not (edep > 0.0):
                        continue
                    detid = int(detid)
                    event["n_steps"] += 1
                    event["total"] += edep
                    event["step_energy"].append(edep)
                    event["cell_counts"][detid] = event["cell_counts"].get(detid, 0) + 1
                    event["cell_energy"][detid] = event["cell_energy"].get(detid, 0.0) + edep
    finally:
        root_file.Close()

    n_steps = []
    n_cells = []
    total_energy = []
    cell_total_energy = []
    step_energy_parts = []
    cell_energy_parts = []
    step_multiplicity = []

    event_ids = sorted(events)
    if max_events is not None:
        event_ids = event_ids[:max_events]

    for event_id in event_ids:
        event = events[event_id]
        n_steps.append(event["n_steps"])
        n_cells.append(len(event["cell_energy"]))
        total_energy.append(event["total"])
        cell_total_energy.append(sum(event["cell_energy"].values()))
        step_energy_parts.extend(event["step_energy"])
        cell_energy_parts.extend(event["cell_energy"].values())
        step_multiplicity.extend(event["cell_counts"].values())

    return {
        "n_hits": np.asarray(n_steps, dtype=np.float64),
        "n_cells": np.asarray(n_cells, dtype=np.float64),
        "total_energy": np.asarray(total_energy, dtype=np.float64),
        "cell_total_energy": np.asarray(cell_total_energy, dtype=np.float64),
        "hit_energy": np.asarray(step_energy_parts, dtype=np.float64),
        "cell_energy": np.asarray(cell_energy_parts, dtype=np.float64),
        "hit_multiplicity": np.asarray(step_multiplicity, dtype=np.float64),
    }


def print_summary(name, summary):
    def describe(values):
        values = finite(values)
        if not values.size:
            return "n=0"
        return f"n={values.size}, mean={values.mean():.6g}, rms={values.std():.6g}, min={values.min():.6g}, max={values.max():.6g}"

    print(f"{name}:")
    if "n_hits" in summary:
        print(f"  N hits/event: {describe(summary['n_hits'])}")
    print(f"  N cells/event: {describe(summary['n_cells'])}")
    if "total_energy" in summary:
        print(f"  total energy/event: {describe(summary['total_energy'])}")
    if "cell_total_energy" in summary:
        print(f"  aggregated cell total energy/event: {describe(summary['cell_total_energy'])}")
    if "hit_energy" in summary:
        print(f"  hit energy: {describe(summary['hit_energy'])}")
    print(f"  cell energy: {describe(summary['cell_energy'])}")
    print(f"  hits per occupied cell: {describe(summary['hit_multiplicity'])}")


PLOT_STYLES = {
    "CMSSW raw simhits": {
        "color": "#1f77b4",
        "histtype": "stepfilled",
        "alpha": 0.20,
        "edgecolor": "#1f77b4",
        "linewidth": 1.0,
        "zorder": 1,
    },
    "CMSSW aggregated cells": {
        "color": "#1f77b4",
        "histtype": "step",
        "linestyle": "--",
        "linewidth": 2.2,
        "zorder": 4,
    },
    "HGCaloChallenge cells": {
        "color": "#111111",
        "histtype": "step",
        "linestyle": "-",
        "linewidth": 2.0,
        "zorder": 5,
    },
    "G4 steps": {
        "color": "#d62728",
        "histtype": "stepfilled",
        "alpha": 0.16,
        "edgecolor": "#d62728",
        "linewidth": 1.0,
        "zorder": 2,
    },
    "G4 steps aggregated cells": {
        "color": "#d62728",
        "histtype": "step",
        "linestyle": "--",
        "linewidth": 2.2,
        "zorder": 6,
    },
}


def plot_style(label):
    return dict(PLOT_STYLES.get(label, {"histtype": "step", "linewidth": 1.6}))


def draw_panels(title, panels, output, bins, density):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    fig.suptitle(title)
    axes = axes.ravel()

    for axis, (panel_title, xlabel, ylabel, series, log_y, integer_bins) in zip(axes, panels):
        if integer_bins:
            max_value = max((float(np.max(finite(values))) for _, values in series if finite(values).size), default=1.0)
            panel_bins = np.arange(0.5, max_value + 1.5, 1.0)
            plot_range = None
        else:
            panel_bins = bins
            plot_range = hist_range([values for _, values in series])

        for label, values in series:
            values = finite(values)
            if not values.size:
                continue
            style = plot_style(label)
            axis.hist(
                values,
                bins=panel_bins,
                range=plot_range,
                label=label,
                **style,
                **hist_kwargs(density),
            )

        axis.set_title(panel_title)
        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.25)
        if log_y:
            axis.set_yscale("log")
        axis.legend(frameon=False, fontsize=8)

    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def simhit_panels(sim, ref):
    return [
        (
            "N hits / cells per event",
            "Count per event",
            None,
            [
                ("CMSSW raw simhits", sim["n_hits"]),
                ("CMSSW aggregated cells", sim["n_cells"]),
                ("HGCaloChallenge cells", ref["n_cells"]),
            ],
            False,
            False,
        ),
        (
            "Total energy per event",
            "Energy",
            None,
            [
                ("CMSSW raw simhits", sim["total_energy"]),
                ("CMSSW aggregated cells", sim["cell_total_energy"]),
                ("HGCaloChallenge cells", ref["total_energy"]),
            ],
            False,
            False,
        ),
        (
            "log10(E) per hit/cell",
            "log10(E)",
            None,
            [
                ("CMSSW raw simhits", np.log10(finite_positive(sim["hit_energy"]))),
                ("CMSSW aggregated cells", np.log10(finite_positive(sim["cell_energy"]))),
                ("HGCaloChallenge cells", np.log10(finite_positive(ref["cell_energy"]))),
            ],
            True,
            False,
        ),
        (
            "Hits per occupied cell",
            "Multiplicity",
            None,
            [
                ("CMSSW raw simhits", sim["hit_multiplicity"]),
                ("CMSSW aggregated cells", np.ones(sim["cell_energy"].size, dtype=np.float64)),
                ("HGCaloChallenge cells", ref["hit_multiplicity"]),
            ],
            True,
            True,
        ),
    ]


def step_panels(steps, ref):
    return [
        (
            "N hits / cells per event",
            "Count per event",
            None,
            [
                ("G4 steps", steps["n_hits"]),
                ("G4 steps aggregated cells", steps["n_cells"]),
                ("HGCaloChallenge cells", ref["n_cells"]),
            ],
            False,
            False,
        ),
        (
            "Total energy per event",
            "Energy",
            None,
            [
                ("G4 steps", steps["total_energy"]),
                ("G4 steps aggregated cells", steps["cell_total_energy"]),
                ("HGCaloChallenge cells", ref["total_energy"]),
            ],
            False,
            False,
        ),
        (
            "log10(E) per hit/cell",
            "log10(E)",
            None,
            [
                ("G4 steps", np.log10(finite_positive(steps["hit_energy"]))),
                ("G4 steps aggregated cells", np.log10(finite_positive(steps["cell_energy"]))),
                ("HGCaloChallenge cells", np.log10(finite_positive(ref["cell_energy"]))),
            ],
            True,
            False,
        ),
        (
            "Hits per occupied cell",
            "Multiplicity",
            None,
            [
                ("G4 steps", steps["hit_multiplicity"]),
                ("G4 steps aggregated cells", np.ones(steps["cell_energy"].size, dtype=np.float64)),
                ("HGCaloChallenge cells", ref["hit_multiplicity"]),
            ],
            True,
            True,
        ),
    ]


def overlay_panels(sim, ref, steps):
    sim_panels = simhit_panels(sim, ref)
    step_panels_ = step_panels(steps, ref)
    panels = []
    for sim_panel, step_panel in zip(sim_panels, step_panels_):
        title, xlabel, _, sim_series, log_y, integer_bins = sim_panel
        _, _, _, step_series, _, _ = step_panel
        hgc_series = [item for item in sim_series if item[0] == "HGCaloChallenge cells"]
        sim_only = [item for item in sim_series if item[0] != "HGCaloChallenge cells"]
        step_only = [item for item in step_series if item[0] != "HGCaloChallenge cells"]
        panels.append((title, xlabel, None, sim_only + hgc_series + step_only, log_y, integer_bins))
    return panels


def with_y_labels(panels, density):
    labelled = []
    for title, xlabel, _, series, log_y, integer_bins in panels:
        ylabel = y_label("Cells" if integer_bins else "Events" if "per event" in title else "Hits / cells", density)
        labelled.append((title, xlabel, ylabel, series, log_y, integer_bins))
    return labelled


def main():
    parser = argparse.ArgumentParser(description="Compare CMSSW simhits, step point cloud, and HGCaloChallenge cells.")
    parser.add_argument("--sim", default=DEFAULT_SIM, help="CMSSW GEN-SIM ROOT file")
    parser.add_argument("--reference", default=DEFAULT_REF, help="HGCaloChallenge HDF5 file")
    parser.add_argument("--steps", default=DEFAULT_STEPS, help="HGCStepPointCloud ROOT file")
    parser.add_argument("--h5-dataset", default="showers", help="HDF5 shower dataset name")
    parser.add_argument("--max-events", type=int, default=None, help="optional maximum events to read")
    parser.add_argument("--bins", type=int, default=80, help="histogram bin count")
    parser.add_argument("--outdir", default="plots_stepcloud", help="output directory")
    parser.add_argument("--prefix", default="hgcal_stepcloud", help="output filename prefix")
    parser.add_argument("--counts", action="store_true", help="plot raw counts instead of normalized densities")
    parser.add_argument(
        "--step-energy",
        choices=("pcalohit", "raw"),
        default="pcalohit",
        help="step energy branch to plot; pcalohit uses edep_pcalohit_GeV when present",
    )
    parser.add_argument(
        "--label",
        action="append",
        type=parse_label,
        default=list(DEFAULT_LABELS),
        help="ROOT PCaloHit label as module:instance:process; can be passed multiple times",
    )
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    sim_max = args.max_events
    ref_max = args.max_events
    step_max = args.max_events
    if Path(args.reference).suffix == ".h5":
        ref_events = int(h5py.File(args.reference, "r")[args.h5_dataset].shape[0])
        sim_max = ref_events if args.max_events is None else min(args.max_events, ref_events)
        step_max = sim_max

    sim = read_root_simhits(Path(args.sim), args.label, sim_max)
    ref = read_hgcalchallenge(Path(args.reference), args.h5_dataset, ref_max)
    steps = read_stepcloud(Path(args.steps), step_max, args.step_energy)

    common_events = min(sim["n_hits"].size, ref["n_cells"].size, steps["n_hits"].size)
    if sim["n_hits"].size != common_events:
        sim = read_root_simhits(Path(args.sim), args.label, common_events)
    if ref["n_cells"].size != common_events:
        ref = read_hgcalchallenge(Path(args.reference), args.h5_dataset, common_events)
    if steps["n_hits"].size != common_events:
        steps = read_stepcloud(Path(args.steps), common_events, args.step_energy)

    print(f"cropped comparison to {common_events} events")
    print_summary("CMSSW simhits", sim)
    print_summary("HGCaloChallenge", ref)
    print_summary(f"step cloud ({args.step_energy} energy)", steps)

    density = not args.counts
    sim_output = outdir / f"{args.prefix}_simhits.png"
    steps_output = outdir / f"{args.prefix}_steps.png"
    overlay_output = outdir / f"{args.prefix}_overlay.png"
    draw_panels(
        "CMSSW simhits vs HGCaloChallenge",
        with_y_labels(simhit_panels(sim, ref), density),
        sim_output,
        args.bins,
        density,
    )
    draw_panels(
        "HGCAL G4 steps vs HGCaloChallenge",
        with_y_labels(step_panels(steps, ref), density),
        steps_output,
        args.bins,
        density,
    )
    draw_panels(
        "CMSSW simhits vs HGCAL G4 steps vs HGCaloChallenge",
        with_y_labels(overlay_panels(sim, ref, steps), density),
        overlay_output,
        args.bins,
        density,
    )
    print("Wrote:")
    print(f"  {sim_output}")
    print(f"  {steps_output}")
    print(f"  {overlay_output}")


if __name__ == "__main__":
    main()
