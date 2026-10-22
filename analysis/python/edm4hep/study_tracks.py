"""Track performance study on EDM4hep reconstruction output (RDataFrame).

RDataFrame-based reimplementation of the two-step ROOT-macro chain in
https://github.com/samf25/TrackingPlots (commit 940ef76):
  * WriteTracksMT.C  -- extracts truth / track / matched / event quantities from
                        the edm4hep file into flat ntuples;
  * PlotTracks.C     -- turns those ntuples into efficiency, fake-rate,
                        resolution and track-quality plots.
Both steps are fused here: a JITted C++ helper, `studyTracks`, runs once per
event over whole EDM4hep collections and returns per-object RVecs, which
RDataFrame then histograms in a single event loop.

Collections (all configurable; the defaults below are the standard reco output
of this stack -- for a QUBO study pass --trackColl QUBOSelectedTracks
--trackStore QUBOTracks --relColl QUBOTrackRelations --mcColl MCParticle):
  * MCParticles                -- truth particles
  * SiTracks                   -- the track collection of interest. It is a podio
                                  *subset* collection: only `SiTracks_objIdx`
                                  exists, indexing into the full `AllTracks`
                                  collection that physically stores the
                                  TrackData + TrackStates.
  * SiTrackRelations           -- MC<->track links. Read via the flat
                                  `_SiTrackRelations_from` (track side) and
                                  `_SiTrackRelations_to` (MCParticles side)
                                  ObjectID branches (the link collection itself
                                  is podio::LinkData, unusable in RDF).

Key quantities (mirroring the macros):
  truth   : pt = hypot(px,py), theta = atan2(pt,pz), charge   (accepted MC only:
            generatorStatus==1, charged, not created-in-sim (bit 30), not
            decayed-in-tracker (bit 27))
  track   : pt = |0.3*B/omega/1000|, theta = atan2(1,tanLambda), d0=D0, z0=Z0,
            nHits = trackerHits_end-begin, nHoles = Nholes, chi2/ndof,
            isReal = matched to an accepted MC particle.
            The track state is chosen as in the macro: prefer trackStates_begin,
            but fall back to trackStates_end-1 when the begin omega is invalid
            (the begin state is frequently omega=nan in this stack).
  matched : true_(pt,theta,charge,d0,z0) + reco_(pt,d0,z0) + nHits/nHoles/chi2.
            true_d0 / true_z0 are the *signed* perigee impact parameters of the
            helix defined by the MC particle's production vertex, momentum and
            charge in the solenoid field, computed w.r.t. the origin in the same
            LCIO/edm4hep convention as the reconstructed TrackState D0/Z0 (so the
            d0/z0 resolutions are physically meaningful and peak at zero). This
            replaces the raw-vertex shortcut (hypot(vx,vy), vz) used in the
            original macro.
  resolutions: q/pt = (q/reco_pt - q/true_pt)/(q/true_pt), d0 = reco-true,
               z0 = reco-true.

Selection (port of the macros' SelectionConfig.h / RunAnalysis.conf):
  --evt{Pt,Theta,AbsEta}{Min,Max} keep the event when at least one accepted
  primary MC particle falls inside all of the windows simultaneously; the whole
  event is dropped otherwise.
  --trk{Pt,Theta,AbsEta,Phi,D0,Z0,Chi2}{Min,Max}, --trkNHitsMin, --trkNHolesMax
  are applied to every track before it enters any histogram, and to the matched
  pairs so the efficiency numerator stays consistent.
  Use the theta OR the absEta window, not both. Defaults cut nothing.

Outputs (-o ROOT file): truth/matched/all/real/fake histograms, the track
quality and resolution histograms, the per-event nTracks / nTruths / nMatched /
nFake histograms (the macros' events_summary columns), and the eff_pt /
eff_theta / fake_rate TEfficiency objects. Plots under --outDir (format set by
--suffix, default png): tracks_eff_pt, tracks_eff_theta, tracks_fake,
tracks_res_{qpt,d0,z0,all}, tracks_{nHits,nHoles,chi2}, tracks_nTracks. The
per-object ntuples (truth, tracks, matched, events_summary) are written only
with --writeTree.
Pass --metrics to write the corresponding compact JSON study sidecar.

Every plot is stamped with a provenance label, set with --label.

Usage:
    python study_tracks.py -i intermediate.edm4hep.root -o histos_tracks.root -d plots
"""
from optparse import OptionParser
from array import array
import os
import math
import ROOT

from benchmark_metrics import fraction, histogram_summary, write_fragment

#########################
parser = OptionParser()
parser.add_option('-i', '--inFile', help='--inFile reco.edm4hep.root (file or directory)',
                  type=str, default='intermediate.edm4hep.root')
parser.add_option('-o', '--outFile', help='--outFile histos_tracks.root',
                  type=str, default='histos_tracks.root')
parser.add_option('-d', '--outDir', help='--outDir directory for the .png plots',
                  type=str, default='.')
parser.add_option('--trackColl', help='track collection of interest (subset or full)',
                  type=str, default='SiTracks')
parser.add_option('--trackStore', help='collection physically holding TrackData/TrackStates '
                  '(parent of a subset; same as --trackColl for a full collection)',
                  type=str, default='AllTracks')
parser.add_option('--relColl', help='MC<->track relation (link) collection',
                  type=str, default='SiTrackRelations')
