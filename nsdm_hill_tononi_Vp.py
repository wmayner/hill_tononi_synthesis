# This tutorial shows you how to implement a simplified version of the
# Hill-Tononi model of the early visual pathway using the NEST Topology
# module.  The model is described in the paper
#
#   S. L. Hill and G. Tononi.
#   Modeling Sleep and Wakefulness in the Thalamocortical System.
#   J Neurophysiology **93**:1671-1698 (2005).
#   Freely available via `doi 10.1152/jn.00915.2004
#   <http://dx.doi.org/10.1152/jn.00915.2004>`_.
#
# And is based on the NEST Topology example of the Hill-Tononi model
# implement by Hans Ekkehard Plesser, which can be found here:
#
# https://github.com/nest/nest-simulator/blob/master/topology/examples/hill_tononi_Vp.py
#
# Authors: Leonardo Barbosa and Keiko Fujii
# Date:    21 September 2016




SHOW_FIGURES = False

import pylab
if not SHOW_FIGURES:
    pylab_show = pylab.show
    def nop(s=None): pass
    pylab.show = nop
else:
    pylab.ion()

import matplotlib.pyplot as plt

# Leonardo: I need to import readline for some reason, otherwise nest wont work
import readline

# Load pynest
import nest
import nest.topology as topo
from nest import raster_plot

# Make sure we start with a clean slate, even if we re-run the script
# in the same Python session.
nest.ResetKernel()

# set multi-thread on
nest.SetKernelStatus({"local_num_threads": 16})

# initialize random seed
import time
nest.SetKernelStatus({'grng_seed' : int(round(time.time() * 1000))})

# Other generic imports
import math
import numpy as np
import scipy.io
import pickle

# --- keiko 9/14/2016
# Import csv to save V_m data
import csv
#f_Vm = open('V_m.csv', 'w')
#writer_Vm = csv.writer(f_Vm)
#f_idx = open('idx.csv', 'w')
#writer_idx = csv.writer(f_idx)

# Configurable Parameters
# =======================
#
# Here we define those parameters that we take to be
# configurable. The choice of configurable parameters is obviously
# arbitrary, and in practice one would have far more configurable
# parameters. We restrict ourselves to:
#
# - Network size in neurons ``N``, each layer is ``N x N``.
# - Network size in subtended visual angle ``visSize``, in degree.
# - Temporal frequency of drifting grating input ``f_dg``, in Hz.
# - Spatial wavelength and direction of drifting grating input,
#   ``lambda_dg`` and ``phi_dg``, in degree/radian.
# - Background firing rate of retinal nodes and modulation amplitude,
#   ``retDC`` and ``retAC``, in Hz.
# - Simulation duration ``simtime``; actual simulation is split into
#   intervals of ``sim_interval`` length, so that the network state
#   can be visualized in those intervals. Times are in ms.
Params = {'N'           :     40,
          'visSize'     :    8.0,
          'f_dg'        :    0.0,
          #'lambda_dg'   :    2.0, # spatial structure
          'lambda_dg'   :   -1.0, # random: each pixel with random lambda_dg / phi_dg
          'phi_dg'      :    0.0,
          'retDC'       :   30.0,
          'retAC'       :   30.0,
          'simtime'     :   40.0,
          'sim_interval':    2.0
          }

# Set folder name from parameter names

folder_name = "sim_%d_" % isim
for p,v in Params.items():
    folder_name += p + "_%.2f_" % v

