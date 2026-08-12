"""Track-seed performance study on EDM4hep reconstruction output (RDataFrame).

RDataFrame-based reimplementation of the seeds half of the ROOT-macro chain in
https://github.com/samf25/TrackingPlots (commit 940ef76):
  * WriteSeedsMT.C -- seed direction, truth matching through the hit relations,
                      per-hit layer occupancy and per-event seed counts;
  * PlotSeeds.C    -- the seed multiplicity, layer occupancy and resolution plots.
Both steps are fused here: a JITted C++ helper, `studySeeds`, runs once per event
and returns per-seed / per-hit RVecs, which RDataFrame then histograms.

Truth matching (identical to the macro): for every hit on a seed, follow the
reco-hit -> sim-hit relation (`_<hitColl>Relations_{from,to}`) and then the
sim-hit -> MCParticle link (`_<simColl>_particle`). A seed is matched when at
least 3 of its hits resolve to an MCParticle and at least 2 of them agree on the
same one. Resolving a hit needs its podio collectionID, which is read from the
`podio_metadata` tree before the event loop.

Layer occupancy uses the same cellID encoding as the macro,
"system:5,side:-2,layer:6,module:11,sensor:8", decoded with DDSegmentation's
BitFieldCoder. Barrel/endcap follows the collection order: even slots are barrel.

Collection order is fixed and must pair up (--hitColls with --simColls):
  ITBarrelHits, ITEndcapHits, VXDBarrelHits, VXDEndcapHits, OTBarrelHits,
  OTEndcapHits  <->  InnerTrackerBarrelCollection, InnerTrackerEndcapCollection,
  VertexBarrelCollection, VertexEndcapCollection, OuterTrackerBarrelCollection,
  OuterTrackerEndcapCollection

Key quantities:
  seed theta : atan2(1, tanLambda) of the seed's first track state
  seed pt    : |0.3*B/omega/1000|
  resolutions: q/pt = (q/reco_pt - q/true_pt)/(q/true_pt), d0 = reco-true,
               z0 = reco-true.
  NOTE: as in study_tracks.py, true_d0/true_z0 are the *signed perigee* impact
  parameters of the MC helix, not the raw production vertex the macro used, so
  the d0/z0 resolutions peak at zero. The seed d0/z0 resolution plots are
  therefore NOT directly comparable with the macro's seeds_res_{d0,z0}.

Outputs (-o ROOT file): the seed theta / multiplicity / per-MCP histograms, the
barrel and endcap layer occupancies (all and unmatched) and the resolutions.
Plots under --outDir: seeds_theta, seeds_nSeeds, seeds_perMCP, seeds_barrel,
seeds_endcap, seeds_res_{qpt,d0,z0}.

Usage:
    python study_seeds.py -i reco.edm4hep.root -o histos_seeds.root -d plots
"""
from optparse import OptionParser
import os
import math
import ROOT

#########################
parser = OptionParser()
parser.add_option('-i', '--inFile', help='reco.edm4hep.root (file or directory)',
                  type=str, default='reco.edm4hep.root')
parser.add_option('-o', '--outFile', help='output ROOT file', type=str,
                  default='histos_seeds.root')
parser.add_option('-d', '--outDir', help='directory for the plots', type=str, default='.')
parser.add_option('--seedColl', help='seed track collection', type=str, default='SeedTracks')
parser.add_option('--mcColl', help='MC particle collection', type=str, default='MCParticles')
parser.add_option('--hitColls', help='comma-separated reco tracker-hit collections',
                  type=str,
                  default='ITBarrelHits,ITEndcapHits,VXDBarrelHits,VXDEndcapHits,'
                          'OTBarrelHits,OTEndcapHits')
parser.add_option('--simColls', help='comma-separated sim tracker-hit collections, '
                  'paired with --hitColls',
                  type=str,
                  default='InnerTrackerBarrelCollection,InnerTrackerEndcapCollection,'
                          'VertexBarrelCollection,VertexEndcapCollection,'
                          'OuterTrackerBarrelCollection,OuterTrackerEndcapCollection')
