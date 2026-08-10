"""Tracker-hit occupancy study on EDM4hep reconstruction output (RDataFrame).

RDataFrame-based reimplementation of the hits half of the ROOT-macro chain in
https://github.com/samf25/TrackingPlots (commit 940ef76):
  * WriteHitsMT.C -- per-hit theta / subdetector and per-event hit counts;
  * PlotHits.C    -- solid-angle-normalised hit densities and per-event yields.
Both steps are fused here: a JITted C++ helper, `studyHits`, runs once per event
over the six tracker-hit collections and returns per-hit RVecs plus the event
totals, which RDataFrame then histograms.

Collections (--hitColls, six names in the fixed order barrel,endcap x VXD,IT,OT):
  VXDBarrelHits, VXDEndcapHits, ITBarrelHits, ITEndcapHits, OTBarrelHits,
  OTEndcapHits -- TrackerHitPlane collections carrying the hit position.
Subdetector grouping follows the macro: pairs map to VXD / IT / OT, and even
slots are barrel.

Key quantities (mirroring the macro):
  hit theta   : atan2(hypot(x,y), z) from the hit position
  hit density : counts / (2*pi*(cos(theta_lo)-cos(theta_hi)) * nEvents),
                i.e. hits per steradian per event
  per event   : nHits in VXD / IT / OT and their total

The optional event-level selection is the same as study_tracks.py: keep the
event when at least one accepted primary MC particle (generatorStatus==1,
charged, not created-in-sim, not decayed-in-tracker) falls inside the pt, theta
AND |eta| windows.

Outputs (-o ROOT file): the three density histograms, the per-event hit-count
histograms, and the raw per-layer theta counts. Plots under --outDir:
hits_{VXD,IT,OT}, hits_combined_hits, hits_total_hits, hits_layer_hits.

Usage:
    python study_hits.py -i reco.edm4hep.root -o histos_hits.root -d plots
"""
from optparse import OptionParser
from array import array
import os
import math
import ROOT

#########################
parser = OptionParser()
parser.add_option('-i', '--inFile', help='reco.edm4hep.root (file or directory)',
                  type=str, default='reco.edm4hep.root')
parser.add_option('-o', '--outFile', help='output ROOT file', type=str,
                  default='histos_hits.root')
parser.add_option('-d', '--outDir', help='directory for the plots', type=str, default='.')
parser.add_option('--hitColls', help='comma-separated tracker-hit collections, in the order '
                  'VXDBarrel,VXDEndcap,ITBarrel,ITEndcap,OTBarrel,OTEndcap',
                  type=str,
                  default='VXDBarrelHits,VXDEndcapHits,ITBarrelHits,ITEndcapHits,'
                          'OTBarrelHits,OTEndcapHits')
parser.add_option('--mcColl', help='MC particle collection', type=str, default='MCParticles')
parser.add_option('--nThetaBins', help='number of theta bins for the density', type=int, default=20)
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

SUBDET = ["VXD", "IT", "OT"]
SUBDET_LABEL = ["Vertex Detector", "Inner Tracker", "Outer Tracker"]
COLOURS = [ROOT.kAzure + 1, ROOT.kRed + 1, ROOT.kGreen + 2]


def plot_name(stem):
    return "%s.%s" % (stem, options.suffix)


_ci_labels = []
def draw_ci_label():
    t = ROOT.TLatex()
    t.SetNDC(); t.SetTextFont(42); t.SetTextSize(0.035); t.SetTextAlign(12)
    t.DrawLatex(0.12, 0.945, options.label)
    _ci_labels.append(t)


hit_colls = [c.strip() for c in options.hitColls.split(',') if c.strip()]
if len(hit_colls) != 6:
    raise RuntimeError("--hitColls needs exactly 6 collection names, got %d" % len(hit_colls))