parser.add_option('--mcColl', help='MC particle collection', type=str, default='MCParticles')
parser.add_option('--Bfield', help='solenoid field [T] for pt = |0.3*B/omega/1000|',
                  type=float, default=5.0)
parser.add_option('--ptMin', help='low edge of the log pt binning [GeV]', type=float, default=0.5)
parser.add_option('--ptMax', help='high edge of the log pt binning [GeV]', type=float, default=10.0)
parser.add_option('--nPtBins', help='number of log pt bins', type=int, default=12)
parser.add_option('--maxTracks', help='upper edge of the nTracks-per-event histogram',
                  type=int, default=500)
parser.add_option('--writeTree', action='store_true', default=False,
                  help='also write the truth/tracks/matched/events_summary ntuples')
parser.add_option('--label', help='provenance label stamped on every plot',
                  type=str, default='Gen3 material handling validation')
parser.add_option('--suffix', help='plot file format (png, pdf, ...)', type=str, default='png')
parser.add_option('--metrics', help='optional JSON metrics sidecar', type=str)

# --- Event-level selection (port of SelectionConfig.h EventSelectionConfig) ---
# Keep the event if at least one accepted primary MC particle passes all cuts.
# Use the theta OR the absEta window, not both, to avoid double-cutting.
FMAX = 3.4028235e+38
parser.add_option('--evtPtMin', type=float, default=0.0)
parser.add_option('--evtPtMax', type=float, default=FMAX)
parser.add_option('--evtThetaMin', type=float, default=0.0)
parser.add_option('--evtThetaMax', type=float, default=math.pi)
parser.add_option('--evtAbsEtaMin', type=float, default=0.0)
parser.add_option('--evtAbsEtaMax', type=float, default=FMAX)

# --- Track-level selection (port of SelectionConfig.h TrackSelectionConfig) ---
# A track must pass every cut to enter any histogram.
parser.add_option('--trkPtMin', type=float, default=0.0)
parser.add_option('--trkPtMax', type=float, default=FMAX)
parser.add_option('--trkThetaMin', type=float, default=0.0)
parser.add_option('--trkThetaMax', type=float, default=math.pi)
parser.add_option('--trkAbsEtaMin', type=float, default=0.0)
parser.add_option('--trkAbsEtaMax', type=float, default=FMAX)
parser.add_option('--trkPhiMin', type=float, default=-math.pi)
parser.add_option('--trkPhiMax', type=float, default=math.pi)
parser.add_option('--trkD0Min', type=float, default=-FMAX)
parser.add_option('--trkD0Max', type=float, default=FMAX)
parser.add_option('--trkZ0Min', type=float, default=-FMAX)
parser.add_option('--trkZ0Max', type=float, default=FMAX)
parser.add_option('--trkChi2Min', type=float, default=0.0)
parser.add_option('--trkChi2Max', type=float, default=FMAX)
parser.add_option('--trkNHitsMin', type=int, default=0)
parser.add_option('--trkNHolesMax', type=int, default=2147483647)
(options, args) = parser.parse_args()

ROOT.gROOT.SetBatch(True)
ROOT.EnableImplicitMT()
ROOT.gStyle.SetOptStat(0)
PI = ROOT.TMath.Pi()

def plot_name(stem):
    """Plot file name for `stem`, honouring --suffix (png, pdf, ...)."""
    return "%s.%s" % (stem, options.suffix)

# Stamp every plot with a provenance label (kept alive until SaveAs)
_ci_labels = []
def draw_ci_label():
    t = ROOT.TLatex()
    t.SetNDC(); t.SetTextFont(42); t.SetTextSize(0.035); t.SetTextAlign(12)
    t.DrawLatex(0.12, 0.945, options.label)
    _ci_labels.append(t)

# --- Binning -----------------------------------------------------------------
# Log-spaced pT bins (efficiency / fake-rate), linear theta, fixed quality/reso.
nPt = max(1, options.nPtBins)
lo, hi = math.log10(options.ptMin), math.log10(max(options.ptMin * 1.0001, options.ptMax))
arrBins_pt = array('d', [10.0 ** (lo + (hi - lo) * i / nPt) for i in range(nPt + 1)])
nT = 12
arrBins_theta = array('d', [i * PI / nT for i in range(nT + 1)])