parser.add_option('--cellIDEncoding', help='cellID bit field used to decode the layer',
                  type=str, default='system:5,side:-2,layer:6,module:11,sensor:8')
parser.add_option('--Bfield', help='solenoid field [T] for pt = |0.3*B/omega/1000|',
                  type=float, default=5.0)
parser.add_option('--nLayers', help='upper edge of the layer axis', type=int, default=12)
parser.add_option('--maxSeeds', help='upper edge of the seeds-per-event axis '
                  '(0 = take it from the data)', type=int, default=0)
parser.add_option('--label', help='provenance label stamped on every plot',
                  type=str, default='Gen3 material handling validation')
parser.add_option('--suffix', help='plot file format (png, pdf, ...)', type=str, default='png')

FMAX = 3.4028235e+38
parser.add_option('--evtPtMin', type=float, default=0.0)
parser.add_option('--evtPtMax', type=float, default=FMAX)
parser.add_option('--evtThetaMin', type=float, default=0.0)
parser.add_option('--evtThetaMax', type=float, default=math.pi)
parser.add_option('--evtAbsEtaMin', type=float, default=0.0)
parser.add_option('--evtAbsEtaMax', type=float, default=FMAX)
(options, args) = parser.parse_args()

ROOT.gROOT.SetBatch(True)
ROOT.EnableImplicitMT()
ROOT.gStyle.SetOptStat(0)
PI = ROOT.TMath.Pi()

COL_ALL, COL_SUB = ROOT.kAzure + 1, ROOT.kRed + 1


def plot_name(stem):
    return "%s.%s" % (stem, options.suffix)


_ci_labels = []
def draw_ci_label():
    t = ROOT.TLatex()
    t.SetNDC(); t.SetTextFont(42); t.SetTextSize(0.035); t.SetTextAlign(12)
    t.DrawLatex(0.12, 0.945, options.label)
    _ci_labels.append(t)


hit_colls = [c.strip() for c in options.hitColls.split(',') if c.strip()]
sim_colls = [c.strip() for c in options.simColls.split(',') if c.strip()]
if len(hit_colls) != len(sim_colls) or not hit_colls:
    raise RuntimeError("--hitColls and --simColls must have the same non-zero length "
                       "(%d vs %d)" % (len(hit_colls), len(sim_colls)))