# Neuron Models
# =============
#
# We declare models in two steps:
#
# 1. We define a dictionary specifying the NEST neuron model to use
#    as well as the parameters for that model.
# #. We create three copies of this dictionary with parameters
#    adjusted to the three model variants specified in Table~2 of
#    Hill & Tononi (2005) (cortical excitatory, cortical inhibitory,
#    thalamic)
#
# In addition, we declare the models for the stimulation and
# recording devices.
#
# The general neuron model
# ------------------------
#
# We use the ``iaf_cond_alpha`` neuron, which is an
# integrate-and-fire neuron with two conductance-based synapses which
# have alpha-function time course.  Any input with positive weights
# will automatically directed to the synapse labeled ``_ex``, any
# with negative weights to the synapes labeled ``_in``.  We define
# **all** parameters explicitly here, so that no information is
# hidden in the model definition in NEST. ``V_m`` is the membrane
# potential to which the model neurons will be initialized.
# The model equations and parameters for the Hill-Tononi neuron model
# are given on pp. 1677f and Tables 2 and 3 in that paper. Note some
# peculiarities and adjustments:
#
# - Hill & Tononi specify their model in terms of the membrane time
#   constant, while the ``iaf_cond_alpha`` model is based on the
#   membrane capcitance. Interestingly, conducantces are unitless in
#   the H&T model. We thus can use the time constant directly as
#   membrane capacitance.
# - The model includes sodium and potassium leak conductances. We
#   combine these into a single one as follows:
#$   \begin{equation}-g_{NaL}(V-E_{Na}) - g_{KL}(V-E_K)
#$      =
#$   -(g_{NaL}+g_{KL})\left(V-\frac{g_{NaL}E_{NaL}+g_{KL}E_K}{g_{NaL}g_{KL}}\right)
#$   \end{equation}
# - We write the resulting expressions for g_L and E_L explicitly
#   below, to avoid errors in copying from our pocket calculator.
# - The paper gives a range of 1.0-1.85 for g_{KL}, we choose 1.5
#   here.
# - The Hill-Tononi model has no explicit reset or refractory
#   time. We arbitrarily set V_reset and t_ref.
# - The paper uses double exponential time courses for the synaptic
#   conductances, with separate time constants for the rising and
#   fallings flanks. Alpha functions have only a single time
#   constant: we use twice the rising time constant given by Hill and
#   Tononi.
# - In the general model below, we use the values for the cortical
#   excitatory cells as defaults. Values will then be adapted below.
#
nest.CopyModel('iaf_cond_alpha', 'NeuronModel',
               params = {'C_m'       :  16.0,
                         'E_L'       : (0.2 * 30.0 + 1.5 * -90.0)/(0.2 + 1.5),
                         'g_L'       : 0.2 + 1.5,
                         #'E_L'       : 30.0,
                         #'g_L'       : 0.2,
                         'E_ex'      :   0.0,
                         'E_in'      : -70.0,
                         'V_reset'   : -60.0,
                         'V_th'      : -51.0,
                         't_ref'     :   2.0,
                         'tau_syn_ex':   1.0,
                         'tau_syn_in':   2.0,
                         'I_e'       :   0.0,
                         'V_m'       : -70.0})

# Adaptation of models for different populations
# ----------------------------------------------

# We must copy the `NeuronModel` dictionary explicitly, otherwise
# Python would just create a reference.

# Cortical excitatory cells
# .........................
# Parameters are the same as above, so we need not adapt anything
nest.CopyModel('NeuronModel', 'CtxExNeuron')

# Cortical inhibitory cells
# .........................
nest.CopyModel('NeuronModel', 'CtxInNeuron',
               params = {'C_m'  :   8.0,
                         'V_th' : -53.0,
                         't_ref':   1.0})

# Thalamic cells
# ..............
nest.CopyModel('NeuronModel', 'ThalamicNeuron',
               params = {'C_m'  :   8.0,
                         'V_th' : -53.0,
                         't_ref':   1.0,
                         'E_in' : -80.0})

# Input generating nodes
# ----------------------

# Input is generated by sinusoidally modulate Poisson generators,
# organized in a square layer of retina nodes. These nodes require a
# slightly more complicated initialization than all other elements of
# the network:
#
# - Average firing rate ``rate``, firing rate modulation depth ``amplitude``, and
#   temporal modulation frequency ``frequency`` are the same for all retinal
#   nodes and are set directly below.
# - The temporal phase ``phase`` of each node depends on its position in
#   the grating and can only be assigned after the retinal layer has
#   been created. We therefore specify a function for initalizing the
#   ``phase``. This function will be called for each node.
def phaseInit(pos, lam, alpha):
    '''Initializer function for phase of drifting grating nodes.

       pos  : position (x,y) of node, in degree
       lam  : wavelength of grating, in degree
       alpha: angle of grating in radian, zero is horizontal

       Returns number to be used as phase of sinusoidal Poisson generator.
    '''
    return 360.0 / lam * (math.cos(alpha) * pos[0] + math.sin(alpha) * pos[1])