# --- JITted per-event analysis ----------------------------------------------
# Inputs are whole EDM4hep collections. Mirrors WriteTracksMT.C's selection,
# state choice, matching and quantity definitions.
ROOT.gInterpreter.Declare(r'''
#include "ROOT/RVec.hxx"
#include "edm4hep/MCParticleData.h"
#include "edm4hep/TrackData.h"
#include "edm4hep/TrackState.h"
#include "podio/ObjectID.h"
#include <cmath>
#include <algorithm>
#include <vector>

using ROOT::VecOps::RVec;

// EDM4hep / LCIO simulator-status bit indices
static const int BITCreatedInSimulation = 30;
static const int BITDecayedInTracker    = 27;
static inline bool checkBit(int v, int b) { return (v >> b) & 1; }

struct TrackResult {
  // truth (accepted MC particles) -- efficiency denominator
  RVec<double> truth_pt, truth_theta, truth_charge;
  // every selected track -- fake-rate denominator + quality
  RVec<double> trk_pt, trk_nHits, trk_nHoles, trk_chi2ndof;
  RVec<int>    trk_isReal;
  // matched track<->truth pairs -- efficiency numerator + resolutions
  RVec<double> m_true_pt, m_true_theta, m_true_charge, m_reco_pt, m_reco_d0,
               m_reco_z0, m_true_d0, m_true_z0, m_nHits, m_nHoles, m_chi2ndof;
  // event-level
  int nTracks = 0, nTruths = 0, nMatched = 0, nFake = 0;
  // false when the event fails the event-level selection (RDF filters on it)
  bool evtPass = true;
};

static inline bool mcAccept(const edm4hep::MCParticleData& m) {
  if (m.generatorStatus != 1) return false;
  if (m.charge == 0) return false;
  if (checkBit(m.simulatorStatus, BITCreatedInSimulation)) return false;
  if (checkBit(m.simulatorStatus, BITDecayedInTracker))    return false;
  return true;
}

// --- Selection (port of the macros' SelectionConfig.h) ----------------------
// Event: keep the event when at least one accepted primary MC particle falls
// inside the pt, theta AND |eta| windows simultaneously.
// Track: a track must satisfy every cut to enter any histogram.
struct EvtSel {
  float ptMin, ptMax, thetaMin, thetaMax, absEtaMin, absEtaMax;
};
struct TrkSel {
  float ptMin, ptMax, thetaMin, thetaMax, absEtaMin, absEtaMax,
        phiMin, phiMax, d0Min, d0Max, z0Min, z0Max, chi2Min, chi2Max;
  int   nHitsMin, nHolesMax;
};

static inline float thetaToEta(float theta) {
  const float eps = 1e-6f;
  float t = std::max(eps, std::min((float)M_PI - eps, theta));
  return -std::log(std::tan(t * 0.5f));
}

static inline bool mcPassesEvtSel(float pt, float theta, const EvtSel& c) {
  if (pt    < c.ptMin    || pt    > c.ptMax)    return false;
  if (theta < c.thetaMin || theta > c.thetaMax) return false;
  float absEta = std::abs(thetaToEta(theta));
  if (absEta < c.absEtaMin || absEta > c.absEtaMax) return false;
  return true;
}

static inline bool trackPasses(float pt, float theta, float phi, float d0, float z0,
                               float chi2ndof, int nHits, int nHoles, const TrkSel& c) {
  if (pt    < c.ptMin    || pt    > c.ptMax)    return false;
  if (theta < c.thetaMin || theta > c.thetaMax) return false;
  float absEta = std::abs(thetaToEta(theta));
  if (absEta < c.absEtaMin || absEta > c.absEtaMax) return false;
  if (phi   < c.phiMin    || phi   > c.phiMax)   return false;
  if (d0    < c.d0Min     || d0    > c.d0Max)    return false;
  if (z0    < c.z0Min     || z0    > c.z0Max)    return false;
  if (chi2ndof < c.chi2Min || chi2ndof > c.chi2Max) return false;
  if (nHits  < c.nHitsMin)   return false;
  if (nHoles > c.nHolesMax)  return false;
  return true;
}

// edm4hep TrackState::location values
static const int LOC_AtIP = 1, LOC_AtFirstHit = 2;

// Pick the track state to read the perigee parameters (D0/Z0/phi) from. The
// AtIP state holds the impact parameters w.r.t. the origin and is the correct
// choice -- but in this stack it is frequently broken (omega=nan, D0=Z0=0), so
// we fall back to AtFirstHit, then to any state with a finite curvature. (omega,
// hence pt and tanLambda, is identical across states, so this choice only
// affects D0/Z0/phi.) Returns an index into `states`, or -1 if none is valid.
static inline bool omegaOk(const edm4hep::TrackState& st) {
  return std::isfinite(st.omega) && std::abs(st.omega) > 1e-9;
}
static inline int chooseState(const edm4hep::TrackData& trk,
                              const RVec<edm4hep::TrackState>& states) {
  int b = trk.trackStates_begin, e = trk.trackStates_end;
  int atIP = -1, atFirst = -1, anyValid = -1;
  for (int i = b; i < e && i < (int)states.size(); ++i) {
    if (!omegaOk(states[i])) continue;
    if (anyValid < 0) anyValid = i;
    if (atIP < 0 && states[i].location == LOC_AtIP) atIP = i;
    if (atFirst < 0 && states[i].location == LOC_AtFirstHit) atFirst = i;
  }
  if (atIP >= 0) return atIP;
  if (atFirst >= 0) return atFirst;
  return anyValid;
}
static inline bool stateValid(int i, const RVec<edm4hep::TrackState>& states) {
  return i >= 0 && i < (int)states.size() && std::abs(states[i].omega) > 1e-9;
}

// Signed perigee impact parameters (w.r.t. the origin) of the helix defined by
// an MC particle's production vertex (mm), momentum (GeV) and charge in a
// solenoid field B (T, along +z). Returns d0,z0 in mm in the LCIO/edm4hep L3
// convention (x_PCA = -d0*sin(phi0)), matching the reconstructed TrackState.
struct ImpactParams { double d0; double z0; };
static inline ImpactParams trueImpactParams(double x0, double y0, double z0v,
                                            double px, double py, double pz,
                                            double q, double B) {
  const double FCT = 2.99792458e-4;            // pt[GeV] = FCT*B[T]*R[mm]
  double pt = std::hypot(px, py);
  if (pt <= 0.0 || q == 0.0 || B == 0.0) return {0.0, z0v};
  double R    = pt / (FCT * std::abs(B));      // radius of curvature [mm], >0
  double sgn  = std::copysign(1.0, q * B);     // sense of curvature
  double phiM = std::atan2(py, px);            // momentum azimuth at vertex
  // Centre of the transverse circle (vertex offset by R perpendicular to p).
  double xC = x0 + R * std::cos(phiM - sgn * M_PI_2);
  double yC = y0 + R * std::sin(phiM - sgn * M_PI_2);
  double D  = std::hypot(xC, yC);
  if (D == 0.0) return {0.0, z0v};
  // Point of closest approach to the origin: on the centre->origin line.
  double xPCA = xC * (1.0 - R / D);
  double yPCA = yC * (1.0 - R / D);
  double phi0 = std::atan2(yC, xC) + sgn * M_PI_2;   // momentum azimuth at PCA
  double d0   = yPCA * std::cos(phi0) - xPCA * std::sin(phi0);
  // z0 from the transverse arc swept between the vertex and the PCA.
  double aRef = std::atan2(y0 - yC, x0 - xC);
  double aPCA = std::atan2(yPCA - yC, xPCA - xC);
  double dphi = aPCA - aRef;
  while (dphi >  M_PI) dphi -= 2.0 * M_PI;
  while (dphi < -M_PI) dphi += 2.0 * M_PI;
  double z0 = z0v - sgn * R * (pz / pt) * dphi;
  return {d0, z0};
}

TrackResult studyTracks(const RVec<edm4hep::MCParticleData>& mcs,
                        const RVec<edm4hep::TrackData>&       tracks,
                        const RVec<edm4hep::TrackState>&      states,
                        const RVec<podio::ObjectID>&          selIdx,
                        const RVec<podio::ObjectID>&          relFrom,
                        const RVec<podio::ObjectID>&          relTo,
                        bool useAllTracks, double Bfield,
                        const EvtSel& evtSel, const TrkSel& trkSel)
{
  TrackResult r;
  const double kappa = 0.3 * Bfield / 1000.0;  // reco_pt = |kappa / omega|

  // --- event-level selection: at least one accepted MC particle in window ---
  r.evtPass = false;
  for (const auto& m : mcs) {
    if (!mcAccept(m)) continue;
    double pt    = std::hypot(m.momentum.x, m.momentum.y);
    double theta = std::atan2(pt, (double)m.momentum.z);
    if (mcPassesEvtSel(pt, theta, evtSel)) { r.evtPass = true; break; }
  }
  if (!r.evtPass) return r;

  // --- truth: accepted MC particles ---
  for (const auto& m : mcs) {
    if (!mcAccept(m)) continue;
    double pt    = std::hypot(m.momentum.x, m.momentum.y);
    double theta = std::atan2(pt, (double)m.momentum.z);
    r.truth_pt.push_back(pt);
    r.truth_theta.push_back(theta);
    r.truth_charge.push_back(m.charge);
    r.nTruths++;
  }

  // --- selected track indices (into `tracks`) ---
  RVec<int> trkIdx;
  if (useAllTracks) {
    for (size_t i = 0; i < tracks.size(); ++i) trkIdx.push_back((int)i);
  } else {
    for (const auto& o : selIdx) trkIdx.push_back(o.index);
  }
  r.nTracks = (int)trkIdx.size();
  std::vector<bool> matched(trkIdx.size(), false);

  // --- matching via relations: from -> track (into `tracks`), to -> MC ---
  for (size_t i = 0; i < relFrom.size() && i < relTo.size(); ++i) {
    int ti = relFrom[i].index;
    int mi = relTo[i].index;
    if (mi < 0 || mi >= (int)mcs.size()) continue;
    if (!mcAccept(mcs[mi])) continue;
    auto it = std::find(trkIdx.begin(), trkIdx.end(), ti);
    if (it == trkIdx.end()) continue;            // track not in selected set
    size_t pos = it - trkIdx.begin();
    if (matched[pos]) continue;                  // one truth per track
    if (ti < 0 || ti >= (int)tracks.size()) continue;
    const auto& trk = tracks[ti];
    int si = chooseState(trk, states);
    if (!stateValid(si, states)) continue;
    const auto& st = states[si];
    // Track selection, applied before the pair is counted as matched so that
    // the efficiency numerator and the per-track loop stay consistent.
    {
      double tpt   = std::abs(kappa / st.omega);
      double tth   = std::atan2(1.0, (double)st.tanLambda);
      int    tnh   = trk.trackerHits_end - trk.trackerHits_begin;
      double tchi2 = trk.ndf > 0 ? (double)trk.chi2 / trk.ndf : -1.0;
      if (!trackPasses(tpt, tth, st.phi, st.D0, st.Z0, tchi2, tnh, trk.Nholes, trkSel))
        continue;
    }
    matched[pos] = true;
    const auto& m = mcs[mi];
    r.m_true_pt.push_back(std::hypot(m.momentum.x, m.momentum.y));
    r.m_true_theta.push_back(std::atan2(std::hypot(m.momentum.x, m.momentum.y), (double)m.momentum.z));
    r.m_true_charge.push_back(m.charge);
    r.m_reco_pt.push_back(std::abs(kappa / st.omega));
    r.m_reco_d0.push_back(st.D0);
    r.m_reco_z0.push_back(st.Z0);
    ImpactParams ip = trueImpactParams(m.vertex.x, m.vertex.y, m.vertex.z,
                                       m.momentum.x, m.momentum.y, m.momentum.z,
                                       m.charge, Bfield);
    r.m_true_d0.push_back(ip.d0);
    r.m_true_z0.push_back(ip.z0);
    r.m_nHits.push_back(trk.trackerHits_end - trk.trackerHits_begin);
    r.m_nHoles.push_back(trk.Nholes);
    r.m_chi2ndof.push_back(trk.ndf > 0 ? (double)trk.chi2 / trk.ndf : -1.0);
    r.nMatched++;
  }

  // --- every selected track: quality + fake flag ---
  for (size_t k = 0; k < trkIdx.size(); ++k) {
    int ti = trkIdx[k];
    if (ti < 0 || ti >= (int)tracks.size()) continue;
    const auto& trk = tracks[ti];
    int si = chooseState(trk, states);
    if (!stateValid(si, states)) continue;       // skip pathological states
    const auto& st = states[si];
    double tpt   = std::abs(kappa / st.omega);
    double tth   = std::atan2(1.0, (double)st.tanLambda);
    int    tnh   = trk.trackerHits_end - trk.trackerHits_begin;
    double tchi2 = trk.ndf > 0 ? (double)trk.chi2 / trk.ndf : -1.0;
    if (!trackPasses(tpt, tth, st.phi, st.D0, st.Z0, tchi2, tnh, trk.Nholes, trkSel))
      continue;
    r.trk_pt.push_back(tpt);
    r.trk_nHits.push_back(tnh);
    r.trk_nHoles.push_back(trk.Nholes);
    r.trk_chi2ndof.push_back(tchi2);
    int isReal = matched[k] ? 1 : 0;
    r.trk_isReal.push_back(isReal);
    if (!isReal) r.nFake++;
  }
  return r;
}
''')

