

if __name__ == '__main__' and __package__ is None:
    from os import sys, path
    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import os
import numpy as np
import glob
import pickle
from pypci import pci
import time
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation

def update_line(num, data, line):
    line.set_data(data[..., :num])
    return line,

#

root_dir = '/home/leonardo/projects/nsdm/hill_tononi_synthesis/data'

#dir_to_load = '/sim_*_lambda_dg_-1.00*'
dir_to_load = '/sim_*_lambda_dg_2.00*'
#dir_to_load = '/sim_*_lambda_dg_8.00*'

files_to_load = '/spikes_Vp*L4*.pickle'
#files_to_load = '/spikes_Retina*.pickle'

all_folders = glob.glob(root_dir + dir_to_load )

# assume all simulations have the same number of files
first_folder = all_folders[0]
all_files = glob.glob(first_folder + files_to_load )
nfiles = len(all_files)
nfolders = len(all_folders)

with open(all_files[0], 'r') as f:
    data = pickle.load(f)

sd = data['senders']
ts = data['times']

ts = np.round(ts*10).astype('int')

mint = min(ts)
maxt = max(ts)
mindiff = min(np.diff(np.unique(ts)))
ntime = len(range(mint, maxt, mindiff)) + 1

#neurons = 1600
#nneurons = max(sd) - min(sd) + 1
# some times do not have all the neurons active in the session, so round up
nneurons = np.int64(np.ceil((max(sd) - min(sd) + 1)/100.)*100.)

downsample_neuron = 0
#downsample_neuron = 4
#downsample_neuron = 16
#nneurons = np.int64(nneurons/downsample_neuron)

# TODO assume they all have the same size!

ntime = 40

_all_sim = np.zeros((nfolders,nfiles,nneurons,ntime))

for folder_idx, this_folder in enumerate(all_folders):

    all_files = glob.glob(this_folder + files_to_load)

    # Set up formatting for the movie files
    #Writer = animation.writers['ffmpeg']
    #writer = Writer(fps=15, metadata=dict(artist='Me'), bitrate=1800)


    for files_idx, next_file in enumerate(all_files):

        print ('Loading ' + next_file)
        with open(next_file, 'r') as f:
            data = pickle.load(f)

        sd = data['senders']
        ts = data['times']

        #plt.plot(sd)
        #plt.show()

        #ts = np.round(ts*10).astype('int')
        ts = np.round(ts).astype('int')

        mint = min(ts)
        maxt = max(ts)
        mindiff = min(np.diff(np.unique(ts)))
        #ntime = len(range(mint, maxt, mindiff)) + 1

        #ntime = 40
        # ntime = 400

        neurons = 1600
        #nneurons = max(sd) - min(sd) + 1
        # some times do not have all the neurons active in the session, so round up
        #nneurons = np.int64(np.ceil((max(sd) - min(sd) + 1)/100.)*100.)
        #nneurons = np.int64(np.ceil((max(sd) - min(sd) + 1)/10.)*10.)

        this_neurons = np.zeros((nneurons, ntime))
        this_neurons[sd-min(sd), ts-mint] = 1.

        # TODO can use this to smooth
        #smoop = 10 # in samples!
        #this_neurons = 1 * (np.array([np.sum(this_neurons[:,t:t+smoop], 1) for t in range(0, ntime-smoop, smoop)]).T > 0)

        if downsample_neuron > 0:
            downsample = downsample_neuron
            this_data = this_neurons
            this_neurons = np.array([1 * (np.any(this_data[x:x + downsample-1, :], 0)) for x in range(0, this_data.shape[0], downsample)])

        _all_sim[folder_idx,files_idx,:,:] = this_neurons

        #_all_sim = zeros((nfiles,) + (nfolders,) + this_neurons.shape)

results = dict()

results['N'] = _all_sim.shape[0]

results['mean'] = np.mean(_all_sim, 0)

neural_std = np.std(_all_sim,0)
neural_std_all = np.unique(neural_std.flatten())
neural_std[neural_std == .0] = neural_std_all[1]
results['z'] = results['mean']/neural_std
results['t'] = stats.ttest_1samp(_all_sim, .5, axis=0).statistic
results['any'] = np.any(_all_sim, 0)
#np.mean((_all_sim - results['mean'])/(np.std(_all_sim,0)/np.sqrt(_all_sim.shape[0])),0)

output_file = ('results_D%d' % downsample_neuron) + dir_to_load.replace('*', '').replace('/', '') + '_' + files_to_load.replace('*', '').replace('/', '')

with open(root_dir + '/' + output_file, 'w') as f:
    pickle.dump(results, f)

print('Done compiling!')