nest.CopyModel('sinusoidal_poisson_generator', 'RetinaNode',
               params = {'amplitude': Params['retAC'],
                         'rate'     : Params['retDC'] + 30 * np.random.rand(),
                         'frequency': Params['f_dg'],
                         'phase'    : 0.0,
                         'individual_spike_trains': True})

# Recording nodes
# ---------------

# We use the new ``multimeter`` device for recording from the model
# neurons. At present, ``iaf_cond_alpha`` is one of few models
# supporting ``multimeter`` recording.  Support for more models will
# be added soon; until then, you need to use ``voltmeter`` to record
# from other models.
#
# We configure multimeter to record membrane potential to membrane
# potential at certain intervals to memory only. We record the GID of
# the recorded neurons, but not the time.
nest.CopyModel('multimeter', 'RecordingNode',
               params = {'interval'   : Params['sim_interval'],
                         'record_from': ['V_m'],
                         'record_to'  : ['memory'],
                         'withgid'    : True,
                         'withtime'   : False})


# Populations
# ===========

# We now create the neuron populations in the model, again in the
# form of Python dictionaries. We define them in order from eye via
# thalamus to cortex.
#
# We first define a dictionary defining common properties for all
# populations
layerProps = {'rows'     : Params['N'],
              'columns'  : Params['N'],
              'extent'   : [Params['visSize'], Params['visSize']],
              'edge_wrap': True}
# This dictionary does not yet specify the elements to put into the
# layer, since they will differ from layer to layer. We will add them
# below by updating the ``'elements'`` dictionary entry for each
# population.

# Retina
# ------
layerProps.update({'elements': 'RetinaNode'})
retina = topo.CreateLayer(layerProps)

# Original: Gabor retina input

if Params['lambda_dg'] >= 0:
    # Now set phases of retinal oscillators; we use a list comprehension instead
    # of a loop.
    [nest.SetStatus([n], {"phase": phaseInit(topo.GetPosition([n])[0],
                                         Params["lambda_dg"],
                                         Params["phi_dg"])})
    for n in nest.GetLeaves(retina)[0]]
else:
    # Leonardo: Random retina input

    [nest.SetStatus([n], {"phase": phaseInit(topo.GetPosition([n])[0],
                                         np.pi * np.random.rand(),
                                         np.pi * np.random.rand())})
    for n in nest.GetLeaves(retina)[0]]

# Thalamus
# --------

# We first introduce specific neuron models for the thalamic relay
# cells and interneurons. These have identical properties, but by
# treating them as different models, we can address them specifically
# when building connections.
#
# We use a list comprehension to do the model copies.
[nest.CopyModel('ThalamicNeuron', SpecificModel) for SpecificModel in ('TpRelay', 'TpInter')]

# Now we can create the layer, with one relay cell and one
# interneuron per location:
layerProps.update({'elements': ['TpRelay', 'TpInter']})
Tp = topo.CreateLayer(layerProps)

# Reticular nucleus
# -----------------
# We follow the same approach as above, even though we have only a
# single neuron in each location.
[nest.CopyModel('ThalamicNeuron', SpecificModel) for SpecificModel in ('RpNeuron',)]
layerProps.update({'elements': 'RpNeuron'})
Rp = topo.CreateLayer(layerProps)

# Primary visual cortex
# ---------------------

# We follow again the same approach. We differentiate neuron types
# between layers and between pyramidal cells and interneurons. At
# each location, there are two pyramidal cells and one interneuron in
# each of layers 2-3, 4, and 5-6. Finally, we need to differentiate
# between vertically and horizontally tuned populations. When creating
# the populations, we create the vertically and the horizontally
# tuned populations as separate populations.

# We use list comprehesions to create all neuron types:
[nest.CopyModel('CtxExNeuron', layer+'pyr') for layer in ('L23','L4','L56')]
[nest.CopyModel('CtxInNeuron', layer+'in' ) for layer in ('L23','L4','L56')]

# Now we can create the populations, suffixes h and v indicate tuning
layerProps.update({'elements': ['L23pyr', 2, 'L23in', 1,
                                'L4pyr' , 2, 'L4in' , 1,
                                'L56pyr', 2, 'L56in', 1]})