# --- Gather input files (single file or a directory tree) --------------------
files = ROOT.std.vector('string')()
if os.path.isdir(options.inFile):
    for root, _, names in os.walk(options.inFile):
        for name in names:
            if name.endswith('.root'):
                files.push_back(os.path.join(root, name))
else:
    files.push_back(options.inFile)

df = ROOT.RDataFrame("events", files)
cols = set(str(c) for c in df.GetColumnNames())

# A subset collection only exposes <coll>_objIdx; a full one exposes the data.
subset_idx = options.trackColl + "_objIdx"
use_all = subset_idx not in cols
store = options.trackStore if not use_all else options.trackColl
if store not in cols:
    raise RuntimeError("track data collection '%s' not found in input" % store)
states_col = "_%s_trackStates" % store
sel_expr = "ROOT::VecOps::RVec<podio::ObjectID>{}" if use_all else subset_idx
rel_from = "_%s_from" % options.relColl
rel_to   = "_%s_to" % options.relColl
for c in (rel_from, rel_to):
    if c not in cols:
        raise RuntimeError("relation branch '%s' not found in input" % c)

# %.9e always emits a decimal point and exponent, so the "f" suffix is a valid
# C++ float literal (%g would render 0.0 as "0", giving the invalid "0f").
evt_sel = "EvtSel{%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef}" % (
    options.evtPtMin, options.evtPtMax, options.evtThetaMin, options.evtThetaMax,
    options.evtAbsEtaMin, options.evtAbsEtaMax)
