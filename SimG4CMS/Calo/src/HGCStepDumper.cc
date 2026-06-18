#include "SimG4CMS/Calo/interface/HGCStepDumper.h"

#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "SimG4CMS/Calo/interface/CaloG4Hit.h"
#include "G4ParticleDefinition.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4Track.hh"
#include "FWCore/Utilities/interface/Exception.h"
#include "TDirectory.h"
#include "TFile.h"
#include "TTree.h"

#include "CLHEP/Units/SystemOfUnits.h"

#include <unordered_map>
#include <utility>

namespace {
constexpr const char* kTreeTitle = "HGCStepPointCloud";
constexpr const char* kSimHitTreePrefix = "HGCSimHitPointCloud";

std::unordered_map<const CaloSD*, HGCStepDumper*>& simHitDumperRegistry() {
  static std::unordered_map<const CaloSD*, HGCStepDumper*> registry;
  return registry;
}
}  // namespace

void registerHGCStepDumperForCaloSD(const CaloSD* sd, HGCStepDumper* dumper) {
  if (sd && dumper) {
    simHitDumperRegistry()[sd] = dumper;
  }
}

void addHGCStepDumperSimHitForCaloSD(
    const CaloSD* sd, const CaloG4Hit* hit, int trackId, double time, int) {
  const auto found = simHitDumperRegistry().find(sd);
  if (found != simHitDumperRegistry().end()) {
    found->second->addSimHit(hit, trackId, time);
  }
}

void fillHGCStepDumperSimHitsForCaloSD(const CaloSD* sd) {
  const auto found = simHitDumperRegistry().find(sd);
  if (found != simHitDumperRegistry().end()) {
    found->second->fillSimHits();
  }
}

HGCStepDumper::HGCStepDumper(std::string treeName) : treeName_(std::move(treeName)) {}

void HGCStepDumper::book(TFileService& fs) {
  if (tree_) {
    return;
  }

  TFile& file = fs.file();
  TDirectory::TContext context(&file);
  tree_ = new TTree(treeName_.c_str(), kTreeTitle);
  tree_->SetDirectory(&file);
  tree_->Branch("event", &event_);
  tree_->Branch("cell_id", &cell_id_);
  tree_->Branch("x_mm", &x_mm_);
  tree_->Branch("y_mm", &y_mm_);
  tree_->Branch("z_mm", &z_mm_);
  tree_->Branch("x_mid_mm", &x_mid_mm_);
  tree_->Branch("y_mid_mm", &y_mid_mm_);
  tree_->Branch("z_mid_mm", &z_mid_mm_);
  tree_->Branch("edep_GeV", &edep_GeV_);
  tree_->Branch("edep_pcalohit_GeV", &edep_pcalohit_GeV_);
  tree_->Branch("time_ns", &time_ns_);
  tree_->Branch("track_id", &track_id_);
  tree_->Branch("pdg_id", &pdg_id_);

  std::string simHitTreeName = treeName_;
  const std::string stepPrefix = "HGCStepPointCloud";
  if (simHitTreeName.compare(0, stepPrefix.size(), stepPrefix) == 0) {
    simHitTreeName.replace(0, stepPrefix.size(), kSimHitTreePrefix);
  } else {
    simHitTreeName += "_SimHits";
  }
  simHitTree_ = new TTree(simHitTreeName.c_str(), "HGCSimHitPointCloud");
  simHitTree_->SetDirectory(&file);
  simHitTree_->Branch("event", &event_);
  simHitTree_->Branch("cell_id", &simhit_cell_id_);
  simHitTree_->Branch("x_mm", &simhit_x_mm_);
  simHitTree_->Branch("y_mm", &simhit_y_mm_);
  simHitTree_->Branch("z_mm", &simhit_z_mm_);
  simHitTree_->Branch("energy_GeV", &simhit_energy_GeV_);
  simHitTree_->Branch("time_ns", &simhit_time_ns_);
  simHitTree_->Branch("track_id", &simhit_track_id_);
  simHitTree_->Branch("depth", &simhit_depth_);
}