# --- JITted per-event analysis ----------------------------------------------
ROOT.gInterpreter.Declare(r'''
#include "ROOT/RVec.hxx"
#include "edm4hep/MCParticleData.h"
#include "edm4hep/TrackerHitPlaneData.h"
#include <cmath>
#include <vector>

using ROOT::VecOps::RVec;

static const int BITCreatedInSimulation = 30;
static const int BITDecayedInTracker    = 27;
static inline bool checkBit(int v, int b) { return (v >> b) & 1; }

struct EvtSelH { float ptMin, ptMax, thetaMin, thetaMax, absEtaMin, absEtaMax; };

static inline float thetaToEtaH(float theta) {
  const float eps = 1e-6f;
  float t = std::max(eps, std::min((float)M_PI - eps, theta));
  return -std::log(std::tan(t * 0.5f));
}

static inline bool mcAcceptH(const edm4hep::MCParticleData& m) {
  if (m.generatorStatus != 1) return false;
  if (m.charge == 0) return false;
  if (checkBit(m.simulatorStatus, BITCreatedInSimulation)) return false;
  if (checkBit(m.simulatorStatus, BITDecayedInTracker))    return false;
  return true;
}

struct HitResult {
  RVec<double> hit_theta;     // polar angle of every tracker hit
  RVec<int>    hit_subdet;    // 0 = VXD, 1 = IT, 2 = OT
  RVec<int>    hit_isBarrel;  // 1 = barrel, 0 = endcap
  int nVXD = 0, nIT = 0, nOT = 0, nTotal = 0;
  bool evtPass = true;
};

// `colls` holds the six TrackerHitPlane collections in the order
// VXDBarrel, VXDEndcap, ITBarrel, ITEndcap, OTBarrel, OTEndcap: consecutive
// pairs share a subdetector and even slots are barrel, exactly as in the macro.
HitResult studyHits(const RVec<edm4hep::MCParticleData>& mcs,
                    const std::vector<const RVec<edm4hep::TrackerHitPlaneData>*>& colls,
                    const EvtSelH& evtSel)
{
  HitResult r;

  r.evtPass = false;
  for (const auto& m : mcs) {
    if (!mcAcceptH(m)) continue;
    double pt    = std::hypot(m.momentum.x, m.momentum.y);
    double theta = std::atan2(pt, (double)m.momentum.z);
    if (pt    < evtSel.ptMin    || pt    > evtSel.ptMax)    continue;
    if (theta < evtSel.thetaMin || theta > evtSel.thetaMax) continue;
    float absEta = std::abs(thetaToEtaH(theta));
    if (absEta < evtSel.absEtaMin || absEta > evtSel.absEtaMax) continue;
    r.evtPass = true;
    break;
  }
  if (!r.evtPass) return r;

  int counts[3] = {0, 0, 0};
  for (size_t slot = 0; slot < colls.size(); ++slot) {
    if (!colls[slot]) continue;
    const int subdet  = (int)(slot / 2);
    const int isBarrel = (slot % 2 == 0) ? 1 : 0;
    for (const auto& h : *colls[slot]) {
      double theta = std::atan2(std::hypot(h.position.x, h.position.y),
                                (double)h.position.z);
      r.hit_theta.push_back(theta);
      r.hit_subdet.push_back(subdet);
      r.hit_isBarrel.push_back(isBarrel);
      counts[subdet]++;
    }
  }
  r.nVXD = counts[0]; r.nIT = counts[1]; r.nOT = counts[2];
  r.nTotal = counts[0] + counts[1] + counts[2];
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


df = ROOT.RDataFrame("events", gather_files(options.inFile))
cols = set(str(c) for c in df.GetColumnNames())
missing = [c for c in hit_colls if c not in cols]
if missing:
    raise RuntimeError("tracker-hit collections not found in input: %s" % ", ".join(missing))

evt_sel = "EvtSelH{%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef}" % (
    options.evtPtMin, options.evtPtMax, options.evtThetaMin, options.evtThetaMax,
    options.evtAbsEtaMin, options.evtAbsEtaMax)
coll_list = "{%s}" % ",".join("&%s" % c for c in hit_colls)

df = df.Define("res", "studyHits(%s, %s, %s)" % (options.mcColl, coll_list, evt_sel))
n_all = df.Count()
df = df.Filter("res.evtPass", "event selection")
n_sel = df.Count()

for col, expr in [("hit_theta", "res.hit_theta"), ("hit_subdet", "res.hit_subdet"),
                  ("nVXD", "res.nVXD"), ("nIT", "res.nIT"), ("nOT", "res.nOT"),
                  ("nTotal", "res.nTotal")]:
    df = df.Define(col, expr)
for i, name in enumerate(SUBDET):
    df = df.Define("theta_" + name, "hit_theta[hit_subdet == %d]" % i)

# The macro sizes the per-event histograms from the data, so take the maxima
# first; this costs one extra (cheap) pass over the already-defined columns.
max_layer_r = df.Max("nVXD"), df.Max("nIT"), df.Max("nOT")
max_total_r = df.Max("nTotal")
max_layer = max(float(m.GetValue()) for m in max_layer_r)
max_total = float(max_total_r.GetValue())
max_layer = max(1.0, max_layer * 1.1)
max_total = max(1.0, max_total * 1.1)

nTh = max(1, options.nThetaBins)
h_theta = {name: df.Histo1D(ROOT.RDF.TH1DModel("hits_theta_" + name, "", nTh, 0.0, PI),
                            "theta_" + name) for name in SUBDET}
h_nVXD = df.Histo1D(ROOT.RDF.TH1DModel("h_nHits_VXD", "", 100, 0, max_layer), "nVXD")
h_nIT = df.Histo1D(ROOT.RDF.TH1DModel("h_nHits_IT", "", 100, 0, max_layer), "nIT")
h_nOT = df.Histo1D(ROOT.RDF.TH1DModel("h_nHits_OT", "", 100, 0, max_layer), "nOT")
h_nTotal = df.Histo1D(ROOT.RDF.TH1DModel("h_nHits_total", "", 100, 0, max_total), "nTotal")

os.makedirs(options.outDir, exist_ok=True)
theta_vals = {name: h_theta[name].GetValue() for name in SUBDET}
count_vals = [h_nVXD.GetValue(), h_nIT.GetValue(), h_nOT.GetValue()]
total_val = h_nTotal.GetValue()
nEvents = float(n_sel.GetValue())

# --- Convert raw theta counts into hits/sr/event -----------------------------
density = {}
for name in SUBDET:
    src = theta_vals[name]
    d = ROOT.TH1D("h_density_" + name, "", nTh, 0.0, PI)
    for b in range(1, nTh + 1):
        lo = src.GetXaxis().GetBinLowEdge(b)
        hi = src.GetXaxis().GetBinUpEdge(b)
        solid = 2.0 * math.pi * (math.cos(lo) - math.cos(hi))   # steradian
        if solid > 0 and nEvents > 0:
            d.SetBinContent(b, src.GetBinContent(b) / (solid * nEvents))
            d.SetBinError(b, math.sqrt(max(0.0, src.GetBinContent(b))) / (solid * nEvents))
    density[name] = d

_keep = []


def style(h, colour):
    h.SetLineColor(colour); h.SetMarkerColor(colour)
    h.SetMarkerStyle(20); h.SetLineWidth(2); h.SetTitle("")


for i, name in enumerate(SUBDET):
    c = ROOT.TCanvas("c_" + name, "", 800, 600)
    style(density[name], COLOURS[i])
    density[name].GetXaxis().SetTitle("#theta [rad]")
    density[name].GetYaxis().SetTitle("Hit density [hits/sr/event]")
    density[name].GetYaxis().SetTitleOffset(1.35)
    density[name].Draw("PE")
    draw_ci_label()
    c.SaveAs(os.path.join(options.outDir, plot_name("hits_" + name)))

c_comb = ROOT.TCanvas("c_combined", "", 800, 600)
c_comb.SetLogy()
ymax = max(density[n].GetMaximum() for n in SUBDET)
leg = ROOT.TLegend(0.58, 0.72, 0.88, 0.88)
leg.SetBorderSize(0); leg.SetFillStyle(0)
for i, name in enumerate(SUBDET):
    style(density[name], COLOURS[i])
    density[name].SetMaximum(ymax * 5.0)
    density[name].GetXaxis().SetTitle("#theta [rad]")
    density[name].GetYaxis().SetTitle("Hit density [hits/sr/event]")
    density[name].Draw("PE" if i == 0 else "PE SAME")
    leg.AddEntry(density[name], SUBDET_LABEL[i], "lep")
leg.Draw(); draw_ci_label()
c_comb.SaveAs(os.path.join(options.outDir, plot_name("hits_combined_hits")))
_keep.append(leg)

c_tot = ROOT.TCanvas("c_total_hits", "", 800, 600)
total_val.SetLineColor(COLOURS[0]); total_val.SetLineWidth(2); total_val.SetTitle("")
total_val.GetXaxis().SetTitle("Hits per event")
total_val.GetYaxis().SetTitle("Events")
total_val.Draw("HIST")
draw_ci_label()
c_tot.SaveAs(os.path.join(options.outDir, plot_name("hits_total_hits")))

c_lay = ROOT.TCanvas("c_layer_hits", "", 800, 600)
ymax = max(h.GetMaximum() for h in count_vals)
leg2 = ROOT.TLegend(0.58, 0.72, 0.88, 0.88)
leg2.SetBorderSize(0); leg2.SetFillStyle(0)
for i, h in enumerate(count_vals):
    h.SetLineColor(COLOURS[i]); h.SetLineWidth(2); h.SetTitle("")
    h.SetMaximum(ymax * 1.3)
    h.GetXaxis().SetTitle("Hits per event")
    h.GetYaxis().SetTitle("Events")
    h.Draw("HIST" if i == 0 else "HIST SAME")
    leg2.AddEntry(h, SUBDET_LABEL[i], "l")
leg2.Draw(); draw_ci_label()
c_lay.SaveAs(os.path.join(options.outDir, plot_name("hits_layer_hits")))
_keep.append(leg2)

# --- Console summary ---------------------------------------------------------
print("\n=== Hit occupancy summary ===")
print("  events        : %d selected / %d total" % (n_sel.GetValue(), n_all.GetValue()))
for i, name in enumerate(SUBDET):
    print("  %-3s hits      : %d   <hits/event> = %.1f"
          % (name, int(theta_vals[name].Integral()), count_vals[i].GetMean()))
print("  total hits    : %d   <hits/event> = %.1f"
      % (int(sum(theta_vals[n].Integral() for n in SUBDET)), total_val.GetMean()))
print("=" * 40 + "\n")

out = ROOT.TFile(options.outFile, "RECREATE")
for name in SUBDET:
    theta_vals[name].Write()
    density[name].Write()
for h in count_vals:
    h.Write()
total_val.Write()
out.Close()