trk_sel = "TrkSel{%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%.9ef,%d,%d}" % (
    options.trkPtMin, options.trkPtMax, options.trkThetaMin, options.trkThetaMax,
    options.trkAbsEtaMin, options.trkAbsEtaMax, options.trkPhiMin, options.trkPhiMax,
    options.trkD0Min, options.trkD0Max, options.trkZ0Min, options.trkZ0Max,
    options.trkChi2Min, options.trkChi2Max, options.trkNHitsMin, options.trkNHolesMax)

df = df.Define("res", "studyTracks(%s, %s, %s, %s, %s, %s, %s, %g, %s, %s)" % (
    options.mcColl, store, states_col, sel_expr, rel_from, rel_to,
    "true" if use_all else "false", options.Bfield, evt_sel, trk_sel))

# Drop events failing the event-level selection before anything is histogrammed.
n_all = df.Count()
df = df.Filter("res.evtPass", "event selection")
n_sel = df.Count()

# Expose the helper's fields as columns.
for col, expr in [
    ("truth_pt", "res.truth_pt"), ("truth_theta", "res.truth_theta"),
    ("m_true_pt", "res.m_true_pt"), ("m_true_theta", "res.m_true_theta"),
    ("m_true_charge", "res.m_true_charge"), ("m_reco_pt", "res.m_reco_pt"),
    ("m_reco_d0", "res.m_reco_d0"), ("m_reco_z0", "res.m_reco_z0"),
    ("m_true_d0", "res.m_true_d0"), ("m_true_z0", "res.m_true_z0"),
    ("trk_pt", "res.trk_pt"), ("trk_nHits", "res.trk_nHits"),
    ("trk_nHoles", "res.trk_nHoles"), ("trk_chi2ndof", "res.trk_chi2ndof"),
    ("trk_isReal", "res.trk_isReal"), ("nTracks", "res.nTracks"),
    ("nTruths", "res.nTruths"), ("nMatched", "res.nMatched"), ("nFake", "res.nFake"),
]:
    df = df.Define(col, expr)

