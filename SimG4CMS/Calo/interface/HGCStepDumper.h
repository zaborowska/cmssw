#ifndef SimG4CMS_HGCStepDumper_h
#define SimG4CMS_HGCStepDumper_h

#include <cstdint>
#include <string>
#include <vector>

class G4Step;
class TFileService;
class TTree;

class HGCStepDumper {
public:
  explicit HGCStepDumper(std::string treeName);

  void book(TFileService& fs);
  void beginEvent(unsigned int event);
  void addStep(const G4Step* step, uint32_t cellId, double weightedEnergy);
  void fill();

private:
  void clear();

  std::string treeName_;
  TTree* tree_{nullptr};
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
};

#endif