Vp_h = topo.CreateLayer(layerProps)
Vp_v = topo.CreateLayer(layerProps)

# Collect all populations
# -----------------------

# For reference purposes, e.g., printing, we collect all populations
# in a tuple:
populations = (retina, Tp, Rp, Vp_h, Vp_v)

# Inspection
# ----------

# We can now look at the network using `PrintNetwork`:
nest.PrintNetwork()

# We can also try to plot a single layer in a network. For
# simplicity, we use Rp, which has only a single neuron per position.
#topo.PlotLayer(Rp)
#pylab.title('Layer Rp')
#pylab.show()


# Synapse models
# ==============

# Actual synapse dynamics, e.g., properties such as the synaptic time
# course, time constants, reversal potentials, are properties of
# neuron models in NEST and we set them in section `Neuron models`_
# above. When we refer to *synapse models* in NEST, we actually mean
# connectors which store information about connection weights and
# delays, as well as port numbers at the target neuron (``rport``)
# and implement synaptic plasticity. The latter two aspects are not
# relevant here.
#
# We just use NEST's ``static_synapse`` connector but copy it to
# synapse models ``AMPA`` and ``GABA_A`` for the sake of
# explicitness. Weights and delays are set as needed in section
# `Connections`_ below, as they are different from projection to
# projection. De facto, the sign of the synaptic weight decides
# whether input via a connection is handle by the ``_ex`` or the
# ``_in`` synapse.
nest.CopyModel('static_synapse', 'AMPA')
nest.CopyModel('static_synapse', 'GABA_A')

# Connections
# ====================

# Building connections is the most complex part of network
# construction. Connections are specified in Table 1 in the
# Hill-Tononi paper. As pointed out above, we only consider AMPA and
# GABA_A synapses here.  Adding other synapses is tedious work, but
# should pose no new principal challenges. We also use a uniform in
# stead of a Gaussian distribution for the weights.
#
# The model has two identical primary visual cortex populations,
# ``Vp_v`` and ``Vp_h``, tuned to vertical and horizonal gratings,
# respectively. The *only* difference in the connection patterns
# between the two populations is the thalamocortical input to layers
# L4 and L5-6 is from a population of 8x2 and 2x8 grid locations,
# respectively. Furthermore, inhibitory connection in cortex go to
# the opposing orientation population as to the own.
#
# To save us a lot of code doubling, we thus defined properties
# dictionaries for all connections first and then use this to connect
# both populations. We follow the subdivision of connections as in
# the Hill & Tononi paper.
#
# **Note:** Hill & Tononi state that their model spans 8 degrees of
# visual angle and stimuli are specified according to this. On the
# other hand, all connection patterns are defined in terms of cell
# grid positions. Since the NEST Topology Module defines connection
# patterns in terms of the extent given in degrees, we need to apply
# the following scaling factor to all lengths in connections:
dpc = Params['visSize'] / (Params['N'] - 1)

# We will collect all same-orientation cortico-cortical connections in
ccConnections = []
# the cross-orientation cortico-cortical connections in
ccxConnections = []
# and all cortico-thalamic connections in
ctConnections = []

# Horizontal intralaminar
# -----------------------
# *Note:* "Horizontal" means "within the same cortical layer" in this
# case.
#
# We first define a dictionary with the (most) common properties for
# horizontal intralaminar connection. We then create copies in which
# we adapt those values that need adapting, and
horIntraBase = {"connection_type": "divergent",
                "synapse_model": "AMPA",
                "mask": {"circular": {"radius": 12.0 * dpc}},
                "kernel": {"gaussian": {"p_center": 0.05, "sigma": 7.5 * dpc}},
                "weights": 1.0,
                "delays": {"uniform": {"min": 1.75, "max": 2.25}}}

