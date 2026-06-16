#include "SimG4CMS/Calo/interface/HGCStepDumper.h"

#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "G4ParticleDefinition.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4Track.hh"
#include "FWCore/Utilities/interface/Exception.h"
#include "TTree.h"

#include "CLHEP/Units/SystemOfUnits.h"

namespace {
constexpr const char* kTreeName = "HGCStepPointCloud";
constexpr const char* kTreeTitle = "HGCStepPointCloud";
}  // namespace

void HGCStepDumper::book(TFileService& fs) {
  if (tree_) {
    return;
  }

  tree_ = fs.make<TTree>(kTreeName, kTreeTitle);
  tree_->Branch("event", &event_);
  tree_->Branch("cell_id", &cell_id_);
  tree_->Branch("x_mm", &x_mm_);
  tree_->Branch("y_mm", &y_mm_);
  tree_->Branch("z_mm", &z_mm_);
  tree_->Branch("x_mid_mm", &x_mid_mm_);
  tree_->Branch("y_mid_mm", &y_mid_mm_);
  tree_->Branch("z_mid_mm", &z_mid_mm_);
  tree_->Branch("edep_GeV", &edep_GeV_);
  tree_->Branch("time_ns", &time_ns_);
  tree_->Branch("track_id", &track_id_);
  tree_->Branch("pdg_id", &pdg_id_);
}

void HGCStepDumper::beginEvent(unsigned int event) {
  event_ = event;
  clear();
}

void HGCStepDumper::addStep(const G4Step* step, uint32_t cellId) {
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
  if (!(edep > 0.0f)) {
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
  time_ns_.push_back(static_cast<float>(pre->GetGlobalTime() / CLHEP::ns));
  track_id_.push_back(track ? track->GetTrackID() : 0);
  pdg_id_.push_back(particle ? particle->GetPDGEncoding() : 0);
}

void HGCStepDumper::fill() {
  if (tree_) {
    tree_->Fill();
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
  time_ns_.clear();
  track_id_.clear();
  pdg_id_.clear();
}