void HGCStepDumper::beginEvent(unsigned int event) {
  event_ = event;
  clear();
}

void HGCStepDumper::addStep(const G4Step* step, uint32_t cellId, double weightedEnergy) {
  if (!step || cellId == 0) {
    return;
  }

  const auto* pre = step->GetPreStepPoint();
  const auto* post = step->GetPostStepPoint();
  if (!pre || !post) {
    return;
  }

  const auto prePos = pre->GetPosition() / CLHEP::mm;
  const auto postPos = post->GetPosition() / CLHEP::mm;
  const auto midPos = 0.5 * (prePos + postPos);
  const float edep = static_cast<float>(step->GetTotalEnergyDeposit() / CLHEP::GeV);
  const float weightedEdep = static_cast<float>(weightedEnergy / CLHEP::GeV);
  if (!(edep > 0.0f) || !(weightedEdep > 0.0f)) {
    return;
  }

  const auto* track = step->GetTrack();
  const auto* particle = track ? track->GetDefinition() : nullptr;

  cell_id_.push_back(cellId);
  x_mm_.push_back(static_cast<float>(prePos.x()));
  y_mm_.push_back(static_cast<float>(prePos.y()));
  z_mm_.push_back(static_cast<float>(prePos.z()));
  x_mid_mm_.push_back(static_cast<float>(midPos.x()));
  y_mid_mm_.push_back(static_cast<float>(midPos.y()));
  z_mid_mm_.push_back(static_cast<float>(midPos.z()));
  edep_GeV_.push_back(edep);
  edep_pcalohit_GeV_.push_back(weightedEdep);
  time_ns_.push_back(static_cast<float>(pre->GetGlobalTime() / CLHEP::ns));
  track_id_.push_back(track ? track->GetTrackID() : 0);
  pdg_id_.push_back(particle ? particle->GetPDGEncoding() : 0);
}

void HGCStepDumper::addSimHit(const CaloG4Hit* hit, int trackId, double time) {
  if (!hit || hit->getUnitID() == 0 || !(hit->getEnergyDeposit() > 0.0)) {
    return;
  }

  const auto pos = hit->getPosition();
  simhit_cell_id_.push_back(hit->getUnitID());
  simhit_x_mm_.push_back(static_cast<float>(pos.x() / CLHEP::mm));
  simhit_y_mm_.push_back(static_cast<float>(pos.y() / CLHEP::mm));
  simhit_z_mm_.push_back(static_cast<float>(pos.z() / CLHEP::mm));
  simhit_energy_GeV_.push_back(static_cast<float>(hit->getEnergyDeposit() / CLHEP::GeV));
  simhit_time_ns_.push_back(static_cast<float>(time));
  simhit_track_id_.push_back(trackId);
  simhit_depth_.push_back(hit->getDepth());
}

void HGCStepDumper::fill() {
  if (tree_) {
    tree_->Fill();
  }
}

void HGCStepDumper::fillSimHits() {
  if (simHitTree_) {
    simHitTree_->Fill();
  }
}

void HGCStepDumper::clear() {
  cell_id_.clear();
  x_mm_.clear();
  y_mm_.clear();
  z_mm_.clear();
  x_mid_mm_.clear();
  y_mid_mm_.clear();
  z_mid_mm_.clear();
  edep_GeV_.clear();
  edep_pcalohit_GeV_.clear();
  time_ns_.clear();
  track_id_.clear();
  pdg_id_.clear();
  simhit_cell_id_.clear();
  simhit_x_mm_.clear();
  simhit_y_mm_.clear();
  simhit_z_mm_.clear();
  simhit_energy_GeV_.clear();
  simhit_time_ns_.clear();
  simhit_track_id_.clear();
  simhit_depth_.clear();
}