# We use a loop to do the for for us. The loop runs over a list of
# dictionaries with all values that need updating
for conn in [{"sources": {"model": "L23pyr"}, "targets": {"model": "L23pyr"}},
             {"sources": {"model": "L23pyr"}, "targets": {"model": "L23in" }},
             {"sources": {"model": "L4pyr" }, "targets": {"model": "L4pyr" },
              "mask"   : {"circular": {"radius": 7.0 * dpc}}},
             {"sources": {"model": "L4pyr" }, "targets": {"model": "L4in"  },
              "mask"   : {"circular": {"radius": 7.0 * dpc}}},
             {"sources": {"model": "L56pyr"}, "targets": {"model": "L56pyr" }},
             {"sources": {"model": "L56pyr"}, "targets": {"model": "L56in"  }}]:
    ndict = horIntraBase.copy()
    ndict.update(conn)
    ccConnections.append(ndict)

# Vertical intralaminar
# -----------------------
# *Note:* "Vertical" means "between cortical layers" in this
# case.
#
# We proceed as above.
verIntraBase = {"connection_type": "divergent",
                "synapse_model": "AMPA",
                "mask": {"circular": {"radius": 2.0 * dpc}},
                "kernel": {"gaussian": {"p_center": 1.0, "sigma": 7.5 * dpc}},
                "weights": 2.0,
                "delays": {"uniform": {"min": 1.75, "max": 2.25}}}

for conn in [{"sources": {"model": "L23pyr"}, "targets": {"model": "L56pyr"}, "weights": 1.0},
             {"sources": {"model": "L23pyr"}, "targets": {"model": "L56in"}, "weights": 1.0}, #---keiko
             #{"sources": {"model": "L23pyr"}, "targets": {"model": "L23in"}, "weights": 1.0}, #---original
             {"sources": {"model": "L4pyr" }, "targets": {"model": "L23pyr"}},
             {"sources": {"model": "L4pyr" }, "targets": {"model": "L23in" }},
             {"sources": {"model": "L56pyr"}, "targets": {"model": "L23pyr"}},
             {"sources": {"model": "L56pyr"}, "targets": {"model": "L23in" }},
             {"sources": {"model": "L56pyr"}, "targets": {"model": "L4pyr" }},
             {"sources": {"model": "L56pyr"}, "targets": {"model": "L4in"  }}]:
    ndict = verIntraBase.copy()
    ndict.update(conn)
    ccConnections.append(ndict)

# Intracortical inhibitory
# ------------------------
#
# We proceed as above, with the following difference: each connection
# is added to the same-orientation and the cross-orientation list of
# connections.
#
# **Note:** Weights increased from -1.0 to -2.0, to make up for missing GabaB
#
# Note that we have to specify the **weight with negative sign** to make
# the connections inhibitory.
intraInhBase = {"connection_type": "divergent",
                "synapse_model": "GABA_A",
                "mask": {"circular": {"radius": 7.0 * dpc}},
                "kernel": {"gaussian": {"p_center": 0.25, "sigma": 7.5 * dpc}},
                "weights": -2.0,
                "delays": {"uniform": {"min": 1.75, "max": 2.25}}}

# We use a loop to do the for for us. The loop runs over a list of
# dictionaries with all values that need updating
for conn in [{"sources": {"model": "L23in"}, "targets": {"model": "L23pyr"}},
             {"sources": {"model": "L23in"}, "targets": {"model": "L23in" }},
             {"sources": {"model": "L4in" }, "targets": {"model": "L4pyr" }},
             {"sources": {"model": "L4in" }, "targets": {"model": "L4in"  }},
             {"sources": {"model": "L56in"}, "targets": {"model": "L56pyr"}},
             {"sources": {"model": "L56in"}, "targets": {"model": "L56in" }}]:
    ndict = intraInhBase.copy()
    ndict.update(conn)
    ccConnections.append(ndict)
    ccxConnections.append(ndict)

# Corticothalamic
# ---------------
corThalBase = {"connection_type": "divergent",
               "synapse_model": "AMPA",
               "mask": {"circular": {"radius": 5.0 * dpc}},
               "kernel": {"gaussian": {"p_center": 0.5, "sigma": 7.5 * dpc}},
               "weights": 1.0,
               "delays": {"uniform": {"min": 7.5, "max": 8.5}}}

# We use a loop to do the for for us. The loop runs over a list of
# dictionaries with all values that need updating
for conn in [{"sources": {"model": "L56pyr"}, "targets": {"model": "TpRelay" }},
             {"sources": {"model": "L56pyr"}, "targets": {"model": "TpInter" }}]:
    #ndict = corThalBase.copy() #---keiko
    ndict = intraInhBase.copy() #---original
    ndict.update(conn)
    ctConnections.append(ndict)

