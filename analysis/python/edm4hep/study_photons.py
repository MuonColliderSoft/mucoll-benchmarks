"""Photon performance study on EDM4hep reconstruction output (RDataFrame).

Modern, RDataFrame-based reimplementation that combines two steps that used to be
separate LCIO/ROOT macros:
  * the per-event analysis (https://github.com/madbaron/LCIOmacros/blob/master/study_photons.py)
  * the energy-resolution plotting (https://github.com/madbaron/PLOTmacros/blob/master/plot_photon_resolution.py)
adapted to the reco.edm4hep.root produced by the validation chain.

The reco file is a plain ROOT TTree ("events") with podio/EDM4hep dictionaries,
so it is read directly with RDataFrame. Whole collections are passed to a JITted
C++ helper, `studyPhoton`, which matches the closest PFO to the truth gun particle
and returns a PhotonResult. The energy resolution is derived directly from a 2D
(true energy vs relative response) histogram filled by RDataFrame, in the same run
-- it does not require the ntuple.

Outputs (written to the -o ROOT file): histograms truth_E/theta, matched_E/theta,
Npfo, pfo_type, the response histograms, the reso_E TGraphErrors, and the reso_theta
histogram, and the eff_E / eff_theta TEfficiency objects; plus reso_vs_E.png,
reso_vs_theta.png, photon_efficiency_vs_E.png, photon_efficiency_vs_theta.png
(and per-slice fit PNGs) under --outDir. The per-event photon_tree ntuple is
written only if --writeTree is given.

Usage:
    python study_photons.py -i reco.edm4hep.root -o histos_photon.root -d plots
"""
from optparse import OptionParser
from array import array
import os
import ROOT

#########################
parser = OptionParser()
parser.add_option('-i', '--inFile', help='--inFile reco.edm4hep.root',
                  type=str, default='reco.edm4hep.root')
parser.add_option('-o', '--outFile', help='--outFile histos_photon.root',
                  type=str, default='histos_photon.root')
parser.add_option('-d', '--outDir', help='--outDir directory for the .png plots',
                  type=str, default='.')
parser.add_option('--writeTree', action='store_true', default=False,
                  help='also write the photon_tree ntuple (off by default)')
(options, args) = parser.parse_args()

ROOT.gROOT.SetBatch(True)
ROOT.EnableImplicitMT()
ROOT.gStyle.SetOptStat(0)

# Stamp every plot with a provenance label (references kept to survive until SaveAs)
_ci_labels = []
def draw_ci_label():
    t = ROOT.TLatex()
    t.SetNDC()
    t.SetTextFont(42)
    t.SetTextSize(0.035)
    t.SetTextAlign(12)
    t.DrawLatex(0.15, 0.94, "CI-generated result")
    _ci_labels.append(t)

# Binning
arrBins_theta = array('d', (0., 30.*ROOT.TMath.Pi()/180., 40.*ROOT.TMath.Pi()/180., 50.*ROOT.TMath.Pi()/180., 60.*ROOT.TMath.Pi()/180., 70.*ROOT.TMath.Pi()/180.,
                            90.*ROOT.TMath.Pi()/180., 110.*ROOT.TMath.Pi()/180., 120.*ROOT.TMath.Pi()/180., 130.*ROOT.TMath.Pi()/180., 140.*ROOT.TMath.Pi()/180., 150.*ROOT.TMath.Pi()/180., ROOT.TMath.Pi()))
arrBins_E = array('d', (0., 5., 10., 15., 20., 25., 30., 40., 50., 75., 100.))
# Energy bins used to slice the response and build the resolution curve
arrBins_Eres = array('d', (0., 10., 20., 30., 40., 50., 75., 100.))