# Real / fake splits of the per-track quantities.
df = df.Define("real_pt", "trk_pt[trk_isReal == 1]")
df = df.Define("fake_pt", "trk_pt[trk_isReal == 0]")
df = df.Define("real_nHits", "trk_nHits[trk_isReal == 1]")
df = df.Define("real_nHoles", "trk_nHoles[trk_isReal == 1]")
df = df.Define("real_chi2ndof", "trk_chi2ndof[trk_isReal == 1]")

# Resolutions (RVec, one entry per matched pair). q/pt as in PlotTracks.C.
df = df.Define("res_qpt", "(m_true_charge/m_reco_pt - m_true_charge/m_true_pt) / (m_true_charge/m_true_pt)")
df = df.Define("res_d0", "m_reco_d0 - m_true_d0")
df = df.Define("res_z0", "m_reco_z0 - m_true_z0")

# --- Book histograms ---------------------------------------------------------
def H(name, nb, edges, col, df_=df):
    return df_.Histo1D(ROOT.RDF.TH1DModel(name, "", nb, edges), col)

def Hr(name, nb, x0, x1, col, df_=df):
    return df_.Histo1D(ROOT.RDF.TH1DModel(name, "", nb, x0, x1), col)

h_allTruths_pt   = H("allTruths_pt",   nPt, arrBins_pt, "truth_pt")
h_realTruths_pt  = H("realTruths_pt",  nPt, arrBins_pt, "m_true_pt")
h_allTruths_th   = H("allTruths_theta", nT, arrBins_theta, "truth_theta")
h_realTruths_th  = H("realTruths_theta", nT, arrBins_theta, "m_true_theta")

h_allTracks  = H("allTracks",  nPt, arrBins_pt, "trk_pt")
h_realTracks = H("realTracks", nPt, arrBins_pt, "real_pt")
h_fakeTracks = H("fakeTracks", nPt, arrBins_pt, "fake_pt")

h_all_nHits  = Hr("allTracks_nHits", 20, 0, 20, "trk_nHits")
h_all_nHoles = Hr("allTracks_nHoles", 10, 0, 10, "trk_nHoles")
h_all_chi2   = Hr("allTracks_chi2ndof", 50, 0, 10, "trk_chi2ndof")
h_real_nHits  = Hr("realTracks_nHits", 20, 0, 20, "real_nHits")
h_real_nHoles = Hr("realTracks_nHoles", 10, 0, 10, "real_nHoles")
h_real_chi2   = Hr("realTracks_chi2ndof", 50, 0, 10, "real_chi2ndof")

h_res_qpt = Hr("resolutions_q_over_pt", 100, -10, 10, "res_qpt")
h_res_d0  = Hr("resolutions_d0", 100, -10, 10, "res_d0")
h_res_z0  = Hr("resolutions_z0", 100, -10, 10, "res_z0")

h_nTracks = Hr("numberOfTracks", 100, 0, max(1, options.maxTracks), "nTracks")
# Per-event counters, the remaining columns of the macros' events_summary ntuple.
h_nTruths = Hr("numberOfTruths", 100, 0, max(1, options.maxTracks), "nTruths")
h_nMatched = Hr("numberOfMatched", 100, 0, max(1, options.maxTracks), "nMatched")
h_nFake = Hr("numberOfFake", 100, 0, max(1, options.maxTracks), "nFake")

histos_list = [h_allTruths_pt, h_realTruths_pt, h_allTruths_th, h_realTruths_th,
               h_allTracks, h_realTracks, h_fakeTracks,
               h_all_nHits, h_all_nHoles, h_all_chi2,
               h_real_nHits, h_real_nHoles, h_real_chi2,
               h_res_qpt, h_res_d0, h_res_z0,
               h_nTracks, h_nTruths, h_nMatched, h_nFake]

# --- Optional ntuples (truth / tracks / matched / events_summary) ------------
if options.writeTree:
    # The macros write flat TNtuples (one row per object). RDataFrame keeps the
    # per-event grouping, so these are trees of vector branches instead: same
    # content, one entry per event rather than per object. events_summary is
    # scalar and so is identical to the macros'.
    opts = ROOT.RDF.RSnapshotOptions()
    opts.fMode = "RECREATE"
    trees = [
        ("truth", ["truth_pt", "truth_theta"]),
        ("tracks", ["trk_pt", "trk_nHits", "trk_nHoles", "trk_chi2ndof", "trk_isReal"]),
        ("matched", ["m_true_pt", "m_true_theta", "m_true_charge", "m_reco_pt",
                     "m_reco_d0", "m_reco_z0", "m_true_d0", "m_true_z0",
                     "res_qpt", "res_d0", "res_z0"]),
        ("events_summary", ["nTracks", "nTruths", "nMatched", "nFake"]),
    ]
    for name, branches in trees:
        df.Snapshot(name, options.outFile, ROOT.std.vector('string')(branches), opts)
        opts.fMode = "UPDATE"   # first Snapshot creates the file, rest append

# --- Materialise (single event loop) -----------------------------------------
os.makedirs(options.outDir, exist_ok=True)
hist_vals = {h.GetValue().GetName(): h.GetValue() for h in histos_list}