# Corticoreticular
# ----------------

# In this case, there is only a single connection, so we write the
# dictionary itself; it is very similar to the corThalBase, and to
# show that, we copy first, then update. We need no ``targets`` entry,
# since Rp has only one neuron per location.
corRet = corThalBase.copy()
corRet.update({"sources": {"model": "L56pyr"}, "weights": 2.5})


# Build all connections beginning in cortex
# -----------------------------------------

# Cortico-cortical, same orientation
print("Connecting: cortico-cortical, same orientation")
[topo.ConnectLayers(Vp_h, Vp_h, conn) for conn in ccConnections]
[topo.ConnectLayers(Vp_v, Vp_v, conn) for conn in ccConnections]

# Cortico-cortical, cross-orientation
print("Connecting: cortico-cortical, other orientation")
[topo.ConnectLayers(Vp_h, Vp_v, conn) for conn in ccxConnections]
[topo.ConnectLayers(Vp_v, Vp_h, conn) for conn in ccxConnections]

# Cortico-thalamic connections
print("Connecting: cortico-thalamic")
[topo.ConnectLayers(Vp_h, Tp, conn) for conn in ctConnections]
[topo.ConnectLayers(Vp_v, Tp, conn) for conn in ctConnections]
topo.ConnectLayers(Vp_h, Rp, corRet)
topo.ConnectLayers(Vp_v, Rp, corRet)

# Thalamo-cortical connections
# ----------------------------

# **Note:** According to the text on p. 1674, bottom right, of
# the Hill & Tononi paper, thalamocortical connections are
# created by selecting from the thalamic population for each
# L4 pyramidal cell, ie, are *convergent* connections.
#
# We first handle the rectangular thalamocortical connections.
thalCorRect = {"connection_type": "convergent",
               "sources": {"model": "TpRelay"},
               "synapse_model": "AMPA",
               "weights": 5.0,
               "delays": {"uniform": {"min": 2.75, "max": 3.25}}}

print("Connecting: thalamo-cortical")

# Horizontally tuned
thalCorRect.update({"mask": {"rectangular": {"lower_left" : [-4.0*dpc, -1.0*dpc],
                                             "upper_right": [ 4.0*dpc,  1.0*dpc]}}})
for conn in [{"targets": {"model": "L4pyr" }, "kernel": 0.5},
             {"targets": {"model": "L56pyr"}, "kernel": 0.3}]:
    thalCorRect.update(conn)
    topo.ConnectLayers(Tp, Vp_h, thalCorRect)

# Vertically tuned
thalCorRect.update({"mask": {"rectangular": {"lower_left" : [-1.0*dpc, -4.0*dpc],
                                             "upper_right": [ 1.0*dpc,  4.0*dpc]}}})
for conn in [{"targets": {"model": "L4pyr" }, "kernel": 0.5},
             {"targets": {"model": "L56pyr"}, "kernel": 0.3}]:
    thalCorRect.update(conn)
    topo.ConnectLayers(Tp, Vp_v, thalCorRect)

# Diffuse connections
thalCorDiff = {"connection_type": "convergent",
               "sources": {"model": "TpRelay"},
               "synapse_model": "AMPA",
               "weights": 5.0,
               "mask": {"circular": {"radius": 5.0 * dpc}},
               "kernel": {"gaussian": {"p_center": 0.1, "sigma": 7.5 * dpc}},
               "delays": {"uniform": {"min": 2.75, "max": 3.25}}}

#---keiko
for conn in [{"targets": {"model": "L4in"}},
             {"targets": {"model": "L56in"}}]:
#---original
#for conn in [{"targets": {"model": "L4pyr"}},
#             {"targets": {"model": "L56pyr"}}]:
    thalCorDiff.update(conn)
    topo.ConnectLayers(Tp, Vp_h, thalCorDiff)
    topo.ConnectLayers(Tp, Vp_v, thalCorDiff)

# Thalamic connections
# --------------------