# JITted per-event analysis: delta-R matching of PFOs to the truth gun particle.
# Inputs are whole EDM4hep collections (RVec of POD "...Data" structs).
ROOT.gInterpreter.Declare(r'''
#include "ROOT/RVec.hxx"
#include "Math/Vector4D.h"
#include "Math/VectorUtil.h"
#include "edm4hep/MCParticleData.h"
#include "edm4hep/ReconstructedParticleData.h"
#include <cmath>

using ROOT::VecOps::RVec;
using ROOT::Math::PxPyPzEVector;
using ROOT::Math::VectorUtil::DeltaR;

struct PhotonResult {
  double E_truth=0, phi_truth=0, theta_truth=0;
  double Esum=-1, phi=-4, theta=-1, dR_match=999;
  int    n_pfos=0;
  RVec<int> matched_pdgs;
};

PhotonResult studyPhoton(const RVec<edm4hep::MCParticleData>& mcs,
                         const RVec<edm4hep::ReconstructedParticleData>& pfos)
{
  PhotonResult r;

  // Truth: the first MCParticle is always the gun. MCParticle energy is derived
  // as sqrt(p^2 + m^2), matching edm4hep::MCParticle::getEnergy().
  const auto& g = mcs[0];
  const double gE = std::sqrt(g.momentum.x*g.momentum.x + g.momentum.y*g.momentum.y +
                              g.momentum.z*g.momentum.z + g.mass*g.mass);
  PxPyPzEVector tlv(g.momentum.x, g.momentum.y, g.momentum.z, gE);
  r.E_truth = gE;
  r.phi_truth = tlv.Phi();
  r.theta_truth = tlv.Theta();

  // Matched candidate: the single PFO closest in delta-R to the truth
  r.n_pfos = pfos.size();
  int best = -1;
  double best_dR = 1e9;
  for (size_t i = 0; i < pfos.size(); ++i) {
    PxPyPzEVector v(pfos[i].momentum.x, pfos[i].momentum.y, pfos[i].momentum.z, pfos[i].energy);
    double d = DeltaR(v, tlv);
    if (d < best_dR) { best_dR = d; best = (int)i; }
  }
  if (best >= 0) {
    const auto& p = pfos[best];
    PxPyPzEVector v(p.momentum.x, p.momentum.y, p.momentum.z, p.energy);
    r.matched_pdgs.push_back(std::abs(p.PDG));
    r.Esum = v.E(); r.phi = v.Phi(); r.theta = v.Theta();
    r.dR_match = best_dR;
  }

  return r;
}
''')

# Gather input files (single file or a directory tree)
files = ROOT.std.vector('string')()
if os.path.isdir(options.inFile):
    for r, d, f in os.walk(options.inFile):
        for name in f:
            if name.endswith('.root'):
                files.push_back(os.path.join(r, name))
else:
    files.push_back(options.inFile)

df = ROOT.RDataFrame("events", files)
cols = set(str(c) for c in df.GetColumnNames())

# PFOs are present only if Pandora ran; fall back to an empty collection
pfo_expr = "PandoraPFOs" if "PandoraPFOs" in cols else "ROOT::VecOps::RVec<edm4hep::ReconstructedParticleData>{}"
df = df.Define("pfos", pfo_expr)

# Run the per-event analysis, then expose its fields as columns
df = df.Define("res", "studyPhoton(MCParticles, pfos)")
for col, expr in [
    ("E_truth", "res.E_truth"), ("phi_truth", "res.phi_truth"), ("theta_truth", "res.theta_truth"),
    ("E", "res.Esum"), ("phi", "res.phi"), ("theta", "res.theta"), ("dR_match", "res.dR_match"),
    ("Npfo", "res.n_pfos"), ("pfo_type_vals", "res.matched_pdgs"),
]:
    df = df.Define(col, expr)
# Relative energy response of the matched PFO (E_truth is always > 0 for the gun)
df = df.Define("response", "(E - E_truth) / E_truth")

# --- Histograms --------------------------------------------------------------
nE, nT, nEres = len(arrBins_E) - 1, len(arrBins_theta) - 1, len(arrBins_Eres) - 1
h_truth_E = df.Histo1D(ROOT.RDF.TH1DModel("truth_E", "truth_E", nE, arrBins_E), "E_truth")
h_truth_theta = df.Histo1D(ROOT.RDF.TH1DModel("truth_theta", "truth_theta", nT, arrBins_theta), "theta_truth")

df_matched = df.Filter("dR_match < 0.1")
h_matched_E = df_matched.Histo1D(ROOT.RDF.TH1DModel("matched_E", "matched_E", nE, arrBins_E), "E_truth")
h_matched_theta = df_matched.Histo1D(ROOT.RDF.TH1DModel("matched_theta", "matched_theta", nT, arrBins_theta), "theta_truth")

h_Npfo = df.Histo1D(ROOT.RDF.TH1DModel("Npfo", "Npfo", 1000, 0, 1000), "Npfo")
h_pfo_type = df.Histo1D(ROOT.RDF.TH1DModel("pfo_type", "pfo_type", 3000, 0, 3000), "pfo_type_vals")

h_response = df.Histo2D(ROOT.RDF.TH2DModel("photon_response", "photon_response", 1000, 0, 500, 1000, 0, 500), "E_truth", "E")
h_deltaresponse = df.Histo2D(ROOT.RDF.TH2DModel("delta_response", "delta_response", 100, 0, 500, 100, -1., 1.), "E_truth", "response")