# --- Plot helpers ------------------------------------------------------------
def save_efficiency(h_pass, h_total, xbins, xtitle, ytitle, name, png, logx=False):
    nb = len(xbins) - 1
    frame = ROOT.TH1D("frame_" + name, "", nb, xbins)
    frame.SetMinimum(0.0); frame.SetMaximum(1.1)
    frame.GetXaxis().SetTitle(xtitle); frame.GetYaxis().SetTitle(ytitle)
    frame.GetYaxis().SetTitleOffset(1.3); frame.GetXaxis().SetTitleOffset(1.2)
    c = ROOT.TCanvas("c_" + name, "", 800, 600)
    if logx:
        c.SetLogx()
        frame.GetXaxis().SetMoreLogLabels(False)
    frame.Draw("AXIS")
    eff = ROOT.TEfficiency(h_pass, h_total)
    eff.SetName(name)
    eff.SetLineColor(ROOT.kRed + 1); eff.SetMarkerColor(ROOT.kRed + 1)
    eff.SetMarkerStyle(20); eff.SetLineWidth(2)
    eff.Draw("E0 SAME")
    draw_ci_label()
    c.SaveAs(os.path.join(options.outDir, png))
    return eff

eff_pt = save_efficiency(hist_vals["realTruths_pt"], hist_vals["allTruths_pt"],
                         arrBins_pt, "Truth p_{T} [GeV]", "Tracking efficiency",
                         "eff_pt", plot_name("tracks_eff_pt"), logx=True)
eff_theta = save_efficiency(hist_vals["realTruths_theta"], hist_vals["allTruths_theta"],
                            arrBins_theta, "Truth #theta [rad]", "Tracking efficiency",
                            "eff_theta", plot_name("tracks_eff_theta"))
fake_rate = save_efficiency(hist_vals["fakeTracks"], hist_vals["allTracks"],
                            arrBins_pt, "Track p_{T} [GeV]", "Fake rate",
                            "fake_rate", plot_name("tracks_fake"), logx=True)

def save_res(h, xtitle, png, color):
    c = ROOT.TCanvas("c_" + h.GetName(), "", 800, 600)
    h.SetLineColor(color); h.SetLineWidth(2)
    h.GetXaxis().SetTitle(xtitle); h.GetYaxis().SetTitle("Entries")
    h.Draw("HIST")
    draw_ci_label()
    c.SaveAs(os.path.join(options.outDir, png))

save_res(hist_vals["resolutions_q_over_pt"], "#Delta(q/p_{T}) / (q/p_{T})",
         plot_name("tracks_res_qpt"), ROOT.kAzure + 1)
save_res(hist_vals["resolutions_d0"], "#Delta d_{0} [mm]", plot_name("tracks_res_d0"), ROOT.kRed + 1)
save_res(hist_vals["resolutions_z0"], "#Delta z_{0} [mm]", plot_name("tracks_res_z0"), ROOT.kGreen + 2)

# Combined resolution overlay (tallest first).
c_all = ROOT.TCanvas("c_res_all", "", 800, 600)
res_set = [(hist_vals["resolutions_d0"], ROOT.kRed + 1, "#Delta d_{0}"),
           (hist_vals["resolutions_z0"], ROOT.kGreen + 2, "#Delta z_{0}"),
           (hist_vals["resolutions_q_over_pt"], ROOT.kAzure + 1, "#Delta(q/p_{T})/(q/p_{T})")]
res_set.sort(key=lambda t: t[0].GetMaximum(), reverse=True)
leg_res = ROOT.TLegend(0.60, 0.72, 0.88, 0.88)
leg_res.SetBorderSize(0); leg_res.SetFillStyle(0)
for j, (h, col, lab) in enumerate(res_set):
    h.SetLineColor(col); h.SetLineWidth(2)
    if j == 0:
        h.GetXaxis().SetTitle("Resolution value"); h.GetYaxis().SetTitle("Entries")
        h.Draw("HIST")
    else:
        h.Draw("HIST SAME")
    leg_res.AddEntry(h, lab, "l")
leg_res.Draw(); draw_ci_label()
c_all.SaveAs(os.path.join(options.outDir, plot_name("tracks_res_all")))

# Track-quality: all vs real, real scaled to a right-hand axis (as in PlotTracks).
_keep = []
def save_quality(h_all, h_real, xtitle, png):
    c = ROOT.TCanvas("c_" + h_all.GetName(), "", 800, 600)
    c.SetRightMargin(0.18); c.SetTicky(0)
    scale = (h_all.GetMaximum() / h_real.GetMaximum()
             if h_all.GetMaximum() > 0 and h_real.GetMaximum() > 0 else 1.0)
    h_real_s = h_real.Clone(h_real.GetName() + "_scaled")
    h_real_s.Scale(scale)
    h_all.SetLineColor(ROOT.kAzure + 1); h_all.SetLineWidth(2)
    h_real_s.SetLineColor(ROOT.kRed + 1); h_real_s.SetLineWidth(2)
    h_all.GetXaxis().SetTitle(xtitle); h_all.GetYaxis().SetTitle("Entries (all tracks)")
    h_all.Draw("HIST"); h_real_s.Draw("HIST SAME")
    leg = ROOT.TLegend(0.45, 0.75, 0.83, 0.88)
    leg.SetBorderSize(0); leg.SetFillStyle(0)
    leg.AddEntry(h_all, "All tracks", "l")
    leg.AddEntry(h_real_s, "Matched tracks (right axis)", "l")
    leg.Draw()
    c.Update()
    xmax = h_all.GetXaxis().GetXmax()
    ax = ROOT.TGaxis(xmax, 0, xmax, h_all.GetMaximum(), 0, h_real.GetMaximum(), 510, "+L")
    ax.SetTitle("Entries (matched tracks)"); ax.SetTitleOffset(1.2)
    ax.SetLineColor(ROOT.kRed + 1); ax.SetLabelColor(ROOT.kRed + 1); ax.SetTitleColor(ROOT.kRed + 1)
    ax.SetLabelFont(42); ax.SetTitleFont(42)
    ax.Draw()
    draw_ci_label()
    c.SaveAs(os.path.join(options.outDir, png))
    _keep.extend([h_real_s, ax, leg])

