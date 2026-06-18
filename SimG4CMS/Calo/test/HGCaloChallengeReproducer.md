# HGCaloChallenge reproducer for point-cloud data

This reproducer is based on the `CMSSW_14_0_14` setup that was used initially to produce showers for
HGCaloChallenge. This code adds a special file producer for step information from HGCalSD, so that
detailed positions can be stored. Comparison of step-level information to HGCal simhits for 50 GeV
photons shows identical output in terms of energy stored and cell multiplicity. There is a small
difference with respect to the HGCaloChallenge dataset which likely comes from additional digitisation/calibration.
If needed, this could be added but for now we continue with direct sim output.

## Environment setup

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh
export SCRAM_ARCH=el9_amd64_gcc12
export SITECONFIG_PATH=/cvmfs/cms.cern.ch/SITECONF/T2_CH_CERN
cmsrel CMSSW_14_0_14
cd CMSSW_14_0_14/src
cmsenv
```

## Build

Only `SimG4CMS/Calo` has been modified. Use the full build so that
`biglib/el9_amd64_gcc12/pluginSimulation.so` is relinked:

```bash
scram b -j 8
```

Optional check if the correct library is taken:

```bash
edmPluginDump --files | grep -A1 -E 'HGCalSensitiveDetector|HGCSensitiveDetector'
```

The selected plugin should be under this CMSSW area:

```text
../biglib/el9_amd64_gcc12/pluginSimulation.so
```

## Validation test: 1000 50 GeV photons

The current generated config is expected in:

```text
SimG4CMS/Calo/test/python/hgcal_photon_50gev_eta2_phi90_GEN_SIM_cfg.py
```

To enable the Geant4 step dump, add:

```python
process.TFileService = cms.Service(
    "TFileService",
    fileName = cms.string("hgcal_g4steps.root"),
)
process.g4SimHits.HGCSD.DumpHGCStepPointCloud = cms.untracked.bool(True)
```

It can be run from `SimG4CMS/Calo/test/python/`:

```bash
cmsRun hgcal_photon_50gev_eta2_phi90_GEN_SIM_cfg.py
```

Expected outputs:

```text
hgcal_photon_50gev_eta2_phi90_GEN-SIM.root
hgcal_g4steps.root
```

## Output file content

The point-cloud dump writes one `TTree` entry per event, with vector branches.
Current tree names are:

```text
HGCStepPointCloud_HGCEE
HGCStepPointCloud_HGCHEF
HGCSimHitPointCloud_HGCEE
HGCSimHitPointCloud_HGCHEF
```

Step branches:

```text
event
cell_id
x_mm, y_mm, z_mm
x_mid_mm, y_mid_mm, z_mid_mm
edep_GeV
edep_pcalohit_GeV
time_ns
track_id
pdg_id
```

`edep_GeV` is raw Geant4 deposited energy. `edep_pcalohit_GeV` is the weighted
step energy from the normal HGCAL sensitive-detector path, and should sum to the
same event energy as the corresponding simhits after aggregation.

Simhit-position branches:

```text
event
cell_id
x_mm, y_mm, z_mm
energy_GeV
time_ns
track_id
depth
```

These are the final cleaned `CaloG4Hit`s immediately before conversion to
`PCaloHit`, so `energy_GeV` should match normal simhit energy. The position is
the stored `CaloG4Hit` position, not an energy-weighted centroid of all steps in
the merged hit.

Note: both step energy branches give the same result in the current 50 GeV photon test. Keep both branches in case this changes for other samples.

## Visualisation

From `CMSSW_14_0_14/src`:

```bash
python3 SimG4CMS/Calo/test/plot_hgcstep_pointcloud.py \
  --sim SimG4CMS/Calo/test/python/hgcal_photon_50gev_eta2_phi90_GEN-SIM.root \
  --steps SimG4CMS/Calo/test/python/hgcal_g4steps.root \
  --reference /eos/geant4/fastSim/CMS_HGCal/gamma_hex/discrete_50GeV_HGCal_showers50.h5 \
  --max-events 1000 \
  --outdir plots_stepcloud \
  --prefix photon_50gev_steps
```

This writes separate simhit and step canvases plus a common overlay. When the
step file contains `HGCSimHitPointCloud_*`, those final simhits-with-position
distributions are drawn in green.

Use raw Geant4 step energy instead of weighted step energy with:

```bash
python3 SimG4CMS/Calo/test/plot_hgcstep_pointcloud.py \
  --sim SimG4CMS/Calo/test/python/hgcal_photon_50gev_eta2_phi90_GEN-SIM.root \
  --steps SimG4CMS/Calo/test/python/hgcal_g4steps.root \
  --reference /eos/geant4/fastSim/CMS_HGCal/gamma_hex/discrete_50GeV_HGCal_showers50.h5 \
  --max-events 1000 \
  --step-energy raw
```