# Connections inside thalamus, including Rp
#
# *Note:* In Hill & Tononi, the inhibition between Rp cells is mediated by
# GABA_B receptors. We use GABA_A receptors here to provide some self-dampening
# of Rp.
#
# **Note:** The following code had a serious bug in v. 0.1: During the first
# iteration of the loop, "synapse_model" and "weights" were set to "AMPA" and "0.1",
# respectively and remained unchanged, so that all connections were created as
# excitatory connections, even though they should have been inhibitory. We now
# specify synapse_model and weight explicitly for each connection to avoid this.

thalBase = {"connection_type": "divergent",
            "delays": {"uniform": {"min": 1.75, "max": 2.25}}}

print("Connecting: intra-thalamic")

for src, tgt, conn in [(Tp, Rp, {"sources": {"model": "TpRelay"},
                                 "synapse_model": "AMPA",
                                 "mask": {"circular": {"radius": 2.0 * dpc}},
                                 "kernel": {"gaussian": {"p_center": 1.0, "sigma": 7.5 * dpc}},
                                 "weights": 2.0}),
                       (Tp, Tp, {"sources": {"model": "TpInter"},
                                 "targets": {"model": "TpRelay"},
                                 "synapse_model": "GABA_A",
                                 "weights": -1.0,
                                 "mask": {"circular": {"radius": 2.0 * dpc}},
                                 "kernel": {"gaussian": {"p_center": 0.25, "sigma": 7.5 * dpc}}}),
                       (Tp, Tp, {"sources": {"model": "TpInter"},
                                 "targets": {"model": "TpInter"},
                                 "synapse_model": "GABA_A",
                                 "weights": -1.0,
                                 "mask": {"circular": {"radius": 2.0 * dpc}},
                                 "kernel": {"gaussian": {"p_center": 0.25, "sigma": 7.5 * dpc}}}),
                       (Rp, Tp, {"targets": {"model": "TpRelay"},
                                 "synapse_model": "GABA_A",
                                 "weights": -1.0,
                                 "mask": {"circular": {"radius": 12.0 * dpc}},
                                 "kernel": {"gaussian": {"p_center": 0.15, "sigma": 7.5 * dpc}}}),
                       (Rp, Tp, {"targets": {"model": "TpInter"},
                                 "synapse_model": "GABA_A",
                                 "weights": -1.0,
                                 "mask": {"circular": {"radius": 12.0 * dpc}},
                                 "kernel": {"gaussian": {"p_center": 0.15, "sigma": 7.5 * dpc}}}),
                       (Rp, Rp, {"targets": {"model": "RpNeuron"},
                                 "synapse_model": "GABA_A",
                                 "weights": -1.0,
                                 "mask": {"circular": {"radius": 12.0 * dpc}},
                                 "kernel": {"gaussian": {"p_center": 0.5, "sigma": 7.5 * dpc}}})]:
    thalBase.update(conn)
    topo.ConnectLayers(src, tgt, thalBase)

# Thalamic input
# --------------

# Input to the thalamus from the retina.
#
# **Note:** Hill & Tononi specify a delay of 0 ms for this connection.
# We use 1 ms here.
retThal = {"connection_type": "divergent",
           "synapse_model": "AMPA",
           "mask": {"circular": {"radius": 1.0 * dpc}},
           "kernel": {"gaussian": {"p_center": 0.75, "sigma": 2.5 * dpc}},
           "weights": 10.0,
           "delays": 1.0}

print("Connecting: retino-thalamic")

for conn in [{"targets": {"model": "TpRelay"}},
             {"targets": {"model": "TpInter"}}]:
    retThal.update(conn)
    topo.ConnectLayers(retina, Tp, retThal)


# Checks on connections
# ---------------------

# As a very simple check on the connections created, we inspect
# the connections from the central node of various layers.

# Connections from Retina to TpRelay
#topo.PlotTargets(topo.FindCenterElement(retina), Tp, 'TpRelay', 'AMPA')
#pylab.title('Connections Retina -> TpRelay')
#pylab.show()

# Connections from TpRelay to L4pyr in Vp (horizontally tuned)
#topo.PlotTargets(topo.FindCenterElement(Tp), Vp_h, 'L4pyr', 'AMPA')
#pylab.title('Connections TpRelay -> Vp(h) L4pyr')
#pylab.show()