# --- JITted per-event analysis ----------------------------------------------
ROOT.gInterpreter.Declare(r'''
#include "ROOT/RVec.hxx"
#include "DDSegmentation/BitFieldCoder.h"
#include "edm4hep/MCParticleData.h"
#include "edm4hep/TrackData.h"
#include "edm4hep/TrackState.h"
#include "edm4hep/TrackerHitPlaneData.h"
#include "podio/ObjectID.h"
#include <cmath>
#include <string>
#include <unordered_map>
#include <vector>

using ROOT::VecOps::RVec;

static const int BITCreatedInSimulationS = 30;
static const int BITDecayedInTrackerS    = 27;
static inline bool checkBitS(int v, int b) { return (v >> b) & 1; }

struct EvtSelS { float ptMin, ptMax, thetaMin, thetaMax, absEtaMin, absEtaMax; };

static inline float thetaToEtaS(float theta) {
  const float eps = 1e-6f;
  float t = std::max(eps, std::min((float)M_PI - eps, theta));
  return -std::log(std::tan(t * 0.5f));
}

static inline bool mcAcceptS(const edm4hep::MCParticleData& m) {
  if (m.generatorStatus != 1) return false;
  if (m.charge == 0) return false;
  if (checkBitS(m.simulatorStatus, BITCreatedInSimulationS)) return false;
  if (checkBitS(m.simulatorStatus, BITDecayedInTrackerS))    return false;
  return true;
}

// Signed perigee impact parameters of the MC helix (see study_tracks.py).
struct ImpactParamsS { double d0; double z0; };
static inline ImpactParamsS trueImpactParamsS(double x0, double y0, double z0v,
                                              double px, double py, double pz,
                                              double q, double B) {
  const double FCT = 2.99792458e-4;
  double pt = std::hypot(px, py);
  if (pt <= 0.0 || q == 0.0 || B == 0.0) return {0.0, z0v};
  double R    = pt / (FCT * std::abs(B));
  double sgn  = std::copysign(1.0, q * B);
  double phiM = std::atan2(py, px);
  double xC = x0 + R * std::cos(phiM - sgn * M_PI_2);
  double yC = y0 + R * std::sin(phiM - sgn * M_PI_2);
  double D  = std::hypot(xC, yC);
  if (D == 0.0) return {0.0, z0v};
  double xPCA = xC * (1.0 - R / D);
  double yPCA = yC * (1.0 - R / D);
  double phi0 = std::atan2(yC, xC) + sgn * M_PI_2;
  double d0   = yPCA * std::cos(phi0) - xPCA * std::sin(phi0);
  double aRef = std::atan2(y0 - yC, x0 - xC);
  double aPCA = std::atan2(yPCA - yC, xPCA - xC);
  double dphi = aPCA - aRef;
  while (dphi >  M_PI) dphi -= 2.0 * M_PI;
  while (dphi < -M_PI) dphi += 2.0 * M_PI;
  double z0 = z0v - sgn * R * (pz / pt) * dphi;
  return {d0, z0};
}

struct SeedResult {
  RVec<double> seed_theta;            // direction of every seed
  RVec<int>    seed_isMatched;
  RVec<double> layer;                 // one entry per hit on a seed
  RVec<int>    layer_isBarrel, layer_isMatched;
  RVec<double> res_qpt, res_d0, res_z0;   // matched seeds only
  int nSeeds = 0, nMatched = 0, nUnmatched = 0;
  double avgSeedsPerMCP = 0.0;
  bool evtPass = true;
};

SeedResult studySeeds(const RVec<edm4hep::MCParticleData>& mcs,
                      const RVec<edm4hep::TrackData>&      seeds,
                      const RVec<edm4hep::TrackState>&     seedStates,
                      const RVec<podio::ObjectID>&         seedHits,
                      const std::vector<const RVec<edm4hep::TrackerHitPlaneData>*>& hitColls,
                      const std::vector<const RVec<podio::ObjectID>*>& relFrom,
                      const std::vector<const RVec<podio::ObjectID>*>& relTo,
                      const std::vector<const RVec<podio::ObjectID>*>& simParts,
                      const std::vector<unsigned int>& collIDs,
                      double Bfield, const std::string& encoding,
                      const EvtSelS& evtSel)
{
  SeedResult r;
  const double kappa = 0.3 * Bfield / 1000.0;

  r.evtPass = false;
  for (const auto& m : mcs) {
    if (!mcAcceptS(m)) continue;
    double pt    = std::hypot(m.momentum.x, m.momentum.y);
    double theta = std::atan2(pt, (double)m.momentum.z);
    if (pt    < evtSel.ptMin    || pt    > evtSel.ptMax)    continue;
    if (theta < evtSel.thetaMin || theta > evtSel.thetaMax) continue;
    float absEta = std::abs(thetaToEtaS(theta));
    if (absEta < evtSel.absEtaMin || absEta > evtSel.absEtaMax) continue;
    r.evtPass = true;
    break;
  }
  if (!r.evtPass) return r;

  // cellID decoder: const after construction, so one shared instance is safe
  // under RDataFrame's implicit multi-threading.
  static const dd4hep::DDSegmentation::BitFieldCoder coder(encoding);

  // collectionID -> slot, and per-slot reco-hit index -> relation index.
  std::unordered_map<unsigned int, size_t> idToSlot;
  for (size_t s = 0; s < collIDs.size(); ++s) idToSlot[collIDs[s]] = s;

  std::vector<std::unordered_map<int, int>> hitToRel(hitColls.size());
  for (size_t s = 0; s < hitColls.size(); ++s) {
    if (s >= relFrom.size() || !relFrom[s]) continue;
    const auto& from = *relFrom[s];
    hitToRel[s].reserve(from.size());
    for (size_t i = 0; i < from.size(); ++i) hitToRel[s][from[i].index] = (int)i;
  }

  std::unordered_map<unsigned int, int> mcpMatchCount;
  r.nSeeds = (int)seeds.size();

  for (const auto& sd : seeds) {
    if (sd.trackStates_begin < 0 || sd.trackStates_begin >= (int)seedStates.size()) continue;
    const auto& st = seedStates[sd.trackStates_begin];
    double theta = std::atan2(1.0, (double)st.tanLambda);

    // Walk the seed's hits: reco hit -> sim hit -> MCParticle.
    std::vector<unsigned int> mcpIdx;
    for (int h = sd.trackerHits_begin; h < sd.trackerHits_end && h < (int)seedHits.size(); ++h) {
      const auto& hid = seedHits[h];
      auto slotIt = idToSlot.find(hid.collectionID);
      if (slotIt == idToSlot.end()) continue;
      const size_t s = slotIt->second;
      if (s >= relTo.size() || !relTo[s] || s >= simParts.size() || !simParts[s]) continue;
      auto relIt = hitToRel[s].find(hid.index);
      if (relIt == hitToRel[s].end()) continue;
      const int ri = relIt->second;
      if (ri < 0 || ri >= (int)relTo[s]->size()) continue;
      const int simIdx = (*relTo[s])[ri].index;
      if (simIdx < 0 || simIdx >= (int)simParts[s]->size()) continue;
      mcpIdx.push_back((unsigned int)(*simParts[s])[simIdx].index);
    }

    // Matched when >=3 hits resolve and >=2 of them agree on one MCParticle.
    bool isMatched = false;
    unsigned int matchedMCP = 0;
    if (mcpIdx.size() >= 3) {
      std::unordered_map<unsigned int, int> count;
      for (unsigned int i : mcpIdx) count[i]++;
      for (const auto& kv : count) {
        if (kv.second >= 2) { isMatched = true; matchedMCP = kv.first; break; }
      }
    }
    if (isMatched) mcpMatchCount[matchedMCP]++;

    r.seed_theta.push_back(theta);
    r.seed_isMatched.push_back(isMatched ? 1 : 0);

    // Per-hit layer occupancy.
    for (int h = sd.trackerHits_begin; h < sd.trackerHits_end && h < (int)seedHits.size(); ++h) {
      const auto& hid = seedHits[h];
      auto slotIt = idToSlot.find(hid.collectionID);
      if (slotIt == idToSlot.end()) continue;
      const size_t s = slotIt->second;
      if (s >= hitColls.size() || !hitColls[s]) continue;
      if (hid.index < 0 || hid.index >= (int)hitColls[s]->size()) continue;
      int lay = (int)coder.get((*hitColls[s])[hid.index].cellID, "layer");
      r.layer.push_back((double)lay);
      r.layer_isBarrel.push_back((s % 2 == 0) ? 1 : 0);
      r.layer_isMatched.push_back(isMatched ? 1 : 0);
    }

    if (!isMatched) { r.nUnmatched++; continue; }
    r.nMatched++;

    if (matchedMCP >= mcs.size()) continue;
    const auto& m = mcs[matchedMCP];
    double true_pt = std::hypot(m.momentum.x, m.momentum.y);
    double reco_pt = std::abs(kappa / st.omega);
    if (!std::isfinite(reco_pt) || reco_pt <= 1e-9 || true_pt <= 1e-9) continue;
    ImpactParamsS ip = trueImpactParamsS(m.vertex.x, m.vertex.y, m.vertex.z,
                                         m.momentum.x, m.momentum.y, m.momentum.z,
                                         m.charge, Bfield);
    double true_q_over_pt = m.charge / true_pt;
    double reco_q_over_pt = m.charge / reco_pt;
    r.res_qpt.push_back((reco_q_over_pt - true_q_over_pt) / true_q_over_pt);
    r.res_d0.push_back(st.D0 - ip.d0);
    r.res_z0.push_back(st.Z0 - ip.z0);
  }

  if (!mcpMatchCount.empty()) {
    double tot = 0;
    for (const auto& kv : mcpMatchCount) tot += kv.second;
    r.avgSeedsPerMCP = tot / mcpMatchCount.size();
  }
  return r;
}
''')


