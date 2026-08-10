"""Diagnostic for events with no reconstructed tracks (RDataFrame).

RDataFrame-based reimplementation of SummarizeNoTrackEvents.C from
https://github.com/samf25/TrackingPlots (commit 940ef76). That macro is not part
of the RunAnalysis.C -> PlotAll.C chain: it is a standalone probe for the events
where the track collection came out empty, answering "what did we fail to
reconstruct, and did the seeding even fire?".

The event is kept when the track collection of interest is empty. For each such
event it profiles the accepted primary MC particles (generatorStatus==1,
charged, not created-in-sim (bit 30), not decayed-in-tracker (bit 27)) and the
number of seeds, so a reconstruction failure can be attributed to seeding
(no seeds) or to the track finding/fitting downstream (seeds present, no track).

A podio *subset* track collection is detected automatically: when only
`<trackColl>_objIdx` exists its length is the track count, otherwise the
collection itself is counted.

As in the macro the seed count is capped at --maxSeeds for plotting, so the top
bin is an overflow bucket.

Outputs (-o ROOT file): h_mc_theta, h_mc_pt, h_mc_pt_vs_theta, h_seed_counts,
h_seeds_vs_theta, h_seeds_vs_pt, h_seeds_vs_pt_theta (3D), h_mc_counts. Plots
under --outDir: notracks_{mc_theta,mc_pt,mc_pt_vs_theta,seed_counts,
seeds_vs_theta,seeds_vs_pt,mc_counts}.

Usage:
    python study_notracks.py -i reco.edm4hep.root -o histos_notracks.root -d plots
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
                  default='histos_notracks.root')
parser.add_option('-d', '--outDir', help='directory for the plots', type=str, default='.')
parser.add_option('--trackColl', help='track collection of interest (subset or full)',
                  type=str, default='SiTracks')
parser.add_option('--trackStore', help='collection physically holding the TrackData '
                  '(parent of a subset; same as --trackColl for a full collection)',
                  type=str, default='AllTracks')
parser.add_option('--seedColl', help='seed track collection', type=str, default='SeedTracks')
parser.add_option('--mcColl', help='MC particle collection', type=str, default='MCParticles')
parser.add_option('--mcPtMax', help='upper edge of the MC pt axis [GeV]',
                  type=float, default=5500.0)
parser.add_option('--maxSeeds', help='seed count is capped at this value for plotting',
                  type=int, default=10)
parser.add_option('--label', help='provenance label stamped on every plot',
                  type=str, default='Gen3 material handling validation')
parser.add_option('--suffix', help='plot file format (png, pdf, ...)', type=str, default='png')
(options, args) = parser.parse_args()

ROOT.gROOT.SetBatch(True)
ROOT.EnableImplicitMT()
ROOT.gStyle.SetOptStat(0)
PI = ROOT.TMath.Pi()


def plot_name(stem):
    return "%s.%s" % (stem, options.suffix)


_ci_labels = []
def draw_ci_label():
    t = ROOT.TLatex()
    t.SetNDC(); t.SetTextFont(42); t.SetTextSize(0.035); t.SetTextAlign(12)
    t.DrawLatex(0.12, 0.945, options.label)
    _ci_labels.append(t)


ROOT.gInterpreter.Declare(r'''
#include "ROOT/RVec.hxx"
#include "edm4hep/MCParticleData.h"
#include "edm4hep/TrackData.h"
#include "podio/ObjectID.h"
#include <cmath>

using ROOT::VecOps::RVec;

static const int BITCreatedInSimulationN = 30;
static const int BITDecayedInTrackerN    = 27;
static inline bool checkBitN(int v, int b) { return (v >> b) & 1; }

struct NoTrackResult {
  RVec<double> mc_pt, mc_theta;   // accepted primaries in a no-track event
  int nMCP = 0;                   // how many of them
  int nSeeds = 0;                 // capped seed count
  bool noTracks = false;          // event has an empty track collection
};

NoTrackResult studyNoTracks(const RVec<edm4hep::MCParticleData>& mcs,
                            const RVec<edm4hep::TrackData>&      tracks,
                            const RVec<podio::ObjectID>&         selIdx,
                            const RVec<edm4hep::TrackData>&      seeds,
                            bool useAllTracks, int maxSeeds)
{
  NoTrackResult r;
  const int nTracks = useAllTracks ? (int)tracks.size() : (int)selIdx.size();
  if (nTracks > 0) return r;             // only empty-track events are profiled
  r.noTracks = true;

  r.nSeeds = std::min((int)seeds.size(), maxSeeds);

  for (const auto& m : mcs) {
    if (m.generatorStatus != 1) continue;
    if (m.charge == 0) continue;
    if (checkBitN(m.simulatorStatus, BITCreatedInSimulationN)) continue;
    if (checkBitN(m.simulatorStatus, BITDecayedInTrackerN))    continue;
    double pt    = std::hypot(m.momentum.x, m.momentum.y);
    double theta = std::atan2(pt, (double)m.momentum.z);
    r.mc_pt.push_back(pt);
    r.mc_theta.push_back(theta);
    r.nMCP++;
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


df = ROOT.RDataFrame("events", gather_files(options.inFile))
cols = set(str(c) for c in df.GetColumnNames())

subset_idx = options.trackColl + "_objIdx"
use_all = subset_idx not in cols
store = options.trackStore if not use_all else options.trackColl
if store not in cols:
    raise RuntimeError("track data collection '%s' not found in input" % store)
if options.seedColl not in cols:
    raise RuntimeError("seed collection '%s' not found in input" % options.seedColl)
sel_expr = "ROOT::VecOps::RVec<podio::ObjectID>{}" if use_all else subset_idx

df = df.Define("res", "studyNoTracks(%s, %s, %s, %s, %s, %d)" % (
    options.mcColl, store, sel_expr, options.seedColl,
    "true" if use_all else "false", options.maxSeeds))

n_all = df.Count()
df_nt = df.Filter("res.noTracks", "events with no reconstructed tracks")
n_notrack = df_nt.Count()

for col, expr in [("mc_pt", "res.mc_pt"), ("mc_theta", "res.mc_theta"),
                  ("nMCP", "res.nMCP"), ("nSeeds", "res.nSeeds")]:
    df_nt = df_nt.Define(col, expr)
# Seed count is per event; broadcast it alongside each MC particle for the 2D/3D
# correlations, exactly as the macro fills them inside its MC loop.
df_nt = df_nt.Define("nSeeds_perMCP", "ROOT::VecOps::RVec<double>(mc_pt.size(), (double)nSeeds)")

ptMax = max(1.0, options.mcPtMax)
nSeedBins = options.maxSeeds + 1

h_theta = df_nt.Histo1D(ROOT.RDF.TH1DModel("h_mc_theta", "", 80, 0.0, 3.2), "mc_theta")
h_pt = df_nt.Histo1D(ROOT.RDF.TH1DModel("h_mc_pt", "", 100, 0.0, ptMax), "mc_pt")
h_pt_vs_theta = df_nt.Histo2D(
    ROOT.RDF.TH2DModel("h_mc_pt_vs_theta", "", 60, 0.0, 3.2, 100, 0.0, ptMax),
    "mc_theta", "mc_pt")
h_seed_counts = df_nt.Histo1D(
    ROOT.RDF.TH1DModel("h_seed_counts", "", nSeedBins, -0.5, options.maxSeeds + 0.5), "nSeeds")
h_seeds_vs_theta = df_nt.Histo2D(
    ROOT.RDF.TH2DModel("h_seeds_vs_theta", "", 60, 0.0, 3.2,
                       nSeedBins, -0.5, options.maxSeeds + 0.5),
    "mc_theta", "nSeeds_perMCP")
h_seeds_vs_pt = df_nt.Histo2D(
    ROOT.RDF.TH2DModel("h_seeds_vs_pt", "", 100, 0.0, ptMax,
                       nSeedBins, -0.5, options.maxSeeds + 0.5),
    "mc_pt", "nSeeds_perMCP")
h_seeds_vs_pt_theta = df_nt.Histo3D(
    ROOT.RDF.TH3DModel("h_seeds_vs_pt_theta", "", 80, 0.0, ptMax, 48, 0.0, 3.2,
                       nSeedBins, -0.5, options.maxSeeds + 0.5),
    "mc_pt", "mc_theta", "nSeeds_perMCP")
h_mc_counts = df_nt.Histo1D(ROOT.RDF.TH1DModel("h_mc_counts", "", 20, -0.5, 19.5), "nMCP")

os.makedirs(options.outDir, exist_ok=True)
histos = [h_theta, h_pt, h_pt_vs_theta, h_seed_counts, h_seeds_vs_theta,
          h_seeds_vs_pt, h_seeds_vs_pt_theta, h_mc_counts]
vals = [h.GetValue() for h in histos]

n_total = n_all.GetValue()
n_empty = n_notrack.GetValue()
print("\n=== No-track event summary (%s) ===" % options.trackColl)
print("  events with no tracks : %d / %d  (%.2f%%)"
      % (n_empty, n_total, 100.0 * n_empty / n_total if n_total else 0.0))
if n_empty:
    print("  accepted MC particles : %d   <MCP/event> = %.2f"
          % (int(vals[0].Integral()), vals[7].GetMean()))
    print("  <seeds/event>         : %.2f  (capped at %d)"
          % (vals[3].GetMean(), options.maxSeeds))
print("=" * 46 + "\n")

if n_empty == 0:
    print("No empty-track events found: nothing to plot.")
else:
    def save1d(h, xtitle, ytitle, stem, colour):
        c = ROOT.TCanvas("c_" + h.GetName(), "", 800, 600)
        h.SetLineColor(colour); h.SetLineWidth(2); h.SetTitle("")
        h.GetXaxis().SetTitle(xtitle); h.GetYaxis().SetTitle(ytitle)
        h.GetYaxis().SetTitleOffset(1.35)
        h.Draw("HIST")
        draw_ci_label()
        c.SaveAs(os.path.join(options.outDir, plot_name(stem)))

    def save2d(h, xtitle, ytitle, stem):
        c = ROOT.TCanvas("c_" + h.GetName(), "", 800, 600)
        c.SetRightMargin(0.16)
        h.SetTitle("")
        h.GetXaxis().SetTitle(xtitle); h.GetYaxis().SetTitle(ytitle)
        h.GetYaxis().SetTitleOffset(1.35)
        h.Draw("COLZ")
        draw_ci_label()
        c.SaveAs(os.path.join(options.outDir, plot_name(stem)))

    save1d(vals[0], "MC #theta [rad]", "Entries", "notracks_mc_theta", ROOT.kAzure + 1)
    save1d(vals[1], "MC p_{T} [GeV]", "Entries", "notracks_mc_pt", ROOT.kRed + 1)
    save2d(vals[2], "MC #theta [rad]", "MC p_{T} [GeV]", "notracks_mc_pt_vs_theta")
    save1d(vals[3], "Number of seeds", "Events", "notracks_seed_counts", ROOT.kGreen + 2)
    save2d(vals[4], "MC #theta [rad]", "Number of seeds", "notracks_seeds_vs_theta")
    save2d(vals[5], "MC p_{T} [GeV]", "Number of seeds", "notracks_seeds_vs_pt")
    save1d(vals[7], "Accepted MC particles", "Events", "notracks_mc_counts", ROOT.kOrange + 7)

out = ROOT.TFile(options.outFile, "RECREATE")
for h in vals:
    h.Write()
out.Close()
