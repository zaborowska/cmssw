#!/usr/bin/env python3
import argparse
from pathlib import Path

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_SIM = "hgcal_photon_50gev_eta2_phi90_GEN-SIM.root"
DEFAULT_REF = "/eos/geant4/fastSim/CMS_HGCal/gamma_hex/discrete_50GeV_HGCal_showers50.h5"
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


def read_simhits(path, labels, max_events=None):
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
        event_cell_energy = {}
        event_cell_counts = {}
        for label in labels:
            event.getByLabel(*label, handle)
            hits = handle.product()
            event_n_hits += len(hits)
            for hit in hits:
                energy = float(hit.energy())
                detid = int(hit.id())
                event_total_energy += energy
                hit_energy.append(energy)
                event_cell_energy[detid] = event_cell_energy.get(detid, 0.0) + energy
                event_cell_counts[detid] = event_cell_counts.get(detid, 0) + 1

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


def h5_event_count(path, dataset):
    with h5py.File(path, "r") as infile:
        return int(infile[dataset].shape[0])


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


def print_summary(name, summary):
    def describe(values):
        values = finite(values)
        if not values.size:
            return "n=0"
        return f"n={values.size}, mean={values.mean():.6g}, rms={values.std():.6g}, min={values.min():.6g}, max={values.max():.6g}"

    print(f"{name}:")
    if "n_hits" in summary:
        print(f"  N simhits/event: {describe(summary['n_hits'])}")
    print(f"  N cells/event: {describe(summary['n_cells'])}")
    if "total_energy" in summary:
        print(f"  total energy/event: {describe(summary['total_energy'])}")
    if "cell_total_energy" in summary:
        print(f"  aggregated cell total energy/event: {describe(summary['cell_total_energy'])}")
    if "hit_energy" in summary:
        print(f"  simhit energy: {describe(summary['hit_energy'])}")
    print(f"  cell energy: {describe(summary['cell_energy'])}")
    print(f"  simhits per cell: {describe(summary['hit_multiplicity'])}")


def plot_overlay(sim, ref, output, bins, density):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    fig.suptitle("CMSSW simhits vs aggregated simhits vs HGCaloChallenge")
    axes = axes.ravel()

    panels = [
        (
            "N cells / hits per event",
            "Count per event",
            y_label("Events", density),
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
            y_label("Events", density),
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
            y_label("Hits / cells", density),
            [
                ("CMSSW raw simhits", np.log10(finite_positive(sim["hit_energy"]))),
                ("CMSSW aggregated cells", np.log10(finite_positive(sim["cell_energy"]))),
                ("HGCaloChallenge cells", np.log10(finite_positive(ref["cell_energy"]))),
            ],
            True,
            False,
        ),
        (
            "Simhits per occupied cell",
            "Multiplicity",
            y_label("Cells", density),
            [
                ("CMSSW raw simhits", sim["hit_multiplicity"]),
                ("CMSSW aggregated cells", np.ones(sim["cell_energy"].size, dtype=np.float64)),
                ("HGCaloChallenge cells", ref["hit_multiplicity"]),
            ],
            True,
            True,
        ),
    ]

    for axis, (title, xlabel, ylabel, series, log_y, integer_bins) in zip(axes, panels):
        values_for_range = [values for _, values in series]
        if integer_bins:
            max_value = max((float(np.max(finite(values))) for _, values in series if finite(values).size), default=1.0)
            panel_bins = np.arange(0.5, max_value + 1.5, 1.0)
            plot_range = None
        else:
            panel_bins = bins
            plot_range = hist_range(values_for_range)

        for label, values in series:
            values = finite(values)
            if not values.size:
                continue
            axis.hist(
                values,
                bins=panel_bins,
                range=plot_range,
                histtype="step",
                linewidth=1.6,
                label=label,
                **hist_kwargs(density),
            )

        axis.set_title(title)
        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.25)
        if log_y:
            axis.set_yscale("log")
        axis.legend()

    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Compare CMSSW HGCAL simhits with HGCaloChallenge cell showers.")
    parser.add_argument("--sim", default=DEFAULT_SIM, help="CMSSW GEN-SIM ROOT file")
    parser.add_argument("--reference", default=DEFAULT_REF, help="HGCaloChallenge HDF5 file")
    parser.add_argument("--h5-dataset", default="showers", help="HDF5 shower dataset name")
    parser.add_argument("--max-events", type=int, default=None, help="optional maximum events to read")
    parser.add_argument("--bins", type=int, default=80, help="histogram bin count")
    parser.add_argument("--outdir", default="plots_hgcalchallenge", help="output directory")
    parser.add_argument("--prefix", default="hgcalchallenge_simhits", help="output filename prefix")
    parser.add_argument("--counts", action="store_true", help="plot raw counts instead of normalized densities")
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

    ref_events = h5_event_count(Path(args.reference), args.h5_dataset)
    limit = ref_events if args.max_events is None else min(args.max_events, ref_events)
    sim = read_simhits(Path(args.sim), args.label, limit)
    ref = read_hgcalchallenge(Path(args.reference), args.h5_dataset, sim["n_hits"].size)
    common_events = min(sim["n_hits"].size, ref["n_cells"].size)
    if sim["n_hits"].size != common_events:
        sim = read_simhits(Path(args.sim), args.label, common_events)
    if ref["n_cells"].size != common_events:
        ref = read_hgcalchallenge(Path(args.reference), args.h5_dataset, common_events)
    print(f"cropped comparison to {common_events} events")

    print_summary("CMSSW simhits", sim)
    print_summary("HGCaloChallenge", ref)

    output = outdir / f"{args.prefix}_overlay.png"
    plot_overlay(sim, ref, output, args.bins, not args.counts)
    print("Wrote:")
    print(f"  {output}")


if __name__ == "__main__":
    main()