def gather_files(path):
    files = ROOT.std.vector('string')()
    if os.path.isdir(path):
        for root, _, names in os.walk(path):
            for name in names:
                if name.endswith('.root'):
                    files.push_back(os.path.join(root, name))
    else:
        files.push_back(path)
    return files


files = gather_files(options.inFile)

# --- podio collection IDs (needed to resolve the seeds' hit ObjectIDs) -------
name2id = {}
probe = ROOT.TFile.Open(files[0])
meta = probe.Get("podio_metadata")
if meta:
    meta.GetEntry(0)
    try:
        for ci in meta.events___CollectionTypeInfo:
            name2id[str(ci.name)] = int(ci.collectionID)
    except AttributeError:
        pass
probe.Close()
if not name2id:
    raise RuntimeError("could not read podio_metadata/events___CollectionTypeInfo from %s; "
                       "the seed hit ObjectIDs cannot be resolved without it" % files[0])
missing_id = [c for c in hit_colls if c not in name2id]
if missing_id:
    raise RuntimeError("no collectionID for: %s" % ", ".join(missing_id))
coll_ids = [name2id[c] for c in hit_colls]

df = ROOT.RDataFrame("events", files)
cols = set(str(c) for c in df.GetColumnNames())
needed = [options.mcColl, options.seedColl,
          "_%s_trackStates" % options.seedColl, "_%s_trackerHits" % options.seedColl]