# 2D response (true energy vs relative response) used to derive the resolution.
# Selection mirrors the plotting macro: matched, reconstructed, response > -0.5.
df_reso = df.Filter("dR_match < 0.1 && E > 0 && response > -0.5")
h_resp2d = df_reso.Histo2D(ROOT.RDF.TH2DModel("response_vs_Etruth", "response_vs_Etruth", nEres, arrBins_Eres, 250, -2.5, 2.5), "E_truth", "response")
h_resp_vs_theta = df_reso.Histo2D(ROOT.RDF.TH2DModel("response_vs_theta", "response_vs_theta", nT, arrBins_theta, 250, -2.5, 2.5), "theta_truth", "response")

histos_list = [h_truth_E, h_truth_theta, h_matched_E, h_matched_theta,
               h_Npfo, h_pfo_type, h_response, h_deltaresponse, h_resp2d, h_resp_vs_theta]

# --- Optional ntuple ---------------------------------------------------------
# Off by default; pass --writeTree to add it. Snapshot triggers the event loop
# (also materialising the histograms above) and creates the output file.
produce_tree = options.writeTree
if produce_tree:
    tree_cols = ROOT.std.vector('string')()
    for c in ["E", "phi", "theta", "E_truth", "phi_truth", "theta_truth"]:
        tree_cols.push_back(c)
    df.Snapshot("photon_tree", options.outFile, tree_cols)

# --- Energy resolution: Gaussian fit of the response in slices of true energy --
# Accessing a result materialises all booked histograms (single event loop).
resp2d = h_resp2d.GetValue()

slice_dir = os.path.join(options.outDir, "slices_ph")
os.makedirs(slice_dir, exist_ok=True)

e_arr, sigma_arr, e_err_arr, sigma_err_arr = array('d'), array('d'), array('d'), array('d')
cx = ROOT.TCanvas("cx", "", 800, 600)
xaxis = resp2d.GetXaxis()
for b in range(1, nEres + 1):
    proj = resp2d.ProjectionY("ph_E%g_py" % xaxis.GetBinLowEdge(b), b, b)
    if proj.GetEntries() < 10 or proj.GetRMS() <= 0:
        continue
    if xaxis.GetBinLowEdge(b) < 160.:
        lo, hi = proj.GetMean() - 2.*proj.GetRMS(), proj.GetMean() + 2.*proj.GetRMS()
    else:
        lo, hi = -0.15, 0.15
    gaussFit = ROOT.TF1("gaussfit", "gaus", lo, hi)
    gaussFit.SetParameter(1, proj.GetMean())
    gaussFit.SetParameter(2, proj.GetRMS())
    proj.Fit(gaussFit, "EQR")
    proj.Draw("HIST")
    gaussFit.Draw("LSAME")
    cx.SaveAs(os.path.join(slice_dir, proj.GetName() + ".png"))
    e_arr.append(xaxis.GetBinCenter(b))
    e_err_arr.append(0.)
    sigma_arr.append(gaussFit.GetParameter(2))
    sigma_err_arr.append(gaussFit.GetParError(2))

# --- Resolution curve sigma_E/E vs E -----------------------------------------
# (an empty array cannot be turned into a TGraphErrors buffer, so guard n == 0)
if len(e_arr) > 0:
    h_reso_E = ROOT.TGraphErrors(len(e_arr), e_arr, sigma_arr, e_err_arr, sigma_err_arr)
else:
    h_reso_E = ROOT.TGraphErrors()
h_reso_E.SetName("reso_E")
h_reso_E.SetTitle("")
h_reso_E.GetYaxis().SetTitle("Photon #sigma_{E}/E")
h_reso_E.GetXaxis().SetTitle("True photon energy [GeV]")
h_reso_E.GetYaxis().SetTitleOffset(1.4)
h_reso_E.SetLineColor(ROOT.kBlack)
h_reso_E.SetLineWidth(2)

resoFit = ROOT.TF1("resofit", "sqrt([0]*[0]/x+[1]*[1]/(x*x)+[2]*[2])", 20., 1000., 3)
resoFit.SetParNames("Stochastic", "Noise", "Constant")
resoFit.SetParameters(0.5, 0., 0.)
if h_reso_E.GetN() >= 3:
    h_reso_E.Fit(resoFit, "RQ")