# Connections from TpRelay to L4pyr in Vp (vertically tuned)
#topo.PlotTargets(topo.FindCenterElement(Tp), Vp_v, 'L4pyr', 'AMPA')
#pylab.title('Connections TpRelay -> Vp(v) L4pyr')
#pylab.show()

# Recording devices
# =================

    # This recording device setup is a bit makeshift. For each population
    # we want to record from, we create one ``multimeter``, then select
    # all nodes of the right model from the target population and
    # connect. ``loc`` is the subplot location for the layer.
    print("Connecting: Recording devices")
    recorders = {}
    for name, loc, population, model in [('TpRelay'   , 1, Tp  , 'TpRelay'),
                                         ('Rp'        , 2, Rp  , 'RpNeuron'),
                                         ('Vp_v L4pyr', 3, Vp_v, 'L4pyr'),
                                         ('Vp_h L4pyr', 4, Vp_h, 'L4pyr')]:
        recorders[name] = (nest.Create('RecordingNode'), loc)
        tgts = [nd for nd in nest.GetLeaves(population)[0]
                if nest.GetStatus([nd], 'model')[0]==model]
        nest.Connect(recorders[name][0], tgts)   # one recorder to all targets

    # create the spike detectors
    detectors = {}
    for name, population, model in [('Vp_v L4pyr', Vp_v, 'L4pyr'),
                                    ('Vp_h L4pyr', Vp_h, 'L4pyr'),
                                    ('Vp_v L23pyr', Vp_v, 'L23pyr'),
                                    ('Vp_h L23pyr', Vp_h, 'L23pyr'),
                                    ('Vp_v L56pyr', Vp_v, 'L56pyr'),
                                    ('Vp_h L56pyr', Vp_h, 'L56pyr'),
                                    ('TpRelay', Tp, 'TpRelay'),
                                    ('Rp', Rp, 'RpNeuron'),
                                    ('Retina', retina, 'RetinaNode')]:
        tgts = [nd for nd in nest.GetLeaves(population)[0]
                if nest.GetStatus([nd], 'model')[0]==model]
        detectors[name] = (nest.Create('spike_detector', params={"withgid": True, "withtime": True}), loc)
        print(name + ' : %d' % max(tgts))

        # TODO For some reason, some retina nodes have different synapse types. Connect one by one for now
        if name == 'Retina':
            for t in tgts:
                try:
                    nest.Connect([t], detectors[name][0])
                except:
                    print('%d did not work' % t)
        else:
            nest.Connect(tgts, detectors[name][0])


    # [n for n in nest.GetLeaves(retina)[0]]


for isim in range(1,201,1):
    # Example simulation
    # ====================

    # This simulation is set up to create a step-wise visualization of
    # the membrane potential. To do so, we simulate ``sim_interval``
    # milliseconds at a time, then read out data from the multimeters,
    # clear data from the multimeters and plot the data as pseudocolor
    # plots.

    # show time during simulation
    nest.SetStatus([0],{'print_time': True})

    #TODO check difference with respect to running each step at a time
    # run simulation
    nest.Simulate(Params['simtime'])

    import os.path

    data_folder = './data/' + folder_name + 'detectors'
    if not os.path.isdir(data_folder):
        os.makedirs(data_folder)

    figure_folder = './figures/' + folder_name + 'detectors'
    if not os.path.isdir(figure_folder):
        os.makedirs(figure_folder)

    # save raster plot and data
    for name, r in detectors.items():
        rec = r[0]

        # raster plot
        p = raster_plot.from_device(rec, hist=True)

        pylab.title(name)
        f = p[0].figure
        f.set_size_inches(15, 9)
        f.savefig(figure_folder + '/spikes_' + name + '.png', dpi=100)

        # data
        spikes = nest.GetStatus(rec, "events")[0]
        print ('Saving spikes for ' + name)
        with open(data_folder + '/spikes_' + name + '.pickle', 'w') as f:
            pickle.dump(spikes, f)

        scipy.io.savemat(data_folder + '/spikes_' + name + '.mat', mdict={'senders': spikes['senders'], 'times': spikes['times']})

        plt.close()

    # just for some information at the end
    #print(nest.GetKernelStatus())

    #--- keiko 9/14/2016
    #f_Vm.close()
    #f_idx.close()