needed += hit_colls
needed += ["_%sRelations_from" % c for c in hit_colls]
needed += ["_%sRelations_to" % c for c in hit_colls]
needed += ["_%s_particle" % c for c in sim_colls]
missing = [c for c in needed if c not in cols]
if missing:
    raise RuntimeError("collections not found in input: %s" % ", ".join(missing))

evt_sel = "EvtSelS{%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef}" % (
    options.evtPtMin, options.evtPtMax, options.evtThetaMin, options.evtThetaMax,
    options.evtAbsEtaMin, options.evtAbsEtaMax)

df = df.Define("res", 'studySeeds(%s, %s, _%s_trackStates, _%s_trackerHits, '
                      '{%s}, {%s}, {%s}, {%s}, {%s}, %g, "%s", %s)' % (
    options.mcColl, options.seedColl, options.seedColl, options.seedColl,
    ",".join("&%s" % c for c in hit_colls),
    ",".join("&_%sRelations_from" % c for c in hit_colls),
    ",".join("&_%sRelations_to" % c for c in hit_colls),
    ",".join("&_%s_particle" % c for c in sim_colls),
    ",".join(str(i) + "u" for i in coll_ids),
    options.Bfield, options.cellIDEncoding, evt_sel))

n_all = df.Count()
df = df.Filter("res.evtPass", "event selection")
n_sel = df.Count()

for col, expr in [
    ("seed_theta", "res.seed_theta"), ("seed_isMatched", "res.seed_isMatched"),
    ("layer", "res.layer"), ("layer_isBarrel", "res.layer_isBarrel"),
    ("layer_isMatched", "res.layer_isMatched"),
    ("res_qpt", "res.res_qpt"), ("res_d0", "res.res_d0"), ("res_z0", "res.res_z0"),
    ("nSeeds", "res.nSeeds"), ("nUnmatched", "res.nUnmatched"),
    ("avgSeedsPerMCP", "res.avgSeedsPerMCP"),
]:
    df = df.Define(col, expr)