save_quality(hist_vals["allTracks_nHits"], hist_vals["realTracks_nHits"],
             "Number of hits", plot_name("tracks_nHits"))
save_quality(hist_vals["allTracks_nHoles"], hist_vals["realTracks_nHoles"],
             "Number of holes", plot_name("tracks_nHoles"))
save_quality(hist_vals["allTracks_chi2ndof"], hist_vals["realTracks_chi2ndof"],
             "#chi^{2}/ndof", plot_name("tracks_chi2"))

# Tracks per event.
c_nt = ROOT.TCanvas("c_numberOfTracks", "", 800, 600)
h_nt = hist_vals["numberOfTracks"]
h_nt.SetLineColor(ROOT.kAzure + 1); h_nt.SetLineWidth(2)
h_nt.GetXaxis().SetTitle("Number of tracks"); h_nt.GetYaxis().SetTitle("Events")
h_nt.Draw("HIST"); draw_ci_label()
c_nt.SaveAs(os.path.join(options.outDir, plot_name("tracks_nTracks")))

# --- Console summary ---------------------------------------------------------
n_truth = hist_vals["allTruths_pt"].Integral()
n_match = hist_vals["realTruths_pt"].Integral()
n_trk   = hist_vals["allTracks"].Integral()
n_fake  = hist_vals["fakeTracks"].Integral()
print("\n=== Track validation summary (%s) ===" % options.trackColl)
print("  events          : %d selected / %d total" % (n_sel.GetValue(), n_all.GetValue()))
print("  truth particles : %d" % int(n_truth))
print("  matched (eff num): %d   -> efficiency = %.4f" % (int(n_match), n_match / n_truth if n_truth else 0.0))
print("  tracks          : %d   fake = %d   -> fake rate = %.4f"
      % (int(n_trk), int(n_fake), n_fake / n_trk if n_trk else 0.0))
print("  <tracks/event>  : %.2f" % h_nt.GetMean())
print("=====================================\n")

# --- Write the output ROOT file ----------------------------------------------
out = ROOT.TFile(options.outFile, 'UPDATE' if options.writeTree else 'RECREATE')
for h in histos_list:
    h.GetValue().Write()
eff_pt.Write(); eff_theta.Write(); fake_rate.Write()
out.Close()

write_fragment(
    options.metrics,
    study="tracks",
    input_path=options.inFile,
    producer_path=__file__,
    total_events=n_all.GetValue(),
    selected_events=n_sel.GetValue(),
    configuration={
        "collections": {
            "truth": options.mcColl,
            "tracks": options.trackColl,
            "track_store": options.trackStore,
            "relations": options.relColl,
            "uses_full_track_collection": use_all,
        },
        "magnetic_field_t": options.Bfield,
        "histogram_binning": {
            "pt_gev": [options.ptMin, options.ptMax],
            "pt_bins": nPt,
        },
        "event_selection": {
            "pt_gev": [options.evtPtMin, options.evtPtMax],
            "theta_rad": [options.evtThetaMin, options.evtThetaMax],
            "abs_eta": [options.evtAbsEtaMin, options.evtAbsEtaMax],
        },
        "track_selection": {
            "pt_gev": [options.trkPtMin, options.trkPtMax],
            "theta_rad": [options.trkThetaMin, options.trkThetaMax],
            "abs_eta": [options.trkAbsEtaMin, options.trkAbsEtaMax],
            "phi_rad": [options.trkPhiMin, options.trkPhiMax],
            "d0_mm": [options.trkD0Min, options.trkD0Max],
            "z0_mm": [options.trkZ0Min, options.trkZ0Max],
            "chi2_over_ndof": [options.trkChi2Min, options.trkChi2Max],
            "minimum_hits": options.trkNHitsMin,
            "maximum_holes": options.trkNHolesMax,
        },
    },
    metrics={
        "truth_particles": int(round(n_truth)),
        "matched_truth_particles": int(round(n_match)),
        "tracking_efficiency": fraction(n_match, n_truth),
        "tracks": int(round(n_trk)),
        "fake_tracks": int(round(n_fake)),
        "fake_rate": fraction(n_fake, n_trk),
        "track_multiplicity": histogram_summary(h_nt),
        "track_quality": {
            "hits": histogram_summary(hist_vals["allTracks_nHits"]),
            "holes": histogram_summary(hist_vals["allTracks_nHoles"]),
            "chi2_over_ndof": histogram_summary(hist_vals["allTracks_chi2ndof"]),
        },
        "resolution": {
            "relative_q_over_pt": histogram_summary(
                hist_vals["resolutions_q_over_pt"]
            ),
            "d0_mm": histogram_summary(hist_vals["resolutions_d0"]),
            "z0_mm": histogram_summary(hist_vals["resolutions_z0"]),
        },
    },
)
