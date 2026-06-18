#ifndef SimG4CMS_HGCStepDumper_h
#define SimG4CMS_HGCStepDumper_h

#include <cstdint>
#include <string>
#include <vector>

class G4Step;
class CaloG4Hit;
class CaloSD;
class TFileService;
class TTree;

class HGCStepDumper {
public:
  explicit HGCStepDumper(std::string treeName);

  void book(TFileService& fs);
  void beginEvent(unsigned int event);
  void addStep(const G4Step* step, uint32_t cellId, double weightedEnergy);
  void addSimHit(const CaloG4Hit* hit, int trackId, double time);
  void fill();
  void fillSimHits();

private:
  void clear();

  std::string treeName_;
  TTree* tree_{nullptr};
  TTree* simHitTree_{nullptr};
  unsigned int event_{0};
  std::vector<unsigned int> cell_id_;
  std::vector<float> x_mm_;
  std::vector<float> y_mm_;
  std::vector<float> z_mm_;
  std::vector<float> x_mid_mm_;
  std::vector<float> y_mid_mm_;
  std::vector<float> z_mid_mm_;
  std::vector<float> edep_GeV_;
  std::vector<float> edep_pcalohit_GeV_;
  std::vector<float> time_ns_;
  std::vector<int> track_id_;
  std::vector<int> pdg_id_;

  std::vector<unsigned int> simhit_cell_id_;
  std::vector<float> simhit_x_mm_;
  std::vector<float> simhit_y_mm_;
  std::vector<float> simhit_z_mm_;
  std::vector<float> simhit_energy_GeV_;
  std::vector<float> simhit_time_ns_;
  std::vector<int> simhit_track_id_;
  std::vector<unsigned int> simhit_depth_;
};

void registerHGCStepDumperForCaloSD(const CaloSD* sd, HGCStepDumper* dumper);
void addHGCStepDumperSimHitForCaloSD(const CaloSD* sd, const CaloG4Hit* hit, int trackId, double time, int collection);
void fillHGCStepDumperSimHitsForCaloSD(const CaloSD* sd);

#endif