df = df.Define("layer_barrel", "layer[layer_isBarrel == 1]")
df = df.Define("layer_endcap", "layer[layer_isBarrel == 0]")
df = df.Define("layer_barrel_unmatched", "layer[layer_isBarrel == 1 && layer_isMatched == 0]")
df = df.Define("layer_endcap_unmatched", "layer[layer_isBarrel == 0 && layer_isMatched == 0]")

maxSeeds = options.maxSeeds
if maxSeeds <= 0:
    maxSeeds = int(max(10.0, float(df.Max("nSeeds").GetValue()) * 1.1))

nL = max(1, options.nLayers)
h_theta = df.Histo1D(ROOT.RDF.TH1DModel("seed_theta", "", 20, 0.0, PI), "seed_theta")
h_nSeeds = df.Histo1D(ROOT.RDF.TH1DModel("seed_number", "", 100, 0, maxSeeds), "nSeeds")
h_nUnmatched = df.Histo1D(ROOT.RDF.TH1DModel("seed_number_unmatched", "", 100, 0, maxSeeds),
                          "nUnmatched")
h_perMCP = df.Histo1D(ROOT.RDF.TH1DModel("seeds_per_MCP", "", 50, 0, 20), "avgSeedsPerMCP")
h_barrel = df.Histo1D(ROOT.RDF.TH1DModel("seed_layer_barrel", "", nL, -0.5, nL - 0.5),
                      "layer_barrel")
h_barrel_u = df.Histo1D(ROOT.RDF.TH1DModel("seed_layer_barrel_unmatched", "", nL, -0.5, nL - 0.5),
                        "layer_barrel_unmatched")
h_endcap = df.Histo1D(ROOT.RDF.TH1DModel("seed_layer_endcap", "", nL, -0.5, nL - 0.5),
                      "layer_endcap")
h_endcap_u = df.Histo1D(ROOT.RDF.TH1DModel("seed_layer_endcap_unmatched", "", nL, -0.5, nL - 0.5),
                        "layer_endcap_unmatched")
h_res_qpt = df.Histo1D(ROOT.RDF.TH1DModel("seed_res_qpt", "", 100, -10, 10), "res_qpt")
h_res_d0 = df.Histo1D(ROOT.RDF.TH1DModel("seed_res_d0", "", 100, -10, 10), "res_d0")
h_res_z0 = df.Histo1D(ROOT.RDF.TH1DModel("seed_res_z0", "", 100, -10, 10), "res_z0")

os.makedirs(options.outDir, exist_ok=True)
histos = [h_theta, h_nSeeds, h_nUnmatched, h_perMCP, h_barrel, h_barrel_u,
          h_endcap, h_endcap_u, h_res_qpt, h_res_d0, h_res_z0]
v = [h.GetValue() for h in histos]
(v_theta, v_nSeeds, v_nUnm, v_perMCP, v_bar, v_bar_u, v_end, v_end_u,
 v_qpt, v_d0, v_z0) = v

_keep = []


def save_simple(h, xtitle, ytitle, stem, colour):
    c = ROOT.TCanvas("c_" + h.GetName(), "", 800, 600)
    h.SetLineColor(colour); h.SetLineWidth(2); h.SetTitle("")
    h.GetXaxis().SetTitle(xtitle); h.GetYaxis().SetTitle(ytitle)
    h.GetYaxis().SetTitleOffset(1.35)
    h.Draw("HIST")
    draw_ci_label()
    c.SaveAs(os.path.join(options.outDir, plot_name(stem)))