c2 = ROOT.TCanvas("c2", "", 800, 600)
c2.SetLogy()
h_reso_E.Draw("AP")
if h_reso_E.GetN() > 0:
    h_reso_E.GetXaxis().SetRangeUser(10., 1000.)
    h_reso_E.GetYaxis().SetRangeUser(0.01, 0.5)
if h_reso_E.GetN() >= 3:
    resoFit.Draw("LSAME")
    h_reso_E.Draw("PSAME")
    t3 = ROOT.TLatex()
    t3.SetNDC()
    t3.SetTextFont(42)
    t3.SetTextSize(0.035)
    t3.DrawLatex(0.6, 0.72, 'Stochastic = %.3f' % resoFit.GetParameter(0))
    t3.DrawLatex(0.6, 0.66, 'Noise = %.3f' % resoFit.GetParameter(1))
    t3.DrawLatex(0.6, 0.60, 'Constant = %.3f' % resoFit.GetParameter(2))
draw_ci_label()
c2.SaveAs(os.path.join(options.outDir, "reso_vs_E.png"))

# --- Energy resolution vs theta ----------------------------------------------
# Gaussian fit of the relative response in slices of true theta.
resp_theta = h_resp_vs_theta.GetValue()
h_reso_theta = ROOT.TH1D("reso_theta", "", nT, arrBins_theta)
for b in range(1, nT + 1):
    proj = resp_theta.ProjectionY("reso_theta_py%d" % b, b, b)
    if proj.GetEntries() < 10 or proj.GetRMS() <= 0:
        continue
    gaussFit = ROOT.TF1("gthetafit", "gaus", proj.GetMean() - 2.*proj.GetRMS(), proj.GetMean() + 2.*proj.GetRMS())
    gaussFit.SetParameter(1, proj.GetMean())
    gaussFit.SetParameter(2, proj.GetRMS())
    proj.Fit(gaussFit, "EQR")
    h_reso_theta.SetBinContent(b, gaussFit.GetParameter(2))
    h_reso_theta.SetBinError(b, gaussFit.GetParError(2))

c3 = ROOT.TCanvas("c3", "", 800, 600)
h_reso_theta.SetTitle("")
h_reso_theta.SetLineColor(ROOT.kBlack)
h_reso_theta.SetLineWidth(2)
h_reso_theta.GetYaxis().SetTitle("Photon #sigma_{E}/E")
h_reso_theta.GetXaxis().SetTitle("Truth photon #theta [rad]")
h_reso_theta.GetYaxis().SetTitleOffset(1.4)
h_reso_theta.GetXaxis().SetTitleOffset(1.2)
h_reso_theta.Draw("E0")
draw_ci_label()
c3.SaveAs(os.path.join(options.outDir, "reso_vs_theta.png"))

# --- Reconstruction efficiency (TEfficiency = matched / truth) ----------------
def make_efficiency(h_pass, h_total, xbins, xtitle, name, png):
    frame = ROOT.TH1D("frame_" + name, "", len(xbins) - 1, xbins)
    frame.SetMinimum(0.0)
    frame.SetMaximum(1.05)
    frame.GetYaxis().SetTitle("Photon reconstruction efficiency")
    frame.GetXaxis().SetTitle(xtitle)
    frame.GetYaxis().SetTitleOffset(1.3)
    frame.GetXaxis().SetTitleOffset(1.2)
    c = ROOT.TCanvas("c_" + name, "", 800, 600)
    frame.Draw()
    eff = ROOT.TEfficiency(h_pass, h_total)
    eff.SetName(name)
    eff.SetLineColor(ROOT.kRed)
    eff.SetLineWidth(2)
    eff.Draw("E0 SAME")
    draw_ci_label()
    c.SaveAs(os.path.join(options.outDir, png))
    return eff

eff_E = make_efficiency(h_matched_E.GetValue(), h_truth_E.GetValue(), arrBins_E,
                        "Truth photon E [GeV]", "eff_E", "photon_efficiency_vs_E.png")
eff_theta = make_efficiency(h_matched_theta.GetValue(), h_truth_theta.GetValue(), arrBins_theta,
                            "Truth photon #theta [rad]", "eff_theta", "photon_efficiency_vs_theta.png")

# --- Write everything to the output ROOT file --------------------------------
# Append to the Snapshot output if a tree was produced, else create it fresh.
output_file = ROOT.TFile(options.outFile, 'UPDATE' if produce_tree else 'RECREATE')
for histo in histos_list:
    histo.GetValue().Write()
h_reso_E.Write()
h_reso_theta.Write()
eff_E.Write()
eff_theta.Write()
output_file.Close()
