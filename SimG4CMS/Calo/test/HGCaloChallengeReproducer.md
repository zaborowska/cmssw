# HGCaloChallenge Reproducer Notes

This note records the local photon test used to compare CMSSW HGCAL `PCaloHit`
output with the HGCaloChallenge cell-energy reference.

The old standalone fragment lived in:

```text
../../tmp/HGCaloChallengePointCloud/Generation/python/hgcal_challenge_photon_50gev_eta2_phi90_cfi.py
```

That fragment is only needed if regenerating the old `cmsDriver.py` config from
the standalone package. For the Calo package workflow, the useful piece is the
existing GEN-SIM ROOT file plus the comparison script in this directory.

## Environment

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh
export SCRAM_ARCH=el9_amd64_gcc12
export SITECONFIG_PATH=/cvmfs/cms.cern.ch/SITECONF/T2_CH_CERN

cd /home/azaborow/CMSSW/CMSSW_14_0_14/src
cmsenv
```

## Old GEN-SIM Command

The 50 GeV photon test used:

```bash
cmsDriver.py HGCaloChallengePointCloud/Generation/hgcal_challenge_photon_50gev_eta2_phi90_cfi \
  -s GEN,SIM \
  -n 1000 \
  --conditions auto:phase2_realistic_T33 \
  --beamspot HGCALCloseBy \
  --datatier GEN-SIM \
  --eventcontent FEVTDEBUG \
  --geometry Extended2026D110 \
  --era Phase2C17I13M9 \
  --fileout file:hgcal_photon_50gev_eta2_phi90_GEN-SIM.root \
  --python_filename hgcal_photon_50gev_eta2_phi90_GEN_SIM_cfg.py \
  --no_exec
```

Run with:

```bash
cmsRun hgcal_photon_50gev_eta2_phi90_GEN_SIM_cfg.py
```

## HGCaloChallenge Comparison

Use the Calo-package plotting script:

```bash
python3 SimG4CMS/Calo/test/plot_hgcalchallenge_summaries.py \
  --sim ../../tmp/hgcal_photon_50gev_eta2_phi90_GEN-SIM.root \
  --reference /eos/geant4/fastSim/CMS_HGCal/gamma_hex/discrete_50GeV_HGCal_showers50.h5 \
  --outdir plots_hgcalchallenge \
  --prefix photon_50gev
```

The overlay compares:

- raw CMSSW HGCAL `PCaloHit.energy()`
- CMSSW simhits aggregated per event by `detid`
- HGCaloChallenge nonzero HDF5 cell energies

The aggregation is:

```text
cell_energy[detid] += hit.energy()
```

The default simhit collections are:

```text
g4SimHits:HGCHitsEE:SIM
g4SimHits:HGCHitsHEfront:SIM
g4SimHits:HGCHitsHEback:SIM
```