def save_pair(h_all, h_sub, xtitle, ytitle, sub_label, stem):
    """All vs unmatched overlay, unmatched scaled onto a right-hand axis
    (the presentation PlotSeeds.C uses for its occupancy plots)."""
    c = ROOT.TCanvas("c_pair_" + h_all.GetName(), "", 800, 600)
    c.SetRightMargin(0.18); c.SetTicky(0)
    scale = (h_all.GetMaximum() / h_sub.GetMaximum()
             if h_all.GetMaximum() > 0 and h_sub.GetMaximum() > 0 else 1.0)
    h_sub_s = h_sub.Clone(h_sub.GetName() + "_scaled")
    h_sub_s.Scale(scale)
    h_all.SetLineColor(COL_ALL); h_all.SetLineWidth(2); h_all.SetTitle("")
    h_sub_s.SetLineColor(COL_SUB); h_sub_s.SetLineWidth(2)
    h_all.GetXaxis().SetTitle(xtitle); h_all.GetYaxis().SetTitle(ytitle)
    h_all.Draw("HIST"); h_sub_s.Draw("HIST SAME")
    leg = ROOT.TLegend(0.42, 0.75, 0.82, 0.88)
    leg.SetBorderSize(0); leg.SetFillStyle(0)
    leg.AddEntry(h_all, "All seeds", "l")
    leg.AddEntry(h_sub_s, sub_label + " (right axis)", "l")
    leg.Draw()
    c.Update()
    xmax = h_all.GetXaxis().GetXmax()
    ax = ROOT.TGaxis(xmax, 0, xmax, h_all.GetMaximum(), 0, h_sub.GetMaximum(), 510, "+L")
    ax.SetTitle(sub_label); ax.SetTitleOffset(1.2)
    ax.SetLineColor(COL_SUB); ax.SetLabelColor(COL_SUB); ax.SetTitleColor(COL_SUB)
    ax.SetLabelFont(42); ax.SetTitleFont(42)
    ax.Draw()
    draw_ci_label()
    c.SaveAs(os.path.join(options.outDir, plot_name(stem)))
    _keep.extend([h_sub_s, ax, leg])


save_simple(v_theta, "#theta [rad]", "Seeds", "seeds_theta", COL_ALL)
save_pair(v_nSeeds, v_nUnm, "Number of seeds", "Events", "Unmatched", "seeds_nSeeds")
save_simple(v_perMCP, "Average seeds per MC particle", "Events", "seeds_perMCP", ROOT.kGreen + 2)
save_pair(v_bar, v_bar_u, "Layer", "Hits on seeds", "Unmatched", "seeds_barrel")
save_pair(v_end, v_end_u, "Layer", "Hits on seeds", "Unmatched", "seeds_endcap")
save_simple(v_qpt, "#Delta(q/p_{T}) / (q/p_{T})", "Entries", "seeds_res_qpt", ROOT.kAzure + 1)
save_simple(v_d0, "#Delta d_{0} [mm]", "Entries", "seeds_res_d0", ROOT.kRed + 1)
save_simple(v_z0, "#Delta z_{0} [mm]", "Entries", "seeds_res_z0", ROOT.kGreen + 2)

# --- Console summary ---------------------------------------------------------
n_seeds = v_nSeeds.GetMean() * n_sel.GetValue()
n_unm = v_nUnm.GetMean() * n_sel.GetValue()
print("\n=== Seed validation summary (%s) ===" % options.seedColl)
print("  events        : %d selected / %d total" % (n_sel.GetValue(), n_all.GetValue()))
print("  seeds         : %d   <seeds/event> = %.2f" % (int(round(n_seeds)), v_nSeeds.GetMean()))
print("  unmatched     : %d   -> matched fraction = %.4f"
      % (int(round(n_unm)), 1.0 - n_unm / n_seeds if n_seeds else 0.0))
print("  <seeds/MCP>   : %.2f" % v_perMCP.GetMean())
print("  hits on seeds : %d barrel, %d endcap"
      % (int(v_bar.Integral()), int(v_end.Integral())))
print("=" * 44 + "\n")

out = ROOT.TFile(options.outFile, "RECREATE")
for h in v:
    h.Write()
out.Close()
